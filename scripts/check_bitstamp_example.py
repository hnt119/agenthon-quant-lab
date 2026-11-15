#!/usr/bin/env python3
"""Compare a saved Bitstamp Q2 example to an independent 50-digit Decimal calculation."""
import argparse
import csv
import hashlib
import json
import sys
from datetime import date, timedelta
from decimal import Decimal, getcontext
from pathlib import Path

D = Decimal
getcontext().prec = 50
CAPITAL = D(10000)
FEE = D('0.001')
SLIP = D('0.0005')
FIXTURE_SHA256 = '371a9692925068a85aa6541fc64675891db48d46d27fa318d558043652ec707e'
PORTFOLIOS = ('sma', 'buy_and_hold', 'cash')
PERIODS = {'train': (0, 30), 'validation': (30, 61), 'test': (61, 91)}
ABS_TOL = D('1e-10')
REL_TOL = D('1e-12')


def require(condition, detail):
    if not condition:
        raise ValueError(detail)


def bars_from_fixture(path):
    require(hashlib.sha256(path.read_bytes()).hexdigest() == FIXTURE_SHA256,
            'Fixture bytes differ from the published Q2 example')
    with path.open(encoding='utf-8', newline='') as handle:
        bars = [(row['SessionUTC'], D(row['FirstTradeOpen']), D(row['LastTradeClose']))
                for row in csv.DictReader(handle)]
    expected_dates = [(date(2025, 4, 1) + timedelta(days=i)).isoformat() for i in range(91)]
    require([row[0] for row in bars] == expected_dates, 'Expected all 91 consecutive Q2 UTC days')
    return bars


def account(bars, strategy, fee, slip):
    # A fully invested or flat book needs only currency and BTC balances.
    cash, units = CAPITAL, D(0)
    events = []
    for i, (day, opening, closing) in enumerate(bars):
        if strategy == 'sma':
            prior = [row[2] for row in bars[max(0, i - 5):i]]
            own = len(prior) == 5 and 5 * prior[-1] > sum(prior)
        else:
            own = strategy == 'buy_and_hold' and i >= 5
        open_equity = cash + units * opening
        fee_paid = slip_paid = quoted_notional = D(0)
        side = None
        if own and cash:
            filled_notional = cash / (1 + fee)
            fee_paid = cash - filled_notional
            units = filled_notional / (opening * (1 + slip))
            quoted_notional = units * opening
            slip_paid = filled_notional - quoted_notional
            cash, side = D(0), 'buy'
        elif not own and units:
            quoted_notional = units * opening
            slip_paid = quoted_notional * slip
            fee_paid = (quoted_notional - slip_paid) * fee
            cash = quoted_notional - slip_paid - fee_paid
            units, side = D(0), 'sell'
        events.append(dict(day=day, cash=cash, units=units, equity=cash + units * closing,
                           fee=fee_paid, slip=slip_paid, notional=quoted_notional,
                           turnover=quoted_notional / open_equity, side=side))
    return events


def drawdowns(equities, starting_equity):
    peak = starting_equity
    path = []
    for value in equities:
        peak = max(peak, value)
        path.append(1 - value / peak)
    return path


def metrics(events, starting_equity):
    equities = [row['equity'] for row in events]
    exposure = D(sum(row['units'] > 0 for row in events)) / len(events)
    fees = sum(row['fee'] for row in events)
    slippage = sum(row['slip'] for row in events)
    return dict(starting_equity=starting_equity, ending_equity=equities[-1],
                ending_cash=events[-1]['cash'], ending_shares=events[-1]['units'],
                observations=len(events), pnl=equities[-1] - starting_equity,
                total_return=equities[-1] / starting_equity - 1,
                max_drawdown=max(drawdowns(equities, starting_equity)),
                mean_close_exposure=exposure, sessions_in_market_fraction=exposure,
                trade_events=sum(row['side'] is not None for row in events),
                fees=fees, slippage_cost=slippage, transaction_cost=fees + slippage,
                turnover=sum(row['turnover'] for row in events),
                quoted_traded_notional=sum(row['notional'] for row in events))


def controls():
    prices = [(100, 100)] * 4 + [(100, 102), (120, 125), (130, 90), (80, 70)]
    bars = [(str(i), D(o), D(c)) for i, (o, c) in enumerate(prices)]
    gross = account(bars, 'sma', D(0), D(0))
    net = account(bars, 'sma', FEE, SLIP)
    expected = CAPITAL * D(80) / D(120) * (1 - SLIP) * (1 - FEE) / ((1 + SLIP) * (1 + FEE))
    flat = [(str(i), D(100), D(100)) for i in range(10)]
    alternate_close = bars[:-1] + [(bars[-1][0], bars[-1][1], D(1_000_000))]
    results = {
        'delayed_entry_exit': [r['side'] for r in gross] == [None] * 5 + ['buy', None, 'sell'],
        'gross_hand_payoff': abs(gross[-1]['equity'] - CAPITAL * 2 / 3) < D('1e-40'),
        'net_hand_payoff': abs(net[-1]['equity'] - expected) < D('1e-40'),
        'strict_equality_flat': all(r['equity'] == CAPITAL and r['side'] is None for r in account(flat, 'sma', FEE, SLIP)),
        'single_benchmark_entry': [r['side'] for r in account(flat, 'buy_and_hold', FEE, SLIP)] == [None] * 5 + ['buy'] + [None] * 4,
        'flat_cash_benchmark': all(r['equity'] == CAPITAL for r in account(bars, 'cash', FEE, SLIP)),
        'unexecuted_final_signal': account(alternate_close, 'sma', FEE, SLIP) == net,
    }
    for name, passed in results.items():
        require(passed, f'Independent calculation failed control {name}')
    return list(results)


