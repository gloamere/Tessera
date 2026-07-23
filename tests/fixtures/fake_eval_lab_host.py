"""Deterministic paired host used by eval-lab integration tests."""

from __future__ import annotations

import json
import sys


condition = sys.argv[1]
prompt = sys.stdin.read()

if "SIMULATE_EXECUTION_ERROR" in prompt:
    print("simulated host failure", file=sys.stderr)
    raise SystemExit(3)
elif "REGEX_CRITERIA_TEST" in prompt:
    answer = "1/5 2/5 3/5" if condition == "skill" else "1/5"
    print(
        json.dumps(
            {
                "answer": answer,
                "observed_skills": (
                    ["gloamere-visual-review"] if condition == "skill" else []
                ),
            }
        )
    )
elif "CONTROLLED_INJECTION_TEST" in prompt:
    if "SIX_DIMENSION_CONTRACT" in prompt:
        print(
            json.dumps(
                {
                    "answer": "层级、留白、配色、字体、一致性、细节均已评审；Top 3：先修层级。",
                    "observed_skills": [],
                }
            )
        )
    else:
        print(json.dumps({"answer": "层级需要改进。", "observed_skills": []}))
elif "SIMULATE_REGRESSION" in prompt and condition == "baseline":
    print(
        json.dumps(
            {
                "answer": "层级、留白、配色、字体、一致性、细节均已评审；Top 3：先修层级。",
                "observed_skills": [],
            }
        )
    )
elif "SIMULATE_REGRESSION" in prompt:
    print(
        json.dumps(
            {
                "answer": "层级需要改进。",
                "observed_skills": ["gloamere-visual-review"],
            }
        )
    )
elif condition == "baseline":
    print(json.dumps({"answer": "层级需要改进。", "observed_skills": []}))
else:
    print(
        json.dumps(
            {
                "answer": "层级、留白、配色、字体、一致性、细节均已评审；Top 3：先修层级。",
                "observed_skills": ["gloamere-visual-review"],
            }
        )
    )
