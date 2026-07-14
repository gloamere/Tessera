"""Codex CLI stand-in that validates per-invocation plugin toggles."""

from __future__ import annotations

import json
from pathlib import Path
import sys


arguments = sys.argv[1:]
if not arguments or arguments[0] != "exec":
    raise SystemExit("expected codex exec")

overrides = [arguments[index + 1] for index, value in enumerate(arguments[:-1]) if value == "-c"]
enabled_overrides = {'plugins."taste@tessera".enabled=true', 'plugins.\\"taste@tessera\\".enabled=true'}
disabled_overrides = {'plugins."taste@tessera".enabled=false', 'plugins.\\"taste@tessera\\".enabled=false'}
if enabled_overrides.intersection(overrides):
    enabled = True
elif disabled_overrides.intersection(overrides):
    enabled = False
else:
    raise SystemExit("missing target plugin override")

output_index = arguments.index("--output-last-message") + 1
output = Path(arguments[output_index])
if enabled:
    answer = "层级、留白、配色、字体、一致性、细节均已评审；Top 3：先修层级。"
    print(
        json.dumps(
            {
                "item": {
                    "command": "Get-Content C:\\fake\\skills\\taste\\SKILL.md"
                }
            }
        )
    )
else:
    answer = "层级需要改进。"
output.write_text(json.dumps({"answer": answer}, ensure_ascii=False), encoding="utf-8")
