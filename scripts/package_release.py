"""Build deterministic, Git-tracked plugin archives with verifiable provenance."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import stat
import subprocess
from typing import Any
import zipfile


ROOT = Path(__file__).resolve().parents[1]
RELEASE_MANIFEST = ROOT / "release-manifest.json"
RELEASE_PROVENANCE = "release-provenance.json"
PLUGIN_PROVENANCE = "RELEASE-PROVENANCE.json"
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
REGULAR_GIT_MODES = {"100644": 0o644, "100755": 0o755}


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def git(*arguments: str, text: bool = True) -> str | bytes:
    command = [
        "git",
        "-c",
        f"safe.directory={ROOT.as_posix()}",
        *arguments,
    ]
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=text,
        encoding="utf-8" if text else None,
        errors="replace" if text else None,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr if text else result.stderr.decode("utf-8", "replace")
        raise RuntimeError(f"{' '.join(command)} failed: {stderr.strip()}")
    return result.stdout


def git_commit() -> str:
    return str(git("rev-parse", "HEAD")).strip()


def tracked_files(plugin_path: str, allow_dirty: bool) -> list[dict[str, Any]]:
    raw = bytes(git("ls-files", "--stage", "-z", "--", plugin_path, text=False))
    entries: list[dict[str, Any]] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, encoded_path = record.split(b"\t", 1)
        mode, _object_id, stage = metadata.decode("ascii").split()
        relative = encoded_path.decode("utf-8")
        if stage != "0":
            raise ValueError(f"{relative}: unmerged Git index entry")
        if mode not in REGULAR_GIT_MODES:
            raise ValueError(
                f"{relative}: release archives only accept regular Git blobs; mode={mode}"
            )
        absolute = ROOT / relative
        if not absolute.is_file():
            if allow_dirty:
                continue
            raise ValueError(f"{relative}: tracked release file is missing")
        content = absolute.read_bytes()
        plugin_relative = absolute.relative_to(ROOT / plugin_path).as_posix()
        entries.append(
            {
                "path": plugin_relative,
                "mode": mode,
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                "_content": content,
            }
        )
    entries.sort(key=lambda item: item["path"])
    if not entries:
        raise ValueError(f"{plugin_path}: no tracked plugin files")
    return entries


def tracked_release_is_dirty(paths: list[str]) -> bool:
    for diff_args in (
        ("diff", "--quiet", "--", *paths),
        ("diff", "--cached", "--quiet", "--", *paths),
    ):
        result = subprocess.run(
            [
                "git",
                "-c",
                f"safe.directory={ROOT.as_posix()}",
                *diff_args,
            ],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
        if result.returncode == 1:
            return True
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode("utf-8", "replace").strip())
    return False


def write_zip_entry(
    bundle: zipfile.ZipFile,
    archive_path: str,
    content: bytes,
    mode: int,
) -> None:
    info = zipfile.ZipInfo(archive_path, ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | mode) << 16
    bundle.writestr(info, content, compresslevel=9)


def write_archive(
    plugin: dict[str, Any],
    archive: Path,
    commit: str,
    dirty: bool,
    allow_dirty: bool,
) -> dict[str, Any]:
    entries = tracked_files(plugin["path"], allow_dirty)
    public_entries = [
        {key: value for key, value in entry.items() if key != "_content"}
        for entry in entries
    ]
    content_digest = hashlib.sha256(canonical_bytes(public_entries)).hexdigest()
    provenance = {
        "schemaVersion": 1,
        "pluginId": plugin["id"],
        "pluginVersion": plugin["version"],
        "commit": commit,
        "dirty": dirty,
        "contentDigest": content_digest,
        "files": public_entries,
    }
    with zipfile.ZipFile(
        archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as bundle:
        for entry in entries:
            write_zip_entry(
                bundle,
                f"{plugin['id']}/{entry['path']}",
                entry["_content"],
                REGULAR_GIT_MODES[entry["mode"]],
            )
        write_zip_entry(
            bundle,
            f"{plugin['id']}/{PLUGIN_PROVENANCE}",
            canonical_bytes(provenance),
            0o644,
        )
    return provenance


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build Gloamere plugin archives from tracked Git files."
    )
    parser.add_argument("--output-dir", default="dist")
    parser.add_argument(
        "--expect-commit",
        help="Require HEAD to match this commit, for CI/release binding.",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Build a non-release-eligible local archive from dirty tracked files.",
    )
    args = parser.parse_args()

    release = json.loads(RELEASE_MANIFEST.read_text(encoding="utf-8"))
    commit = git_commit()
    if args.expect_commit and commit != args.expect_commit:
        raise ValueError(
            f"HEAD {commit} does not match expected release commit {args.expect_commit}"
        )

    tracked_surfaces = [
        "release-manifest.json",
        "release-index.json",
        "VERSION",
        ".agents/plugins/marketplace.json",
        "website/app/generated-release.ts",
        *(plugin["path"] for plugin in release["plugins"]),
    ]
    dirty = tracked_release_is_dirty(tracked_surfaces)
    if dirty and not args.allow_dirty:
        raise ValueError(
            "tracked release files differ from HEAD; commit them or use "
            "--allow-dirty for a non-release local build"
        )

    output_dir = (ROOT / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_digests: dict[str, str] = {}
    for field in ("releaseManifestAsset", "releaseIndex"):
        name = release["distribution"][field]
        source = ROOT / name
        destination = output_dir / name
        if not source.is_file():
            raise FileNotFoundError(f"missing release metadata: {source}")
        content = source.read_bytes()
        destination.write_bytes(content)
        metadata_digests[name] = hashlib.sha256(content).hexdigest()
        print(f"Built {destination.name}")

    plugin_records: list[dict[str, Any]] = []
    for plugin in release["plugins"]:
        archive = output_dir / plugin["archive"]
        checksum = output_dir / plugin["checksum"]
        provenance = write_archive(plugin, archive, commit, dirty, args.allow_dirty)
        archive_digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        checksum.write_text(
            f"{archive_digest}  {archive.name}\n",
            encoding="utf-8",
            newline="\n",
        )
        plugin_records.append(
            {
                "id": plugin["id"],
                "version": plugin["version"],
                "archive": archive.name,
                "archiveSha256": archive_digest,
                "contentDigest": provenance["contentDigest"],
            }
        )
        print(f"Built {archive.name} ({archive.stat().st_size} bytes)")
        print(f"Built {checksum.name}")

    global_provenance = {
        "schemaVersion": 1,
        "distributionVersion": release["distribution"]["version"],
        "tag": release["distribution"]["tag"],
        "commit": commit,
        "dirty": dirty,
        "metadataSha256": metadata_digests,
        "plugins": plugin_records,
    }
    provenance_path = output_dir / RELEASE_PROVENANCE
    provenance_path.write_bytes(canonical_bytes(global_provenance))
    print(f"Built {provenance_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
