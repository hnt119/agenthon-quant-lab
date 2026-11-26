"""Render the weekly allocation comparison from its checked total-wealth records."""
from datetime import date
from math import ceil
from xml.etree import ElementTree as ET

from agenthon_quant.records import write_json
from .cost_report import LICENSE_URL, SOURCE_URL, TERMS_URL, fmt
from .weekly_report import COSTS, DISPLAY_METRICS


FOCUS = ("target50", "half_funded")
ARMS = {
    "target50": "Monday 50% target", "half_funded": "Half-funded weekly",
    "weekly20": "Full-size weekly", "momentum20": "Daily momentum", "passive_mix": "Annual passive BTC/cash",
}
COMMAND = "quant-lab btc-weekly-allocation --out runs/allocation"
CREDIT = ("Zielak (mczielinski), Bitcoin Historical Data, Kaggle v706, normalized by ff137. "
          "Adapted to UTC daily sessions, simulated spot accounts and weekly allocation comparisons.")
SAMPLING = ("First close, final close of each month, and dated peaks and troughs of both accounts’ "
            "worst base-cost declines. Lines join these selected daily closes. Each maximum uses all daily closes.")
WEEKLY_URL = "https://github.com/hnt119/agenthon-quant-lab/blob/v0.4.0/reports/btc-weekly-cadence-v1/README.md"


def drawdown_points(paths, worst):
    target, control = (paths["base", arm] for arm in FOCUS)
    extremes = {worst[arm][key] for arm in FOCUS for key in ("peak_date", "trough_date")}
    points = []
    for i, (left, right) in enumerate(zip(target, control, strict=True)):
        day = left["date"]
        if day != right["date"]:
            raise ValueError("Misaligned allocation chart dates")
        month_end = i == len(target) - 1 or target[i + 1]["date"][:7] != day[:7]
        if i == 0 or month_end or day in extremes:
            points.append({"date": day, "target50": left["drawdown"], "half_funded": right["drawdown"]})
    return points


def public_projection(spec, metrics, primary, diagnostics, paths, provenance):
    portfolios = {
        scenario: {
            arm: {period: {k: values[k] for k in DISPLAY_METRICS} for period, values in metrics[scenario][arm].items()}
            for arm in ARMS
        } for scenario in COSTS
    }
    return {
        "schema_version": 1, "study_id": spec["id"], "question": spec["question"],
        "evaluation": spec["evaluation"], "evidence": spec["evidence"],
        "prospective_observations": 0, "initial_usd": spec["initial_cash"],
        "scenarios": spec["scenarios"], "scenario_units": spec["scenario_units"],
        "primary": {k: primary[k] for k in ("difference_pp", "interval95_pp")},
        "primary_definition": "Base-cost maximum drawdown of half-funded weekly minus Monday target, in percentage points.",
        "uncertainty": spec["uncertainty"], "portfolios": portfolios,
        "diagnostics": {scenario: {k: diagnostics[scenario][k] for k in ("first_fill", "unchanged_positive", "worst_declines")}
                        for scenario in COSTS},
        "drawdown": {"scenario": "base", "unit": "positive_fraction_below_prior_total_wealth_peak",
                     "sampling": SAMPLING, "points": drawdown_points(paths, diagnostics["base"]["worst_declines"])},
        "provenance": {k: provenance[k] for k in ("protocol_commit", "protocol_sha256", "snapshot_sha256")},
        "reproduction_command": COMMAND, "distribution": "Development study; unavailable in public v0.4.0",
        "attribution": CREDIT, "license": "CC BY-SA 4.0", "license_url": LICENSE_URL,
        "dataset_url": SOURCE_URL, "publisher_terms_url": TERMS_URL,
        "source_manifest_sha256": spec["source_manifest_sha256"],
    }


