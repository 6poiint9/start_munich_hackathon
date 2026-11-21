"""Reads selected documents of a pack with the real LLM and prints facts.

Usage: python scripts/read_selected.py <pack> <source folder> <substring>...
A development aid for prompt work. It uses a temporary database.
"""

import json
import pathlib
import sys
import tempfile

from lineguard import config
from lineguard import db
from lineguard import llm
from lineguard import pack as pack_module
from lineguard import pipeline
from lineguard import runtime
from lineguard.connectors import blob
from lineguard.connectors import source


def main() -> int:
    config.load_dotenv()
    pack = pack_module.load(sys.argv[1])
    folder = pathlib.Path(sys.argv[2])
    wanted = sys.argv[3:]
    tmp = pathlib.Path(tempfile.mkdtemp())
    conn = db.connect(pack.workspace, tmp / "t.sqlite")
    rt = runtime.Runtime(conn=conn, pack=pack,
                         blob=blob.LocalBlobStore(tmp / "blobs"),
                         llm=llm.from_env())
    pipeline.import_wave_one(rt, source.LocalFolderSource(folder))
    while True:
        event = db.claim_next(conn, rt.ws, "dev", ["file.added", "notes.read"])
        if event is None:
            break
        file = db.one(conn, rt.ws, "SELECT * FROM files WHERE workspace_id = ? AND id = ?",
                      (event["payload"]["file_id"],))
        if any(text in file["path"] for text in wanted):
            pipeline.handle_one(rt, "reader", event)
            status = db.one(conn, rt.ws, "SELECT * FROM files WHERE workspace_id = ? AND id = ?", (file["id"],))
            print(f"\n=== {event['type']} {file['path']} -> {status['parse_status']} "
                  f"{status['doc_class']} {status['parse_error'] or ''}")
            for fact in db.rows(conn, rt.ws,
                                "SELECT * FROM facts WHERE workspace_id = ? AND source_file_id = ? "
                                "AND extracted_by IN ('llm', 'vision', 'llm_note') ORDER BY id",
                                (file["id"],)):
                shown = {k: v for k, v in fact.items() if v not in (None, "", 0) and k in (
                    "fact_type", "component_id", "supplier_id", "po_number", "batch", "rev",
                    "ref", "qty", "value_num", "value_text", "eta", "valid_until",
                    "source_rank", "confidence", "suspicious", "needs_review", "data")}
                print("  ", json.dumps(shown, ensure_ascii=False)[:420])
        else:
            db.finish(conn, rt.ws, event, "skipped")
    calls = db.one(conn, rt.ws, "SELECT COUNT(*) AS n, SUM(tokens_in) AS tin, SUM(tokens_out) AS tout, "
                   "SUM(ms) AS ms FROM llm_calls WHERE workspace_id = ?")
    print("\nLLM calls:", calls)
    return 0


if __name__ == "__main__":
    sys.exit(main())
