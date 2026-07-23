"""Generate checked release mirrors from release-manifest.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "release-manifest.json"
MARKETPLACE_PATH = ROOT / ".agents" / "plugins" / "marketplace.json"


def canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def build_marketplace(release: dict[str, Any]) -> dict[str, Any]:
    distribution = release["distribution"]
    return {
        "name": distribution["marketplace"],
        "interface": {
            "displayName": distribution["marketplaceDisplayName"],
        },
        "plugins": [
            {
                "name": plugin["id"],
                "source": {
                    "source": "local",
                    "path": f"./{plugin['path']}",
                },
                "policy": plugin["policy"],
                "category": plugin["category"],
            }
            for plugin in release["plugins"]
        ],
    }


def build_release_index(release: dict[str, Any]) -> dict[str, Any]:
    distribution = release["distribution"]
    repository = distribution["repository"]
    tag = distribution["tag"]
    download_root = f"{repository}/releases/download/{tag}"
    return {
        "schemaVersion": 1,
        "name": distribution["name"],
        "version": distribution["version"],
        "tag": tag,
        "repository": repository,
        "releaseURL": f"{repository}/releases/tag/{tag}",
        "marketplace": distribution["marketplace"],
        "installProfiles": distribution["installProfiles"],
        "manifest": distribution["releaseManifestAsset"],
        "manifestURL": (
            f"{download_root}/{distribution['releaseManifestAsset']}"
        ),
        "plugins": [
            {
                "id": plugin["id"],
                "displayName": plugin["displayName"],
                "version": plugin["version"],
                "maturity": plugin["maturity"],
                "archive": plugin["archive"],
                "archiveURL": f"{download_root}/{plugin['archive']}",
                "checksum": plugin["checksum"],
                "checksumURL": f"{download_root}/{plugin['checksum']}",
            }
            for plugin in release["plugins"]
        ],
    }


def generated_files(release: dict[str, Any]) -> dict[Path, str]:
    index_path = ROOT / release["distribution"]["releaseIndex"]
    return {
        MARKETPLACE_PATH: canonical_json(build_marketplace(release)),
        index_path: canonical_json(build_release_index(release)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate marketplace and release index from the release manifest."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when generated files differ instead of writing them.",
    )
    args = parser.parse_args()

    release = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    drift: list[str] = []
    for path, expected in generated_files(release).items():
        if args.check:
            actual = path.read_text(encoding="utf-8") if path.is_file() else None
            if actual != expected:
                drift.append(path.relative_to(ROOT).as_posix())
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(expected, encoding="utf-8", newline="\n")
        print(f"Generated {path.relative_to(ROOT).as_posix()}")

    if drift:
        print(
            "Generated release files are stale: " + ", ".join(drift),
            file=sys.stderr,
        )
        print(
            "Run: python scripts/generate_release_files.py",
            file=sys.stderr,
        )
        return 1
    if args.check:
        print("Generated marketplace and release index are current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
