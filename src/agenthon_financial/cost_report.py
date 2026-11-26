"""Static exhibits for the independently checked, descriptive BTC cost study."""
from math import ceil, floor, log10
from pathlib import Path
from xml.etree import ElementTree as ET

from agenthon_quant.records import write_json

CRITERIA = {
    "passive_sharpe": ("Passive BTC/cash", "Net Sharpe"),
    "passive_wealth": ("Passive BTC/cash", "Terminal wealth (USD)"),
    "hold_sharpe": ("Buy and hold BTC", "Net Sharpe"),
    "hold_wealth": ("Buy and hold BTC", "Terminal wealth (USD)"),
}
SOURCE_URL = "https://www.kaggle.com/datasets/mczielinski/bitcoin-historical-data"
TERMS_URL = "https://github.com/ff137/bitstamp-btcusd-minute-data/blob/d7156d68d85714e188a1e152818281e97c89fbe5/DATA_LICENSE"
LICENSE_URL = "https://creativecommons.org/licenses/by-sa/4.0/"
ORIGINAL_URL = "https://github.com/hnt119/agenthon-quant-lab/blob/v0.3.1/reports/btc-financial-v1/README.md"
ATTRIBUTION = ("Zielak (mczielinski), Bitcoin Historical Data, Kaggle v706, normalized by ff137. "
               "Adapted to UTC sessions, simulated spot portfolios and a fee/slippage sensitivity analysis.")


def fmt(value, spec):
    return "Undefined" if value is None else format(value, spec)


def public_projection(protocol, grid, crossings, provenance):
    # Publish only curve values, search outcomes and public identities. Runtime
    # paths, full ledgers and environment details do not belong on the portfolio.
    ids = ("protocol_sha256", "snapshot_sha256", "source_manifest_sha256", "original_receipt_sha256",
           "protocol_commit")
    return {
        "schema_version": 1, "study_id": protocol["id"], "question": protocol["question"],
        "scope": protocol["scope"], "evaluation": protocol["evaluation"], "cost_path": protocol["cost_path"],
        "initial_usd": protocol["initial_usd"], "criteria": protocol["criteria"],
        "curve": [{k: row[k] for k in ("lambda", "fee_bps", "slippage_bps", "differences")} for row in grid],
        "crossings": {key: {k: crossings[key][k] for k in
                            ("status", "events", "undefined_samples", "near_flat_intervals")} for key in CRITERIA},
        "search": {k: protocol["search"][k] for k in
                   ("lambda_width_tolerance", "sharpe_zero_tolerance", "wealth_zero_tolerance_usd")},
        "provenance": {k: provenance[k] for k in ids},
        "software_version": "0.4.0.dev1", "reproduction_command": "quant-lab btc-cost-break-even --out btc-cost-review",
        "attribution": ATTRIBUTION, "license": "CC BY-SA 4.0", "license_url": LICENSE_URL,
        "dataset_url": SOURCE_URL, "publisher_terms_url": TERMS_URL,
    }


def tick_range(values):
    """An evenly spaced axis shared by the two comparator panels in the same unit."""
    low, high = min([0, *values]), max([0, *values])
    if low == high:
        return [-1, 0, 1]
    rough = (high - low) / 4
    scale = 10 ** floor(log10(rough))
    step = next(s * scale for s in (1, 2, 2.5, 5, 10) if s * scale >= rough)
    return [i * step for i in range(floor(low / step), ceil(high / step) + 1)]


