"""
verify_noaa_isd.py – Download NOAA ISD hourly weather data near the Holiday
Farm ignition point (Eugene Airport, OR) for August–September 2020.

NOAA ISD (Integrated Surface Database):
  https://www.ncei.noaa.gov/products/land-based-station/integrated-surface-database

Station used: Eugene Airport (EUG)
  USAF: 726930 | WBAN: 24221 | Distance from ignition: ~56 km (closest full record)

Variables extracted:
  - wind_speed_m_s       (from ISD field WND)
  - wind_gust_m_s        (from ISD field WND peak, if available)
  - air_temp_C           (from ISD field TMP)
  - dew_point_C          (from ISD field DEW)
  - relative_humidity_pct (calculated from temp and dew point)
  - precip_mm_1h         (from ISD field AA1, if available)

Manual fallback:
  If the NCEI CDO API is unavailable, download ISD data directly:
  URL: https://www.ncei.noaa.gov/data/global-hourly/access/2020/726930-24221.csv
  Place in: gridspark-ai/data/raw/726930-24221.csv
"""

import sys
import math
import logging
from io import StringIO
from pathlib import Path

import requests
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (
    NOAA_ISD_STATION_ID, NOAA_ISD_YEAR,
    DATA_RAW, DATA_PROCESSED, NOAA_OUT,
)
from build_feasibility_matrix import update_feasibility_field

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# NCEI global-hourly direct CSV URL
ISD_CSV_URL = (
    f"https://www.ncei.noaa.gov/data/global-hourly/access/"
    f"{NOAA_ISD_YEAR}/{NOAA_ISD_STATION_ID}.csv"
)

LOCAL_FILE = DATA_RAW / f"{NOAA_ISD_STATION_ID}.csv"

# Focus window around the ignition event
FOCUS_START = f"{NOAA_ISD_YEAR}-08-01"
FOCUS_END = f"{NOAA_ISD_YEAR}-09-30"


def dewpoint_to_rh(temp_c: float, dew_c: float) -> float:
    """Estimate relative humidity using Magnus approximation."""
    a, b = 17.625, 243.04
    gamma_d = (a * dew_c) / (b + dew_c)
    gamma_t = (a * temp_c) / (b + temp_c)
    rh = 100.0 * math.exp(gamma_d - gamma_t)
    return round(min(max(rh, 0), 100), 1)


