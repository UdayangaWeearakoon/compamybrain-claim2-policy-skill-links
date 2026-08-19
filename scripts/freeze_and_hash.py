#!/usr/bin/env python3
"""
Freeze + hash the v1 policy corpus.

Non-negotiable hygiene rule #1 (execution guide): "Compute a checksum for
every policy file and commit the corpus before any skill is distilled."

This script computes a SHA-256 checksum for every policy JSON file in
policy_corpus/v1 (excluding the manifest itself, which is regenerated
last and then hashed too), writes them to policy_corpus/hashes/, and
writes a single corpus-level hash (the hash of the sorted concatenation
of all per-file hashes) that acts as the freeze fingerprint for the
whole v1 corpus.

After this script is run and the printed fingerprint is recorded in the
datasheet / checkpoint, policy_corpus/v1/*.json MUST be treated as
read-only. Any future policy change is a NEW version (v2, ...), written
to policy_corpus/v2/, never an edit here.
"""
import hashlib
import json
import os
from datetime import datetime, timezone

BASE = os.path.join(os.path.dirname(__file__), "..", "policy_corpus")
V1_DIR = os.path.join(BASE, "v1")
HASH_DIR = os.path.join(BASE, "hashes")
os.makedirs(HASH_DIR, exist_ok=True)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    files = sorted(f for f in os.listdir(V1_DIR) if f.endswith(".json"))
    assert files, "no policy files found -- run build_policy_corpus_v1.py first"

    per_file = {}
    for fname in files:
        path = os.path.join(V1_DIR, fname)
        per_file[fname] = sha256_file(path)

    # Corpus-level fingerprint: sha256 of the sorted "filename:hash" lines,
    # so it's stable regardless of filesystem iteration order and changes
    # if ANY file changes, is added, or is removed.
    lines = [f"{fname}:{h}" for fname, h in sorted(per_file.items())]
    corpus_fingerprint = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()

    record = {
        "corpus_version": "v1",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "num_files": len(files),
        "algorithm": "sha256",
        "corpus_fingerprint": corpus_fingerprint,
        "files": per_file,
    }

    out_path = os.path.join(HASH_DIR, "v1_checksums.json")
    with open(out_path, "w") as fh:
        json.dump(record, fh, indent=2, sort_keys=False)
        fh.write("\n")

    # Also a flat sha256sum-compatible file for easy `sha256sum -c`.
    flat_path = os.path.join(HASH_DIR, "v1_checksums.sha256")
    with open(flat_path, "w") as fh:
        for fname, h in sorted(per_file.items()):
            fh.write(f"{h}  {fname}\n")

    print(f"Hashed {len(files)} v1 policy files.")
    print(f"Corpus fingerprint (v1): {corpus_fingerprint}")
    print(f"Wrote: {out_path}")
    print(f"Wrote: {flat_path}")


if __name__ == "__main__":
    main()
