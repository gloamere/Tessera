"""Pure policy helpers for doctor remediation outcomes."""

from __future__ import annotations

from typing import Any


EXECUTABLE_SCOPES = {"host-lifecycle", "trusted-install"}
PLAN_ONLY_SCOPES = {"repository-structure", "trust", "rollback"}


def remediation_mode(scope: str) -> str:
    if scope in EXECUTABLE_SCOPES:
        return "execute"
    if scope in PLAN_ONLY_SCOPES:
        return "plan-only"
    raise ValueError(f"unknown remediation scope: {scope}")


def resolve_outcomes(
    items: list[dict[str, Any]],
    confirmations: dict[str, bool],
    executions: dict[str, bool],
    verifications: dict[str, bool],
) -> dict[str, str]:
    outcomes: dict[str, str] = {}
    for item in items:
        item_id = item["id"]
        if remediation_mode(item["scope"]) == "plan-only":
            outcomes[item_id] = "plan-only"
            continue
        dependencies = item.get("depends_on", [])
        if any(outcomes.get(dependency) != "succeeded" for dependency in dependencies):
            outcomes[item_id] = "blocked"
        elif not confirmations.get(item_id, False):
            outcomes[item_id] = "skipped"
        elif not executions.get(item_id, False) or not verifications.get(item_id, False):
            outcomes[item_id] = "failed"
        else:
            outcomes[item_id] = "succeeded"
    return outcomes
