"""One run of the control tower: sync, rebuild, forecast, compare risks.

The risk list of the last run is kept in data/risk_state.json. A new run
reports which risks are new, which got worse and which are resolved. Only
new and worse risks need an action. This is how the agents avoid asking a
supplier twice about the same problem.
"""

import dataclasses
import json
import math

import pandas as pd

from soony_tower import forecast
from soony_tower import model
from soony_tower import portal
from soony_tower import risks

RISK_STATE_PATH = portal.DATA_DIR / "risk_state.json"


def to_jsonable(value):
    """Converts dataclasses, timestamps and NaN into plain JSON values."""
    if dataclasses.is_dataclass(value):
        return {k: to_jsonable(v) for k, v in dataclasses.asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if hasattr(value, "item"):  # numpy scalars
        return value.item()
    return value


def _compare(previous: dict[str, dict], current: list[risks.Risk]) -> dict:
    current_ids = {r.id for r in current}
    new = [r.id for r in current if r.id not in previous]
    worse = [r.id for r in current if r.id in previous and (
        r.impact_copies > previous[r.id]["impact_copies"] or
        risks.SEVERITY_ORDER[r.severity] <
        risks.SEVERITY_ORDER[previous[r.id]["severity"]])]
    resolved = [i for i in previous if i not in current_ids]
    return {"new": new, "worse": worse, "resolved": resolved}


def run(do_sync: bool = True, at: pd.Timestamp | None = None,
        remember: bool = True) -> dict:
    """Runs the full cycle and returns a JSON-ready status."""
    changes = portal.sync() if do_sync else []
    data = model.build()
    result = forecast.run(data, at)
    found = risks.evaluate(data, result)

    previous = {}
    if RISK_STATE_PATH.exists():
        previous = json.loads(RISK_STATE_PATH.read_text(encoding="utf-8"))
    delta = _compare(previous, found)
    if remember:
        RISK_STATE_PATH.write_text(
            json.dumps({r.id: to_jsonable(r) for r in found}, indent=1),
            encoding="utf-8")

    return to_jsonable({
        "at": result.at,
        "deadline": result.deadline,
        "stock_snapshot_as_of": result.snapshot_as_of,
        "products": result.products,
        "components": result.components,
        "inbound": result.inbound,
        "risks": found,
        "risk_changes": delta,
        "file_changes": changes,
        "notes": [{"text": t, "source": s} for t, s in data.notes],
        "data_problems": data.problems,
    })
