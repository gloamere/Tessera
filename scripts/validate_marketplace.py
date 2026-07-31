"""Validate Gloamere's Git marketplace and maintainer release surfaces."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
RELEASE_MANIFEST = ROOT / "release-manifest.json"
MARKETPLACE = ROOT / ".agents" / "plugins" / "marketplace.json"
PLUGINS_ROOT = ROOT / "plugins"
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
EXPECTED_PLUGIN_IDS = {"gloamere-eval", "gloamere-workflows"}
EXPECTED_INSTALL_PROFILES = {
    "workflows": ["gloamere-workflows"],
    "maintainer": ["gloamere-eval"],
    "complete": ["gloamere-workflows", "gloamere-eval"],
}
EXPECTED_PLUGIN_MATURITY = {
    "gloamere-eval": "beta",
    "gloamere-workflows": "stable",
}
EXPECTED_PLUGIN_PUBLIC_ROLE = {
    "gloamere-eval": "maintainer",
    "gloamere-workflows": "public",
}
REQUIRED_TOP_LEVEL_FIELDS = {
    "name",
    "version",
    "description",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
    "skills",
    "interface",
}
REQUIRED_INTERFACE_FIELDS = {
    "displayName",
    "shortDescription",
    "longDescription",
    "developerName",
    "category",
    "capabilities",
    "websiteURL",
    "privacyPolicyURL",
    "termsOfServiceURL",
    "supportURL",
    "defaultPrompt",
    "brandColor",
    "composerIcon",
    "logo",
}


def relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{relative(path)}: 必须是 JSON 对象")
    return value


def require_https(value: Any, label: str, errors: list[str]) -> None:
    if not isinstance(value, str):
        errors.append(f"{label}: 必须是 HTTPS URL")
        return
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        errors.append(f"{label}: 必须是 HTTPS URL")


def parse_frontmatter(path: Path, errors: list[str]) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        errors.append(f"{relative(path)}: 缺少 YAML frontmatter")
        return {}
    end = normalized.find("\n---", 4)
    if end < 0:
        errors.append(f"{relative(path)}: YAML frontmatter 未闭合")
        return {}
    raw = normalized[4:end]
    fields: dict[str, str] = {}
    for name in ("name", "description"):
        match = re.search(rf"^{name}:\s*(.*?)\s*$", raw, re.MULTILINE)
        if not match or not match.group(1):
            errors.append(f"{relative(path)}: frontmatter 缺少 {name}")
            continue
        fields[name] = match.group(1).strip("'\"")
    return fields


def marketplace_entries(
    marketplace: dict[str, Any], errors: list[str]
) -> dict[str, dict[str, Any]]:
    items = marketplace.get("plugins")
    if not isinstance(items, list):
        errors.append(f"{relative(MARKETPLACE)}: plugins 必须是数组")
        return {}
    entries: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            errors.append(f"{relative(MARKETPLACE)}: 每个插件必须有字符串 name")
            continue
        name = item["name"]
        if name in entries:
            errors.append(f"{relative(MARKETPLACE)}: 插件 {name} 重复")
        entries[name] = item
    return entries


def release_plugins(
    release: dict[str, Any], errors: list[str]
) -> dict[str, dict[str, Any]]:
    items = release.get("plugins")
    if not isinstance(items, list):
        errors.append(f"{relative(RELEASE_MANIFEST)}: plugins 必须是数组")
        return {}
    plugins: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            errors.append(f"{relative(RELEASE_MANIFEST)}: 每个插件必须有字符串 id")
            continue
        plugin_id = item["id"]
        if plugin_id in plugins:
            errors.append(f"{relative(RELEASE_MANIFEST)}: 插件 {plugin_id} 重复")
        plugins[plugin_id] = item
    return plugins


def validate_install_profiles(
    distribution: dict[str, Any],
    plugins: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    profiles = distribution.get("installProfiles")
    if not isinstance(profiles, dict):
        errors.append(
            f"{relative(RELEASE_MANIFEST)}: distribution.installProfiles 必须是对象"
        )
        return

    if profiles != EXPECTED_INSTALL_PROFILES:
        errors.append(
            f"{relative(RELEASE_MANIFEST)}: distribution.installProfiles 应为 "
            f"{EXPECTED_INSTALL_PROFILES!r}，实际 {profiles!r}"
        )
    for profile_name, plugin_ids in profiles.items():
        if not isinstance(profile_name, str) or not profile_name:
            errors.append(
                f"{relative(RELEASE_MANIFEST)}: install profile 名称必须是非空字符串"
            )
            continue
        if (
            not isinstance(plugin_ids, list)
            or any(not isinstance(plugin_id, str) for plugin_id in plugin_ids)
        ):
            errors.append(
                f"{relative(RELEASE_MANIFEST)}: installProfiles.{profile_name} "
                "必须是插件 ID 数组"
            )
            continue
        if len(plugin_ids) != len(set(plugin_ids)):
            errors.append(
                f"{relative(RELEASE_MANIFEST)}: installProfiles.{profile_name} "
                "不得包含重复插件"
            )
        unknown = set(plugin_ids) - set(plugins)
        if unknown:
            errors.append(
                f"{relative(RELEASE_MANIFEST)}: installProfiles.{profile_name} "
                f"包含未发布插件 {sorted(unknown)}"
            )


def validate_release_identity(
    release: dict[str, Any], errors: list[str]
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    if release.get("schemaVersion") != 1:
        errors.append(f"{relative(RELEASE_MANIFEST)}: schemaVersion 必须为 1")

    distribution = release.get("distribution")
    if not isinstance(distribution, dict):
        errors.append(f"{relative(RELEASE_MANIFEST)}: distribution 必须是对象")
        distribution = {}

    version = distribution.get("version")
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        errors.append(f"{relative(RELEASE_MANIFEST)}: distribution.version 不是有效 SemVer")
    root_version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if root_version != version:
        errors.append(
            f"VERSION: 应镜像 release-manifest.json 的分发版本 {version!r}，实际 {root_version!r}"
        )
    if distribution.get("tag") != f"v{version}":
        errors.append(f"{relative(RELEASE_MANIFEST)}: distribution.tag 必须为 v{version}")
    if os.environ.get("GITHUB_REF_TYPE") == "tag":
        actual_tag = os.environ.get("GITHUB_REF_NAME")
        if actual_tag != distribution.get("tag"):
            errors.append(
                f"Git tag {actual_tag!r} 与 release manifest "
                f"{distribution.get('tag')!r} 不一致"
            )
    if distribution.get("name") != "gloamere-codex-plugins":
        errors.append(
            f"{relative(RELEASE_MANIFEST)}: distribution.name 必须为 gloamere-codex-plugins"
        )
    if distribution.get("marketplace") != "gloamere":
        errors.append(
            f"{relative(RELEASE_MANIFEST)}: distribution.marketplace 必须为 gloamere"
        )
    if distribution.get("marketplaceDisplayName") != "Gloamere":
        errors.append(
            f"{relative(RELEASE_MANIFEST)}: marketplaceDisplayName 必须为 Gloamere"
        )
    if distribution.get("distributionChannel") != "git-marketplace":
        errors.append(
            f"{relative(RELEASE_MANIFEST)}: distributionChannel 必须为 git-marketplace"
        )
    repository = distribution.get("repository")
    marketplace_source = distribution.get("marketplaceSource")
    if (
        not isinstance(repository, str)
        or marketplace_source != repository.removeprefix("https://github.com/")
    ):
        errors.append(
            f"{relative(RELEASE_MANIFEST)}: marketplaceSource 必须镜像 Git 仓库来源"
        )
    release_status = distribution.get("releaseStatus")
    directory_status = distribution.get("directoryStatus")
    directory_url = distribution.get("directoryURL")
    if release_status not in {"release-candidate", "published"}:
        errors.append(
            f"{relative(RELEASE_MANIFEST)}: releaseStatus 必须为 "
            "release-candidate 或 published"
        )
    if directory_status not in {"optional", "preparing", "submitted", "approved"}:
        errors.append(
            f"{relative(RELEASE_MANIFEST)}: directoryStatus 必须为 "
            "optional、preparing、submitted 或 approved"
        )
    elif directory_status == "approved":
        require_https(
            directory_url,
            f"{relative(RELEASE_MANIFEST)}: distribution.directoryURL",
            errors,
        )
    elif directory_url is not None:
        errors.append(
            f"{relative(RELEASE_MANIFEST)}: 目录获批前 directoryURL 必须为 null"
        )
    if os.environ.get("GITHUB_REF_TYPE") == "tag" and release_status != "published":
        errors.append(
            f"{relative(RELEASE_MANIFEST)}: tag 发布仅允许 published 状态"
        )
    if distribution.get("releaseManifestAsset") != "release-manifest.json":
        errors.append(
            f"{relative(RELEASE_MANIFEST)}: releaseManifestAsset 必须为 release-manifest.json"
        )
    if distribution.get("releaseIndex") != "release-index.json":
        errors.append(
            f"{relative(RELEASE_MANIFEST)}: releaseIndex 必须为 release-index.json"
        )
    if repository != "https://github.com/gloamere/codex-plugins":
        errors.append(
            f"{relative(RELEASE_MANIFEST)}: distribution.repository 与公开仓库不一致"
        )

    legacy = release.get("legacy")
    if not isinstance(legacy, dict) or legacy.get("behavior") != "detect-only":
        errors.append(
            f"{relative(RELEASE_MANIFEST)}: legacy.behavior 必须为 detect-only"
        )
    elif (
        legacy.get("marketplace") != "tessera"
        or legacy.get("migrationGuide") != "MIGRATION.md"
    ):
        errors.append(f"{relative(RELEASE_MANIFEST)}: legacy 迁移元数据不完整")

    plugins = release_plugins(release, errors)
    if set(plugins) != EXPECTED_PLUGIN_IDS:
        errors.append(
            f"{relative(RELEASE_MANIFEST)}: 只能发布 {sorted(EXPECTED_PLUGIN_IDS)}，"
            f"实际 {sorted(plugins)}"
        )
    validate_install_profiles(distribution, plugins, errors)
    return distribution, plugins


def validate_asset_path(
    plugin_dir: Path, value: Any, label: str, errors: list[str]
) -> None:
    if not isinstance(value, str) or not value.startswith("./"):
        errors.append(f"{label}: 必须是以 ./ 开头的插件内相对路径")
        return
    target = (plugin_dir / value[2:]).resolve()
    try:
        target.relative_to(plugin_dir.resolve())
    except ValueError:
        errors.append(f"{label}: 不得逃逸插件目录")
        return
    if not target.is_file():
        errors.append(f"{label}: 文件不存在 ({relative(target)})")
    elif target.suffix.lower() != ".png" or target.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
        errors.append(f"{label}: 必须引用有效 PNG 文件")


def validate_plugin(
    plugin_id: str,
    release_entry: dict[str, Any],
    marketplace_entry: dict[str, Any],
    repository: str,
    errors: list[str],
) -> None:
    version = release_entry.get("version")
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        errors.append(f"{plugin_id}: release version 不是有效 SemVer")
    expected_maturity = EXPECTED_PLUGIN_MATURITY[plugin_id]
    if release_entry.get("maturity") != expected_maturity:
        errors.append(
            f"{plugin_id}: maturity 必须为 {expected_maturity}"
        )
    expected_public_role = EXPECTED_PLUGIN_PUBLIC_ROLE[plugin_id]
    if release_entry.get("publicRole") != expected_public_role:
        errors.append(
            f"{plugin_id}: publicRole 必须为 {expected_public_role}"
        )

    expected_path = f"plugins/{plugin_id}"
    if release_entry.get("path") != expected_path:
        errors.append(f"{plugin_id}: release path 必须为 {expected_path}")
    expected_archive = f"{plugin_id}-{version}.zip"
    if release_entry.get("archive") != expected_archive:
        errors.append(f"{plugin_id}: archive 必须为 {expected_archive}")
    if release_entry.get("checksum") != f"{expected_archive}.sha256":
        errors.append(f"{plugin_id}: checksum 文件名与 archive 不一致")

    plugin_dir = ROOT / expected_path
    if not plugin_dir.is_dir():
        errors.append(f"{plugin_id}: 插件目录不存在")
        return

    source = marketplace_entry.get("source")
    expected_source = f"./{expected_path}"
    if (
        not isinstance(source, dict)
        or source.get("source") != "local"
        or source.get("path") != expected_source
    ):
        errors.append(f"{plugin_id}: marketplace source 必须指向 {expected_source}")
    policy = release_entry.get("policy")
    if policy != {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL",
    }:
        errors.append(f"{plugin_id}: release policy 不完整")
    if marketplace_entry.get("policy") != policy:
        errors.append(f"{plugin_id}: marketplace policy 未从 release manifest 生成")
    category = release_entry.get("category")
    if not isinstance(category, str) or not category:
        errors.append(f"{plugin_id}: release category 不能为空")
    if marketplace_entry.get("category") != category:
        errors.append(f"{plugin_id}: marketplace category 未从 release manifest 生成")

    manifest_path = plugin_dir / ".codex-plugin" / "plugin.json"
    if not manifest_path.is_file():
        errors.append(f"{plugin_id}: 缺少 {relative(manifest_path)}")
        return
    manifest = read_json(manifest_path)
    missing_top = REQUIRED_TOP_LEVEL_FIELDS - set(manifest)
    if missing_top:
        errors.append(f"{relative(manifest_path)}: 缺少字段 {sorted(missing_top)}")
    if manifest.get("name") != plugin_id:
        errors.append(f"{relative(manifest_path)}: name 不匹配")
    if manifest.get("version") != version:
        errors.append(f"{relative(manifest_path)}: version 未镜像 release manifest")
    if manifest.get("repository") != repository:
        errors.append(f"{relative(manifest_path)}: repository 与 release manifest 不一致")
    if manifest.get("license") != "MIT":
        errors.append(f"{relative(manifest_path)}: license 必须为 MIT")
    if not (plugin_dir / "LICENSE").is_file():
        errors.append(f"{plugin_id}: 发布包缺少 LICENSE")
    if not isinstance(manifest.get("description"), str) or not manifest[
        "description"
    ].strip():
        errors.append(f"{relative(manifest_path)}: description 不能为空")
    if manifest.get("skills") != "./skills/":
        errors.append(f"{relative(manifest_path)}: skills 必须为 ./skills/")
    for excluded in ("mcpServers", "apps", "screenshots"):
        if excluded in manifest:
            errors.append(
                f"{relative(manifest_path)}: skills-only 包不得声明 {excluded}"
            )
    if (
        not isinstance(manifest.get("keywords"), list)
        or not manifest["keywords"]
        or any(not isinstance(item, str) or not item for item in manifest["keywords"])
    ):
        errors.append(f"{relative(manifest_path)}: keywords 必须是非空数组")
    require_https(manifest.get("homepage"), f"{relative(manifest_path)} homepage", errors)

    author = manifest.get("author")
    if (
        not isinstance(author, dict)
        or author.get("name") != "Gloamere"
        or not author.get("url")
    ):
        errors.append(f"{relative(manifest_path)}: author 必须标识 Gloamere 及 URL")
    else:
        require_https(author["url"], f"{relative(manifest_path)} author.url", errors)

    interface = manifest.get("interface")
    if not isinstance(interface, dict):
        errors.append(f"{relative(manifest_path)}: interface 必须是对象")
        interface = {}
    missing_interface = REQUIRED_INTERFACE_FIELDS - set(interface)
    if missing_interface:
        errors.append(
            f"{relative(manifest_path)}: interface 缺少字段 {sorted(missing_interface)}"
        )
    if interface.get("developerName") != "Gloamere":
        errors.append(f"{relative(manifest_path)}: developerName 必须为 Gloamere")
    if interface.get("displayName") != release_entry.get("displayName"):
        errors.append(f"{relative(manifest_path)}: displayName 未镜像 release manifest")
    if interface.get("category") != category:
        errors.append(f"{relative(manifest_path)}: category 未镜像 release manifest")
    for field, limit in (
        ("displayName", 30),
        ("shortDescription", 30),
        ("developerName", 80),
    ):
        value = interface.get(field)
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            errors.append(f"{relative(manifest_path)}: {field} 必须为 1-{limit} 个字符")
    if (
        not isinstance(interface.get("longDescription"), str)
        or not interface["longDescription"].strip()
    ):
        errors.append(f"{relative(manifest_path)}: longDescription 不能为空")
    if (
        not isinstance(interface.get("capabilities"), list)
        or not interface["capabilities"]
        or any(not isinstance(item, str) for item in interface["capabilities"])
    ):
        errors.append(f"{relative(manifest_path)}: capabilities 必须是非空字符串数组")
    prompts = interface.get("defaultPrompt")
    if (
        not isinstance(prompts, list)
        or not prompts
        or any(not isinstance(item, str) or not item.strip() for item in prompts)
    ):
        errors.append(f"{relative(manifest_path)}: defaultPrompt 必须是非空字符串数组")
    elif (
        len(prompts) > 3
        or len(prompts) != len({re.sub(r"\s+", " ", item).strip() for item in prompts})
        or any("\n" in item or len(item) > 128 for item in prompts)
    ):
        errors.append(
            f"{relative(manifest_path)}: defaultPrompt 最多 3 条、每条单行不超过 128 字符且不得重复"
        )
    if not isinstance(interface.get("brandColor"), str) or not HEX_COLOR.fullmatch(
        interface["brandColor"]
    ):
        errors.append(f"{relative(manifest_path)}: brandColor 必须是六位十六进制颜色")
    elif interface["brandColor"].upper() != "#8B74D6":
        errors.append(f"{relative(manifest_path)}: brandColor 必须使用 Gloamere 紫色")
    for field in (
        "websiteURL",
        "privacyPolicyURL",
        "termsOfServiceURL",
        "supportURL",
    ):
        require_https(
            interface.get(field), f"{relative(manifest_path)} interface.{field}", errors
        )
    for field in ("composerIcon", "logo"):
        validate_asset_path(
            plugin_dir,
            interface.get(field),
            f"{relative(manifest_path)} interface.{field}",
            errors,
        )
    if "screenshots" in interface:
        errors.append(
            f"{relative(manifest_path)}: 无 UI 的 skills-only 插件不得提交 screenshots"
        )

    skill_dirs = {
        path.name for path in (plugin_dir / "skills").iterdir() if path.is_dir()
    }
    declared_skills = release_entry.get("skills")
    if (
        not isinstance(declared_skills, list)
        or any(not isinstance(item, str) for item in declared_skills)
        or set(declared_skills) != skill_dirs
    ):
        errors.append(
            f"{plugin_id}: release skills 与插件目录不一致，"
            f"声明 {declared_skills!r}，实际 {sorted(skill_dirs)}"
        )
    for skill_name in sorted(skill_dirs):
        skill_path = plugin_dir / "skills" / skill_name / "SKILL.md"
        if not skill_path.is_file():
            errors.append(f"{plugin_id}: 缺少 {relative(skill_path)}")
            continue
        frontmatter = parse_frontmatter(skill_path, errors)
        if frontmatter.get("name") != skill_name:
            errors.append(
                f"{relative(skill_path)}: frontmatter name 必须与目录名 {skill_name} 一致"
            )

def validate_eval_runtime(errors: list[str]) -> None:
    skill = (
        PLUGINS_ROOT
        / "gloamere-eval"
        / "skills"
        / "gloamere-skill-eval"
    )
    required = (
        skill / "scripts" / "run_routing_eval.py",
        skill / "scripts" / "run.ps1",
        skill / "scripts" / "run.sh",
        skill / "references" / "schemas" / "eval-suite.schema.json",
        skill / "references" / "schemas" / "target-lock.schema.json",
        skill / "references" / "schemas" / "native-invocation-output.schema.json",
        skill / "references" / "schemas" / "report.schema.json",
    )
    for path in required:
        if not path.is_file():
            errors.append(f"{relative(path)}: 自包含 Eval 运行资产缺失")
    runner = skill / "scripts" / "run_routing_eval.py"
    if runner.is_file():
        source = runner.read_text(encoding="utf-8")
        for forbidden in ("import yaml", "site-packages", "requirements-dev.txt"):
            if forbidden in source:
                errors.append(
                    f"{relative(runner)}: 包含第三方或仓库运行时依赖 {forbidden!r}"
                )
    for schema in (skill / "references" / "schemas").glob("*.json"):
        read_json(schema)


def validate_installers(
    distribution: dict[str, Any],
    plugins: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    repository = distribution.get("repository", "")
    shorthand = distribution.get("marketplaceSource", "")
    tag = distribution.get("tag", "")
    profiles = distribution.get("installProfiles")
    if not isinstance(profiles, dict):
        errors.append("release manifest installProfiles 必须是对象")
        profiles = {}
    for installer in (ROOT / "install.ps1", ROOT / "install.sh"):
        if not installer.is_file():
            errors.append(f"{relative(installer)}: 缺少安装入口")
            continue
        source = installer.read_text(encoding="utf-8")
        for token in (
            shorthand,
            tag,
            "plugin list --json",
            "@gloamere",
            "@tessera",
            "MIGRATION.md",
            "marketplace",
            "add",
        ):
            if token not in source:
                errors.append(f"{relative(installer)}: 缺少发布约束 {token!r}")
        for plugin_id in plugins:
            if plugin_id not in source:
                errors.append(f"{relative(installer)}: 缺少插件 {plugin_id}")

        if installer.suffix == ".ps1":
            profile_matches = re.findall(
                r"(?m)^\s*'(workflows|maintainer|complete)'\s*"
                r"\{\s*@\(([^)]*)\)\s*\}\s*$",
                source,
            )
            parsed_profiles = {
                profile: re.findall(r"'([a-z0-9-]+)'", values)
                for profile, values in profile_matches
            }
            if (
                "$Profile = 'workflows'" not in source
                or "if ($All)" not in source
                or set(parsed_profiles) != set(profiles)
            ):
                errors.append(
                    f"{relative(installer)}: 无法确认 profile 与 -All 兼容入口"
                )
            else:
                for profile, expected in profiles.items():
                    if parsed_profiles[profile] != expected:
                        errors.append(
                            f"{relative(installer)}: {profile} 插件 "
                            f"{parsed_profiles[profile]!r} 未镜像 "
                            f"installProfiles.{profile} {expected!r}"
                        )
        else:
            profile_matches = re.findall(
                r"(?m)^\s*(workflows|maintainer|complete)\)\s*"
                r"PLUGINS='([^']*)'\s*;;\s*$",
                source,
            )
            parsed_profiles = {
                profile: values.split() for profile, values in profile_matches
            }
            if (
                "PROFILE=${GLOAMERE_PROFILE:-workflows}" not in source
                or "--profile)" not in source
                or "--all)" not in source
                or set(parsed_profiles) != set(profiles)
            ):
                errors.append(
                    f"{relative(installer)}: 无法确认 profile 与 --all 兼容入口"
                )
            else:
                for profile, expected in profiles.items():
                    if parsed_profiles[profile] != expected:
                        errors.append(
                            f"{relative(installer)}: {profile} 插件 "
                            f"{parsed_profiles[profile]!r} 未镜像 "
                            f"installProfiles.{profile} {expected!r}"
                        )
        if re.search(
            r"(?m)^\s*(?:&\s+\$codex\S*|codex)\s+plugin\s+remove\b",
            source,
        ):
            errors.append(f"{relative(installer)}: 不得自动卸载旧插件")
        if re.search(
            r"(?m)^\s*(?:&\s+\$codex\S*|codex)\s+plugin\s+"
            r"marketplace\s+remove\b",
            source,
        ):
            errors.append(f"{relative(installer)}: 不得自动移除旧 marketplace")


def validate_public_docs(
    distribution: dict[str, Any],
    plugins: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    common_tokens = (
        distribution.get("version", ""),
        distribution.get("tag", ""),
        distribution.get("repository", "").removeprefix("https://github.com/"),
        "gloamere-eval@gloamere",
        "gloamere-workflows@gloamere",
    )
    for document in (ROOT / "README.md", ROOT / "docs" / "DEPLOYMENT.md"):
        source = document.read_text(encoding="utf-8")
        for token in common_tokens:
            if token not in source:
                errors.append(f"{relative(document)}: 缺少当前发布值 {token!r}")
    deployment = (ROOT / "docs" / "DEPLOYMENT.md").read_text(encoding="utf-8")
    for field in ("releaseManifestAsset", "releaseIndex"):
        value = distribution.get(field)
        if not isinstance(value, str) or value not in deployment:
            errors.append(f"docs/DEPLOYMENT.md: 缺少发布元数据资产 {value!r}")
    for plugin in plugins.values():
        for field in ("archive", "checksum"):
            value = plugin.get(field)
            if not isinstance(value, str) or value not in deployment:
                errors.append(
                    f"docs/DEPLOYMENT.md: 缺少 release manifest 的 {field} {value!r}"
                )


def main() -> int:
    errors: list[str] = []
    try:
        release = read_json(RELEASE_MANIFEST)
        distribution, plugins = validate_release_identity(release, errors)
        marketplace = read_json(MARKETPLACE)
        if marketplace.get("name") != distribution.get("marketplace"):
            errors.append(f"{relative(MARKETPLACE)}: name 未镜像 release manifest")
        interface = marketplace.get("interface")
        if (
            not isinstance(interface, dict)
            or interface.get("displayName")
            != distribution.get("marketplaceDisplayName")
        ):
            errors.append(f"{relative(MARKETPLACE)}: displayName 未镜像 release manifest")
        entries = marketplace_entries(marketplace, errors)
        if set(entries) != set(plugins):
            errors.append(
                f"{relative(MARKETPLACE)}: 插件集合应为 {sorted(plugins)}，"
                f"实际 {sorted(entries)}"
            )

        plugin_dirs = {
            path.name for path in PLUGINS_ROOT.iterdir() if path.is_dir()
        }
        if plugin_dirs != set(plugins):
            errors.append(
                f"plugins/: 只能包含发布插件 {sorted(plugins)}，实际 {sorted(plugin_dirs)}"
            )
        active_manifests = {
            relative(path)
            for path in ROOT.rglob("plugin.json")
            if path.parent.name == ".codex-plugin"
        }
        expected_manifests = {
            f"plugins/{plugin_id}/.codex-plugin/plugin.json"
            for plugin_id in plugins
        }
        if active_manifests != expected_manifests:
            errors.append(
                "Codex manifest 集合与双插件发布面不一致: "
                f"{sorted(active_manifests)}"
            )
        if (ROOT / ".claude-plugin" / "marketplace.json").exists():
            errors.append(".claude-plugin/marketplace.json: v4 不得继续发布 Claude marketplace")

        repository = distribution.get("repository", "")
        for plugin_id in sorted(set(plugins) & set(entries)):
            validate_plugin(
                plugin_id,
                plugins[plugin_id],
                entries[plugin_id],
                repository,
                errors,
            )
        validate_eval_runtime(errors)
        validate_installers(distribution, plugins, errors)
        validate_public_docs(distribution, plugins, errors)

        if not (ROOT / "MIGRATION.md").is_file():
            errors.append("MIGRATION.md: 缺少 v4 迁移说明")
        for document in ("docs/PRIVACY.md", "docs/TERMS.md"):
            if not (ROOT / document).is_file():
                errors.append(f"{document}: 公开 manifest 引用的文档不存在")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(str(exc))

    if errors:
        print("Gloamere 发布物校验失败:", file=sys.stderr)
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1
    print(
        "校验通过：release manifest、2 个 Codex 插件、品牌元数据、"
        "成熟度、安装 profile、固定 tag 安装入口与迁移边界一致。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
