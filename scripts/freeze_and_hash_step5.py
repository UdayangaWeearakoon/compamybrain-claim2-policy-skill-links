#!/usr/bin/env python3
"""
Claim 2 -- Phase 5, final step: freeze + hash the Phase 5 scoring outputs.

Mirrors the Phase 1/2/3/4 freeze scripts. Hashes the main results table, the
Condition B error slice, the ablations, and RESULTS.md into one fingerprint,
then sets them read-only.
"""
import glob
import hashlib
import json
import os
from datetime import datetime, timezone

PATTERNS = [
    "results/scoring/*.json",
    "results/scoring/*.csv",
    "results/scoring/*.md",
    "results/RESULTS.md",
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

    assert per_file, "no Phase 5 outputs found -- run the scoring scripts first"

    lines = [f"{name}:{h}" for name, h in sorted(per_file.items())]
    fingerprint = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()

    record = {
        "artifact": "Phase 5 scoring outputs (main results, error slice, ablations, RESULTS.md)",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "num_files": len(per_file),
        "algorithm": "sha256",
        "fingerprint": fingerprint,
        "files": per_file,
    }
    os.makedirs(HASH_DIR, exist_ok=True)
    with open(f"{HASH_DIR}/step5_checksums.json", "w") as fh:
        json.dump(record, fh, indent=2)
    with open(f"{HASH_DIR}/step5_checksums.sha256", "w") as fh:
        for name, h in sorted(per_file.items()):
            fh.write(f"{h}  {name}\n")

    for path in per_file:
        os.chmod(path, 0o444)

    print(f"Hashed {len(per_file)} files (Phase 5 scoring outputs).")
    print(f"Phase 5 fingerprint: {fingerprint}")


if __name__ == "__main__":
    main()
