"""
Verification manifest generator (P0-5).

Computes SHA-256 checksums of all committed result files, transcripts,
and configurations, and binds them to the current Git commit SHA.
Reviewers can run this script with --verify to confirm that committed
numbers have not drifted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def get_git_commit_sha() -> str:
    """Retrieve the current Git commit SHA."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return "UNKNOWN_COMMIT"


def compute_sha256(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def generate_manifest() -> dict:
    results_dir = REPO_ROOT / "experiments" / "results"
    transcripts_dir = REPO_ROOT / "experiments" / "transcripts"
    llm_transcripts_dir = REPO_ROOT / "experiments" / "results" / "llm_transcripts"
    configs_dir = REPO_ROOT / "data" / "configs"

    manifest = {
        "manifest_version": "1.0",
        "git_commit_sha": get_git_commit_sha(),
        "files": {},
    }

    # Result JSON files (ignore run_meta.json and RESULTS_MANIFEST.json)
    if results_dir.exists():
        for f in sorted(results_dir.glob("*.json")):
            if f.name in ("run_meta.json", "RESULTS_MANIFEST.json"):
                continue
            rel = f.relative_to(REPO_ROOT).as_posix()
            manifest["files"][rel] = compute_sha256(f)

    # Transcript files (legacy and llm_transcripts)
    if transcripts_dir.exists():
        for f in sorted(transcripts_dir.glob("*.json")):
            rel = f.relative_to(REPO_ROOT).as_posix()
            manifest["files"][rel] = compute_sha256(f)

    if llm_transcripts_dir.exists():
        for f in sorted(llm_transcripts_dir.glob("*.json")):
            rel = f.relative_to(REPO_ROOT).as_posix()
            manifest["files"][rel] = compute_sha256(f)

    # Config files
    if configs_dir.exists():
        for f in sorted(configs_dir.glob("*.json")):
            rel = f.relative_to(REPO_ROOT).as_posix()
            manifest["files"][rel] = compute_sha256(f)

    return manifest


def main():
    parser = argparse.ArgumentParser(description="Generate or verify RESULTS_MANIFEST.json")
    parser.add_argument("--verify", action="store_true", help="Verify existing manifest against current files")
    args = parser.parse_args()

    manifest_path = REPO_ROOT / "experiments" / "results" / "RESULTS_MANIFEST.json"

    if args.verify:
        if not manifest_path.exists():
            print(f"Error: {manifest_path} does not exist.")
            sys.exit(1)
        expected = json.loads(manifest_path.read_text(encoding="utf-8"))
        current = generate_manifest()

        mismatches = []
        for file_path, exp_hash in expected["files"].items():
            curr_hash = current["files"].get(file_path)
            if curr_hash != exp_hash:
                mismatches.append(f"  {file_path}: expected {exp_hash}, got {curr_hash}")

        if mismatches:
            print("Manifest verification FAILED! Hash mismatches detected:")
            print("\n".join(mismatches))
            sys.exit(1)
        else:
            print(f"Manifest verification PASSED: {len(expected['files'])} files match SHA-256 checksums.")
            print(f"Git commit binding: {expected.get('git_commit_sha', 'N/A')}")
            sys.exit(0)

    manifest = generate_manifest()
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Generated manifest with {len(manifest['files'])} tracked files at: {manifest_path.relative_to(REPO_ROOT)}")
    print(f"Git commit SHA: {manifest['git_commit_sha']}")


if __name__ == "__main__":
    main()
