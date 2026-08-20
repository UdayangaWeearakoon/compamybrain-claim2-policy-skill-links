#!/usr/bin/env python3
"""
Claim 2 -- Phase 2, step E: freeze + hash the v1 skill library.

Mirrors scripts/freeze_and_hash.py from Phase 1 (hygiene rule #1: "Freeze
and hash every artifact ... the moment it's finalized. Never edit a
frozen artifact -- version it instead," and the guide names "skill
library" explicitly alongside policy corpora and ground-truth labels).

Hashes every file in skill_library/v1/ (the 131 skill JSON files + the
_skill_index.json manifest) plus the two top-level dependency-link table
files and the audit outputs, so the whole Phase 2 deliverable set has a
verifiable fingerprint. skill_library/intermediate/ (the raw extracted
action traces) is deliberately excluded -- it's fully reproducible from
the (gitignored) raw ABCD file via extract_action_traces.py and is not
itself a frozen research artifact.

After this script runs, skill_library/v1/*.json is set read-only. Any
future skill-library change (e.g. Phase 3 relabeling) is a new version,
not an edit in place.
"""
import hashlib
import json
import os
from datetime import datetime, timezone

BASE = os.path.join(os.path.dirname(__file__), "..", "skill_library")
V1_DIR = os.path.join(BASE, "v1")
HASH_DIR = os.path.join(BASE, "hashes")
os.makedirs(HASH_DIR, exist_ok=True)

EXTRA_FILES = ["dependency_links.json", "dependency_links.csv",
               "audit/audit_sample.json", "audit/annotator_a_verdicts.json",
               "audit/annotator_b_verdicts.json", "audit/kappa_result.json",
               "audit/kappa_report.md"]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    v1_files = sorted(f for f in os.listdir(V1_DIR) if f.endswith(".json"))
    assert v1_files, "no skill files found -- run distill_skills.py first"

    per_file = {}
    for fname in v1_files:
        per_file[f"v1/{fname}"] = sha256_file(os.path.join(V1_DIR, fname))
    for rel in EXTRA_FILES:
        path = os.path.join(BASE, rel)
        if os.path.exists(path):
            per_file[rel] = sha256_file(path)

    lines = [f"{name}:{h}" for name, h in sorted(per_file.items())]
    fingerprint = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()

    record = {
        "artifact": "skill_library v1",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "num_files": len(per_file),
        "num_skills": len(v1_files) - 1,  # minus _skill_index.json
        "algorithm": "sha256",
        "fingerprint": fingerprint,
        "files": per_file,
    }
    with open(os.path.join(HASH_DIR, "v1_checksums.json"), "w") as fh:
        json.dump(record, fh, indent=2)
    with open(os.path.join(HASH_DIR, "v1_checksums.sha256"), "w") as fh:
        for name, h in sorted(per_file.items()):
            fh.write(f"{h}  {name}\n")

    os.chmod(V1_DIR, 0o755)
    for fname in v1_files:
        os.chmod(os.path.join(V1_DIR, fname), 0o444)

    print(f"Hashed {len(per_file)} files ({len(v1_files) - 1} skills + supporting artifacts).")
    print(f"Skill library fingerprint (v1): {fingerprint}")


if __name__ == "__main__":
    main()
