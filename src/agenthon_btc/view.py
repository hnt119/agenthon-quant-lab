"""Read-only HTML panel for the offline Edge Lab dashboard or a standalone page."""
from html import escape

from .run import load_results, saved

LABEL = {"buy_and_hold":"Buy and hold","cash":"Cash","momentum20":"Momentum 20","momentum20_fft":"Momentum + FFT"}
COLORS = ("#935119","#555961","#14695f","#6047a2")
DASHES = ("8 3","2 3","","6 2 1 2")


def chart(title, series, dates, boundary, fmt, reverse=False):
    w, start, end, top, bottom = 760, 83, 734, 23, 155
    observed = [v for _, values in series for v in values if v is not None]
    low, high = min(observed), max(observed)
    if reverse:
        low = 0
    def x(i):
        return start+(end-start)*i/(len(dates)-1)
    def y(v):
        f = (v-low)/(high-low) if high != low else 0.5
        return top + (bottom-top)*(f if reverse else 1-f)
    svg = [f'<figure><figcaption>{escape(title)}</figcaption><svg role="img" aria-label="{escape(title)}" viewBox="0 0 {w} 192">']
    for v in sorted({low,(low+high)/2,high}):
        svg.append(f'<path d="M {start} {y(v):.2f} H {end}" stroke="#d9ded8"/>'
                   f'<text x="75" y="{y(v)+4:.2f}" text-anchor="end">{fmt(v)}</text>')
    xx = x(dates.index(boundary))
    svg.append(f'<path d="M {xx:.2f} {top} V {bottom}" stroke="#687169" stroke-dasharray="2 4"/>')
    for i,(name,values) in enumerate(series):
        points = []
        new_segment = True
        for j, value in enumerate(values):
            if value is None:
                new_segment = True
                continue
            points.append(f'{"M" if new_segment else "L"}{x(j):.2f},{y(value):.2f}')
            new_segment = False
        svg.append(f'<path fill="none" stroke="{COLORS[i]}" stroke-width="2" stroke-dasharray="{DASHES[i]}" '
                   f'd="{" ".join(points)}"><title>{escape(name)}</title></path>')
    for i,anchor in ((0,"start"),(dates.index(boundary),"middle"),(len(dates)-1,"end")):
        svg.append(f'<text x="{x(i):.2f}" y="180" text-anchor="{anchor}">{dates[i]}</text>')
    svg.append('</svg><div class="btc-key">')
    for i,(name,_) in enumerate(series):
        svg.append(f'<span><svg aria-hidden="true" width="29" height="12"><path d="M1 6h26" stroke="{COLORS[i]}" '
                   f'stroke-width="2" stroke-dasharray="{DASHES[i]}"/></svg> {escape(name)}</span>')
    return "".join(svg) + "</div></figure>"


