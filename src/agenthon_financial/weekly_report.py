"""Publish the frozen weekly-cadence comparisons from the verified portfolio records."""
from xml.etree import ElementTree as ET

from agenthon_quant.records import write_json

from .cost_report import LICENSE_URL, ORIGINAL_URL, SOURCE_URL, TERMS_URL, fmt, tick_range


ARMS = {
    "weekly20": "Weekly momentum", "momentum20": "Daily momentum",
    "passive_mix": "Passive BTC/cash", "buy_and_hold": "Buy and hold BTC", "cash": "Cash",
}
COMPARISONS = {"vs_passive": "Weekly minus passive BTC/cash", "vs_daily": "Weekly minus daily momentum"}
COSTS = {"gross": "Zero", "base": "Base", "double_cost": "Double"}
DISPLAY_METRICS = ("total_return", "sharpe", "max_drawdown", "mean_close_exposure",
                   "turnover", "trade_events", "transaction_cost", "fees", "slippage_cost", "ending_equity")
CREDIT = ("Zielak (mczielinski), Bitcoin Historical Data, Kaggle v706, normalized by ff137. "
          "Adapted to UTC daily sessions, simulated spot portfolios and a weekly decision schedule.")
COMMAND = "quant-lab btc-weekly-cadence --out btc-weekly-review"


def public_projection(spec, metrics, study, provenance):
    portfolios = {}
    for scenario in COSTS:
        portfolios[scenario] = {}
        for arm in ARMS:
            portfolios[scenario][arm] = {
                period: {k: values[k] for k in DISPLAY_METRICS}
                for period, values in metrics[scenario][arm].items()
            }
    return {
        "schema_version": 1, "study_id": spec["id"], "question": spec["question"],
        "evidence": spec["evidence"], "evaluation": spec["evaluation"], "schedule": spec["weekly"],
        "scenarios": spec["scenarios"], "scenario_units": spec["scenario_units"],
        "initial_usd": spec["initial_cash"], "portfolios": portfolios,
        "comparisons": {key: study[key] for key in ("contrasts", "interval95", "position_days",
                        "scheduled_opportunities", "first_opportunity", "first_fill")},
        "uncertainty": spec["uncertainty"],
        "provenance": {key: provenance[key] for key in ("protocol_commit", "protocol_sha256",
                       "source_receipt_sha256", "snapshot_sha256")},
        "reproduction_command": COMMAND, "distribution": "Development study",
        "attribution": CREDIT, "license": "CC BY-SA 4.0", "license_url": LICENSE_URL,
        "dataset_url": SOURCE_URL, "publisher_terms_url": TERMS_URL,
    }


