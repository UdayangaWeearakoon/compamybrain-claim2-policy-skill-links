#!/usr/bin/env python3
"""
Claim 2 -- Phase 4, step F: freeze + hash the Step 4 run outputs.

Mirrors freeze_and_hash.py (Phase 1), freeze_and_hash_skills.py (Phase 2),
and freeze_and_hash_v2.py (Phase 3). Hashes the preregistration and every
raw flag table / execution log into one fingerprint, then sets them
read-only.

The preregistration is included in the hash deliberately: its whole value is
that its contents predate the results, and a hash covering both makes "the
thresholds were not edited after seeing the numbers" checkable rather than
merely asserted. (Commit order in git already shows it landed first; the
hash pins the content.)
"""
import glob
import hashlib
import json
import os
from datetime import datetime, timezone

PATTERNS = [
    "preregistration/*.md",
    "results/condition_a/*.json",
    "results/condition_a/*.csv",
    "results/condition_b/*.json",
    "results/condition_b/*.csv",
    "results/silent_wrong_action/*.json",
    "results/silent_wrong_action/*.csv",
]
HASH_DIR = "results/hashes"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    per_file = {}
    for pattern in PATTERNS:
        for path in sorted(glob.glob(pattern)):
            per_file[path] = sha256_file(path)

    assert per_file, "no Step 4 outputs found -- run the conditions first"

    lines = [f"{name}:{h}" for name, h in sorted(per_file.items())]
    fingerprint = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()

    record = {
        "artifact": "Step 4 preregistration + raw flag tables + execution logs",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "num_files": len(per_file),
        "algorithm": "sha256",
        "fingerprint": fingerprint,
        "files": per_file,
    }
    os.makedirs(HASH_DIR, exist_ok=True)
    with open(f"{HASH_DIR}/step4_checksums.json", "w") as fh:
        json.dump(record, fh, indent=2)
    with open(f"{HASH_DIR}/step4_checksums.sha256", "w") as fh:
        for name, h in sorted(per_file.items()):
            fh.write(f"{h}  {name}\n")

    for path in per_file:
        os.chmod(path, 0o444)

    print(f"Hashed {len(per_file)} files (preregistration + Step 4 outputs).")
    print(f"Step 4 fingerprint: {fingerprint}")


if __name__ == "__main__":
    main()
