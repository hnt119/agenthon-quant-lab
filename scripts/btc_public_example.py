"""Generate or check the public reading example from the frozen, verified BTC record."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from agenthon_btc.view import standalone
from agenthon_financial.reader import paragraphs, projection, spectral_finding
from agenthon_financial.reproduce import RECEIPT, SAVED, admitted_reference
from agenthon_financial.run import read_verified
from agenthon_financial.view import panel


# Preserve the v1 base fields for existing readers. The scenario layer is public
# presentation only and never participates in calculation or study identity.
COST_SCENARIOS = ("gross", "base", "double_cost")
RELEASE_SOURCE = "https://github.com/hnt119/agenthon-quant-lab/blob/8fd6f46875f58a6c493078f560b2b1ad7cf3d8f8"


def scenario_projection(verified):
    record, spec, _, _, ledger, results, _ = verified
    public = projection(verified)
    month_ends = [row["date"] for row in public["month_ends"]]
    paths = {scenario: {day: {"date": day} for day in month_ends} for scenario in COST_SCENARIOS}
    for entry in ledger:
        scenario, day = entry["scenario"], entry["date"]
        if scenario in paths and day in paths[scenario]:
            paths[scenario][day][entry["arm"]] = {key: entry[key] for key in ("equity", "drawdown")}

    # Select the same public metrics used by the original base display. Fees,
    # slippage and equity already include the scenario's own simulated fills.
    metrics = public["portfolios"]["momentum20"].keys()
    scenarios = {}
    for scenario in (*COST_SCENARIOS, "later_fill"):
        summary = dict(zip(spec["scenario_units"], spec["scenarios"][scenario], strict=True))
        summary["portfolios"] = {
            arm: {key: results["portfolios"][scenario][arm]["pooled"][key] for key in metrics}
            for arm in spec["arms"]
        }
        summary["sharpe_delta"] = results["sharpe_delta"][scenario]["pooled"]
        if scenario in paths:
            if any(row.keys() != {"date", *spec["arms"]} for row in paths[scenario].values()):
                raise ValueError(f"Incomplete verified month-end marks for {scenario}")
            summary["month_ends"] = list(paths[scenario].values())
        scenarios[scenario] = summary

    source = json.loads((ROOT / "experiments/btc-financial-v1/source.json").read_bytes())
    evidence_dir = RELEASE_SOURCE + "/reports/btc-financial-v1"
    public.update(
        schema_version=2,
        scenarios={name: scenarios[name] for name in COST_SCENARIOS},
        later_fill=scenarios["later_fill"],
        inference_scope="Five retrospective annual folds. The 95% intervals apply to the base Sharpe difference "
                        "and predictive difference at the five-minute execution proxy.",
        original_receipt_sha256=RECEIPT,
        source_manifest_sha256=record["source_manifest_sha256"],
        verification_sha256=record["output_artifacts_sha256"]["verification.json"],
        evidence={
            "report_url": evidence_dir + "/README.md",
            "metrics_url": evidence_dir + "/metrics.json",
            "verification_url": evidence_dir + "/verification.json",
            "protocol_url": RELEASE_SOURCE + "/experiments/btc-financial-v1/protocol.json",
            "source_url": RELEASE_SOURCE + "/experiments/btc-financial-v1/source.json",
            "publisher_terms_url": source["publisher_terms"],
            "reproduction_command": "quant-lab btc-study",
        },
    )
    return public


def outputs():
    admitted_reference()
    verified = read_verified(SAVED)
    spec,result=verified[1],verified[-2]
    folder=ROOT/"examples/btc-study"
    prefix="../../reports/btc-financial-v1/"
    intro=paragraphs(spec,result)
    report = ["# Did buying BTC after a rise earn enough to cover trading costs?",intro[0],intro[1],
              f"[View equity curves]({prefix}equity.svg) · [Read the financial report]({prefix}README.md) · "
              "[Download the offline dashboard](dashboard.html) · [Reproduce this study](../../docs/plugin-guide.md)",
              intro[2],intro[3],
              f"![After-cost equity from the five calendar years. The passive BTC/cash line ends above the momentum line.]({prefix}equity.svg)",
              spectral_finding(spec, result),
              f"[Frozen specification](../../experiments/btc-financial-v1/protocol.json) · [Numerical checks]({prefix}verification.json) · "
              "[Earlier six-month pilot](../../research/btc-pilot-audit/README.md)",
              "Adapted from Zielak (mczielinski), *Bitcoin Historical Data*, Kaggle v706, normalized by ff137. "
              "The UTC portfolio tables and plots use [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)."]
    return {folder/"README.md":"\n\n".join(report)+"\n",
            folder/"dashboard.html":standalone(panel(verified)).replace("BTC/USD momentum pilot ·","BTC/USD momentum study ·"),
            ROOT/"site-export/btc-study.json":json.dumps(scenario_projection(verified),indent=2,sort_keys=True,allow_nan=False)+"\n"}


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check",action="store_true")
    args=parser.parse_args()
    for path,value in outputs().items():
        if args.check:
            if path.read_text()!=value:
                sys.exit(f"Saved presentation differs: {path.relative_to(ROOT)}")
        else:
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(value)
        print(path.relative_to(ROOT))