def write_figure(path: Path, grid, crossings, protocol):
    svg = ET.Element("svg", {"xmlns": "http://www.w3.org/2000/svg", "viewBox": "0 0 960 656",
                             "role": "img", "aria-labelledby": "title description"})
    ET.SubElement(svg, "title", id="title").text = "Where did Bitcoin momentum change rank?"
    ET.SubElement(svg, "desc", id="description").text = (
        "Pooled momentum minus comparator outcomes across 41 simulated cost settings in 2020–2024. "
        "Sharpe ratios and ending US dollars have separate axes. The dashed line is equality. "
        "Hollow diamonds mark crossing estimates. The report lists their checked brackets.")
    ET.SubElement(svg, "style").text = (
        "text{font-family:Arial,Helvetica,sans-serif;fill:#23322c}"
        ".heading{font-size:25px;font-weight:700}.subhead{font-size:16px;font-weight:600}"
        ".label{font-size:14px}.tick{font-size:12px;fill:#44584e}"
        ".grid{stroke:#d7e0db}.zero{stroke:#4d5752;stroke-dasharray:5 3}"
        ".curve{fill:none;stroke:#1e6474;stroke-width:2}.dot{fill:#1e6474}"
        ".root{fill:white;stroke:#813f19;stroke-width:2}"
    )
    ET.SubElement(svg, "rect", width="960", height="656", fill="white")

    def label(x, y, content, cls="label", anchor="start"):
        ET.SubElement(svg, "text", {"x": str(x), "y": str(y), "class": cls, "text-anchor": anchor}).text = content

    label(28, 35, "Where did Bitcoin momentum change rank?", "heading")
    label(28, 61, "Bitstamp BTC/USD spot  ·  2020–2024  ·  Positive values favor momentum over the named comparator.")
    label(28, 86, "41 simulated cost settings  ·  Dashed line: equal performance  ·  Hollow diamond: crossing estimate", "tick")
    cost_path = protocol["cost_path"]
    for row, suffix in enumerate(("sharpe", "wealth")):
        keys = [f"{c}_{suffix}" for c in ("passive", "hold")]
        ticks = tick_range([r["differences"][key] for r in grid for key in keys if r["differences"][key] is not None])
        for column, key in enumerate(keys):
            title, unit = CRITERIA[key]
            x, y = 76 + 456 * column, 150 + 221 * row
            width, height = 360, 119
            def xcoord(multiplier):
                return x + width * ((multiplier - cost_path["min_lambda"])
                                    / (cost_path["max_lambda"] - cost_path["min_lambda"]))
            def ycoord(value):
                return y + height * (ticks[-1] - value) / (ticks[-1] - ticks[0])
            label(x, y - 28, title + " · " + unit, "subhead")
            for tick in ticks:
                yy = f"{ycoord(tick):.2f}"
                ET.SubElement(svg, "line", {"x1": str(x), "x2": str(x+width), "y1": yy, "y2": yy,
                                            "class": "zero" if tick == 0 else "grid"})
                label(x - 8, f"{float(yy) + 4:.2f}", fmt(tick, ",.0f" if suffix == "wealth" else ".2f"), "tick", "end")
            for multiplier in (0, 0.5, 1, 1.5, 2):
                xx = xcoord(multiplier)
                label(xx, y + height + 17, f"{multiplier:g}×", "tick", "middle")
            commands = []
            start_segment = True
            for point in grid:
                delta = point["differences"][key]
                if delta is None:
                    start_segment = True
                    continue
                xx, yy = f'{xcoord(point["lambda"]):.2f}', f"{ycoord(delta):.2f}"
                commands.append(("M" if start_segment else "L") + f"{xx} {yy}")
                ET.SubElement(svg, "circle", {"cx": xx, "cy": yy, "r": "2", "class": "dot"})
                start_segment = False
            ET.SubElement(svg, "path", {"d": " ".join(commands), "class": "curve"})
            estimates = []
            for event in crossings[key]["events"]:
                if event["estimate"] is None or event["kind"] not in {"bracketed", "sampled_equality"}:
                    continue
                est = event["estimate"]
                estimates.append(f"{est:.4f}×")
                mark = ET.SubElement(svg, "path", {"class": "root", "d": "M0 -5 L5 0 0 5 -5 0Z",
                    "transform": f"translate({xcoord(est):.2f} {ycoord(0):.2f})"})
                ET.SubElement(mark, "title").text = f"λ ≈ {est:.5f}"
            if not estimates:
                annotation = crossings[key]["status"].replace("_", " ").capitalize()
            elif len(estimates) > 3:
                annotation = f"{len(estimates)} crossing estimates · see the bracket table"
            else:
                annotation = "λ ≈ " + ", ".join(estimates)
            label(x, y + height + 38, annotation, "tick")
    label(28, 579, "Cost multiplier λ  ·  50λ bp fee on filled notional and 10λ bp adverse slippage per fill (one way).")
    label(28, 602, "0× = zero friction; 1× = base assumptions; 2× = double costs. Lines join coarse-grid samples as a visual guide.", "tick")
    label(28, 625, "Retrospective sensitivity. Root markers show numerical estimates. Economic threshold uncertainty is unmeasured.", "tick")
    credit = ET.SubElement(svg, "a", href=LICENSE_URL)
    ET.SubElement(credit, "text", {"x": "28", "y": "647", "class": "tick"}).text = (
        "Adapted from Zielak (mczielinski), Bitcoin Historical Data, v706, normalized by ff137 · CC BY-SA 4.0")
    ET.ElementTree(svg).write(path, encoding="utf-8", xml_declaration=True)


