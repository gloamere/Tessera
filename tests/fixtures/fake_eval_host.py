"""Deterministic stdin/stdout adapter used to test the eval runner."""

from __future__ import annotations

import json
import re
import sys


ROUTES = {
    "direct-small-edit": "direct",
    "multi-intent": "piece-router",
    "evaluate-routing": "tessera-eval",
}

prompt = sys.stdin.read()
match = re.search(r"^CASE_ID: (.+)$", prompt, re.MULTILINE)
case_id = match.group(1).strip() if match else ""
route = ROUTES.get(case_id, "direct")
print(json.dumps({"route": route, "reason": "deterministic fixture", "router_used": route == "piece-router"}))
