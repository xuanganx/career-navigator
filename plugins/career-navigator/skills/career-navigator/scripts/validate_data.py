#!/usr/bin/env python3
"""校验 Career Navigator 本地职业与专业底库。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from collections import defaultdict
from pathlib import Path


MAJOR_REQUIRED = {
    "major_name",
    "major_code",
    "education_level",
    "major_category",
    "definition",
}

OCCUPATION_REQUIRED = {
    "cate1",
    "cate2",
    "cate3",
    "occupation_name",
    "occupation_code",
    "definition",
    "aliases",
    "keywords",
    "major_category_code",
    "major_category_name",
    "middle_category_code",
    "middle_category_name",
    "minor_category_code",
    "minor_category_name",
    "catalog_version",
    "source_type",
    "verification_status",
}

EXPECTED_OCCUPATIONS = {
    "2-02-24-00": "食品工程技术人员",
    "2-03-06-03": "宠物医师",
    "2-07-11-04": "养老服务师",
    "4-01-06-02": "互联网营销师",
    "4-01-06-03": "跨境电商运营管理师",
    "4-04-05-05": "人工智能训练师",
    "4-04-05-13": "生成式人工智能系统应用员",
    "4-10-07-01": "宠物健康护理员",
    "6-02-06-13": "咖啡加工工",
    "6-11-10-07": "调香师",
    "8-00-00-00": "不便分类的其他从业人员",
}

EXPECTED_MAJORS = {
    ("本科", "网络与新媒体"): "050306T",
    ("本科", "食品科学与工程"): "082701",
    ("本科", "动物医学"): "090401",
    ("本科", "旅游管理"): "120901K",
    ("本科", "数字媒体艺术"): "130508",
    ("本科", "香料香精技术与工程"): "081704T",
}

MAJOR_CODE_PATTERNS = {
    # 普通本科以 6 位代码为主，可带 T/K；2026 版外国语言文学类新增专业中存在 7 位代码。
    "本科": re.compile(r"\d{6}[TK]?|\d{7}"),
    "职业本科": re.compile(r"\d{6}"),
    "高职专科": re.compile(r"\d{6}"),
}

ALLOWED_OCCUPATION_SOURCE_TYPES = {
    "pdf_derived_official_catalog",
    "official_new_occupation_increment",
}

ALLOWED_OCCUPATION_VERIFICATION = {
    "official_pdf_derived",
    "official_increment_source_verified",
}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise AssertionError(f"missing file: {path}")
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise AssertionError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
            if not isinstance(row, dict):
                raise AssertionError(f"{path}:{lineno}: expected object")
            rows.append(row)
    if not rows:
        raise AssertionError(f"{path}: no records")
    return rows


def require_fields(rows: list[dict], fields: set[str], label: str) -> None:
    for idx, row in enumerate(rows, 1):
        missing = fields - row.keys()
        if missing:
            raise AssertionError(f"{label} row {idx}: missing {sorted(missing)}")


def require_nonempty_string(row: dict, field: str, label: str, idx: int) -> None:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise AssertionError(f"{label} row {idx}: {field} must be a nonempty string")


def require_string_list(row: dict, field: str, label: str, idx: int) -> None:
    value = row.get(field)
    if not isinstance(value, list):
        raise AssertionError(f"{label} row {idx}: {field} must be a list")
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise AssertionError(f"{label} row {idx}: {field} contains empty/non-string item")


def validate_year_value(value: object, field: str, label: str, idx: int) -> None:
    if isinstance(value, int):
        if value < 1900 or value > 2100:
            raise AssertionError(f"{label} row {idx}: unreasonable {field}={value}")
        return
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise AssertionError(f"{label} row {idx}: empty {field}")
        if re.fullmatch(r"\d{4}", text) and not (1900 <= int(text) <= 2100):
            raise AssertionError(f"{label} row {idx}: unreasonable {field}={text}")
        return
    raise AssertionError(f"{label} row {idx}: {field} must be int or explanatory string")


def validate_occupations(rows: list[dict]) -> None:
    require_fields(rows, OCCUPATION_REQUIRED, "occupations")
    if len(rows) != 1671:
        raise AssertionError(f"occupations: expected 1671 records, got {len(rows)}")

    duplicate_codes = [code for code, count in Counter(row["occupation_code"] for row in rows).items() if count > 1]
    if duplicate_codes:
        raise AssertionError(f"occupations: duplicate code {duplicate_codes[0]}")

    for idx, row in enumerate(rows, 1):
        code = str(row["occupation_code"])
        for field in [
            "cate1",
            "cate2",
            "cate3",
            "occupation_name",
            "occupation_code",
            "definition",
            "major_category_name",
            "middle_category_name",
            "minor_category_name",
            "catalog_version",
            "source_type",
            "verification_status",
            "source",
        ]:
            require_nonempty_string(row, field, "occupations", idx)

        if not re.fullmatch(r"[1-8]-[0-9]{2}-[0-9]{2}-[0-9]{2}", code):
            raise AssertionError(f"occupations row {idx}: invalid code {code}")
        if row["major_category_code"] != code[:1]:
            raise AssertionError(f"occupations row {idx}: bad major code")
        if row["middle_category_code"] != code[:4]:
            raise AssertionError(f"occupations row {idx}: bad middle code")
        if row["minor_category_code"] != code[:7]:
            raise AssertionError(f"occupations row {idx}: bad minor code")
        if row["cate1"] != row["major_category_name"] or row["cate2"] != row["middle_category_name"] or row["cate3"] != row["minor_category_name"]:
            raise AssertionError(f"occupations row {idx}: compatibility category mismatch")
        if row["source_type"] not in ALLOWED_OCCUPATION_SOURCE_TYPES:
            raise AssertionError(f"occupations row {idx}: unexpected source_type")
        if row["verification_status"] not in ALLOWED_OCCUPATION_VERIFICATION:
            raise AssertionError(f"occupations row {idx}: unexpected verification_status")

        require_string_list(row, "aliases", "occupations", idx)
        require_string_list(row, "keywords", "occupations", idx)
        require_string_list(row, "included_work_types", "occupations", idx)
        if not row["keywords"]:
            raise AssertionError(f"occupations row {idx}: keywords must not be empty")
        if row["occupation_name"] not in row["keywords"]:
            raise AssertionError(f"occupations row {idx}: keywords must include occupation_name")

        for optional_source in ["source_title", "source_url", "source_published_at"]:
            if optional_source in row:
                require_nonempty_string(row, optional_source, "occupations", idx)
        for year_field in ["release_year", "catalog_year", "catalog_version"]:
            if year_field in row:
                validate_year_value(row[year_field], year_field, "occupations", idx)
        if "new_occupation_release_years" in row:
            years = row["new_occupation_release_years"]
            if not isinstance(years, list) or not years:
                raise AssertionError(f"occupations row {idx}: bad new_occupation_release_years")
            for year in years:
                validate_year_value(year, "new_occupation_release_years", "occupations", idx)

    by_code = {row["occupation_code"]: row["occupation_name"] for row in rows}
    for code, name in EXPECTED_OCCUPATIONS.items():
        if by_code.get(code) != name:
            raise AssertionError(f"occupations: expected {code}={name}, got {by_code.get(code)}")


def validate_majors(rows: list[dict]) -> None:
    require_fields(rows, MAJOR_REQUIRED, "majors")
    if len(rows) < 1900:
        raise AssertionError(f"majors: expected at least 1900 records, got {len(rows)}")
    keys = Counter((row["education_level"], row["major_code"], row["major_name"]) for row in rows)
    duplicates = [key for key, count in keys.items() if count > 1]
    if duplicates:
        raise AssertionError(f"majors: duplicate {duplicates[0]}")
    levels = {row["education_level"] for row in rows}
    if not {"本科", "职业本科", "高职专科"} <= levels:
        raise AssertionError(f"majors: missing levels")

    code_names: dict[tuple[str, str], set[str]] = defaultdict(set)
    by_level_name: dict[tuple[str, str], str] = {}
    for idx, row in enumerate(rows, 1):
        for field in MAJOR_REQUIRED:
            require_nonempty_string(row, field, "majors", idx)
        level = row["education_level"]
        code = row["major_code"]
        name = row["major_name"]
        if level not in MAJOR_CODE_PATTERNS:
            raise AssertionError(f"majors row {idx}: unexpected education_level {level}")
        if not isinstance(code, str):
            raise AssertionError(f"majors row {idx}: major_code must be string")
        if not MAJOR_CODE_PATTERNS[level].fullmatch(code):
            raise AssertionError(f"majors row {idx}: invalid {level} major_code {code}")
        code_names[(level, code)].add(name)
        by_level_name[(level, name)] = code
        if "source" in row:
            require_nonempty_string(row, "source", "majors", idx)

    for (level, code), names in code_names.items():
        if len(names) > 1:
            raise AssertionError(f"majors: {level} code {code} maps to multiple names {sorted(names)}")

    for key, code in EXPECTED_MAJORS.items():
        if by_level_name.get(key) != code:
            raise AssertionError(f"majors: expected {key}={code}, got {by_level_name.get(key)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("skill_dir", type=Path)
    args = parser.parse_args()
    data_dir = args.skill_dir / "data"
    occupations = load_jsonl(data_dir / "occupations.jsonl")
    majors = load_jsonl(data_dir / "majors.jsonl")
    validate_occupations(occupations)
    validate_majors(majors)
    print(f"occupations: {len(occupations)} records")
    print(f"majors: {len(majors)} records")
    print("data validation passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