def compare_number(actual, expected, path):
    if type(expected) is int:
        require(type(actual) is int and actual == expected, f'{path}: expected integer {expected} but got {actual}')
        return
    require(type(actual) in (int, D), f'{path}: expected a JSON number, got {type(actual).__name__}')
    number = D(actual)
    require(number.is_finite(), f'{path}: expected a finite number')
    threshold = max(ABS_TOL, REL_TOL * abs(expected))
    require(abs(number - expected) <= threshold,
            f'{path}: saved {number} differs from Decimal reference {expected} by more than {threshold}')


def check(fixture, run_path):
    bars = bars_from_fixture(fixture)
    record = json.loads(run_path.read_text(encoding='utf-8'), parse_float=D)
    require(record['status'] == 'passed' and record['workflow'] == 'historical', 'Expected a passed historical run')
    data = [item['sha256'] for item in record['input_provenance'] if item['role'] == 'market_data']
    require(data == [FIXTURE_SHA256], 'Run does not identify the published market input')
    spec = record['specification']
    fixed = dict(initial_cash=10000, fee_bps=10, slippage_bps=5, lookback=5,
                 train_end='2025-04-30', validation_end='2025-05-31', synthetic=False,
                 timestamp_convention='session_date', price_adjustment='unadjusted',
                 strategies=list(PORTFOLIOS),
                 columns={'date': 'SessionUTC', 'open': 'FirstTradeOpen', 'close': 'LastTradeClose'})
    for field, value in fixed.items():
        actual = spec[field]
        require(actual == value and (type(actual) is bool) == (type(value) is bool),
                f'Unexpected example contract at specification.{field}')
    results = record['analysis']['results']
    require(results['dates'] == [r[0] for r in bars], 'Saved result dates differ from the fixture')
    require(set(results['strategies']) == set(PORTFOLIOS), 'Expected three saved portfolios')
    metric_count = path_count = 0
    control_names = controls()
    for name in PORTFOLIOS:
        for treatment, (fee, slip) in {'net': (FEE, SLIP), 'gross': (D(0), D(0))}.items():
            rows = account(bars, name, fee, slip)
            saved = results['strategies'][name][treatment]
            location = f'analysis.results.strategies.{name}.{treatment}'
            equities = [r['equity'] for r in rows]
            for key, values in [('equity', equities), ('drawdown', drawdowns(equities, CAPITAL))]:
                require(len(saved[key]) == len(values), f'{location}.{key}: expected {len(values)} sessions')
                for i, expected in enumerate(values):
                    compare_number(saved[key][i], expected, f'{location}.{key}[{i}]')
                    path_count += 1
            for period, (start, stop) in {'full': (0, len(rows)), **PERIODS}.items():
                detail = saved['metrics'] if period == 'full' else saved['periods'][period]
                prefix = f'{location}.metrics' if period == 'full' else f'{location}.periods.{period}'
                if period != 'full':
                    require((detail['start'], detail['end']) == (bars[start][0], bars[stop-1][0]),
                            f'{prefix}: period dates differ')
                expected = metrics(rows[start:stop], rows[start-1]['equity'] if start else CAPITAL)
                for key, value in expected.items():
                    compare_number(detail[key], value, f'{prefix}.{key}')
                    metric_count += 1
    return dict(status='passed', fixture=str(fixture), fixture_sha256=FIXTURE_SHA256, run=str(run_path),
                portfolio_count=len(PORTFOLIOS), treatment_count=2, periods=['full', *PERIODS],
                metric_fields=list(expected), metric_comparisons=metric_count,
                path_fields=['equity', 'drawdown'], daily_path_values=path_count,
                relative_tolerance=str(REL_TOL), absolute_tolerance=str(ABS_TOL),
                control_count=len(control_names), controls=control_names)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', required=True, type=Path, help='Published Q2 daily Bitstamp CSV')
    parser.add_argument('--run', required=True, type=Path, help='Saved historical run.json')
    args = parser.parse_args()
    try:
        print(json.dumps(check(args.fixture, args.run), indent=2))
    except (KeyError, TypeError, ValueError, ArithmeticError, OSError) as exc:
        print(f'Bitstamp example verification failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
