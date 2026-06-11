import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import httpx


def has_mention(record: dict[str, Any]) -> bool:
    value = record.get("mention")
    return isinstance(value, str) and bool(value.strip())


async def post_record(client: httpx.AsyncClient, record: dict[str, Any], token: str) -> tuple[int, str]:
    response = await client.post("/ingest/email", json=record, headers={"X-Webhook-Token": token})
    return response.status_code, response.text


async def main() -> None:
    parser = argparse.ArgumentParser(description="Replay Data/Email.json through the ingest endpoint")
    parser.add_argument("--file", default="../Data/Email.json")
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--token", required=True)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    records = json.loads(Path(args.file).read_text(encoding="utf-8"))
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