def write_figure(path, exhibit):
    series = exhibit["drawdown"]["points"]
    worst = exhibit["diagnostics"]["base"]["worst_declines"]
    first, last = (date.fromisoformat(point["date"]) for point in (series[0], series[-1]))
    left, right, top, bottom = 76, 854, 102, 327
    ceiling = max(10, ceil(max(p[key] * 100 for p in series for key in FOCUS) / 10) * 10)

    def x(day):
        return left + (day - first).days / max(1, (last - first).days) * (right - left)

    def y(percent):
        return top + percent / ceiling * (bottom - top)

    svg = ET.Element("svg", {"xmlns": "http://www.w3.org/2000/svg", "viewBox": "0 0 900 426",
                             "role": "img", "aria-labelledby": "title description"})
    ET.SubElement(svg, "title", id="title").text = "How far did each account fall from its previous peak?"
    ET.SubElement(svg, "desc", id="description").text = (
        "Base-cost total-wealth drawdowns below their running peaks. Deeper losses appear lower. "
        + SAMPLING + " Circles mark each worst trough. Dates and losses appear in the report.")
    ET.SubElement(svg, "metadata").text = f"{CREDIT} CC BY-SA 4.0. {LICENSE_URL}"
    ET.SubElement(svg, "rect", width="900", height="426", fill="white")
    ET.SubElement(svg, "style").text = (
        "text{font-family:Arial,Helvetica,sans-serif;font-size:14px;fill:#20332f}"
        ".heading{font-size:23px;font-weight:600}.small{font-size:12px}"
        ".target50{stroke:#24685f}.half_funded{stroke:#935525;stroke-dasharray:7 4}"
        ".series{stroke-width:2.5;fill:none}.grid{stroke:#d3ded9;stroke-width:1}")

    def label(px, py, value, css="", anchor="start"):
        ET.SubElement(svg, "text", {"x": f"{px:.2f}", "y": f"{py:.2f}",
                                    "class": css, "text-anchor": anchor}).text = value

    def line(x1, y1, x2, y2, css):
        ET.SubElement(svg, "line", {"x1": f"{x1:.2f}", "y1": f"{y1:.2f}",
                                    "x2": f"{x2:.2f}", "y2": f"{y2:.2f}", "class": css})

    label(24, 32, "How far did each account fall from its previous peak?", "heading")
    label(24, 56, f"Bitstamp BTC/USD · {first.year}–{last.year} · Base costs · Total wealth including inactive cash")
    label(24, 83, "Below peak", "small")
    for tick in range(0, ceiling + 1, 10):
        line(left, y(tick), right, y(tick), "grid")
        label(left - 12, y(tick) + 4, f"{tick}%", "small", "end")
    for year in range(first.year, last.year + 1):
        label(x(max(first, date(year, 1, 1))), bottom + 21, str(year), "small", "middle")
    for arm, legend_x in zip(FOCUS, (90, 360), strict=True):
        coords = [(x(date.fromisoformat(p["date"])), y(100 * p[arm])) for p in series]
        ET.SubElement(svg, "polyline", {"class": "series " + arm,
                                      "points": " ".join(f"{px:.2f},{py:.2f}" for px, py in coords)})
        episode = worst[arm]
        ET.SubElement(svg, "circle", {"cx": f"{x(date.fromisoformat(episode['trough_date'])):.2f}",
                                    "cy": f"{y(100 * episode['drawdown']):.2f}", "r": "4",
                                    "fill": "#24685f" if arm == "target50" else "#935525"})
        line(legend_x, 378, legend_x + 38, 378, "series " + arm)
        label(legend_x + 46, 383, ARMS[arm])
    label(24, 410, "Month-end closes plus both maximum-drawdown episodes. Each maximum uses the full daily record.", "small")
    ET.ElementTree(svg).write(path, encoding="utf-8", xml_declaration=True)


def _table(headings, rows):
    header = "| " + " | ".join(headings) + " |"
    alignment = "|---" + "|---:" * (len(headings) - 1) + "|"
    return "\n".join([header, alignment, *("| " + " | ".join(row) + " |" for row in rows)])


def _finding(primary):
    difference = primary["difference_pp"]
    if difference == 0:
        observation = "The two accounts had equal maximum drawdowns."
    else:
        direction = "smaller" if difference > 0 else "larger"
        observation = f"The Monday target’s maximum drawdown was **{abs(difference):.2f} percentage points {direction}**."
    lo, hi = primary["interval95_pp"]
    if lo <= 0 <= hi:
        judgment = "The interval includes zero. The historical comparison leaves the incremental drawdown benefit uncertain."
    elif lo > 0:
        judgment = "The interval favors the target on drawdown within this retrospective comparison."
    else:
        judgment = "The interval favors the half-funded account on drawdown within this retrospective comparison."
    return (f"{observation} Subtracting target drawdown from half-funded drawdown gives **{difference:+.2f} points** "
            f"(paired 95% interval **{lo:+.2f} to {hi:+.2f}**). {judgment}")