def write_figure(path, study, years):
    """Six point estimates on one scale. Horizontal intervals apply only to base costs."""
    contrasts, bands = study["contrasts"], study["interval95"]
    ticks = tick_range([v for key in COMPARISONS for v in
                        [*(contrasts[s]["pooled"][key] for s in COSTS), *(bands[key] or [])] if v is not None])
    svg = ET.Element("svg", {"xmlns": "http://www.w3.org/2000/svg", "viewBox": "0 0 900 454",
                             "role": "img", "aria-labelledby": "title desc"})
    ET.SubElement(svg, "title", id="title").text = "How did the weekly BTC decision schedule compare?"
    ET.SubElement(svg, "desc", id="desc").text = (
        "Six pooled Sharpe differences for weekly momentum against passive BTC/cash and daily momentum, "
        "at zero, base and double costs. Dots to the right of zero favor weekly momentum. "
        "The horizontal capped lines show the two base-cost paired 95% intervals. The report tabulates all values.")
    ET.SubElement(svg, "rect", width="900", height="454", fill="#fff")
    ET.SubElement(svg, "style").text = (
        "text{font-family:Arial,Helvetica,sans-serif;fill:#23322c;font-size:14px}"
        ".heading{font-weight:bold;font-size:23px}.panel{font-weight:bold;font-size:16px}"
        ".small{font-size:12px}.grid{stroke:#d6dfdb}.zero{stroke:#43594c;stroke-dasharray:4 3}"
        ".interval{stroke:#885027;stroke-width:2.5}.estimate{fill:#1c6974;stroke:white;stroke-width:1.5}"
    )

    def label(x, y, text, css="", anchor="start"):
        ET.SubElement(svg, "text", {"x": str(x), "y": str(y), "class": css, "text-anchor": anchor}).text = text

    def line(x1, y1, x2, y2, css):
        ET.SubElement(svg, "line", {"x1": f"{x1:.3f}", "y1": str(y1), "x2": f"{x2:.3f}",
                                    "y2": str(y2), "class": css})

    left, right = 126, 764
    def coordinate(value):
        return left + (value-ticks[0]) * (right-left) / (ticks[-1]-ticks[0])

    label(24, 33, "How did the weekly BTC decision schedule compare?", "heading")
    label(24, 58, f"Bitstamp BTC/USD spot · {years[0]}–{years[-1]} · Positive Sharpe differences favor weekly momentum.")
    label(right+24, 87, "Estimate", "small")
    for n, (key, title) in enumerate(COMPARISONS.items()):
        start = 117 + n*137
        label(24, start-24, title, "panel")
        for tick in ticks:
            x = coordinate(tick)
            line(x, start-10, x, start+63, "zero" if tick == 0 else "grid")
            if n == len(COMPARISONS)-1:
                label(f"{x:.3f}", start+81, format(tick, ".2f"), "small", "middle")
        for i, scenario in enumerate(COSTS):
            y = start+i*27
            value = contrasts[scenario]["pooled"][key]
            label(32, y+4, COSTS[scenario] + " costs")
            if scenario == "base" and bands[key] is not None:
                a, b = map(coordinate, bands[key])
                line(a, y, b, y, "interval")
                for edge in (a, b):
                    line(edge, y-5, edge, y+5, "interval")
            if value is not None:
                dot = ET.SubElement(svg, "circle", {"cx": f"{coordinate(value):.3f}", "cy": str(y),
                                                    "r": "5", "class": "estimate"})
                ET.SubElement(dot, "title").text = f"{title}, {COSTS[scenario].lower()} costs: {value:+.3f}"
            label(right+24, y+4, fmt(value, "+.3f"))

    label(24, 366, "Dots show pooled Sharpe differences. Capped lines show the paired 95% intervals at base costs.")
    label(24, 390, "At base costs each fill incurs a 50 bp fee and 10 bp adverse slippage. The double-cost case doubles both.")
    label(24, 414, "Both schedules use the same 20-session signal. This comparison reuses previously examined history.", "small")
    label(24, 438, "Adapted from Zielak (mczielinski), Bitcoin Historical Data, v706, normalized by ff137 · CC BY-SA 4.0", "small")
    ET.ElementTree(svg).write(path, encoding="utf-8", xml_declaration=True)


