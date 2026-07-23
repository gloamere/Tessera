"""Build deterministic plugin ZIP archives and SHA-256 sidecars."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import stat
import zipfile


ROOT = Path(__file__).resolve().parents[1]
RELEASE_MANIFEST = ROOT / "release-manifest.json"
IGNORED_PARTS = {"__pycache__"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def iter_release_files(plugin_dir: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in plugin_dir.rglob("*")
            if path.is_file()
            and not any(part in IGNORED_PARTS for part in path.parts)
            and path.suffix not in IGNORED_SUFFIXES
        ),
        key=lambda path: path.relative_to(plugin_dir).as_posix(),
    )


def write_archive(plugin_id: str, plugin_dir: Path, archive: Path) -> None:
    files = iter_release_files(plugin_dir)
    if not files:
        raise ValueError(f"{plugin_id}: plugin directory is empty")
    with zipfile.ZipFile(
        archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as bundle:
        for path in files:
            relative = path.relative_to(plugin_dir).as_posix()
            info = zipfile.ZipInfo(f"{plugin_id}/{relative}", ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            mode = 0o755 if path.suffix == ".sh" else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            bundle.writestr(info, path.read_bytes(), compresslevel=9)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build Gloamere plugin archives from release-manifest.json."
    )
    parser.add_argument("--output-dir", default="dist")
    args = parser.parse_args()

    release = json.loads(RELEASE_MANIFEST.read_text(encoding="utf-8"))
    output_dir = (ROOT / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    for field in ("releaseManifestAsset", "releaseIndex"):
        name = release["distribution"][field]
        source = ROOT / name
        destination = output_dir / name
        if not source.is_file():
            raise FileNotFoundError(f"missing release metadata: {source}")
        destination.write_bytes(source.read_bytes())
        print(f"Built {destination.name}")

    for plugin in release["plugins"]:
        plugin_id = plugin["id"]
        plugin_dir = ROOT / plugin["path"]
        archive = output_dir / plugin["archive"]
        checksum = output_dir / plugin["checksum"]
        if not plugin_dir.is_dir():
            raise FileNotFoundError(f"{plugin_id}: missing {plugin_dir}")
        write_archive(plugin_id, plugin_dir, archive)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        checksum.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
        print(f"Built {archive.name} ({archive.stat().st_size} bytes)")
        print(f"Built {checksum.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
