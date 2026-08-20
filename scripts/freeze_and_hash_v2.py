#!/usr/bin/env python3
"""
Claim 2 -- Phase 3, step F: freeze + hash the v2 policy corpus, the
ground-truth label table, and the environment-drift sanity anchor.

Mirrors scripts/freeze_and_hash.py (Phase 1) and freeze_and_hash_skills.py
(Phase 2). Hashes every file in policy_corpus/v2/ plus the ground_truth/
and environment_contracts/ directories, computes one fingerprint over the
sorted set, and sets policy_corpus/v2/*.json and ground_truth/*.json/.csv
read-only. Future changes (e.g. a v3, or a relabeling) are a new version,
never an edit in place.
"""
import hashlib
import json
import os
from datetime import datetime, timezone

DIRS = {
    "policy_corpus/v2": "policy_corpus/v2/*.json",
    "ground_truth": "ground_truth/*.json",
    "ground_truth_csv": "ground_truth/*.csv",
    "environment_contracts": "environment_contracts/*.json",
}
HASH_DIR = "policy_corpus/hashes"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    import glob
    per_file = {}
    for label, pattern in DIRS.items():
        for path in sorted(glob.glob(pattern)):
            rel = path
            per_file[rel] = sha256_file(path)

    assert per_file, "no Phase 3 files found -- run the build scripts first"

    lines = [f"{name}:{h}" for name, h in sorted(per_file.items())]
    fingerprint = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()

    record = {
        "artifact": "policy_corpus v2 + ground_truth + environment_contracts",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "num_files": len(per_file),
        "algorithm": "sha256",
        "fingerprint": fingerprint,
        "files": per_file,
    }
    os.makedirs(HASH_DIR, exist_ok=True)
    with open(f"{HASH_DIR}/v2_checksums.json", "w") as fh:
        json.dump(record, fh, indent=2)
    with open(f"{HASH_DIR}/v2_checksums.sha256", "w") as fh:
        for name, h in sorted(per_file.items()):
            fh.write(f"{h}  {name}\n")

    for path in glob.glob("policy_corpus/v2/*.json"):
        os.chmod(path, 0o444)
    for path in glob.glob("ground_truth/*.json") + glob.glob("ground_truth/*.csv"):
        os.chmod(path, 0o444)

    print(f"Hashed {len(per_file)} files across policy_corpus/v2/, ground_truth/, "
          f"environment_contracts/.")
    print(f"Phase 3 fingerprint (v2): {fingerprint}")


if __name__ == "__main__":
    main()
