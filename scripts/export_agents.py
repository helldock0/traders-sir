"""Write the Claude Code subagent definitions (.claude/agents/*.md) from the role prompts, so the
prompts in edge/agents/prompts.py stay the single source of truth."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from edge.agents import prompts  # noqa: E402

AGENTS = ROOT / ".claude" / "agents"

CRITIC_FRONT = """---
name: critic
description: Research Critic for the edge programme. Reviews proposed hypotheses before any compute is spent and reviews Builder strategy modules for look-ahead, rule mismatches and parameter plumbing. Always writes its JSON verdict to the file named in the prompt.
model: opus
tools: Read, Grep, Glob, Write, Bash
---
"""

BUILDER_FRONT = """---
name: builder
description: Strategy Builder for the edge programme. Turns an approved hypothesis brief into one strategy module under strategies/auto/, runs the checker until it passes, and never edits other files.
model: sonnet
tools: Read, Write, Edit, Grep, Glob, Bash
---
"""

CRITIC_TAIL = """
# How you work in Claude Code

You receive a prompt naming a brief file and an output file. Read the brief fully (it contains the charter,
the material to review and the JSON schema). For code reviews also read `edge/engine/strategy.py`,
`edge/engine/features.py` and `edge/engine/executor.py` when a detail matters, and you may run read-only
commands (for example `.\\.venv\\Scripts\\python.exe scripts\\cycle_step.py check <slug>`) from
`D:\\Traders sir`. Never modify strategy or engine files. Write exactly one JSON object matching the schema to the
output file with the Write tool, then reply with a two-line summary.

Schemas:

```json
""" + json.dumps({"hypothesis_review": prompts.CRITIC_REVIEW_SCHEMA, "code_review": prompts.CRITIC_CODE_SCHEMA}, indent=1) + """
```
"""

BUILDER_TAIL = """
# How you work in Claude Code

You receive a prompt naming a builder brief (`runs/<slug>/builder_brief.md`). Read it, read the example
strategies in `strategies/oracle/` and `edge/engine/features.py` if you need the helper signatures, then
write the module to `strategies/auto/<slug>.py` with the Write tool. Run the checker from `D:\\Traders sir`:

    .\\.venv\\Scripts\\python.exe scripts\\cycle_step.py check <slug>

Read its JSON output. Fix every reported issue and rerun until it prints `"ok": true` (at most three
attempts). Never edit any file except your own module. Reply with a short summary: what the module does,
the checker result, and any assumption you had to make about the rules.
"""


def main() -> None:
    AGENTS.mkdir(parents=True, exist_ok=True)
    (AGENTS / "critic.md").write_text(CRITIC_FRONT + prompts.CRITIC_SYSTEM + "\n\n" + prompts.strategy_contract() + CRITIC_TAIL, encoding="utf-8")
    (AGENTS / "builder.md").write_text(BUILDER_FRONT + prompts.BUILDER_SYSTEM + "\n\n" + prompts.strategy_contract() + BUILDER_TAIL, encoding="utf-8")
    for p in sorted(AGENTS.glob("*.md")):
        print(p, p.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
