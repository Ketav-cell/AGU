"""
build_training_table_schema.py – Create a blank schema CSV that defines the
expected column layout for the GridSpark AI training table.

This schema is a design artifact only. No real data is written here.
Actual feature extraction follows after all feasibility checks pass.
"""

import sys
import csv
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import MODEL_SCHEMA_CSV

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

SCHEMA = [
    {
        "column": "sample_id",
        "dtype": "str",
        "source": "generated",
        "description": "Unique row identifier (county_event_buffer_corridor_date)",
    },
    {
        "column": "county",
        "dtype": "str",
        "source": "config",
        "description": "County name (e.g. Lane County)",
    },
    {
        "column": "event_name",
        "dtype": "str",
        "source": "config",
        "description": "Fire event name (e.g. Holiday Farm Fire)",
    },
    {
        "column": "date",
        "dtype": "date",
        "source": "NOAA ISD",
        "description": "Observation date (YYYY-MM-DD)",
    },
    {
        "column": "buffer_m",
        "dtype": "int",
        "source": "config",
        "description": "Buffer distance in meters (1000, 3000, or 5000)",
    },
    {
        "column": "corridor_id",
        "dtype": "str",
        "source": "HIFLD",
        "description": "HIFLD transmission line segment ID",
    },
    {
        "column": "distance_to_transmission_line_m",
        "dtype": "float",
        "source": "HIFLD + spatial join",
        "description": "Distance from grid sample point to nearest HIFLD transmission line",
    },
    {
        "column": "ndvi_mean",
        "dtype": "float",
        "source": "Sentinel-2 B8/B4 (10 m)",
        "description": "Mean NDVI within sample buffer — proxy for vegetation density",
    },
    {
        "column": "ndmi_mean",
        "dtype": "float",
        "source": "Sentinel-2 B8/B11 (10–20 m)",
        "description": "Mean NDMI — normalized difference moisture index; lower = drier fuel",
    },
    {
        "column": "nbr_mean",
        "dtype": "float",
        "source": "Sentinel-2 B8/B12 (10–20 m)",
        "description": "Mean NBR — normalized burn ratio; used pre-fire as fuel-load proxy",
    },
    {
        "column": "wind_speed",
        "dtype": "float",
        "source": "NOAA ISD",
        "description": "Hourly wind speed (m/s) at nearest ISD station",
    },
    {
        "column": "wind_gust",
        "dtype": "float",
        "source": "NOAA ISD",
        "description": "Hourly peak wind gust (m/s) if available; else NaN",
    },
    {
        "column": "temperature",
        "dtype": "float",
        "source": "NOAA ISD",
        "description": "Air temperature (°C)",
    },
    {
        "column": "dew_point",
        "dtype": "float",
        "source": "NOAA ISD",
        "description": "Dew point temperature (°C)",
    },
    {
        "column": "relative_humidity",
        "dtype": "float",
        "source": "derived (Magnus formula)",
        "description": "Relative humidity (%) derived from temp and dew point",
    },
    {
        "column": "precipitation",
        "dtype": "float",
        "source": "NOAA ISD AA1",
        "description": "1-hour precipitation accumulation (mm); NaN if not reported",
    },
    {
        "column": "ignition_label",
        "dtype": "int",
        "source": "FPA-FOD / WFIGS",
        "description": "Binary label: 1 = known ignition within buffer, 0 = no ignition",
    },
    {
        "column": "label_source",
        "dtype": "str",
        "source": "FPA-FOD / WFIGS",
        "description": "Dataset from which the label was derived",
    },
    {
        "column": "notes",
        "dtype": "str",
        "source": "generated",
        "description": "Free-text quality notes (e.g. cloud contamination, gap-filled weather)",
    },
]


def run():
    MODEL_SCHEMA_CSV.parent.mkdir(parents=True, exist_ok=True)

    with open(MODEL_SCHEMA_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["column", "dtype", "source", "description"])
        writer.writeheader()
        writer.writerows(SCHEMA)

    log.info("Schema written to %s  (%d columns)", MODEL_SCHEMA_CSV, len(SCHEMA))

    print(f"\nTraining table schema saved to: {MODEL_SCHEMA_CSV}")
    print(f"Columns defined: {len(SCHEMA)}")
    print("\nColumn list:")
    for row in SCHEMA:
        print(f"  {row['column']:40s} [{row['dtype']}]  — {row['source']}")


if __name__ == "__main__":
    run()
