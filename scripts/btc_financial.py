"""Replay the frozen BTC study, verify receipts, render results or log a manual observation."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from agenthon_financial.run import read_verified
from agenthon_financial.study import DATA


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    subs=parser.add_subparsers(dest="action",required=True)
    run=subs.add_parser("run",help="recompute the frozen study and render tables and charts")
    run.add_argument("--out",type=Path,required=True)
    for name in ("verify","dashboard"):
        sub=subs.add_parser(name)
        sub.add_argument("folder",type=Path)
        if name=="dashboard":
            sub.add_argument("--out",type=Path,required=True)
            sub.add_argument("--edge",type=Path,help="optional existing offline Edge Lab dashboard")
    obs=subs.add_parser("observe",help="record a single dated intent from a qualified local snapshot")
    obs.add_argument("--snapshot",type=Path,default=DATA/"sessions.csv")
    obs.add_argument("--source",type=Path,default=DATA/"source.json")
    obs.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    if args.action=="run":
        from agenthon_financial.reproduce import reproduce
        reproduce(args.out)
    elif args.action=="verify":
        print(json.dumps(read_verified(args.folder)[-1],indent=2))
    elif args.action=="dashboard":
        from agenthon_financial.view import panel
        from agenthon_btc.view import standalone
        html=panel(read_verified(args.folder))
        if args.edge:
            from edge_lab_spectral import write_panel
            write_panel(args.edge,args.out,html)
        else:
            with args.out.open("x") as handle:
                handle.write(standalone(html).replace("BTC/USD momentum pilot ·","BTC/USD momentum study ·"))
    else:
        from agenthon_financial.observe import record
        print(json.dumps(record(args.snapshot,args.source,args.out),indent=2))


if __name__=="__main__":
    try:
        main()
    except (OSError,ValueError,KeyError) as exc:
        sys.exit(f"BTC research: {exc}")
