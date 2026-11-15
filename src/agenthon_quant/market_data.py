"""Import one local daily open/close series with explicit session-date conventions."""
from __future__ import annotations

import csv
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO, TextIOWrapper
import hashlib
import math
from pathlib import Path
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


MAX_BYTES = 25 * 1024 * 1024
MAX_ROWS = 10_000
MAX_COLUMNS = 256
MAX_CSV_LINE_CHARS = 256 * 1024
MAX_PARQUET_UNCOMPRESSED_BYTES = 25 * 1024 * 1024
_FIELDS = ("date", "open", "close")
_OFFSET_TIME = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}"
    r"(?::[0-9]{2}(?:\.[0-9]{1,9})?)?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])"
)


def _declarations(spec):
    if not isinstance(spec, dict):
        raise ValueError("Market data specification must be an object")
    source = spec.get("source")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("source must describe where the observations came from")
    adjustment = spec.get("price_adjustment")
    if adjustment not in ("unadjusted", "split_adjusted"):
        raise ValueError("price_adjustment must be 'unadjusted' or 'split_adjusted'")
    columns = spec.get("columns", {k: k for k in _FIELDS})
    if not isinstance(columns, dict) or set(columns) != set(_FIELDS):
        raise ValueError("columns must map exactly date, open, and close to their source column names")
    if any(not isinstance(v, str) or not v.strip() for v in columns.values()):
        raise ValueError("Source column names must be nonempty strings")
    if len(set(columns.values())) != len(_FIELDS):
        raise ValueError("date, open, and close must map to distinct source columns")
    convention = spec.get("timestamp_convention", "session_date")
    zone = None
    if convention == "offset_timestamp":
        name = spec.get("session_timezone")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("offset_timestamp requires an IANA session_timezone, e.g. America/New_York")
        if name in ("localtime", "posixrules") or name.startswith(("posix/", "right/")):
            raise ValueError("session_timezone must identify a portable IANA time zone")
        try:
            zone = ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"Unknown IANA session_timezone: {name}") from exc
    elif convention == "session_date":
        if "session_timezone" in spec:
            raise ValueError("session_timezone applies only to offset_timestamp")
    else:
        raise ValueError("timestamp_convention must be 'session_date' or 'offset_timestamp'")
    return source, adjustment, dict(columns), convention, zone


def _check_header(names, columns):
    if not names or len(names) > MAX_COLUMNS:
        raise ValueError(f"Input must have between 1 and {MAX_COLUMNS} columns")
    if any(not n.strip() for n in names) or len(names) != len(set(names)):
        raise ValueError("Price input requires a unique, nonempty header")
    missing = [name for name in columns.values() if name not in names]
    if missing:
        raise ValueError(f"Price data requires date, open, and close columns; missing source column(s): {', '.join(missing)}")


def _csv_rows(data, columns):
    with TextIOWrapper(BytesIO(data), encoding="utf-8-sig", newline="") as handle:
        def bounded_lines():
            while line := handle.readline(MAX_CSV_LINE_CHARS + 1):
                if len(line) > MAX_CSV_LINE_CHARS:
                    raise ValueError(f"CSV physical line exceeds {MAX_CSV_LINE_CHARS} characters")
                yield line

        try:
            reader = csv.reader(bounded_lines(), strict=True)
            names = next(reader, [])
            _check_header(names, columns)
            selected = [names.index(columns[field]) for field in _FIELDS]
            for values in reader:
                if len(values) != len(names):
                    raise ValueError(f"CSV row at line {reader.line_num} has the wrong number of columns")
                yield tuple(values[i] for i in selected)
        except (csv.Error, UnicodeError) as exc:
            raise ValueError(f"Invalid UTF-8 CSV: {exc}") from exc


