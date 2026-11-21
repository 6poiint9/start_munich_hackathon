"""Command line entry point.

python -m soony_tower sync      pull new files from the portal
python -m soony_tower report    print forecast and risks
python -m soony_tower read      let Radeon read documents not read yet
python -m soony_tower watch     sync every few minutes, read new documents, print changes
python -m soony_tower serve     start the cockpit and HTTP API on port 8000
python -m soony_tower drafts    let Radeon write supplier mails for open risks (not sent)
python -m soony_tower inbox     fetch and read supplier replies
python -m soony_tower models    list models available from Radeon
python -m soony_tower ping      test the Radeon endpoint
"""

import argparse
import sys
import time

import pandas as pd

from soony_tower import documents
from soony_tower import engine
from soony_tower import mail
from soony_tower import portal
from soony_tower import settings


def _print_report(status: dict) -> None:
    print(f"As of {status['at']}  |  deadline {status['deadline']}")
    for p in status["products"]:
        print(f"  {p['product_id']}: to pack {p['remaining']:,.0f} | "
              f"plan {p['forecast_plan']:,.0f} | realistic "
              f"{p['forecast_realistic']:,.0f} | limit: {p['limiting_factor']}")
    changes = status["risk_changes"]
    print(f"Risks: {len(status['risks'])} (new {len(changes['new'])}, "
          f"worse {len(changes['worse'])}, resolved {len(changes['resolved'])})")
    for r in status["risks"]:
        mark = "NEW " if r["id"] in changes["new"] else "    "
        print(f"  {mark}[{r['severity']}] {r['title']}")
        print(f"        -> {r['action']} ({r['owner']})")


def main() -> int:
    parser = argparse.ArgumentParser(prog="soony_tower")
    parser.add_argument(
        "command",
        choices=["sync", "report", "read", "watch", "serve", "drafts",
                 "inbox", "models", "ping"],
    )
    parser.add_argument("--at", help="replay a moment, e.g. 2026-11-21T17:00")
    parser.add_argument("--limit", type=int, help="read at most N documents")
    parser.add_argument("--match", help="read only paths that contain this text")
    parser.add_argument("--every", type=int, default=300,
                        help="seconds between syncs for watch")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    at = pd.Timestamp(args.at).tz_localize(settings.TIMEZONE) if args.at else None

    if args.command == "sync":
        for change in portal.sync():
            print(f"{change.kind:9} {change.path}")
    elif args.command == "models":
        client = documents.client_or_none()
        if client is None:
            raise RuntimeError("No Radeon key. Set RADEON_API_KEY in .env.")
        for model_name in documents.list_models(client):
            print(model_name)
    elif args.command == "ping":
        client = documents.client_or_none()
        if client is None:
            raise RuntimeError("No Radeon key. Set RADEON_API_KEY in .env.")
        models = documents.pick_models(client)
        response = client.chat.completions.create(
            model=models[0],
            messages=[{"role": "user", "content": "Reply with exactly: pong"}],
        )
        print(f"{models[0]}: {response.choices[0].message.content}")
    elif args.command == "read":
        documents.read_pending(limit=args.limit, match=args.match)
    elif args.command == "report":
        _print_report(engine.run(do_sync=False, at=at))
    elif args.command == "watch":
        while True:
            changed = [c.path for c in portal.sync()]
            if changed and documents.client_or_none() is not None:
                for path in changed:
                    documents.read_pending(match=path)
            status = engine.run(do_sync=False, at=at)
            status["file_changes"] = [{"kind": "changed", "path": p} for p in changed]
            for change in status["file_changes"]:
                print(f"FILE {change['kind']}: {change['path']}")
            _print_report(status)
            time.sleep(args.every)
    elif args.command == "drafts":
        status = engine.run(do_sync=False, at=at, remember=False)
        for item in mail.draft(status):
            print(f"--- to {item['to']} ({item['risk_id']})")
            print(f"Subject: {item['subject']}\n\n{item['body']}\n")
    elif args.command == "inbox":
        for reply in mail.poll():
            print(f"{reply['from']}: {reply['analysis']['summary']}")
    elif args.command == "serve":
        import uvicorn  # pylint: disable=import-outside-toplevel
        uvicorn.run("soony_tower.api:app", host="127.0.0.1", port=8000)
    return 0


if __name__ == "__main__":
    sys.exit(main())