def panel(folder):
    _,spec,source = saved(folder)
    signals,fit,books,metrics = load_results(folder)
    val = spec["partitions"]["validation"][0]
    evaluation = spec["partitions"]["evaluation"][0]
    offset = next(i for i,s in enumerate(signals) if s["date"] == val)
    scored = signals[offset:]
    dates = [s["date"] for s in scored]
    plain,gated = (metrics[a]["net"]["evaluation"]["total_return"] for a in ("momentum20","momentum20_fft"))
    delta = 100*(gated-plain)
    out = ['<section class="btc-pilot"><h1>BTC/USD momentum pilot</h1>',
           f'<p>Bitstamp spot · UTC daily sessions · Retrospective evaluation {evaluation} to {dates[-1]}</p>',
           f'<p>The FFT gate changed the evaluation return by <strong>{delta:+.2f} percentage points</strong> '
           f'after costs. Plain momentum returned {plain:+.2%} and gated momentum returned {gated:+.2%}.</p>',
           '<p>Each fill assumes a 0.50% fee and 0.10% adverse slippage. Final positions use the closing mark. '
           'Prices are single-venue bar proxies. Q2 2025 was previously examined and appears in training.</p>']
    for field,title,formatter in (("equity","After-cost equity · USD",lambda v:f"{v:,.0f}"),
                                 ("drawdown","Drawdown from the running peak",lambda v:f"{v:.1%}")):
        series = [(label,[r[field] for r in books[key]["net"][offset:]]) for key,label in LABEL.items()]
        out.append(chart(title,series,dates,evaluation,formatter,field=="drawdown"))
    out.append('<p>The vertical line marks the start of retrospective evaluation. Books carry holdings from validation.</p>')
    for period,title in (("evaluation","Retrospective evaluation"),("validation","Validation")):
        out.append(f'<h2>{title}</h2><div class="btc-scroll"><table><thead><tr><th>Portfolio</th><th>Gross return</th>'
                   '<th>Net return</th><th>Max drawdown</th><th>Turnover</th><th>Fills</th><th>Fees (USD)</th>'
                   '<th>Slippage (USD)</th></tr></thead><tbody>')
        for key,label in LABEL.items():
            gross = metrics[key]["gross"][period]
            m = metrics[key]["net"][period]
            out.append(f'<tr><th scope="row">{label}</th><td>{gross["total_return"]:+.2%}</td><td>{m["total_return"]:+.2%}</td>'
                       f'<td>{m["max_drawdown"]:.2%}</td><td>{m["turnover"]:.2f}×</td><td>{m["trade_events"]}</td>'
                       f'<td>{m["fees"]:,.2f}</td><td>{m["slippage_cost"]:,.2f}</td></tr>')
        out.append('</tbody></table></div>')
    out.append('<h2>Signals at the completed close</h2>')
    out.append(f'<p>Positive 20-session momentum targets BTC. The gated variant also requires 64-return entropy at or below '
               f'the training median of {fit["median"]:.6f}. Each target applies to the following open.</p>')
    out.append(chart("Momentum over 20 sessions", [("Close-to-close return",[s["momentum20"] for s in scored]),
                     ("Zero",[0.0]*len(scored))], dates, evaluation, lambda v:f"{v:.1%}"))
    out.append(chart("Normalized spectral entropy", [("Entropy",[s["entropy"] for s in scored]),
                     ("Frozen median",[fit["median"]]*len(scored))], dates,evaluation,lambda v:f"{v:.3f}"))
    out.append('<details><summary>Daily decisions and marked equity</summary><div class="btc-scroll"><table><thead><tr>'
               '<th>UTC close</th><th>Momentum</th><th>Entropy</th><th>Plain target</th><th>Gated target</th>'
               '<th>Plain equity (USD)</th><th>Gated equity (USD)</th></tr></thead><tbody>')
    for i,s in enumerate(scored,offset):
        targets=s["targets"]
        ent = "Unavailable" if s["entropy"] is None else f'{s["entropy"]:.5f}'
        out.append(f'<tr><th scope="row">{s["date"]}</th><td>{s["momentum20"]:+.2%}</td><td>{ent}</td>'
                   f'<td>{"BTC" if targets["momentum20"] else "Cash"}</td><td>{"BTC" if targets["momentum20_fft"] else "Cash"}</td>'
                   f'<td>{books["momentum20"]["net"][i]["equity"]:,.2f}</td><td>{books["momentum20_fft"]["net"][i]["equity"]:,.2f}</td></tr>')
    out.append('</tbody></table></div></details>')
    out.append(f'<p>Daily adaptation of <a href="{escape(source["repository"])}">Bitstamp BTC/USD minute data</a> by ff137. '
               f'<a href="{escape(source["license_url"])}">CC BY 4.0</a>. Positive-volume minutes were aggregated into UTC sessions.</p></section>')
    return "\n".join(out)


def standalone(content):
    return """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BTC/USD momentum pilot · Agenthon Quant Lab</title><style>
*{box-sizing:border-box}body{margin:0;background:#f5f6f0;color:#172b26;font:16px/1.5 system-ui,sans-serif}
main{max-width:58rem;padding:clamp(1rem,4vw,3rem);margin:auto}h1{font-size:clamp(2rem,5vw,3.5rem);line-height:1.08}
figure{margin:1rem 0;background:#fff;padding:1rem;border:1px solid #dce1d7}figcaption,summary{font-weight:600}
figure>svg{display:block;width:100%;height:auto}svg text{font-size:12px;fill:#364840}.btc-key{display:flex;flex-wrap:wrap;gap:.3rem 1rem;font-size:.85rem}
.btc-scroll{overflow-x:auto}table{border-collapse:collapse;min-width:100%;background:white;font-variant-numeric:tabular-nums}
td,th{padding:.45rem;text-align:right;border-bottom:1px solid #ddd;white-space:nowrap}th:first-child{text-align:left}
details{margin:1rem 0}summary{cursor:pointer;padding:.5rem 0}a{color:#14695f}
</style><main>""" + content + "</main></html>\n"