def _parquet_rows(data, columns):
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ValueError("Parquet input requires PyArrow; install the parquet extra") from exc
    selected = [columns[k] for k in _FIELDS]
    try:
        # Preserve dictionary encoding for strings so repeated values do not expand
        # into a large collection of Python strings during decoding.
        with pq.ParquetFile(pa.BufferReader(data), read_dictionary=selected,
                            thrift_string_size_limit=4 * 1024 * 1024,
                            thrift_container_size_limit=100_000) as file:
            meta = file.metadata
            if meta.num_rows > MAX_ROWS:
                raise ValueError(f"Price input exceeds the {MAX_ROWS}-row limit")
            if meta.num_columns > MAX_COLUMNS or meta.num_row_groups > MAX_ROWS:
                raise ValueError("Parquet input exceeds the column or row-group limit")
            if sum(meta.row_group(i).total_byte_size for i in range(meta.num_row_groups)) > MAX_PARQUET_UNCOMPRESSED_BYTES:
                raise ValueError(f"Parquet input exceeds the {MAX_PARQUET_UNCOMPRESSED_BYTES}-byte uncompressed limit")
            schema = file.schema_arrow
            _check_header(schema.names, columns)
            for logical, name in zip(_FIELDS, selected):
                dtype = schema.field(name).type
                if pa.types.is_dictionary(dtype):
                    dtype = dtype.value_type
                is_text = pa.types.is_string(dtype) or pa.types.is_large_string(dtype)
                if logical == "date":
                    supported = is_text or pa.types.is_date(dtype) or pa.types.is_timestamp(dtype)
                else:
                    supported = is_text or pa.types.is_integer(dtype) or pa.types.is_floating(dtype) or pa.types.is_decimal(dtype)
                if not supported:
                    raise ValueError(f"Unsupported Parquet type for {logical}: {dtype}")
            for batch in file.iter_batches(batch_size=256, columns=selected, use_threads=False):
                arrays = [batch.column(batch.schema.get_field_index(name)) for name in selected]
                for index in range(batch.num_rows):
                    row = []
                    for array in arrays:
                        cell = array[index]
                        if pa.types.is_dictionary(cell.type) and cell.is_valid:
                            cell = cell.value
                        if cell.is_valid and (pa.types.is_string(cell.type) or pa.types.is_large_string(cell.type)) and cell.as_buffer().size > 128:
                            raise ValueError("Parquet date/price text exceeds 128 bytes")
                        if cell.is_valid and pa.types.is_timestamp(cell.type) and cell.type.unit == "ns":
                            # Session dates need at most microseconds. Floor rather
                            # than round nanoseconds at a local midnight boundary.
                            cell = pa.scalar(cell.value // 1000, type=pa.timestamp("us", tz=cell.type.tz))
                        row.append(cell.as_py())
                    yield tuple(row)
    except (pa.ArrowException, OSError, OverflowError, ZoneInfoNotFoundError) as exc:
        raise ValueError(f"Invalid or unsupported Parquet input: {exc}") from exc


def _session(value, zone, index):
    if zone is None:
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                parsed = date.fromisoformat(value)
                if parsed.isoformat() == value:
                    return parsed
            except ValueError:
                pass
        raise ValueError(f"row {index} date must be a YYYY-MM-DD session date")
    if isinstance(value, str) and _OFFSET_TIME.fullmatch(value):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            pass
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError(f"row {index} date must be an offset timestamp with Z or an explicit UTC offset")
    try:
        return value.astimezone(zone).date()
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"row {index} timestamp cannot be converted to the declared session_timezone") from exc


def _price(value, field, index):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError(f"row {index} {field} must be numeric")
    try:
        price = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"row {index} {field} must be numeric") from exc
    if not math.isfinite(price) or price <= 0:
        raise ValueError(f"row {index} {field} must be positive and finite")
    return price


def read_market_data(data_path, spec):
    """Return normalized rows and data-quality observations for a local price file.

    Adjacent dates define calendar gaps only. An exchange schedule or the source's
    corporate-action treatment cannot be verified by inspecting these three fields.
    """
    source, adjustment, columns, convention, zone = _declarations(spec)
    path = Path(data_path)
    if not path.is_file():
        raise ValueError(f"Price input does not exist or is not a regular file: {path}")
    if path.suffix.lower() not in (".csv", ".parquet", ".pq"):
        raise ValueError("Price input must be .csv, .parquet, or .pq")
    if path.stat().st_size > MAX_BYTES:
        raise ValueError(f"Price input exceeds the {MAX_BYTES}-byte limit")
    with path.open("rb") as handle:
        data = handle.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError(f"Price input exceeds the {MAX_BYTES}-byte limit")
    records = _csv_rows(data, columns) if path.suffix.lower() == ".csv" else _parquet_rows(data, columns)
    rows = []
    gaps = {"interval_count": 0, "unobserved_calendar_days": 0, "longest_unobserved_calendar_days": 0, "examples": []}
    previous = None
    for index, (raw_date, opened, closed) in enumerate(records, start=1):
        if index > MAX_ROWS:
            raise ValueError(f"Price input exceeds the {MAX_ROWS}-row limit")
        session = _session(raw_date, zone, index)
        if previous is not None:
            days = (session - previous).days
            if days <= 0:
                reason = "duplicate session" if days == 0 else "out-of-order session"
                raise ValueError(f"row {index}: {reason} {session}; session dates must be unique and strictly increasing")
            if days > 1:
                unobserved = days - 1
                gaps["interval_count"] += 1
                gaps["unobserved_calendar_days"] += unobserved
                gaps["longest_unobserved_calendar_days"] = max(gaps["longest_unobserved_calendar_days"], unobserved)
                if len(gaps["examples"]) < 10:
                    gaps["examples"].append({"after": previous.isoformat(), "before": session.isoformat(), "unobserved_calendar_days": unobserved})
        rows.append({"date": session.isoformat(), "open": _price(opened, "open", index), "close": _price(closed, "close", index)})
        previous = session
    if not rows:
        raise ValueError("Price input contains no observations")
    quality = {"source": source, "input_bytes": len(data), "input_sha256": hashlib.sha256(data).hexdigest(), "price_adjustment": adjustment, "timestamp_convention": convention,
               "session_timezone": zone.key if zone else None, "columns": columns,
               "first_date": rows[0]["date"], "last_date": rows[-1]["date"], "observation_count": len(rows),
               "calendar_gaps": gaps,
               "limitations": ["Source and price adjustments are user declarations. Both price fields must use the same adjustment basis.",
                               "Calendar gaps count dates between observations. Exchange sessions and data completeness were not independently verified."]}
    if zone is not None:
        quality["limitations"].append("Offset timestamps map to local civil dates. Overnight exchange sessions may use a different trading date.")
    return rows, quality
