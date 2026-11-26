"""Apply the frozen Sunday-close schedule with the original spot ledger."""
from datetime import date, timedelta
from math import isfinite

from .study import books, require


def weekly_entries(rows, features, parent_spec, scenario):
    """Return daily marks and the dated weekly decisions for a single cost scenario."""
    require(scenario in ("gross", "base", "double_cost"), "Undeclared weekly cost scenario")
    costs = parent_spec["scenarios"][scenario]
    require(costs[0] == 5, "Weekly schedule requires the 00:05 UTC execution proxy")
    first = date(parent_spec["evaluation_years"][0], 1, 1)
    seed_date = first - timedelta(days=1)
    end = date(parent_spec["evaluation_years"][-1], 12, 31)

    # The prior session seeds next-open execution. No pre-evaluation position carries in.
    market = []
    observations = []
    previous = None
    for row, feature in zip(rows, features, strict=True):
        require(row["date"] == feature["date"], "Weekly feature/session dates differ")
        day = date.fromisoformat(row["date"])
        if seed_date <= day <= end:
            require(day == (seed_date if previous is None else previous + timedelta(days=1)),
                    "Weekly evaluation requires contiguous UTC sessions including the preceding close")
            market.append(row)
            observations.append(feature)
            previous = day
    require(len(market) >= 2, "Weekly evaluation has no eligible sessions")

    # The spot engine expects a target at every close. Forward-fill the last Sunday
    # decision for accounting, then distinguish actual decisions from holds in the journal.
    target = 0
    targets = []
    scheduled = set()
    for i, feature in enumerate(observations):
        day = date.fromisoformat(feature["date"])
        if day.weekday() == 6 and i + 1 < len(market):
            momentum = feature["momentum20"]
            require(isinstance(momentum, (float, int)) and not isinstance(momentum, bool)
                    and isfinite(momentum), "A scheduled Sunday requires a completed momentum observation")
            target = int(momentum > 0)
            scheduled.add(market[i + 1]["date"])
        targets.append({"targets": {"weekly20": target}})

    spec = {**parent_spec, "arms": ["weekly20"], "scenarios": {scenario: costs}}
    ledger = list(books(market, targets, {}, spec))
    for entry in ledger:
        if entry["date"] not in scheduled:
            require(entry["trade_quantity"] == 0, "Unscheduled weekly trade")
            for key in ("target_for_open", "signal_session", "feature_cutoff", "decision_time"):
                entry[key] = None
    return ledger