def parse_isd_csv(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parse NCEI global-hourly CSV (ISD format).
    Relevant fields vary by station; we gracefully skip missing ones.
    """
    out = pd.DataFrame()

    # Timestamp
    date_col = next((c for c in df.columns if c.upper() in ("DATE", "DATETIME")), None)
    if date_col is None:
        raise ValueError("No DATE column found in ISD CSV.")
    out["datetime_utc"] = pd.to_datetime(df[date_col], errors="coerce", utc=True)
    out = out.dropna(subset=["datetime_utc"])

    # Wind speed – WND field: direction,dir_quality,obs_type,speed(m/s*10),speed_quality
    if "WND" in df.columns:
        wnd = df["WND"].str.split(",", expand=True)
        # speed is column index 3 (m/s × 10), 9999 = missing
        out["wind_speed_m_s"] = pd.to_numeric(wnd[3], errors="coerce").replace(9999, pd.NA) / 10
    else:
        out["wind_speed_m_s"] = pd.NA

    # Temperature – TMP field: temp(C*10),quality
    if "TMP" in df.columns:
        tmp = df["TMP"].str.split(",", expand=True)
        out["air_temp_C"] = pd.to_numeric(tmp[0], errors="coerce").replace(9999, pd.NA) / 10
    else:
        out["air_temp_C"] = pd.NA

    # Dew point – DEW field: dew(C*10),quality
    if "DEW" in df.columns:
        dew = df["DEW"].str.split(",", expand=True)
        out["dew_point_C"] = pd.to_numeric(dew[0], errors="coerce").replace(9999, pd.NA) / 10
    else:
        out["dew_point_C"] = pd.NA

    # Relative humidity (derived)
    def safe_rh(row):
        if pd.isna(row["air_temp_C"]) or pd.isna(row["dew_point_C"]):
            return pd.NA
        return dewpoint_to_rh(row["air_temp_C"], row["dew_point_C"])

    out["relative_humidity_pct"] = out.apply(safe_rh, axis=1)

    # Precipitation – AA1 field (hourly liquid precip): period,depth(mm*10),condition,quality
    if "AA1" in df.columns:
        aa1 = df["AA1"].str.split(",", expand=True)
        out["precip_mm_1h"] = pd.to_numeric(aa1[1], errors="coerce").replace(9999, pd.NA) / 10
    else:
        out["precip_mm_1h"] = pd.NA

    # Wind gust – not always present in ISD CSV, mark NA
    out["wind_gust_m_s"] = pd.NA

    return out


def load_local_isd() -> pd.DataFrame | None:
    if LOCAL_FILE.exists():
        log.info("Using local ISD file: %s", LOCAL_FILE)
        try:
            df = pd.read_csv(LOCAL_FILE, low_memory=False)
            return parse_isd_csv(df)
        except Exception as exc:
            log.warning("Failed to parse local ISD file: %s", exc)
    return None


def download_isd() -> pd.DataFrame | None:
    log.info("Downloading NOAA ISD from: %s", ISD_CSV_URL)
    try:
        resp = requests.get(ISD_CSV_URL, timeout=120)
        resp.raise_for_status()
        df = pd.read_csv(StringIO(resp.text), low_memory=False)
        log.info("Downloaded %d rows from NCEI.", len(df))
        return parse_isd_csv(df)
    except requests.exceptions.RequestException as exc:
        log.warning("NCEI download failed: %s", exc)
        return None


def run():
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)

    # Try local file first, then download
    parsed = load_local_isd() or download_isd()

    if parsed is None:
        msg = (
            "\n"
            "=================================================================\n"
            "NOAA ISD DOWNLOAD FAILED — MANUAL FALLBACK\n"
            "=================================================================\n"
            f"Download CSV directly:\n"
            f"  URL: {ISD_CSV_URL}\n"
            f"  Save to: gridspark-ai/data/raw/{NOAA_ISD_STATION_ID}.csv\n"
            "\n"
            "Station: Eugene Airport (EUG)  USAF 726930 / WBAN 24221\n"
            "Alternative: NCEI Climate Data Online (CDO) order:\n"
            "  https://www.ncdc.noaa.gov/cdo-web/\n"
            "  Order type: Global Surface Hourly, Station: 726930, Year: 2020\n"
            "================================================================="
        )
        log.error(msg)
        update_feasibility_field(
            "noaa_isd_status",
            "Manual Check",
            f"NOAA ISD download failed. Manual download from {ISD_CSV_URL}",
        )
        return

    # Filter to focus window
    mask = (parsed["datetime_utc"] >= FOCUS_START) & (parsed["datetime_utc"] <= FOCUS_END)
    parsed = parsed[mask].copy()
    log.info("Rows in Aug–Sep %d window: %d", NOAA_ISD_YEAR, len(parsed))

    if parsed.empty:
        log.warning("No records in the Aug–Sep window after parsing.")
        update_feasibility_field(
            "noaa_isd_status",
            "Manual Check",
            "ISD data downloaded but no records in Aug–Sep 2020 window.",
        )
        return

    # Save
    parsed.to_csv(NOAA_OUT, index=False)
    log.info("Saved NOAA ISD data to %s", NOAA_OUT)

    # Summary around ignition date (Sep 7)
    ignition_window = parsed[
        (parsed["datetime_utc"] >= "2020-09-07") &
        (parsed["datetime_utc"] < "2020-09-08")
    ]
    log.info("Records on ignition date (Sep 7 UTC): %d", len(ignition_window))
    if not ignition_window.empty:
        log.info(
            "Sep 7 summary — wind speed (m/s): mean=%.1f max=%.1f | temp (C): mean=%.1f | RH (%%): mean=%.1f",
            ignition_window["wind_speed_m_s"].mean(),
            ignition_window["wind_speed_m_s"].max(),
            ignition_window["air_temp_C"].mean(),
            ignition_window["relative_humidity_pct"].mean(),
        )

    status = "Pass"
    notes = (
        f"NOAA ISD (station {NOAA_ISD_STATION_ID}) downloaded. "
        f"{len(parsed)} hourly records in Aug–Sep {NOAA_ISD_YEAR}. "
        "Variables: wind_speed, air_temp, dew_point, relative_humidity, precip."
    )
    update_feasibility_field("noaa_isd_status", status, notes)
    print(f"\nNOAA ISD status: {status}")
    print(f"Notes: {notes}")


if __name__ == "__main__":
    run()
