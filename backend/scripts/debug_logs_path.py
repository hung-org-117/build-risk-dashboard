#!/usr/bin/env python3
"""Debug script to check logs_path in raw_build_runs."""

import os
import sys

sys.path.insert(0, ".")

from pymongo import MongoClient

# Get MongoDB URI from environment or default
mongo_uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
client = MongoClient(mongo_uri)
db = client["build_risk_dashboard"]

# Get latest raw_build_runs
runs = list(
    db.get_collection("raw_build_runs").find({}).sort("created_at", -1).limit(5)
)

print("=" * 80)
print("Latest raw_build_runs:")
print("=" * 80)

for r in runs:
    print(
        f"""
build_id: {r.get('build_id')}
_id: {r.get('_id')}
logs_path: {r.get('logs_path')}
logs_available: {r.get('logs_available')}
logs_expired: {r.get('logs_expired')}
raw_repo_id: {r.get('raw_repo_id')}
---"""
    )

print("\n" + "=" * 80)
print("Checking if logs exist on disk:")
print("=" * 80)

from pathlib import Path
from app.paths import LOGS_DIR

for r in runs:
    repo_id = str(r.get("raw_repo_id"))
    build_id = str(r.get("build_id"))

    # Check logs_path from entity
    entity_logs_path = r.get("logs_path")
    entity_path_exists = Path(entity_logs_path).exists() if entity_logs_path else False

    # Check fallback path
    fallback_path = LOGS_DIR / repo_id / build_id
    fallback_exists = fallback_path.exists()

    # Check wrong path (using _id instead of build_id)
    wrong_path = LOGS_DIR / repo_id / str(r.get("_id"))
    wrong_path_exists = wrong_path.exists()

    print(
        f"""
build_id: {build_id}
  entity logs_path: {entity_logs_path} (exists: {entity_path_exists})
  fallback path: {fallback_path} (exists: {fallback_exists})
  wrong path (using _id): {wrong_path} (exists: {wrong_path_exists})
  log files in fallback: {list(fallback_path.glob('*.log')) if fallback_exists else []}
"""
    )
