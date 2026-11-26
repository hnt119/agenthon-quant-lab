"""Reprice the frozen BTC portfolios at one point on the declared cost path."""
from __future__ import annotations

import gzip
import hashlib
import json
from itertools import groupby
from operator import itemgetter

from .analysis import group, summarize
from .cost_verify import verify_cost_books
from .reproduce import RECEIPT, SAVED, admitted_reference, compare
from .run import inputs, read_verified
from .study import books, require


ANCHORS = {0.0: "gross", 1.0: "base", 2.0: "double_cost"}
decision = itemgetter("arm", "date", "signal_session", "feature_cutoff", "decision_time",
                      "target_for_open", "execution_proxy_time", "execution_time")


def _json_line(value):
    # Same line representation as the released financial ledger's write_ledger.
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def _summaries(entries, initial_cash):
    portfolios = {}
    for (_, arm), path in group(entries).items():
        periods = {"pooled": summarize(path, initial_cash)}
        previous_close = initial_cash
        for year, days in groupby(path, key=lambda row: row["date"][:4]):
            year_path = list(days)
            periods[year] = summarize(year_path, previous_close)
            previous_close = year_path[-1]["equity"]
        portfolios[arm] = periods
    return portfolios


def _differences(portfolios):
    momentum = portfolios["momentum20"]["pooled"]
    result = {}
    for name, arm in (("passive", "passive_mix"), ("hold", "buy_and_hold")):
        other = portfolios[arm]["pooled"]
        sharpe_pair = momentum["sharpe"], other["sharpe"]
        result[name + "_sharpe"] = None if None in sharpe_pair else sharpe_pair[0] - sharpe_pair[1]
        result[name + "_wealth"] = momentum["ending_equity"] - other["ending_equity"]
    return result


class CostBooks:
    """Admit the original study once; keep only summaries across cost evaluations."""

    def __init__(self):
        reference = admitted_reference()
        record, self.spec, self.features, fit, original, metrics, receipt = read_verified(SAVED)
        require(record == reference, "Saved run differs from the admitted receipt")
        _, self.rows = inputs()
        self.weights = {int(year): value for year, value in fit["annual_weights"].items()}
        self._original_portfolios = metrics["portfolios"]
        self._anchor_rows = {scenario: [] for scenario in ANCHORS.values()}
        hashes = {scenario: hashlib.sha256() for scenario in ANCHORS.values()}
        # Compare generated ledger bytes with actual decompressed lines, preserving their order.
        with gzip.open(SAVED / "ledger.jsonl.gz", "rb") as stream:
            for row, line in zip(original, stream, strict=True):
                scenario = row["scenario"]
                if scenario in hashes:
                    hashes[scenario].update(line)
                    self._anchor_rows[scenario].append(row)
        self._ledger_hashes = {k: v.hexdigest() for k, v in hashes.items()}
        self._base_decisions = [decision(row) for row in self._anchor_rows["base"]]
        self.verification = {
            "original_receipt_sha256": RECEIPT,
            "original_ledger_sha256": record["output_artifacts_sha256"]["ledger.jsonl.gz"],
            "original_metrics_sha256": record["output_artifacts_sha256"]["metrics.json"],
            "original_financial_checks": receipt,
            "settings_checked": 0,
            "decision_rows_matched": 0,
            "independent_totals": {"portfolio_sessions": 0, "period_summaries": 0, "fills": 0},
            "anchors": {},
        }

    def _anchor_check(self, scenario, entries, portfolios):
        rebuilt = hashlib.sha256()
        for row in entries:
            rebuilt.update(_json_line(row))
        actual_hash = rebuilt.hexdigest()
        original_hash = self._ledger_hashes[scenario]
        same_ledger = actual_hash == original_hash
        if not same_ledger:
            require(compare(self._anchor_rows[scenario], entries), f"Anchor ledger differs: {scenario}")
        original_summary = self._original_portfolios[scenario]
        same_summary = _json_line(original_summary) == _json_line(portfolios)
        if not same_summary:
            require(compare(original_summary, portfolios), f"Anchor period metrics differ: {scenario}")
        return {
            "ledger_jsonl": "byte-identical" if same_ledger else "numerically equivalent",
            "expected_ledger_jsonl_sha256": original_hash,
            "actual_ledger_jsonl_sha256": actual_hash,
            "canonical_summary_json": "byte-identical" if same_summary else "numerically equivalent",
            "portfolio_sessions": len(entries),
            "period_summaries": sum(len(p) for p in portfolios.values()),
        }

    def evaluate(self, multiplier: float) -> dict:
        """Re-simulate each account continuously from its original starting capital."""
        if type(multiplier) not in (float, int) or not 0 <= multiplier <= 2:
            raise ValueError("Expected a finite cost multiplier in the frozen range [0, 2]")
        multiplier = float(multiplier)
        delay, base_fee, base_slip = self.spec["scenarios"]["base"]
        fee, slip = base_fee * multiplier, base_slip * multiplier
        scenario = ANCHORS.get(multiplier, "cost_path")
        experiment = {**self.spec, "scenarios": {scenario: (delay, fee, slip)}}
        entries = list(books(self.rows, self.features, self.weights, experiment))
        require([decision(row) for row in entries] == self._base_decisions,
                f"Decisions or timing differ from the original base ledger at multiplier {multiplier}")
        portfolios = _summaries(entries, self.spec["initial_cash"])
        checks = verify_cost_books(self.rows, self.features, self.weights, self.spec, entries,
                                   portfolios, multiplier)
        require(checks["status"] == "passed", "Independent cost-path verification failed")
        if multiplier in ANCHORS:
            self.verification["anchors"][scenario] = self._anchor_check(scenario, entries, portfolios)
        self.verification["settings_checked"] += 1
        self.verification["decision_rows_matched"] += len(entries)
        for field in self.verification["independent_totals"]:
            self.verification["independent_totals"][field] += checks[field]
        return {"lambda": multiplier, "fee_bps": fee, "slippage_bps": slip,
                "portfolios": portfolios, "differences": _differences(portfolios)}
