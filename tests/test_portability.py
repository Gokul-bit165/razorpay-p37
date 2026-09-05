"""
Portability and environment hygiene tests.
Verifies that the codebase contains no machine-specific absolute paths,
no drive letters, has standard packaging files, and runs cleanly across OSes.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_no_pytest_bat_at_root():
    """Verify Windows-only batch file is not in repo root."""
    assert not (REPO_ROOT / "pytest.bat").exists(), "pytest.bat should not exist in repo root"


def test_pyproject_toml_exists_and_declares_python_requirement():
    """Verify pyproject.toml exists and specifies python requirement >=3.13."""
    pyproject = REPO_ROOT / "pyproject.toml"
    assert pyproject.exists(), "pyproject.toml must exist"
    content = pyproject.read_text(encoding="utf-8")
    assert 'requires-python = ">=3.13"' in content, "pyproject.toml must declare requires-python = '>=3.13'"


def test_makefile_exists_with_required_targets():
    """Verify Makefile exists and contains standard targets."""
    makefile = REPO_ROOT / "Makefile"
    assert makefile.exists(), "Makefile must exist"
    content = makefile.read_text(encoding="utf-8")
    for target in ["all:", "install:", "test:", "bench:", "demo:"]:
        assert target in content, f"Makefile must contain {target}"


def test_no_hardcoded_drive_letters_or_user_paths_in_tracked_files():
    r"""
    Ensure no tracked files contain hardcoded Windows drive letters (e.g. C:\ or C:/)
    or developer home paths like /Users/username.
    """
    try:
        res = subprocess.run(
            ["git", "ls-files"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        tracked_files = [f.strip() for f in res.stdout.splitlines() if f.strip()]
    except Exception:
        # Fallback if git is not in PATH
        tracked_files = []
        for root, _, files in os.walk(str(REPO_ROOT)):
            if ".git" in root or "__pycache__" in root or ".pytest_cache" in root:
                continue
            for f in files:
                tracked_files.append(str(Path(root, f).relative_to(REPO_ROOT).as_posix()))

    # Regex matching Windows drive letters (e.g. C:\ or C:/) preceded by non-word/start
    # or developer user directories like /Users/...
    drive_pattern = re.compile(r"(?<![a-zA-Z0-9_])([a-zA-Z]:[\\/][a-zA-Z0-9_.-]+|/Users/[a-zA-Z0-9_-]+)", re.IGNORECASE)

    violations = []
    text_extensions = {".py", ".md", ".json", ".toml", ".txt", ".ps1", ".sh", ".yml", ".yaml"}

    for rel_path in tracked_files:
        p = REPO_ROOT / rel_path
        if not p.exists() or p.suffix.lower() not in text_extensions:
            continue
        # Skip this test file itself since it contains regex patterns
        if p.name == "test_portability.py":
            continue

        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        matches = drive_pattern.findall(content)
        if matches:
            violations.append(f"{rel_path}: found {matches[:3]}")

    assert not violations, f"Found hardcoded drive letters or user paths in tracked files:\n" + "\n".join(violations)
