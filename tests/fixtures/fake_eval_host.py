"""Deterministic stdin/stdout adapter used to test the eval runner."""

from __future__ import annotations

import json
import re
import sys


ROUTES = {
    "direct-small-edit": "direct",
    "multi-intent": "piece-router",
    "evaluate-routing": "tessera-eval",
    "resolve-capabilities": "tessera-capabilities",
}
NATIVE_SKILLS = {
    "multi-intent": ["piece-router", "planner", "knowledge-base"],
}

prompt = sys.stdin.read()
match = re.search(r"^CASE_ID: (.+)$", prompt, re.MULTILINE)
case_id = match.group(1).strip() if match else ""
route = ROUTES.get(case_id, "direct")
if "MODE: native" in prompt:
    selected = NATIVE_SKILLS.get(
        case_id,
        [] if route == "direct" else ["piece-router" if route == "piece-admission" else route],
    )
    print(
        json.dumps(
            {
                "decision": "direct" if not selected else ("router" if "piece-router" in selected else "skill"),
                "selected_skills": selected,
                "observed_skills": selected,
                "observation_source": "host-events",
                "reason": "deterministic fixture",
            }
        )
    )
else:
    print(json.dumps({"route": route, "reason": "deterministic fixture", "router_used": route == "piece-router"}))
