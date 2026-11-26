"""Generate or check the public reading example from the frozen, verified BTC record."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from agenthon_btc.view import standalone
from agenthon_financial.reader import paragraphs, projection, spectral_finding
from agenthon_financial.reproduce import SAVED, admitted_reference
from agenthon_financial.run import read_verified
from agenthon_financial.view import panel


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
            ROOT/"site-export/btc-study.json":json.dumps(projection(verified),indent=2,sort_keys=True,allow_nan=False)+"\n"}


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
