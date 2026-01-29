import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone


def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def ensure_record(value):
    if isinstance(value, list):
        return [ensure_record(item) for item in value]
    if not isinstance(value, dict):
        return {"id": str(uuid.uuid4()), "value": value}
    data = dict(value)
    data.setdefault("id", str(uuid.uuid4()))
    data.setdefault("timestamp", datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--json", required=True)
    args = parser.parse_args()

    try:
        import lancedb  # type: ignore
    except Exception as exc:
        print(f"lancedb not installed; skipping (python={sys.executable})", file=sys.stderr)
        print(f"lancedb import error: {exc}", file=sys.stderr)
        return 0

    if not os.path.exists(args.json):
        print("json not found", file=sys.stderr)
        return 0

    os.makedirs(args.db, exist_ok=True)
    payload = load_json(args.json)
    records = ensure_record(payload)
    if isinstance(records, dict):
        records = [records]

    db = lancedb.connect(args.db)
    table_name = "codex_memory"
    try:
        table = db.open_table(table_name)
        table.add(records)
    except Exception:
        db.create_table(table_name, data=records)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
