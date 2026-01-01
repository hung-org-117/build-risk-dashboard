from pymongo import MongoClient
import os

client = MongoClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017/buildguard?directConnection=true"))
db = client.buildguard

# Find build #697
training = db.model_training_builds.find_one({"build_number": 697})
if training:
    print("Found in model_training_builds")
    print(training)
else:
    print("Not found in model_training_builds")
    raw = db.raw_build_runs.find_one({"build_number": 697})
    if raw:
        print("Found in raw_build_runs")
        print(f"ID: {raw.get('_id')}")
        print(f"SHA: {raw.get('commit_sha')}")
    else:
        print("Not found anywhere")
