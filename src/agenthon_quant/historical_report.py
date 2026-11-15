"""Render human-readable summaries and portable curves from verified portfolio results."""
import csv
import io

LABELS = {"sma": "Moving average", "buy_and_hold": "Buy and hold", "cash": "Cash"}
STYLES = {"sma": ("#135e74", ""), "buy_and_hold": ("#97481e", "8 3"), "cash": ("#555761", "2 4")}
CURVE_FILES = ("equity-drawdown.csv", "equity-drawdown.svg")


def markdown(result, assumptions):
    quality, books = result["quality"], result["strategies"]
    gaps = quality["calendar_gaps"]
    lines = [f"{quality['observation_count']} sessions from {quality['first_date']} through {quality['last_date']}. "
             f"The input declares {quality['price_adjustment'].replace('_', ' ')} prices. "
             f"There are {gaps['unobserved_calendar_days']} intervening calendar dates without observations.",
             "", f"The portfolio starts with {assumptions['initial_cash']:,.2f} in cash. "
             f"The moving-average rule compares the last close to its trailing {assumptions['lookback']}-session mean. "
             f"Orders execute at the next observed open, with {assumptions['fee_bps']:g} bps in fees "
             f"and {assumptions['slippage_bps']:g} bps in slippage on each fill. Buy and hold observes the same warmup.",
             "", "### After-cost comparison", "",
             "Returns use close-marked equity. Excess is the difference from buy and hold in percentage points. "
             "Costs combine fees and adverse execution slippage in the starting cash currency.", "",
             "| Period | Portfolio | Return | Excess (pp) | Max drawdown | Mean exposure | Fees | Slippage | Ending equity | Fills |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for period in ("test", "full", "train", "validation"):
        def metrics(book):
            net = book["net"]
            return net["metrics"] if period == "full" else net["periods"][period]
        benchmark = metrics(books["buy_and_hold"])["total_return"]
        for name in LABELS:
            if name not in books:
                continue
            m = metrics(books[name])
            lines.append(f"| {period} | {LABELS[name]} | {m['total_return']:.2%} | "
                         f"{100 * (m['total_return'] - benchmark):+.2f} | {m['max_drawdown']:.2%} | "
                         f"{m['mean_close_exposure']:.2%} | {m['fees']:.2f} | {m['slippage_cost']:.2f} | "
                         f"{m['ending_equity']:,.2f} | {m['trade_events']} |")
    book = books["buy_and_hold"]["net"]
    lines += ["", " · ".join(f"{name.capitalize()} {book['periods'][name]['start']} to {book['periods'][name]['end']}"
                              for name in ("train", "validation", "test")), "",
              "Positions carry through period boundaries. Period drawdowns use the period opening equity as their first peak. "
              "The daily drawdown path measures the fall from the highest equity since inception.", "",
              "All gross and net results, including turnover, are available in the saved results."]
    return lines


def curve_csv(result):
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("date", "period", "strategy", "treatment", "equity", "drawdown_fraction"))
    books = result["strategies"]
    periods = books["buy_and_hold"]["net"]["periods"]
    for i, date in enumerate(result["dates"]):
        period = next(key for key in ("train", "validation", "test") if date <= periods[key]["end"])
        for name in LABELS:
            if name in books:
                for treatment in ("gross", "net"):
                    book = books[name][treatment]
                    writer.writerow((date, period, name, treatment, book["equity"][i], book["drawdown"][i]))
    return output.getvalue()


def curve_svg(result):
    dates, books = result["dates"], result["strategies"]
    names = [name for name in LABELS if name in books]
    left, right = 91, 744
    def x(index):
        return left + (right - left) * index / (len(dates) - 1)

    lines = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 770 450" role="img" aria-labelledby="title desc">',
             '<title id="title">After-cost equity and drawdown by session</title>',
             '<desc id="desc">Equity and loss from the preceding peak for each simulated portfolio. Vertical guides mark the start of validation and test. The linked CSV contains the plotted values.</desc>',
             '<rect width="770" height="450" fill="#fff"/>', '<g font-family="system-ui,sans-serif" font-size="13" fill="#232629">']
    for i, name in enumerate(names):
        color, dash = STYLES[name]
        start = left + 160 * i
        lines += [f'<path d="M {start} 20 h 26" fill="none" stroke="{color}" stroke-width="2.5" stroke-dasharray="{dash or "none"}"/>',
                  f'<text x="{start + 32}" y="25">{LABELS[name]}</text>']
    for field, title, top, bottom in (("equity", "Equity at the close", 80, 216),
                                      ("drawdown", "Drawdown from the running peak", 279, 395)):
        paths = {name: books[name]["net"][field] for name in names}
        low, high = min(min(v) for v in paths.values()), max(max(v) for v in paths.values())
        if field == "drawdown":
            low = 0.0
        # Flat paths use a middle line for equity and a top line for zero drawdown.
        def y(value):
            if high == low:
                return top if field == "drawdown" else (top + bottom) / 2
            fraction = (value - low) / (high - low)
            return top + (bottom - top) * (fraction if field == "drawdown" else 1 - fraction)
        lines.append(f'<text x="{left}" y="{top - 13}" font-weight="600">{title}</text>')
        ticks = (low,) if high == low else (low, low + (high - low) / 2, high)
        for tick in ticks:
            label = f"{tick:.1%}" if field == "drawdown" else f"{tick:,.5g}"
            yy = y(tick)
            lines.extend([f'<line x1="{left}" x2="{right}" y1="{yy:.2f}" y2="{yy:.2f}" stroke="#d7dadd"/>',
                          f'<text x="{left-8}" y="{yy+4:.2f}" text-anchor="end">{label}</text>'])
        for period in ("validation", "test"):
            xx = x(dates.index(books["buy_and_hold"]["net"]["periods"][period]["start"]))
            lines.append(f'<line x1="{xx:.2f}" x2="{xx:.2f}" y1="{top}" y2="{bottom}" stroke="#767676" stroke-dasharray="3 4"/>')
        for name, values in paths.items():
            points = " ".join(f"{x(i):.2f},{y(v):.2f}" for i, v in enumerate(values))
            color, dash = STYLES[name]
            lines.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2" stroke-dasharray="{dash or "none"}"/>')
    lines.extend([f'<text x="{left}" y="425">{dates[0]}</text>', '<text x="415" y="425" text-anchor="middle">Observed sessions</text>',
                  f'<text x="{right}" y="425" text-anchor="end">{dates[-1]}</text>', '</g></svg>'])
    return "\n".join(lines) + "\n"
