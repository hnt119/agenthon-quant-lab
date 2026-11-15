"""Daily market import tests use local synthetic observations exclusively."""
import csv
from datetime import date, datetime, timezone
from decimal import Decimal
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agenthon_quant import market_data
from agenthon_quant.market_data import read_market_data


class MarketDataTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.folder = Path(directory.name)
        self.path = self.folder / "prices.csv"
        self.spec = {"source": "authored synthetic observations", "price_adjustment": "unadjusted"}
        self.columns = {"date": "Session", "open": "Opening", "close": "Closing"}

    def write_csv(self, header, rows):
        with self.path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)

    def test_mapped_columns_gap_counts_and_declarations(self):
        self.write_csv(["Closing", "Unused", "Session", "Opening"],
                       [[3, "x", "2025-03-07", 2], [4, "x", "2025-03-10", 3], [5, "x", "2025-03-12", 4]])
        rows, quality = read_market_data(self.path, {**self.spec, "columns": self.columns})
        self.assertEqual([r['date'] for r in rows], ["2025-03-07", "2025-03-10", "2025-03-12"])
        self.assertEqual(rows[0], {"date": "2025-03-07", "open": 2.0, "close": 3.0})
        self.assertEqual((quality['first_date'], quality['last_date'], quality['observation_count']), ("2025-03-07", "2025-03-12", 3))
        self.assertEqual(quality['source'], self.spec['source'])
        self.assertEqual(quality['price_adjustment'], 'unadjusted')
        self.assertEqual(quality['calendar_gaps'], {'interval_count': 2, 'unobserved_calendar_days': 3,
                         'longest_unobserved_calendar_days': 2, 'examples': [
                             {'after': '2025-03-07', 'before': '2025-03-10', 'unobserved_calendar_days': 2},
                             {'after': '2025-03-10', 'before': '2025-03-12', 'unobserved_calendar_days': 1}]})
        self.assertIn('Exchange sessions', ' '.join(quality['limitations']))

    def test_offset_dates_convert_across_daylight_saving_change(self):
        self.write_csv(["date", "open", "close"], [["2025-03-08T04:30:00Z", 1, 1],
                       ["2025-03-09T04:30:00+00:00", 2, 2], ["2025-03-10T04:30:00Z", 3, 3]])
        spec = {**self.spec, 'timestamp_convention': 'offset_timestamp', 'session_timezone': 'America/New_York'}
        rows, quality = read_market_data(self.path, spec)
        self.assertEqual([r['date'] for r in rows], ['2025-03-07', '2025-03-08', '2025-03-10'])
        self.assertEqual(quality['session_timezone'], 'America/New_York')
        self.assertEqual(quality['calendar_gaps']['unobserved_calendar_days'], 1)

    def test_duplicate_local_dates_and_out_of_order_sessions_are_rejected(self):
        for timestamps, error in [(['2025-11-02T01:30:00-04:00', '2025-11-02T01:30:00-05:00'], 'duplicate'),
                                  (['2025-11-03T08:00:00Z', '2025-11-02T08:00:00Z'], 'out-of-order')]:
            self.write_csv(['date', 'open', 'close'], [[t, 1, 2] for t in timestamps])
            with self.subTest(timestamps=timestamps), self.assertRaisesRegex(ValueError, error):
                read_market_data(self.path, {**self.spec, 'timestamp_convention': 'offset_timestamp', 'session_timezone': 'America/New_York'})

    def test_invalid_convention_timezone_or_timestamp(self):
        for change, value in [({'timestamp_convention': 'offset_timestamp'}, '2025-03-10T00:30:00Z'),
                              ({'timestamp_convention': 'offset_timestamp', 'session_timezone': 'Mars/Test'}, '2025-03-10T00:30:00Z'),
                              ({'timestamp_convention': 'offset_timestamp', 'session_timezone': 'localtime'}, '2025-03-10T00:30:00Z'),
                              ({'timestamp_convention': 'offset_timestamp', 'session_timezone': 'UTC'}, '2025-03-10T00:30:00'),
                              ({'timestamp_convention': 'offset_timestamp', 'session_timezone': 'UTC'}, '2025-03-10T00:30:00+01:75'),
                              ({'timestamp_convention': 'offset_timestamp', 'session_timezone': 'UTC'}, '2025-03-10'),
                              ({'session_timezone': 'UTC'}, '2025-03-10'), ({}, '20250310'), ({}, '2025-03-10T00:30:00Z')]:
            self.write_csv(['date', 'open', 'close'], [[value, 1, 2]])
            with self.subTest(change=change, value=value), self.assertRaises(ValueError):
                read_market_data(self.path, {**self.spec, **change})

    def test_ambiguous_missing_or_incomplete_mappings(self):
        self.write_csv(['Session', 'Opening', 'Closing'], [['2025-05-12', 1, 2]])
        for mapping in [{**self.columns, 'close': 'Opening'}, {**self.columns, 'date': 'Closing'},
                        {**self.columns, 'open': 'missing'}, {'date': 'Session'}, {**self.columns, 'extra': 'x'},
                        {**self.columns, 'open': None}]:
            with self.subTest(mapping=mapping), self.assertRaises(ValueError):
                read_market_data(self.path, {**self.spec, 'columns': mapping})

    def test_missing_values_nonfinite_numbers_and_bad_rows(self):
        for price in ['', 'NA', 'NaN', '-inf', 0, -4]:
            self.write_csv(['date', 'open', 'close'], [['2025-05-12', 1, price]])
            with self.subTest(price=price), self.assertRaisesRegex(ValueError, 'row 1 close'):
                read_market_data(self.path, self.spec)
        for content in [b'date,open,close\n', b'date,open,close\n2025-05-12,1,2\n\n',
                        b'date,open,close\n2025-05-12,1\n', b'date,open,close,close\n2025-05-12,1,2,2\n',
                        b'date,open,close\n2025-05-12,1,"2\n', b'date,open,close\n\xff,1,2\n']:
            self.path.write_bytes(content)
            with self.subTest(content=content), self.assertRaises(ValueError):
                read_market_data(self.path, self.spec)

    def test_limits_and_required_provenance(self):
        self.write_csv(['date', 'open', 'close'], [['2025-05-12', 1, 2], ['2025-05-13', 3, 4]])
        for spec in [{'source':'sample'}, {'price_adjustment':'unadjusted'}, {**self.spec, 'source':' '},
                     {**self.spec, 'price_adjustment':'total_return'}]:
            with self.subTest(spec=spec), self.assertRaises(ValueError):
                read_market_data(self.path, spec)
        with patch.object(market_data, 'MAX_BYTES', 15), self.assertRaisesRegex(ValueError, 'byte limit'):
            read_market_data(self.path, self.spec)
        with patch.object(market_data, 'MAX_CSV_LINE_CHARS', 8), self.assertRaisesRegex(ValueError, 'physical line'):
            read_market_data(self.path, self.spec)
        with patch.object(market_data, 'MAX_ROWS', 1), self.assertRaisesRegex(ValueError, 'row limit'):
            read_market_data(self.path, self.spec)

    @unittest.skipUnless(importlib.util.find_spec('pyarrow'), 'optional PyArrow unavailable')
    def test_native_parquet_and_mapped_csv_agree(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        dates = [datetime(2025, 3, 8, 4, 30, tzinfo=timezone.utc), datetime(2025, 3, 10, 4, 30, tzinfo=timezone.utc)]
        self.write_csv(['Closing', 'Session', 'Opening'], [['2.45', t.isoformat(), 1] for t in dates])
        spec = {**self.spec, 'columns': self.columns, 'timestamp_convention':'offset_timestamp', 'session_timezone':'America/New_York'}
        parquet = self.path.with_suffix('.parquet')
        pq.write_table(pa.table({'Closing':[Decimal('2.45')]*2, 'Session':pa.array(dates, type=pa.timestamp('ns', tz='UTC')), 'Opening':[1, 1]}), parquet)
        csv_rows, csv_quality = read_market_data(self.path, spec)
        parquet_rows, parquet_quality = read_market_data(parquet, spec)
        self.assertEqual(csv_rows, parquet_rows)
        for field in ("input_sha256", "input_bytes"):
            self.assertNotEqual(csv_quality.pop(field), parquet_quality.pop(field))
        self.assertEqual(csv_quality, parquet_quality)
        pq.write_table(pa.table({'date':[date(2025, 5, 12)], 'open':['2.45'], 'close':[3]}), parquet)
        self.assertEqual(read_market_data(parquet, self.spec)[0], [{'date':'2025-05-12', 'open':2.45, 'close':3.0}])

    @unittest.skipUnless(importlib.util.find_spec('pyarrow'), 'optional PyArrow unavailable')
    def test_compressed_parquet_budget_and_nulls(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        parquet = self.path.with_suffix('.parquet')
        table = pa.table({'date':['2025-03-01'], 'open':[1], 'close':[2], 'padding':['a'*100_000]})
        pq.write_table(table, parquet, compression='gzip', use_dictionary=False)
        self.assertLess(parquet.stat().st_size, 20_000)
        with patch.object(market_data, 'MAX_PARQUET_UNCOMPRESSED_BYTES', 20_000), self.assertRaisesRegex(ValueError, 'uncompressed limit'):
            read_market_data(parquet, self.spec)
        for value in [None, float('inf'), False]:
            pq.write_table(pa.table({'date':['2025-03-01'], 'open':[value], 'close':[1]}), parquet)
            with self.subTest(value=value), self.assertRaises(ValueError):
                read_market_data(parquet, self.spec)
