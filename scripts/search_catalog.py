#!/usr/bin/env python3
"""检索 Career Navigator 职业与专业底库。

脚本只负责本地底库召回和字段级解释，不做语义扩展。模糊兴趣、市场岗位名、
网感称呼应先由大模型拆成若干 `--query-term`，再交给本脚本验证和召回。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Iterable, NamedTuple


SPECIAL_OCCUPATION_CODES = {"8-00-00-00"}

TERM_EXPANSIONS = {
    "日化": ["日用化学", "日用化学品"],
    "数媒": ["数字媒体"],
}


class Term(NamedTuple):
    raw: str
    norm: str


class Reason(NamedTuple):
    score: int
    term: str
    field: str
    match_type: str
    matched_value: str | None = None


def normalize(text: Any) -> str:
    return re.sub(r"\s+", "", str(text).lower())


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build_terms(query: str, query_terms: list[str]) -> list[Term]:
    seen: set[str] = set()
    terms: list[Term] = []
    expanded: list[str] = []
    for raw in [query, *query_terms]:
        expanded.append(raw)
        expanded.extend(TERM_EXPANSIONS.get(str(raw).strip(), []))
    for raw in expanded:
        raw = str(raw).strip()
        norm = normalize(raw)
        if norm and norm not in seen:
            terms.append(Term(raw=raw, norm=norm))
            seen.add(norm)
    return terms


def field_values(row: dict[str, Any], field: str) -> list[str]:
    value = row.get(field)
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def first_exact(values: Iterable[str], term: str) -> str | None:
    for value in values:
        if normalize(value) == term:
            return value
    return None


def first_contains(values: Iterable[str], term: str) -> str | None:
    for value in values:
        value_norm = normalize(value)
        if term and (term in value_norm or value_norm in term):
            return value
    return None


def add_reason(
    reasons: list[Reason],
    score: int,
    term: Term,
    field: str,
    match_type: str,
    matched_value: str | None = None,
) -> None:
    reasons.append(Reason(score, term.raw, field, match_type, matched_value))


def score_occupation(row: dict[str, Any], terms: list[Term], include_special: bool) -> tuple[int, list[Reason]]:
    if row.get("occupation_code") in SPECIAL_OCCUPATION_CODES and not include_special:
        return 0, []

    reasons: list[Reason] = []
    code_values = field_values(row, "occupation_code")
    name_values = field_values(row, "occupation_name")
    alias_values = field_values(row, "aliases")
    work_type_values = field_values(row, "included_work_types")
    keyword_values = field_values(row, "keywords")
    definition_values = field_values(row, "definition")
    category_fields = [
        "cate1",
        "cate2",
        "cate3",
        "major_category_name",
        "middle_category_name",
        "minor_category_name",
    ]
    category_values = [value for field in category_fields for value in field_values(row, field)]

    for term in terms:
        if match := first_exact(code_values, term.norm):
            add_reason(reasons, 1200, term, "occupation_code", "exact_code", match)
        if match := first_exact(name_values, term.norm):
            add_reason(reasons, 1100, term, "occupation_name", "exact_name", match)
        if match := first_exact(alias_values, term.norm):
            add_reason(reasons, 950, term, "aliases", "alias_exact", match)
        if match := first_exact(work_type_values, term.norm):
            add_reason(reasons, 900, term, "included_work_types", "work_type_exact", match)
        if match := first_contains(name_values, term.norm):
            add_reason(reasons, 600, term, "occupation_name", "name_contains", match)
        if match := first_contains(work_type_values, term.norm):
            add_reason(reasons, 300, term, "included_work_types", "work_type_contains", match)
        if match := first_contains(keyword_values, term.norm):
            add_reason(reasons, 120, term, "keywords", "keyword_contains", match)
        if match := first_contains(category_values, term.norm):
            add_reason(reasons, 80, term, "category", "category_contains", match)
        if match := first_contains(definition_values, term.norm):
            add_reason(reasons, 45, term, "definition", "definition_contains", match)

    return sum(reason.score for reason in reasons), reasons


def score_major(row: dict[str, Any], terms: list[Term]) -> tuple[int, list[Reason]]:
    reasons: list[Reason] = []
    code_values = field_values(row, "major_code")
    source_code_values = field_values(row, "source_code")
    name_values = field_values(row, "major_name")
    category_values = field_values(row, "major_category")
    definition_values = field_values(row, "definition")
    level_values = field_values(row, "education_level")

    for term in terms:
        if match := first_exact(code_values, term.norm):
            add_reason(reasons, 1200, term, "major_code", "exact_code", match)
        if match := first_exact(source_code_values, term.norm):
            add_reason(reasons, 1100, term, "source_code", "source_code_exact", match)
        if match := first_exact(name_values, term.norm):
            add_reason(reasons, 1100, term, "major_name", "exact_name", match)
        if match := first_contains(name_values, term.norm):
            add_reason(reasons, 600, term, "major_name", "name_contains", match)
        if match := first_contains(category_values, term.norm):
            add_reason(reasons, 80, term, "major_category", "category_contains", match)
        if match := first_contains(definition_values, term.norm):
            add_reason(reasons, 45, term, "definition", "definition_contains", match)
        if match := first_contains(level_values, term.norm):
            add_reason(reasons, 20, term, "education_level", "level_contains", match)

    return sum(reason.score for reason in reasons), reasons


def primary_match_type(reasons: list[Reason]) -> str:
    if not reasons:
        return "none"
    priority = {
        "exact_code": 1,
        "exact_name": 2,
        "source_code_exact": 3,
        "alias_exact": 4,
        "work_type_exact": 5,
        "name_contains": 6,
        "work_type_contains": 7,
        "keyword_contains": 8,
        "category_contains": 9,
        "definition_contains": 10,
        "level_contains": 11,
        "domain_task_bonus": 12,
    }
    return min(reasons, key=lambda reason: (priority.get(reason.match_type, 99), -reason.score)).match_type


def unique(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        if item and item not in seen:
            output.append(item)
            seen.add(item)
    return output


def trim_row(row: dict[str, Any], kind: str, score: int, reasons: list[Reason], explain: bool) -> dict[str, Any]:
    if kind == "occupation":
        keys = [
            "occupation_name",
            "occupation_code",
            "definition",
            "cate1",
            "cate2",
            "cate3",
            "major_category_name",
            "middle_category_name",
            "minor_category_name",
            "source_type",
            "verification_status",
            "source",
            "source_title",
            "source_url",
            "source_published_at",
            "catalog_year",
            "included_work_types",
            "release_year",
            "new_occupation_release_years",
            "release_batch",
        ]
    else:
        keys = [
            "major_name",
            "major_code",
            "education_level",
            "major_category",
            "definition",
            "source",
            "source_title",
            "source_url",
            "catalog_year",
        ]
    output = {key: row.get(key) for key in keys if key in row}
    output["score"] = score
    output["match_type"] = primary_match_type(reasons)
    output["matched_terms"] = unique(reason.term for reason in reasons)
    output["matched_fields"] = unique(reason.field for reason in reasons)
    if kind == "occupation":
        work_types = [
            str(reason.matched_value)
            for reason in reasons
            if reason.field == "included_work_types" and reason.matched_value
        ]
        output["matched_work_types"] = unique(work_types)
    if explain:
        output["match_details"] = [
            {
                "term": reason.term,
                "field": reason.field,
                "match_type": reason.match_type,
                "score": reason.score,
                "matched_value": reason.matched_value,
            }
            for reason in sorted(reasons, key=lambda item: (-item.score, item.field, item.term))
        ]
    return output


ScoreFn = Callable[[dict[str, Any], list[Term]], tuple[int, list[Reason]]]


def score_with_intent(row: dict[str, Any], score_fn: ScoreFn, groups: dict[str, list[Term]]) -> tuple[int, list[Reason]]:
    """Score OR-style recall terms, then boost object+task matches and penalize exclusions."""

    general_score, general_reasons = score_fn(row, groups["general"])
    domain_score, domain_reasons = score_fn(row, groups["domain"])
    task_score, task_reasons = score_fn(row, groups["task"])
    exclude_score, _exclude_reasons = score_fn(row, groups["exclude"])

    reasons = [*general_reasons, *domain_reasons, *task_reasons]
    score = general_score + domain_score + task_score

    if domain_score and task_score:
        reasons.append(Reason(400, "domain+task", "intent", "domain_task_bonus", "domain and task matched"))
        score += 400

    if exclude_score:
        score -= max(300, exclude_score)

    return max(0, score), reasons


def main() -> int:
    parser = argparse.ArgumentParser()
    default_skill_dir = Path(__file__).resolve().parents[1]
    parser.add_argument("--skill-dir", type=Path, default=default_skill_dir, help="默认按脚本所在目录自动推断")
    parser.add_argument("--type", choices=["occupation", "major"], required=True)
    parser.add_argument("--query", default="")
    parser.add_argument("--query-term", action="append", default=[], help="可重复传入；由大模型语义扩展后给脚本召回")
    parser.add_argument("--domain-term", action="append", default=[], help="行业对象、产品对象或服务对象；与 task-term 同时命中会加权")
    parser.add_argument("--task-term", action="append", default=[], help="核心工作任务；与 domain-term 同时命中会加权")
    parser.add_argument("--candidate-title", action="append", default=[], help="可能的官方职业、工种或专业正式名")
    parser.add_argument("--exclude-term", action="append", default=[], help="明显不属于用户语义的相邻领域；命中后降权")
    parser.add_argument("--explain", action="store_true")
    parser.add_argument("--min-score", type=int, default=1)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--include-special", action="store_true", help="包含 8-00-00-00 等特殊兜底记录")
    args = parser.parse_args()

    groups = {
        "general": build_terms(args.query, [*args.query_term, *args.candidate_title]),
        "domain": build_terms("", args.domain_term),
        "task": build_terms("", args.task_term),
        "exclude": build_terms("", args.exclude_term),
    }
    if not any(groups[name] for name in ["general", "domain", "task"]):
        parser.error("provide --query, --query-term, --candidate-title, --domain-term, or --task-term")

    data_file = args.skill_dir / "data" / ("occupations.jsonl" if args.type == "occupation" else "majors.jsonl")
    rows = load_jsonl(data_file)
    scored: list[tuple[int, dict[str, Any], list[Reason]]] = []
    for row in rows:
        if args.type == "occupation":
            score_fn: ScoreFn = lambda item, terms: score_occupation(item, terms, args.include_special)
        else:
            score_fn = score_major
        score, reasons = score_with_intent(row, score_fn, groups)
        if score >= args.min_score:
            scored.append((score, row, reasons))
    scored.sort(key=lambda item: (-item[0], item[1].get("occupation_code") or item[1].get("major_code") or ""))
    output = [trim_row(row, args.type, score, reasons, args.explain) for score, row, reasons in scored[: args.limit]]
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