def write_report(out, spec, metrics, primary, diagnostics, paths, provenance):
    exhibit = public_projection(spec, metrics, primary, diagnostics, paths, provenance)
    write_json(out / "public.json", exhibit)
    write_figure(out / "drawdown.svg", exhibit)
    base = metrics["base"]
    target, control = (base[arm]["pooled"] for arm in FOCUS)
    changes = diagnostics["base"]["unchanged_positive"]
    episodes = diagnostics["base"]["worst_declines"]
    settings = spec["uncertainty"]
    pooled_rows = []
    for arm, label in ARMS.items():
        m = base[arm]["pooled"]
        pooled_rows.append([label, f"${m['ending_equity']:,.0f}", f"{m['total_return']:+.2%}",
                            fmt(m["sharpe"], ".3f"), f"{m['max_drawdown']:.2%}", f"{m['mean_close_exposure']:.2%}",
                            str(m["trade_events"]), f"{m['turnover']:.2f}×", f"${m['fees']:,.2f}",
                            f"${m['slippage_cost']:,.2f}"])
    costs_rows, fill_rows = [], []
    for scenario, name in COSTS.items():
        t, c = (metrics[scenario][arm]["pooled"] for arm in FOCUS)
        _, fee, slip = spec["scenarios"][scenario]
        costs_rows.append([f"{name} ({fee} + {slip} bp)", f"{t['max_drawdown']:.2%}", f"{c['max_drawdown']:.2%}",
                           f"{100*(c['max_drawdown'] - t['max_drawdown']):+.2f}",
                           f"${t['ending_equity']:,.2f}", f"${c['ending_equity']:,.2f}"])
        fill = diagnostics[scenario]["first_fill"]
        fill_rows.append([name, fill["date"], f"{fill['target50_weight']:.4%}", f"{fill['half_funded_weight']:.4%}",
                          f"{fill['difference_pp']:+.4f}"])
    annual_rows = []
    for year in spec["evaluation_years"]:
        t, c = (base[arm][str(year)] for arm in FOCUS)
        annual_rows.append([str(year), f"{t['total_return']:+.2%}", f"{c['total_return']:+.2%}",
                            f"{t['max_drawdown']:.2%}", f"{c['max_drawdown']:.2%}"])
    decline_rows = []
    for arm in FOCUS:
        d = episodes[arm]
        decline_rows.append([ARMS[arm], d["peak_date"], d["trough_date"], f"{d['drawdown']:.2%}",
                             f"{d['peak_exposure']:.2%}", f"{d['trough_exposure']:.2%}"])

    paragraphs = [
        "# Did a weekly 50% BTC target reduce the worst decline beyond starting smaller?",
        f"Both accounts began with ${spec['initial_cash']:,.0f}. One traded back to 50% BTC on positive-momentum "
        "Mondays. The other put half its initial capital in the original weekly strategy and left the other half "
        f"in cash. Both followed the same Sunday-close signal from {spec['evaluation'][0]} through {spec['evaluation'][1]}.",
        _finding(primary),
        f"The target ended at **${target['ending_equity']:,.2f}** and the half-funded account at "
        f"**${control['ending_equity']:,.2f}**. Their average daily closing BTC weights were "
        f"{target['mean_close_exposure']:.2%} and {control['mean_close_exposure']:.2%}, respectively. "
        f"The target finished ${abs(target['ending_equity'] - control['ending_equity']):,.2f} "
        f"{'ahead of' if target['ending_equity'] >= control['ending_equity'] else 'behind'} the sizing control. "
        f"Fees and adverse slippage totaled ${target['transaction_cost']:,.2f} and ${control['transaction_cost']:,.2f}.",
        "![Base-cost decline from each account’s preceding total-wealth peak. "
        "The table below gives exact worst-episode dates and losses.](drawdown.svg)",
        _table(["Base-cost account", "Peak close", "Trough close", "Drawdown", "BTC at peak", "BTC at trough"], decline_rows),
        "The chart samples closing marks. Maximum drawdown uses every daily close and includes the inactive cash. "
        "Each account can reach its peak and trough on different days.",
        "## Where the exposure changed",
        "After a strictly positive 20-session return at the completed Sunday UTC close, the target traded at the first "
        "trade-bearing Monday minute open at or after 00:05 UTC. It aimed to hold half of post-cost wealth in BTC, "
        "valued at the unadjusted quote. A zero or negative signal liquidated BTC. Between decisions units and cash "
        "stayed fixed, so BTC weight could rise above or fall below 50%.",
        f"There were **{changes['decisions']} Mondays with consecutive positive signals**. Restoring the target "
        f"generated {changes['fills']} fills on those days ({changes['sells']} sales and {changes['buys']} purchases), "
        f"{changes['turnover']:.2f}× one-way turnover, ${changes['fees_usd']:,.2f} in fees and "
        f"${changes['slippage_usd']:,.2f} in adverse slippage. The half-funded weekly sleeve held its units on those "
        "Mondays. Selling after a rise reduced exposure to subsequent price moves, while buying after a fall increased it. "
        "Costs and the sequence of those moves both affected wealth.",
        _table(["First purchase", "UTC date", "Monday target", "Half-funded BTC weight", "Target minus control (points)"], fill_rows),
        "At positive costs the half-funded account paid for its first fill from the active sleeve. Its BTC at the unadjusted "
        "quote was then worth slightly less than its untouched $5,000 reserve. The target account allowed for costs when "
        "sizing the purchase. At every close the sizing control was worth $5,000 plus half the full-size weekly account. "
        "Its active share of total wealth changed over time.",
        "## Base-cost account comparison",
        _table(["Account", "Ending wealth", "Return", "Sharpe", "Max drawdown", "Avg BTC", "Fills", "Turnover", "Fees", "Slippage"],
               pooled_rows),
        "The passive account set its BTC weight once each year using earlier training observations. All accounts paid "
        "the scenario’s costs on actual fills and earned zero cash interest. Sharpe uses each account’s own daily total-wealth "
        "returns, their sample standard deviation and 365-day annualization. Turnover sums quoted traded values divided by "
        "pretrade wealth at each fill.",
        "## Cost sensitivity and calendar years",
        _table(["Fee + slippage per fill", "Target drawdown", "Half-funded drawdown", "Difference (points)",
                "Target ending wealth", "Half-funded ending wealth"], costs_rows),
        _table(["Year at base costs", "Target return", "Half-funded return", "Target drawdown", "Half-funded drawdown"], annual_rows),
        "For the pooled result the peak starts at initial capital. For each annual drawdown the peak starts at the preceding "
        "year-end closing wealth, or initial capital in the first year. Cash and holdings continue through every year boundary. "
        "The [full metrics](metrics.json) give pooled and annual results for all five accounts under all three cost settings.",
        "## Uncertainty and limits",
        f"The paired interval uses {settings['draws']:,} draws of circular {settings['block_sessions']}-session blocks within "
        "calendar years. Each draw takes the same dates for the full-size weekly and target returns, compounds both paths "
        "continuously across years and reconstructs the half-funded account with its fixed cash reserve at every simulated "
        "close. The interval describes variation conditional on these observed portfolio returns. It does not simulate fills "
        "on new price histories. A handful of peaks and troughs can determine a drawdown estimate.",
        "These studies reuse previously examined Bitstamp BTC/USD history. Minute-candle opening prices stand in for fills. "
        "Actual spreads, fees, depth and latency can differ. There are zero prospective observations.",
        "## Reproduce and inspect",
        "Use the development build containing this study in a Python 3.12+ environment and choose a fresh output directory. "
        "Public v0.4.0 provides the three earlier studies.",
        f"```sh\n{COMMAND}\n```",
        "[Frozen protocol](protocol.json) · [Daily accounting ledger](ledger.jsonl.gz) · [Verification](verification.json) "
        f"· [Run receipt](run.json) · [Public exhibit](public.json) · [Original weekly comparison]({WEEKLY_URL})",
        f"{CREDIT} The derived report, figure and numerical exhibits use [CC BY-SA 4.0]({LICENSE_URL}). "
        f"[Original dataset]({SOURCE_URL}) · [Publisher terms]({TERMS_URL})",
    ]
    (out / "README.md").write_text("\n\n".join(paragraphs) + "\n", encoding="utf-8")
