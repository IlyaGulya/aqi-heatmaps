"""Utilities for processing raw pollutant concentration data into AQI aggregates.

This module exposes a CLI that converts a CSV file of pollutant concentrations
into a JSON file that the web client can consume.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

ISO_FORMATS = (
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
)


@dataclass
class StationReading:
    station_id: str
    station_name: str
    latitude: float
    longitude: float
    timestamp: datetime
    aqi: float


AQI_BREAKPOINTS: Dict[str, Tuple[Tuple[float, float, int, int], ...]] = {
    "pm25": (
        (0.0, 12.0, 0, 50),
        (12.1, 35.4, 51, 100),
        (35.5, 55.4, 101, 150),
        (55.5, 150.4, 151, 200),
        (150.5, 250.4, 201, 300),
        (250.5, 500.4, 301, 500),
    ),
    "pm10": (
        (0, 54, 0, 50),
        (55, 154, 51, 100),
        (155, 254, 101, 150),
        (255, 354, 151, 200),
        (355, 424, 201, 300),
        (425, 604, 301, 500),
    ),
    "o3": (
        (0, 0.054, 0, 50),
        (0.055, 0.070, 51, 100),
        (0.071, 0.085, 101, 150),
        (0.086, 0.105, 151, 200),
        (0.106, 0.200, 201, 300),
    ),
    "no2": (
        (0, 53, 0, 50),
        (54, 100, 51, 100),
        (101, 360, 101, 150),
        (361, 649, 151, 200),
        (650, 1249, 201, 300),
        (1250, 2049, 301, 400),
        (2050, 4049, 401, 500),
    ),
    "so2": (
        (0, 35, 0, 50),
        (36, 75, 51, 100),
        (76, 185, 101, 150),
        (186, 304, 151, 200),
        (305, 604, 201, 300),
        (605, 804, 301, 400),
        (805, 1004, 401, 500),
    ),
    "co": (
        (0.0, 4.4, 0, 50),
        (4.5, 9.4, 51, 100),
        (9.5, 12.4, 101, 150),
        (12.5, 15.4, 151, 200),
        (15.5, 30.4, 201, 300),
        (30.5, 40.4, 301, 400),
        (40.5, 50.4, 401, 500),
    ),
}


def _parse_datetime(raw: str) -> datetime:
    raw = raw.strip()
    for fmt in ISO_FORMATS:
        try:
            dt = datetime.strptime(raw, fmt)
            break
        except ValueError:
            continue
    else:
        raise ValueError(f"Unsupported datetime format: {raw}")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


def calculate_individual_aqi(concentration: float, pollutant: str) -> Optional[float]:
    if pollutant not in AQI_BREAKPOINTS or concentration is None:
        return None

    for c_low, c_high, i_low, i_high in AQI_BREAKPOINTS[pollutant]:
        if c_low <= concentration <= c_high:
            return (i_high - i_low) / (c_high - c_low) * (concentration - c_low) + i_low
    return None


def calculate_composite_aqi(row: Dict[str, str]) -> Optional[float]:
    aqi_values: List[float] = []
    for pollutant in AQI_BREAKPOINTS:
        raw_value = row.get(pollutant)
        if raw_value in (None, ""):
            continue
        try:
            concentration = float(raw_value)
        except ValueError:
            continue
        aqi = calculate_individual_aqi(concentration, pollutant)
        if aqi is not None:
            aqi_values.append(aqi)
    if not aqi_values:
        return None
    return max(aqi_values)


def read_station_readings(csv_path: Path) -> Iterable[StationReading]:
    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        required_columns = {"station_id", "station_name", "latitude", "longitude", "timestamp"}
        missing = required_columns - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV is missing required columns: {', '.join(sorted(missing))}")

        for row in reader:
            aqi = calculate_composite_aqi(row)
            if aqi is None:
                continue
            try:
                yield StationReading(
                    station_id=row["station_id"],
                    station_name=row.get("station_name", row["station_id"]),
                    latitude=float(row["latitude"]),
                    longitude=float(row["longitude"]),
                    timestamp=_parse_datetime(row["timestamp"]),
                    aqi=aqi,
                )
            except ValueError as exc:  # pragma: no cover - defensive
                raise ValueError(f"Invalid row for station {row.get('station_id')}: {exc}") from exc


def aggregate_by_timestamp(readings: Iterable[StationReading]) -> List[Dict[str, object]]:
    grouped: Dict[Tuple[str, datetime], List[StationReading]] = defaultdict(list)
    for reading in readings:
        key = (reading.station_id, reading.timestamp)
        grouped[key].append(reading)

    aggregated: List[Dict[str, object]] = []
    for (station_id, timestamp), station_readings in grouped.items():
        # currently there's one reading per timestamp, but averaging keeps the function
        # robust to potential duplicates or overlapping windows.
        avg_aqi = sum(r.aqi for r in station_readings) / len(station_readings)
        base = station_readings[0]
        aggregated.append(
            {
                "station_id": station_id,
                "station_name": base.station_name,
                "latitude": base.latitude,
                "longitude": base.longitude,
                "timestamp": base.timestamp.isoformat().replace("+00:00", "Z"),
                "aqi": round(avg_aqi, 2),
            }
        )

    aggregated.sort(key=lambda item: item["timestamp"])  # stable ordering for deterministic builds
    return aggregated


def write_json(data: List[Dict[str, object]], output_path: Path) -> None:
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def process(csv_path: Path, output_path: Path) -> int:
    readings = list(read_station_readings(csv_path))
    aggregated = aggregate_by_timestamp(readings)
    write_json(aggregated, output_path)
    return len(aggregated)


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Convert raw pollutant data into AQI heatmap JSON")
    parser.add_argument("csv", type=Path, help="Path to the raw pollutant CSV file")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/aggregated_aqi.json"),
        help="Destination for the aggregated JSON (default: data/aggregated_aqi.json)",
    )

    args = parser.parse_args(argv)
    count = process(args.csv, args.output)
    print(f"Wrote {count} aggregated readings to {args.output}")


if __name__ == "__main__":
    main()