def crossing_finding(summary, name, protocol):
    events = summary["events"]
    path = protocol["cost_path"]
    resolved = [e for e in events if e["kind"] == "bracketed"]
    if len(resolved) == 1 and len(events) == 1 and summary["status"] == "crossing_detected":
        event = resolved[0]
        value = event["estimate"]
        direction = "ahead" if event["value_lo"] > 0 else "behind"
        end = "behind" if direction == "ahead" else "ahead"
        return (f"Momentum moved from {direction} to {end} passive BTC/cash on {name} "
                f"near **{value:.4f}×** base costs "
                f"({value*path['fee_bps_per_lambda']:.2f} bp fee and "
                f"{value*path['slippage_bps_per_lambda']:.2f} bp slippage per fill).")
    if summary["status"] == "no_crossing_detected":
        return f"The sampled range yielded no crossing against passive BTC/cash on {name}."
    return f"The search for equality with passive BTC/cash on {name} returned **{summary['status'].replace('_',' ')}**; see the individual brackets below."


def crossing_table(crossings):
    rows = ["| Comparator | Momentum minus comparator | Search outcome | Final λ bounds | Estimate λ |",
            "|---|---|---|---:|---:|"]
    for key, (comparator, measure) in CRITERIA.items():
        summary = crossings[key]
        if not summary["events"]:
            rows.append(f"| {comparator} | {measure} | {summary['status'].replace('_',' ')} | — | — |")
        for event in summary["events"]:
            bounds = f"{event['lo']:.7f} to {event['hi']:.7f}"
            rows.append(f"| {comparator} | {measure} | {event['kind'].replace('_',' ')} | {bounds} | {fmt(event['estimate'], '.7f')} |")
    return "\n".join(rows)


def anchor_table(grid):
    rows = ["| λ | Fee / slippage per fill (bp) | Momentum USD | Passive USD | Hold BTC USD | Δ Sharpe vs passive | Δ Sharpe vs hold |",
            "|---:|---:|---:|---:|---:|---:|---:|"]
    for row in grid:
        if row["lambda"] not in (0, 1, 2):
            continue
        end = [row["portfolios"][a]["pooled"]["ending_equity"] for a in ("momentum20", "passive_mix", "buy_and_hold")]
        delta = row["differences"]
        cells = [f"{row['lambda']:g}×", f"{row['fee_bps']:g} / {row['slippage_bps']:g}", *[f"{v:,.2f}" for v in end],
                 fmt(delta["passive_sharpe"], "+.3f"), fmt(delta["hold_sharpe"], "+.3f")]
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def annual_table(base):
    rows = ["| Year | Portfolio | Net return | Net Sharpe | Turnover | Fills | Fees + slippage, USD |",
            "|---|---|---:|---:|---:|---:|---:|"]
    labels = {"momentum20": "Momentum", "passive_mix": "Passive BTC/cash", "buy_and_hold": "Buy and hold"}
    years = sorted(set(base["portfolios"]["momentum20"]) - {"pooled"})
    for year in years:
        for arm, name in labels.items():
            m = base["portfolios"][arm][year]
            rows.append(f"| {year} | {name} | {m['total_return']:+.2%} | {fmt(m['sharpe'], '.3f')} | "
                        f"{m['turnover']:.2f}× | {m['trade_events']} | {m['transaction_cost']:,.2f} |")
    return "\n".join(rows)


