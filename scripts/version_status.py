"""Conservative version comparison used by Tessera diagnostic fixtures."""

from __future__ import annotations

import re


CORE_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def classify_version(installed: str | None, available: str | None) -> str:
    if not installed or not available:
        return "unknown"
    if installed == available:
        return "current"

    installed_base = installed.split("+", 1)[0]
    available_base = available.split("+", 1)[0]
    if installed_base == available_base:
        return "refresh-available"

    installed_match = CORE_SEMVER.fullmatch(installed_base)
    available_match = CORE_SEMVER.fullmatch(available_base)
    if installed_match is None or available_match is None:
        return "unknown"
    installed_tuple = tuple(int(part) for part in installed_match.groups())
    available_tuple = tuple(int(part) for part in available_match.groups())
    if available_tuple > installed_tuple:
        return "update-available"
    if installed_tuple > available_tuple:
        return "ahead"
    return "unknown"
