"""Opt-in consumer replay. Never finish, edit or remove supplied source roots."""
import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
from pathlib import Path


def inventory(root):
    result = {}
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode):
            continue
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("unsafe replay source")
        result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def invoke(launcher, arguments):
    completed = subprocess.run([str(launcher), *arguments], capture_output=True, text=True, check=False)
    return {"exit": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}


def main():
    parser = argparse.ArgumentParser()
    for name in ("source", "original", "repository", "baseline-launcher", "candidate-launcher", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    before = {str(root): inventory(root) for root in (args.source, args.original)}
    (args.output / "original-digests.json").write_text(json.dumps(before, sort_keys=True) + "\n")
    run_id = json.loads((args.source / ".depot-owned-run.json").read_text())["run_id"]
    start = invoke(args.candidate_launcher, ["owned-run-start", "--workflow", "dm-review", "--run-id", run_id])
    assert start["exit"] == 0, start
    root = Path(json.loads(start["stdout"])["path"])
    (args.output / "isolated-root.txt").write_text(str(root) + "\n")
    for path in args.source.iterdir():
        if path.name in {".depot-owned-run.json", ".depot-owned-run.lock", "diagnostic", "CLEANUP.txt"}:
            continue
        if path.is_dir():
            shutil.copytree(path, root / path.name)
        else:
            shutil.copyfile(path, root / path.name)
            os.chmod(root / path.name, 0o600)
    common = ["--run-root", str(root), "--repository-root", str(args.repository),
              "--request", str(root / "review/request-with-native.json"),
              "--receipts", str(root / "review/authoritative-receipts.json"),
              "--lane-receipts", str(root / "review/review-lane-receipts.json"),
              "--raw-lane-outputs", str(root / "review/raw-lane-outputs.json"),
              "--raw-findings", str(root / "review/raw-finding-inventory.json"),
              "--decisions", str(root / "review/synthesis-decisions.json"),
              "--private-router-directory", str(root / "receipts/private/router"),
              "--report", str(root / "report-final.md")]
    results = {"isolated_root": str(root), "baseline": invoke(args.baseline_launcher, ["preserve-review-evidence", *common])}
    assert results["baseline"]["exit"] == 3, results["baseline"]
    assert json.loads(results["baseline"]["stderr"])["error"]["details"]["reason"] == "retention_limit"
    after_baseline = inventory(root)
    results["projection"] = invoke(args.candidate_launcher, ["project-review-evidence", *common])
    assert inventory(root) == after_baseline, "projection wrote to isolated inputs"
    assert results["projection"]["exit"] == 0, results["projection"]
    results["preservation"] = invoke(args.candidate_launcher, ["preserve-review-evidence", *common])
    (args.output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    assert results["preservation"]["exit"] == 0, results["preservation"]
    result = json.loads(results["preservation"]["stdout"])
    assert result["status"] == "complete", result
    evidence = Path(result["evidence_path"])
    retained = inventory(evidence)
    for relative, digest in retained.items():
        source = "report-final.md" if relative == "report.md" else "review/request-with-native.json" if relative == "review/request.json" else relative
        assert hashlib.sha256((root / source).read_bytes()).hexdigest() == digest, relative
    results["repeat_preservation"] = invoke(args.candidate_launcher, ["preserve-review-evidence", *common])
    assert results["repeat_preservation"]["exit"] == 0, results["repeat_preservation"]
    assert inventory(evidence) == retained
    finish = ["owned-run-finish", "--run-root", str(root), "--outcome", "succeeded", "--retain-diagnostics"]
    results["terminal"] = invoke(args.candidate_launcher, finish)
    assert results["terminal"]["exit"] == 0, results["terminal"]
    finished = inventory(root)
    results["repeat_terminal"] = invoke(args.candidate_launcher, finish)
    assert results["repeat_terminal"] == results["terminal"]
    assert inventory(root) == finished
    assert inventory(evidence) == retained
    after = {str(source): inventory(source) for source in (args.source, args.original)}
    assert before == after, "original consumer bytes changed"
    results["original_bytes_identical"] = True
    results["retained_files"] = len(retained)
    results["retained_bytes"] = sum(path.stat().st_size for path in evidence.rglob("*") if path.is_file())
    (args.output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    (args.output / "retained-digests.json").write_text(json.dumps(retained, sort_keys=True) + "\n")
    print(json.dumps({key: results[key] for key in ("isolated_root", "original_bytes_identical", "retained_files", "retained_bytes")}))


if __name__ == "__main__":
    main()
