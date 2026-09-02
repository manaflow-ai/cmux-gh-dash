#!/usr/bin/env python3
"""Reject mutable extension sources and malformed gh-dash release pins."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_ASSETS = {
    "darwin-arm64": (
        "472375589",
        "22930386",
        "gh-dash_v4.25.2_darwin-arm64",
        "a0e787ef5679e45e08c69edb34f25ed811aefc14157dd08f5721edcb5a3ec671",
    ),
    "darwin-amd64": (
        "472375685",
        "24346336",
        "gh-dash_v4.25.2_darwin-amd64",
        "ced29d14d9cf4a7508ca3a7466f0a6867fe9694fc8c65cd354bc842f7f32c18a",
    ),
}
MUTABLE = re.compile(
    r"(?:releases/latest|releases/download/|archive/(?:refs/)?(?:heads|tags)/|"
    r"refs/(?:heads|tags)/|\b(?:latest|master|main|HEAD)\b)",
    re.IGNORECASE,
)


def fail(message: str) -> None:
    print(f"manifest check: {message}", file=sys.stderr)
    raise SystemExit(1)


def all_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for child in value for item in all_strings(child)]
    if isinstance(value, dict):
        return [item for child in value.values() for item in all_strings(child)]
    return []


def parse_lock() -> None:
    lock = ROOT / "third_party" / "gh-dash.lock"
    if not lock.is_file():
        fail(f"missing {lock.relative_to(ROOT)}")

    metadata: dict[str, str] = {}
    assets: dict[str, tuple[str, str, str, str]] = {}
    for line_number, raw_line in enumerate(lock.read_text().splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if fields[0] in {"release", "release_id", "tag_object", "source_commit"}:
            if len(fields) != 2 or fields[0] in metadata:
                fail(f"invalid lock metadata on line {line_number}")
            metadata[fields[0]] = fields[1]
        elif fields[0] == "asset":
            if len(fields) != 6 or fields[1] in assets:
                fail(f"invalid lock asset on line {line_number}")
            assets[fields[1]] = (fields[2], fields[3], fields[4], fields[5])
        else:
            fail(f"unknown lock record on line {line_number}")

    if metadata != {
        "release": "v4.25.2",
        "release_id": "352033227",
        "tag_object": "61e619ba8a9682ba8a822282d1da8c5eb7b0bbff",
        "source_commit": "a613ef744c99ef8d8ead33467813c6ee6086af52",
    }:
        fail("release metadata is not the audited v4.25.2 record")
    if assets != EXPECTED_ASSETS:
        fail("release assets do not match the audited IDs, sizes, names, and digests")
    if not HEX40.fullmatch(metadata["tag_object"]):
        fail("tag object is not a full commit object ID")
    if not HEX40.fullmatch(metadata["source_commit"]):
        fail("source commit is not a full commit ID")


def main() -> None:
    manifest_path = ROOT / "cmux-extension.json"
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot parse cmux-extension.json: {error}")

    if not isinstance(manifest, dict):
        fail("manifest root must be an object")

    if manifest.get("platforms") != ["macos"]:
        fail("extension must be restricted to macOS")
    build = manifest.get("build")
    if build != [{"command": ["sh", "scripts/install-gh-dash.sh"], "platforms": ["macos"]}]:
        fail("build must use the pinned installer on macOS")
    panes = manifest.get("panes")
    if (
        not isinstance(panes, list)
        or len(panes) != 1
        or not isinstance(panes[0], dict)
    ):
        fail("expected exactly one pane")
    if panes[0].get("command") != ["bin/gh-dash"]:
        fail("pane must execute the verified local binary")
    if panes[0].get("platforms") != ["macos"]:
        fail("pane must be restricted to macOS")

    # Inspect executable argv only. The schema URL and explanatory text may
    # legitimately mention a branch name, while a command must never resolve
    # one at runtime.
    command_values = all_strings(manifest.get("build", [])) + all_strings(
        manifest.get("panes", [])
    )
    for value in command_values:
        if MUTABLE.search(value):
            fail(f"mutable reference found in manifest: {value}")
        if value.startswith("gh extension install"):
            fail("global gh extension installation is not allowed")

    installer = (ROOT / "scripts" / "install-gh-dash.sh").read_text()
    if "releases/latest" in installer or "gh extension install" in installer:
        fail("installer contains a mutable or global extension install")
    if MUTABLE.search(installer):
        fail("installer contains a mutable reference")
    if "releases/assets/$asset_id" not in installer:
        fail("installer must use an immutable release asset ID")
    if (
        "actual_sha" not in installer
        or "--proto '=https'" not in installer
        or "--proto-redir '=https'" not in installer
        or "--max-filesize" not in installer
        or "--netrc-file" not in installer
        or "gh auth token --hostname github.com" not in installer
        or "codesign --verify" not in installer
    ):
        fail("installer must enforce authenticated HTTPS, a size bound, SHA-256, and code signing")
    parse_lock()
    print("manifest check: OK")


if __name__ == "__main__":
    main()
