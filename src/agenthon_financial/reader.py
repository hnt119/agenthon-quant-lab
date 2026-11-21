"""Human-readable interpretation and approved static projection of a verified study."""
from html import escape

from .study import PROTOCOL


def paragraphs(spec, result):
    arms = result["portfolios"]["base"]
    plain, mix = (arms[k]["pooled"] for k in ("momentum20", "passive_mix"))
    first, last = spec["evaluation_years"][0], spec["evaluation_years"][-1]
    pred = result["prediction"]["5"]["pooled"]["difference"]
    low, high = result["interval95"]["predictive_difference"]
    sl, sh = result["interval95"]["sharpe_delta"]
    return [
        f"On Bitstamp from {first} through {last}, did buying BTC when its last daily close was higher than "
        "20 sessions earlier pay for the trading it required? We used the preceding 2017–2019 history for the initial fit.",
        f"Starting with ${spec['initial_cash']:,}, momentum finished at ${plain['ending_equity']:,.0f} after costs. "
        f"Passive BTC/cash finished at ${mix['ending_equity']:,.0f}. The passive account set its BTC share once each year "
        "from earlier signals and held the rest in cash. Each fill paid a 0.50% fee and assumed a 0.10% worse price.",
        f"Momentum made {plain['trade_events']} trades against the passive account’s {mix['trade_events']}. "
        f"Its deepest fall from a previous closing high (drawdown) was {plain['max_drawdown']:.2%}, versus "
        f"{mix['max_drawdown']:.2%}. Its Sharpe ratio, which measures average return relative to variability, "
        f"was {plain['sharpe']:.3f} versus {mix['sharpe']:.3f}.",
        f"The price signal and the investment answer different questions. The next day’s BTC return averaged "
        f"{pred*100:.3f} percentage points more after a positive signal. The 95% interval spans "
        f"{low*100:+.3f} to {high*100:+.3f} points. The interval for the net Sharpe difference spans "
        f"{sl:+.3f} to {sh:+.3f}. The passive account did better here. Both intervals include zero, "
        f"so the study’s decision is {result['decision']}. Future performance is unmeasured.",
    ]


def overview_html(spec, result):
    return "\n".join(f"<p>{escape(p)}</p>" for p in paragraphs(spec, result))


def projection(verified):
    record, spec, _, _, entries, result, receipt = verified
    arms = result["portfolios"]["base"]
    # Publish actual month-end closing marks. Daily extremes live in the full-period summaries.
    marks = {}
    for e in entries:
        arm = e["arm"]
        if e["scenario"] == "base" and arm in ("momentum20", "passive_mix"):
            row = marks.setdefault(e["date"][:7], {})
            row["date"] = e["date"]
            row[arm] = {k:e[k] for k in ("equity", "drawdown")}
    return dict(study=spec["id"], start="2020-01-01", end="2024-12-31", development=spec["development"],
                decision=result["decision"], initial_usd=spec["initial_cash"], prospective_observations=0,
                scenario_units=spec["scenario_units"], base_scenario=spec["scenarios"]["base"],
                portfolios={a:{k:periods["pooled"][k] for k in ("ending_equity","total_return","sharpe",
                            "max_drawdown","mean_close_exposure","trade_events","transaction_cost")}
                            for a,periods in arms.items()},
                predictive=result["prediction"]["5"]["pooled"], sharpe_delta=result["sharpe_delta"]["base"]["pooled"],
                interval95=result["interval95"], month_ends=list(marks.values()),
                sampling="Last UTC close each month. Drawdown at that close uses the daily running peak. "
                         "The maximum drawdown in the table uses all daily closes.",
                verification=receipt["status"], protocol_sha256=PROTOCOL,
                inputs_sha256=record["input_sha256"], ledger_sha256=record["output_artifacts_sha256"]["ledger.jsonl.gz"],
                metrics_sha256=record["output_artifacts_sha256"]["metrics.json"],
                attribution="Zielak (mczielinski), Bitcoin Historical Data, Kaggle v706, normalized by ff137. "
                            "Adapted to UTC sessions, simulated portfolios and sampled month-end marks.",
                license="CC BY-SA 4.0", license_url="https://creativecommons.org/licenses/by-sa/4.0/")


def write_report(out, verified):
    _,spec,_,_,_,result,_ = verified
    body = ["# Does BTC momentum pay for trading?", *paragraphs(spec,result),
            "[Explore the charts and daily decisions](dashboard.html) · [All tables](tables.csv) · "
            "[Calculation receipt](verification.json) · [Reproduction comparison](reproduction.json)",
            "From the installed toolkit, run `quant-lab btc-study` to repeat this exact comparison in a new folder.",
            "Prices are trade-bearing candle proxies on one exchange. Spreads, actual execution and capacity are unknown.",
            "Derived from Zielak (mczielinski), *Bitcoin Historical Data*, Kaggle v706, normalized by ff137. "
            "UTC aggregation and simulated financial results are shared under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)."]
    with (out/"report.md").open("x",encoding="utf-8") as handle:
        handle.write("\n\n".join(body)+"\n")
