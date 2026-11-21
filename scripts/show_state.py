"""Prints the state of the configured workspace. A development aid."""

import contextlib
import sys

from lineguard import config
from lineguard import runtime
from lineguard import views
from lineguard.coverage import core


def main() -> int:
    config.load_dotenv()
    rt = runtime.open_runtime()
    with contextlib.closing(rt.conn):
        conn = rt.conn
        for row in conn.execute("SELECT parser, parse_status, COUNT(*) c FROM files GROUP BY 1, 2"):
            print(dict(row))
        for row in conn.execute("SELECT path, parse_error FROM files WHERE parse_status IN ('failed', 'manual') LIMIT 10"):
            print("NOT READ", dict(row))
        for row in conn.execute("SELECT status, COUNT(*) c FROM events GROUP BY 1"):
            print(dict(row))
        for row in conn.execute("SELECT type, error FROM events WHERE error IS NOT NULL LIMIT 5"):
            print("ERROR", dict(row))
        print(dict(conn.execute("SELECT COUNT(*) n, SUM(cache_hit) hits, SUM(tokens_in) tin, SUM(tokens_out) tout, SUM(ms)/1000 secs FROM llm_calls").fetchone()))
        for row in conn.execute("SELECT fact_type, COUNT(*) c, SUM(needs_review) review, SUM(suspicious) sus FROM facts WHERE extracted_by != 'parser' GROUP BY 1 ORDER BY 2 DESC"):
            print(f"  {row['fact_type']:26} {row['c']:5} review {row['review']} suspicious {row['sus']}")
        state = core.compute(rt)
        for p in state.products.values():
            print("product", p.product_id, "to pack", p.still_to_pack, {k: round(v, 4) for k, v in p.coverage.items()}, "limit", p.limiting_component)
        for c in state.components.values():
            print(f"{c.component_id:12} book {c.erp_stock:9,.0f} usable {c.usable:9,.0f} need {c.need:8,.0f} "
                  f"gap {c.gap_qty:8,.0f} stocked {c.stocked} breaks {str(c.breaks_at)[:16]} "
                  f"blocks {[(b.reason, b.qty) for b in c.blocks]} "
                  f"secured_in {c.inbound_secured:,.0f}")
        for row in conn.execute("SELECT gr_number, component_id, booked_qty, proposed_qty, cause, agreeing_sources, status FROM booking_findings WHERE status IN ('proposed','needs_count')"):
            print("FINDING", dict(row))
        body = views.state(rt)
        for case in body["cases_now"] + body["cases_later"]:
            print("CASE", case["rank"], case["kind"], case["impact"], case["state"], case["title"])
        print("people", [(p["name"], p["roles"]) for p in body["people"]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
