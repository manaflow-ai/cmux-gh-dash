#!/usr/bin/env python3
"""Exercise manifest rejection paths without changing the checkout."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable


SOURCE_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_FILES = (
    "cmux-extension.json",
    "scripts/check-manifest.py",
    "scripts/install-gh-dash.sh",
    "third_party/gh-dash.lock",
)
Mutator = Callable[[Path], None]


def copy_fixture(root: Path) -> None:
    for relative_path in FIXTURE_FILES:
        source = SOURCE_ROOT / relative_path
        destination = root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def run_checker(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(root / "scripts" / "check-manifest.py")],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )


def load_manifest(root: Path) -> tuple[Path, dict[str, object]]:
    path = root / "cmux-extension.json"
    return path, json.loads(path.read_text())


def reject_case(name: str, mutate: Mutator, expected: str) -> None:
    with tempfile.TemporaryDirectory(prefix="cmux-gh-dash-manifest-") as directory:
        root = Path(directory)
        copy_fixture(root)
        mutate(root)
        result = run_checker(root)
        output = result.stdout + result.stderr
        if result.returncode == 0:
            raise SystemExit(f"{name}: checker accepted invalid fixture")
        if expected not in output:
            raise SystemExit(f"{name}: missing {expected!r} in checker output: {output}")
        print(f"manifest rejection: {name}")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="cmux-gh-dash-manifest-") as directory:
        baseline = Path(directory)
        copy_fixture(baseline)
        result = run_checker(baseline)
        if result.returncode != 0:
            raise SystemExit(f"baseline fixture failed: {result.stdout}{result.stderr}")

    def malformed_root(root: Path) -> None:
        (root / "cmux-extension.json").write_text("[]\n")

    def malformed_pane(root: Path) -> None:
        path, manifest = load_manifest(root)
        manifest["panes"] = [None]
        path.write_text(json.dumps(manifest) + "\n")

    def mutable_manifest_reference(root: Path) -> None:
        path, manifest = load_manifest(root)
        manifest["panes"][0]["title"] = (
            "https://github.com/dlvhdr/gh-dash/releases/latest"
        )
        path.write_text(json.dumps(manifest) + "\n")

    def mutable_release_reference(root: Path) -> None:
        path = root / "scripts" / "install-gh-dash.sh"
        path.write_text(
            path.read_text()
            + "\n# mutable URL: "
            + "https://github.com/dlvhdr/gh-dash/releases/download/v4.25.2\n"
        )

    def mutable_branch_reference(root: Path) -> None:
        path = root / "scripts" / "install-gh-dash.sh"
        path.write_text(path.read_text() + "\n# mutable ref: refs/heads/main\n")

    def missing_cleanup_trap(root: Path) -> None:
        path = root / "scripts" / "install-gh-dash.sh"
        path.write_text(path.read_text().replace("trap cleanup EXIT", "# cleanup trap removed"))

    reject_case("malformed manifest root", malformed_root, "manifest root must be an object")
    reject_case("malformed pane", malformed_pane, "expected exactly one pane")
    reject_case("mutable manifest reference", mutable_manifest_reference, "mutable reference found")
    reject_case(
        "mutable release reference",
        mutable_release_reference,
        "installer contains a mutable reference",
    )
    reject_case(
        "mutable branch reference",
        mutable_branch_reference,
        "installer contains a mutable reference",
    )
    reject_case(
        "missing cleanup trap",
        missing_cleanup_trap,
        "installer must enforce",
    )
    print("manifest rejection tests: OK")


if __name__ == "__main__":
    main()
