# Career Navigator

Career Navigator 是一个面向中国高考生的 coding-agent skill。它把学生的职业兴趣、网感职业名、冷门/新职业名或模糊职业幻想，先校准成现实职业方向，再反推出可报考的专业路线。

这个仓库参考 `zarazhangrui/frontend-slides` 的组织方式：根目录保留一份可直接阅读/安装的 skill 文件，同时提供 Claude Code custom marketplace source 所需的插件结构。

## What This Does

Career Navigator 默认服务于中国高考、职业教育和升学选专业语境。

### Key Features

- **职业校准** - 区分官方职业、新职业、新工种和市场岗位方向，不把网感称呼直接当正式职业。
- **专业路线反推** - 从真实工作任务生成专业路线，专业名称、代码和层次以本地专业底库为准。
- **本地底库召回** - 内置职业底库、专业底库和 Python 检索脚本，优先用数据校验结果而不是凭印象回答。
- **分步交互** - 职业方向、专业路线、专业候选、专业详情分四步输出，避免一次性把学生淹没在信息里。
- **边界清晰** - 不做院校推荐、分数线判断、录取概率、志愿梯度或就业承诺。

## Installation

### Via Claude Code Custom Marketplace Source

Install directly from this public GitHub repo. Run these as two separate Claude Code messages; do not paste both lines into the prompt at once.

```text
/plugin marketplace add https://github.com/yangyuxing/career-navigator
```

After that finishes, run:

```text
/plugin install career-navigator@career-navigator
```

Use the HTTPS URL. The shorter `yangyuxing/career-navigator` form may make Claude Code try SSH, which can fail if GitHub is not already in your `known_hosts` file.

Then use it by typing:

```text
/career-navigator:career-navigator
```

If your GitHub username or repo name is different, replace the URL in the first command after uploading.

### Codex Manual Installation

Copy the skill files into your Codex skills directory:

```bash
mkdir -p ~/.codex/skills/career-navigator
cp SKILL.md ~/.codex/skills/career-navigator/
cp -R agents data scripts ~/.codex/skills/career-navigator/
```

Then start a new Codex session and ask it to use the Career Navigator skill.

### Claude Code Manual Installation

Copy the same user-facing skill files into your Claude skills directory:

```bash
mkdir -p ~/.claude/skills/career-navigator
cp SKILL.md ~/.claude/skills/career-navigator/
cp -R data scripts ~/.claude/skills/career-navigator/
```

If installed manually as a standalone Claude skill, use:

```text
/career-navigator
```

### Other Coding Agents

Agents such as Codex, Kimi Code, OpenCode, Gemini CLI, or other local coding assistants can use the core skill by reading:

```text
https://github.com/yangyuxing/career-navigator
```

The agent should start from `SKILL.md` and load the bundled resources it needs:

- `data/occupations.jsonl`
- `data/majors.jsonl`
- `scripts/search_catalog.py`
- `scripts/validate_data.py`

## Usage

Example prompts:

```text
我喜欢做香水，未来能报什么专业？
```

```text
酒店试睡员现实里算什么职业？能反推哪些专业？
```

```text
想做 AI 训练师，高考选专业怎么看？
```

The skill will:

1. Calibrate the input into 1-3 realistic career directions.
2. Ask you to choose one direction.
3. Generate verified major routes from that career direction.
4. Let you pick a route and then a specific major.
5. Provide major details only after the major is selected.

## Architecture

This repo keeps two entry points in sync:

| Path | Purpose |
| --- | --- |
| `SKILL.md` | Core workflow for agents that can read a skill directly |
| `agents/openai.yaml` | Codex UI metadata |
| `data/occupations.jsonl` | Local occupation catalog |
| `data/majors.jsonl` | Local major catalog |
| `scripts/search_catalog.py` | Local search and explainable recall |
| `scripts/validate_data.py` | Dataset integrity validation |
| `.claude-plugin/marketplace.json` | Claude Code custom marketplace metadata |
| `plugins/career-navigator/.claude-plugin/plugin.json` | Claude Code plugin metadata |
| `plugins/career-navigator/skills/career-navigator/` | Plugin-packaged copy of the skill |

## Validation

Run the bundled data validator from the repo root:

```bash
python3 scripts/validate_data.py .
python3 plugins/career-navigator/skills/career-navigator/scripts/validate_data.py plugins/career-navigator/skills/career-navigator
```

Try a local search:

```bash
python3 scripts/search_catalog.py --type occupation --query "酒店试睡员" --domain-term "酒店" --task-term "服务体验" --limit 5 --explain
```

## Requirements

- A local coding agent with filesystem access.
- Python 3 for the bundled search and validation scripts.
- Network access is only needed when the skill verifies recent facts, salary samples, policy changes, or other time-sensitive information during use.

## License

MIT