def write_report(out: Path, protocol: dict, grid: list[dict], crossings: dict, provenance: dict):
    """Render immutable study outcomes after independent numerical qualification."""
    base = next(row for row in grid if row["lambda"] == 1)
    exhibit = public_projection(protocol, grid, crossings, provenance)
    findings = [crossing_finding(crossings[key], name, protocol)
                for key, name in (("passive_sharpe", "net Sharpe"), ("passive_wealth", "terminal wealth"))]
    exhibit["findings"] = [s.replace("**", "") for s in findings]
    write_json(out / "public.json", exhibit)
    write_figure(out / "crossings.svg", grid, crossings, protocol)
    search = protocol["search"]
    momentum, passive = (base["portfolios"][a]["pooled"] for a in ("momentum20", "passive_mix"))
    body = [
        "# Where did trading costs reverse the Bitcoin momentum comparison?",
        "Five retrospective calendar years of Bitstamp spot BTC/USD, January 2020 through December 2024. "
        "All accounts began with $10,000. A positive difference favors momentum.",
        *findings,
        "Sharpe measures average daily net return relative to daily variability. Terminal wealth measures "
        "the dollars remaining at the last close. A change in rank can occur at different costs for these two criteria.",
        "![Pooled net Sharpe and terminal wealth differences against passive BTC/cash and buy-and-hold across the cost path. "
        "The table below lists all detected brackets.](crossings.svg)",
        "## What was held fixed",
        "The long-only rule enters BTC after a positive 20-session change in completed closes and otherwise holds cash. "
        "The passive account sets its BTC share once per year from earlier signals and lets it drift. "
        "The buy-and-hold account pays its entry costs. The grid also retains zero-interest cash and the original "
        "64-return FFT-gated rule. The original prices, training-period entropy threshold, allocation weights and "
        "decision times are fixed for every simulation.",
        "Let λ scale the one-way fee of 50 basis points on filled value and the adverse slippage of 10 basis points "
        "on the quote. Each simulated trade uses the first trade-bearing minute open at or after 00:05 UTC following "
        "the completed-close decision. Each multiplier uses a fresh continuous replay of every portfolio with its "
        "own available cash, quantities and costs. The final mark uses the last daily close without a liquidation trade.",
        "## Pooled outcomes at the original cost settings", anchor_table(grid),
        f"At base costs momentum made {momentum['trade_events']} fills with {momentum['turnover']:.2f}× "
        f"turnover and paid ${momentum['transaction_cost']:,.2f} in fees plus slippage. Passive BTC/cash made "
        f"{passive['trade_events']} fills with {passive['turnover']:.2f}× turnover and paid "
        f"${passive['transaction_cost']:,.2f}. Repeated trading changed both subsequent position sizes and compounding. "
        "The accumulated charges and the final difference in wealth measure different effects.",
        "## Where the differences changed sign", crossing_table(crossings),
        f"The search inspected all {len(grid)} simulated grid settings, from 0× to 2× at 0.05× increments. "
        f"Opposite, defined signs at adjacent points triggered bisection with target bracket width "
        f"{search['lambda_width_tolerance']:g}×, at most {search['max_midpoints_per_bracket']} midpoints per bracket "
        f"and {search['max_additional_settings']} additional settings overall. Sampled differences within "
        f"{search['sharpe_zero_tolerance']:g} Sharpe units or ${search['wealth_zero_tolerance_usd']:g} of zero "
        "count as equality within tolerance. For a bracketed crossing the estimate is the midpoint of its final bounds. "
        "The crossing record retains the two checked endpoint values, undefined samples and nearly flat intervals. "
        "Equal signs at adjacent samples can hide other crossings.",
        "## Calendar-year behavior under base costs", annual_table(base),
        "Each year's return starts at the preceding December close (initial capital in 2020). Positions carry across "
        "each year boundary. Sharpe uses daily close-to-close returns, sample standard deviation, a zero cash rate "
        "and √365 annualization. Turnover sums one-way quoted trade value divided by pretrade equity. All five "
        "accounts' annual and pooled results at every coarse-grid cost are in the [grid](grid.json).",
        "## What this can establish",
        "These are descriptive thresholds conditional on one fee/slippage ratio and previously examined BTC history. "
        "A bracket’s width describes numerical precision. Economic uncertainty about the threshold remains "
        "unmeasured. The original predictive and base-case Sharpe intervals both included zero. They do not "
        "give a confidence interval for either crossing. Candle-price proxies leave actual spreads, latency, "
        "order size and available account fees uncertain. There are no prospective outcomes.",
        "A separate turnover study could predeclare a slower decision cadence or different entry and exit rules, "
        "charge the same costs and compare both turnover and market exposure. The current results evaluate the "
        "original daily rule alone.",
        "## Reproduce and inspect",
        "From a writable directory with the study development wheel installed, run",
        "```sh\nquant-lab btc-cost-break-even --out btc-cost-review\n```",
        "Use a fresh destination. The published v0.3.1 package runs the original study with `quant-lab btc-study`. "
        "The cost-crossing command is available in the 0.4.0.dev1 review build.",
        "[Protocol](protocol.json) · [Full grid](grid.json) · [Crossing records](crossings.json) · "
        "[Independent checks](verification.json) · [Run and source identity](run.json) · "
        f"[Public exhibit](public.json) · [Original BTC report]({ORIGINAL_URL})",
        f"{ATTRIBUTION} The derived report, figure and results use [CC BY-SA 4.0]({LICENSE_URL}). "
        f"[Original dataset]({SOURCE_URL}) · [Publisher terms]({TERMS_URL})",
    ]
    (out / "README.md").write_text("\n\n".join(body) + "\n", encoding="utf-8")
