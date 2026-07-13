"""Aggregate Tessera doctor check severities without treating unknown as failure."""

from __future__ import annotations

from collections.abc import Iterable


VALID_RESULTS = {"PASS", "WARN", "FAIL", "UNKNOWN", "INFO"}


def overall_status(results: Iterable[str]) -> str:
    values = list(results)
    invalid = set(values) - VALID_RESULTS
    if invalid:
        raise ValueError(f"未知 doctor 结果: {sorted(invalid)}")
    if "FAIL" in values:
        return "error"
    if "WARN" in values:
        return "warning"
    if "UNKNOWN" in values:
        return "unknown"
    return "healthy"