def performance_table(rows):
    lines = ["| Period | Portfolio | Return | Sharpe | Max drawdown | Turnover | Fills | Costs (USD) | Avg BTC weight |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for label, arm, m in rows:
        values = [label, ARMS[arm], fmt(m["total_return"], "+.2%"), fmt(m["sharpe"], ".3f"),
                  fmt(m["max_drawdown"], ".2%"), f"{m['turnover']:.2f}×", str(m["trade_events"]),
                  fmt(m["transaction_cost"], ",.2f"), fmt(m["mean_close_exposure"], ".2%")]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def interval_finding(name, estimate, band):
    if estimate is None or band is None:
        return f"{name}: estimated difference {fmt(estimate, '+.3f')}. The interval is unavailable."
    lo, hi = band
    if lo <= 0 <= hi:
        judgment = "The interval includes zero and leaves the comparison inconclusive."
    else:
        direction = "higher" if lo > 0 else "lower"
        judgment = f"The interval supports a {direction} weekly Sharpe on these historical paths."
    return f"{name}: **{estimate:+.3f}** (paired 95% interval **{lo:+.3f} to {hi:+.3f}**). {judgment}"


def write_report(out, spec, metrics, study, provenance):
    public = public_projection(spec, metrics, study, provenance)
    write_json(out / "public.json", public)
    years = spec["evaluation_years"]
    write_figure(out / "weekly-cadence.svg", study, years)
    base = metrics["base"]
    weekly, daily = [base[a]["pooled"] for a in ("weekly20", "momentum20")]
    gross = metrics["gross"]
    positions = study["position_days"]
    differences = study["contrasts"]
    sensitivity = ["| Costs | Fee + slippage (bp per fill) | Weekly return | Daily return | Passive return | Δ Sharpe vs passive | Δ Sharpe vs daily |",
                   "|---|---:|---:|---:|---:|---:|---:|"]
    for scenario, title in COSTS.items():
        _, fee, slip = spec["scenarios"][scenario]
        row = [title, f"{fee} + {slip}"]
        row.extend(fmt(metrics[scenario][a]["pooled"]["total_return"], "+.2%")
                   for a in ("weekly20", "momentum20", "passive_mix"))
        row.extend(fmt(differences[scenario]["pooled"][key], "+.3f") for key in COMPARISONS)
        sensitivity.append("| " + " | ".join(row) + " |")
    first_fill = study["first_fill"] or "none in the evaluation period"
    body = [
        "# Did weekly decisions improve BTC momentum after costs?",
        f"Bitstamp BTC/USD spot, {spec['evaluation'][0]} through {spec['evaluation'][1]}. "
        "Both momentum accounts used the same change over 20 daily closes. One could change position every day. "
        "The other could act only once each Monday, using the completed Sunday close.",
        *[interval_finding(label, differences["base"]["pooled"][key], study["interval95"][key])
          for key, label in COMPARISONS.items()],
        "![Pooled weekly-minus-comparator Sharpe differences at zero, base and double costs, "
        "with paired intervals for base costs. Exact comparisons follow below.](weekly-cadence.svg)",
        "## Turnover, timing and exposure",
        f"The weekly account made **{weekly['trade_events']} fills** over {study['scheduled_opportunities']} "
        f"scheduled opportunities. Daily momentum made **{daily['trade_events']} fills**. "
        f"One-way turnover was {weekly['turnover']:.2f}× for weekly and {daily['turnover']:.2f}× for daily. "
        f"Across the five years, fees and adverse slippage totaled ${weekly['transaction_cost']:,.2f} for weekly "
        f"and ${daily['transaction_cost']:,.2f} for daily.",
        f"Weekly momentum held an average closing BTC weight of {weekly['mean_close_exposure']:.2%}, "
        f"compared with {daily['mean_close_exposure']:.2%} for daily. Only weekly held BTC on "
        f"{positions['weekly_only']} closes. Only daily held BTC on {positions['daily_only']} closes. "
        f"Both held BTC on {positions['both_long']} closes and both held cash on {positions['both_cash']}. "
        f"The first weekly opportunity was {study['first_opportunity']}. Its first fill was {first_fill}.",
        f"At zero friction the weekly account ended with ${gross['weekly20']['pooled']['ending_equity']:,.2f} "
        f"and the daily account with ${gross['momentum20']['pooled']['ending_equity']:,.2f}. "
        f"At base costs they ended with ${weekly['ending_equity']:,.2f} and ${daily['ending_equity']:,.2f}, respectively. "
        "Differences at zero friction reflect which price moves each schedule captured. Costs also changed the cash "
        "available for each subsequent purchase. A difference in accumulated charges alone cannot explain ending wealth.",
        "## Pooled comparisons across costs", "\n".join(sensitivity),
        "Each account began once with $10,000. A strictly positive 20-session return targets BTC, and a zero or "
        "negative return targets cash. Weekly started in cash and waited for its first Monday. The fill proxy uses "
        "the first trade-bearing minute open at or after 00:05 UTC after the decision. Passive BTC/cash rebalances "
        "annually to its allocation estimated from earlier signals, then drifts. Buy-and-hold pays its entry cost. "
        "Cash earns zero interest. The final daily close values each account without a liquidation trade.",
        "## Portfolio outcomes at base costs",
        performance_table(("Pooled", arm, base[arm]["pooled"]) for arm in ARMS),
        "### Calendar-year outcomes",
        performance_table((str(year), arm, base[arm][str(year)]) for year in years
                          for arm in ("weekly20", "momentum20", "passive_mix")),
        "Calendar returns begin at the preceding year-end equity, with initial cash used for the first year. "
        "Cash and BTC carry across year boundaries. Sharpe annualizes daily arithmetic returns using sample "
        "standard deviation and √365. Drawdown measures the largest decline from a prior peak in the reported period. "
        "Turnover sums one-way quoted traded value divided by pretrade equity at each fill. The "
        "[full metrics](metrics.json) contain all five accounts, all three cost settings, each year and the pooled period.",
        "## What remains uncertain",
        f"The paired intervals resample {spec['uncertainty']['block_sessions']}-day circular blocks within each year, "
        f"using {spec['uncertainty']['draws']:,} draws with the same indices for each pair of accounts. They are "
        "separate marginal intervals conditional on these years, fitted allocations and observed trading paths. "
        "They do not measure generalization to new markets or future periods. The assumed fee and minute-open "
        "fill proxies leave actual account fees, bid–ask spreads, trade size and latency uncertain. "
        "This exploratory comparison reused previously examined history and has no prospective observations.",
        "## Reproduce and inspect",
        "Install the development build containing the weekly study, then choose a fresh output directory.",
        f"```sh\n{COMMAND}\n```",
        f"[Protocol](protocol.json) · [Comparisons](comparisons.json) · [Daily ledger](ledger.jsonl.gz) · "
        f"[Verification](verification.json) · [Run receipt](run.json) · [Public exhibit](public.json) · "
        f"[Original BTC study]({ORIGINAL_URL})",
        f"{CREDIT} The derived report, figure and results use [CC BY-SA 4.0]({LICENSE_URL}). "
        f"[Original dataset]({SOURCE_URL}) · [Publisher terms]({TERMS_URL})",
    ]
    (out / "README.md").write_text("\n\n".join(body) + "\n", encoding="utf-8")
