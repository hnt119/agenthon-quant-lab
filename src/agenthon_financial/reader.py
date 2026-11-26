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
        f"Bitstamp BTC/USD, {first}–{last}. Momentum meant buying when BTC closed higher than 20 days earlier.",
        f"Starting with ${spec['initial_cash']:,}, momentum finished at ${plain['ending_equity']:,.0f} after costs. "
        f"The passive BTC/cash account finished at ${mix['ending_equity']:,.0f}. It set its BTC share yearly from past signals. "
        f"The evidence is {result['decision']}. Future performance is unmeasured.",
        f"Momentum made {plain['trade_events']} trades against the passive account’s {mix['trade_events']}. Each fill paid a 0.50% fee and assumed a 0.10% worse price. "
        f"Its deepest fall from a previous closing high (drawdown) was {plain['max_drawdown']:.2%}, versus "
        f"{mix['max_drawdown']:.2%}. Its Sharpe ratio, which measures average return relative to variability, "
        f"was {plain['sharpe']:.3f} versus {mix['sharpe']:.3f}.",
        f"The price signal and the investment answer different questions. The next day’s BTC return averaged "
        f"{pred*100:.3f} percentage points more after a positive signal. The 95% interval spans "
        f"{low*100:+.3f} to {high*100:+.3f} points. The interval for the net Sharpe difference spans "
        f"{sl:+.3f} to {sh:+.3f}. Both intervals include zero. The passive account’s advantage in this sample leaves the ranking in future periods uncertain.",
    ]


def spectral_finding(spec, result):
    portfolios = result["portfolios"]["base"]
    plain = portfolios["momentum20"]["pooled"]
    gated = portfolios["momentum20_fft"]["pooled"]
    return (
        f"The secondary FFT rule kept a positive momentum signal only when spectral entropy over the last "
        f"{spec['entropy_returns']} completed returns was at or below its training median. "
        f"Average BTC exposure fell from {plain['mean_close_exposure']:.2%} to {gated['mean_close_exposure']:.2%}. "
        f"After costs, plain momentum returned {plain['total_return']:+,.2%} and the gated rule returned "
        f"{gated['total_return']:+,.2%}. The gated account ended at ${gated['ending_equity']:,.0f}."
    )


def overview_html(spec, result):
    intro=paragraphs(spec,result)
    links=('<p><a href="#portfolio">Compare the accounts</a> · <a href="#evidence">Inspect the run</a>. '
           'Repeat locally with <code>quant-lab btc-study</code>.</p>')
    return "\n".join([*(f"<p>{escape(p)}</p>" for p in intro[:2]), links,
                      *(f"<p>{escape(p)}</p>" for p in intro[2:]),
                      f"<p>{escape(spectral_finding(spec, result))}</p>"])


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
    intro = paragraphs(spec, result)
    portfolios = result["portfolios"]["base"]
    deltas = result["sharpe_delta"]
    delay = spec["scenarios"]["later_fill"][0]
    body = ["# Does BTC momentum pay for trading?", *intro[:2],
            "[Explore the charts and daily decisions](dashboard.html) · [All tables](tables.csv) · "
            "[Calculation receipt](verification.json) · [Reproduction comparison](reproduction.json)",
            *intro[2:],
            "## How much did exposure and trading costs matter?",
            f"Buying and holding BTC throughout returned {portfolios['buy_and_hold']['pooled']['total_return']:+,.2%} "
            f"after entry costs. Cash returned {portfolios['cash']['pooled']['total_return']:.2%}.",
            f"Momentum’s Sharpe advantage over passive BTC/cash was {deltas['gross']['pooled']:+.3f} before "
            f"fees and slippage. The difference was {deltas['base']['pooled']:+.3f} at base costs, "
            f"{deltas['double_cost']['pooled']:+.3f} at double costs and {deltas['later_fill']['pooled']:+.3f} "
            f"at base costs with the {delay}-minute delay.",
            spectral_finding(spec, result),
            "From the installed toolkit, run `quant-lab btc-study` to repeat this exact comparison in a new folder.",
            "Prices are trade-bearing candle proxies on one exchange. Spreads, actual execution and capacity are unknown.",
            "Derived from Zielak (mczielinski), *Bitcoin Historical Data*, Kaggle v706, normalized by ff137. "
            "UTC aggregation and simulated financial results are shared under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)."]
    with (out/"report.md").open("x",encoding="utf-8") as handle:
        handle.write("\n\n".join(body)+"\n")
