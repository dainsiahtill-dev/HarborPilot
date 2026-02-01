import argparse
import json
import os
import re
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


def normalize_db_dir(path: str) -> str:
    raw = (path or "").strip().strip('"')
    if re.match(r"^[A-Za-z]:$", raw):
        raw = raw + "\\"
    raw = os.path.abspath(raw)
    if re.match(r"^[A-Za-z]:$", raw):
        raw = raw + "\\"
    if re.match(r"^[A-Za-z]:\\?$", raw):
        raw = os.path.join(raw, ".harborpilot", "lancedb")
    return raw


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

    db_dir = normalize_db_dir(args.db)
    try:
        os.makedirs(db_dir, exist_ok=True)
    except Exception as exc:
        print(f"failed to create lancedb dir: {db_dir}: {exc}", file=sys.stderr)
        return 0

    payload = load_json(args.json)
    records = ensure_record(payload)
    if isinstance(records, dict):
        records = [records]

    try:
        db = lancedb.connect(db_dir)
    except Exception as exc:
        print(f"lancedb connect failed for {db_dir}: {exc}", file=sys.stderr)
        return 0

    table_name = "codex_memory"
    try:
        table = db.open_table(table_name)
        table.add(records)
    except Exception:
        try:
            db.create_table(table_name, data=records)
        except Exception as exc:
            print(f"lancedb create_table failed for {db_dir}: {exc}", file=sys.stderr)
            return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
