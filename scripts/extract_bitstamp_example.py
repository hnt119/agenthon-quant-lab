"""Rebuild the attributed 91-session example from the publisher's local minute CSV."""
import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import io
from pathlib import Path

SOURCE_SHA256 = "1d920d9cd8c2e03c8d17a2b686017dd544f1c175cd11a330d817d30b3258c6e3"
FIXTURE_SHA256 = "371a9692925068a85aa6541fc64675891db48d46d27fa318d558043652ec707e"
START = 1743465600  # 2025-04-01 00:00 UTC
STOP = 1751328000   # 2025-07-01 00:00 UTC


def extract(source):
    with source.open("rb") as handle:
        if hashlib.file_digest(handle, "sha256").hexdigest() != SOURCE_SHA256:
            raise ValueError("Input does not match the pinned publisher file")
        handle.seek(0)
        bars = {}
        next_minute = START
        for row in csv.DictReader(io.TextIOWrapper(handle, encoding="utf-8", newline="")):
            timestamp = int(row["timestamp"])
            if timestamp < START:
                continue
            if timestamp >= STOP:
                break
            if timestamp != next_minute:
                raise ValueError("Unexpected minute ordering or gap")
            next_minute += 60
            if Decimal(row["volume"]) <= 0:
                continue
            day = datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat()
            if day not in bars:
                bars[day] = [row["open"], row["close"]]
            else:
                bars[day][1] = row["close"]
    if next_minute != STOP or len(bars) != 91:
        raise ValueError("Incomplete quarter")
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["SessionUTC", "FirstTradeOpen", "LastTradeClose"])
    for day, prices in bars.items():
        writer.writerow([day, *prices])
    data = output.getvalue().encode("utf-8")
    if hashlib.sha256(data).hexdigest() != FIXTURE_SHA256:
        raise ValueError("Derived fixture differs from the recorded hash")
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--out", type=Path, required=True, help="New CSV path")
    args = parser.parse_args()
    data = extract(args.source)
    with args.out.open("xb") as handle:
        handle.write(data)
    print(FIXTURE_SHA256, args.out)
