import argparse
import asyncio
import json
import os
import random
from pathlib import Path
from typing import Any

import httpx


def has_mention(record: dict[str, Any]) -> bool:
    value = record.get("mention")
    return isinstance(value, str) and bool(value.strip())


async def post_record(client: httpx.AsyncClient, record: dict[str, Any], token: str) -> tuple[int, str]:
    response = await client.post("/ingest/email", json=record, headers={"X-Webhook-Token": token})
    return response.status_code, response.text


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


async def main() -> None:
    script_dir = Path(__file__).resolve().parent
    project_dir = script_dir.parent
    workspace_dir = project_dir.parent
    load_env_file(project_dir / ".env.deploy")
    load_env_file(project_dir / ".env")

    parser = argparse.ArgumentParser(description="Replay random records from Data/Email.json through the ingest endpoint")
    parser.add_argument("--file", default=str(workspace_dir / "Data" / "Email.json"))
    parser.add_argument(
        "--base-url",
        default=os.getenv(
            "ENDPOINT",
            "https://endpoint-3e5c87ac-ccfd-431c-b020-853e73862c5a.agentbase-runtime.aiplatform.vngcloud.vn",
        ),
    )
    parser.add_argument("--token", default=os.getenv("WEBHOOK_TOKEN"))
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--ordered", action="store_true", help="Send records in file order instead of random order")
    parser.add_argument("--seed", type=int, default=None, help="Optional random seed for repeatable replays")
    args = parser.parse_args()

    if not args.token:
        raise SystemExit("Missing webhook token. Set WEBHOOK_TOKEN in .env/.env.deploy or pass --token.")

    records = json.loads(Path(args.file).read_text(encoding="utf-8"))
    if not args.ordered:
        rng = random.Random(args.seed)
        records = records.copy()
        rng.shuffle(records)
    sent = skipped = failed = 0
    async with httpx.AsyncClient(base_url=args.base_url, timeout=30.0) as client:
        for record in records:
            if args.limit and sent >= args.limit:
                break
            if not has_mention(record):
                skipped += 1
                continue
            status_code, text = await post_record(client, record, args.token)
            if status_code >= 400:
                failed += 1
                print(f"FAIL {record.get('_id')} {status_code}: {text[:300]}")
            else:
                sent += 1
                if sent % 100 == 0:
                    print(f"sent={sent} skipped={skipped} failed={failed}")
    print(f"done sent={sent} skipped={skipped} failed={failed}")


if __name__ == "__main__":
    asyncio.run(main())
