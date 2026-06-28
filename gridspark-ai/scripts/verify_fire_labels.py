"""
verify_fire_labels.py – Search FPA-FOD (Fire Program Analysis Fire Occurrence
Database) for wildfire ignition records near the Holiday Farm Fire.

IMPORTANT scientific note:
FPA-FOD coordinates are NOT precise ignition points. They are reported or
inferred locations that may carry positional uncertainty of hundreds of meters
to several kilometers. Use buffer sensitivity tests (1 km / 3 km / 5 km)
rather than treating any single coordinate as ground truth.

Data source:
  Short, K.C. (2022). Spatial wildfire occurrence data for the United States,
  1992–2020 (FPA FOD). 6th Ed. USDA Forest Service Research Data Archive.
  https://www.fs.usda.gov/rds/archive/catalog/RDS-2013-0009.6

Manual download instructions:
  1. Go to https://www.fs.usda.gov/rds/archive/catalog/RDS-2013-0009.6
  2. Download the GeoPackage (.gpkg) or ESRI File Geodatabase (.gdb).
  3. Place the file in: gridspark-ai/data/raw/
  4. Re-run this script.
"""

import sys
import logging
from pathlib import Path

import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (
    IGNITION_LAT, IGNITION_LON, BUFFER_DISTANCES_M,
    STATE_ABBR, FIRE_YEAR, FIRE_NAME,
    DATA_RAW, DATA_PROCESSED, FPA_FOD_CANDIDATES, FPA_FOD_OUT,
    CRS_GEO, CRS_PROJ, FEASIBILITY_CSV,
)
from build_feasibility_matrix import update_feasibility_field

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# Columns that hold lat/lon across different FPA-FOD schema versions
LAT_COLS = ["LATITUDE", "lat", "latitude", "Y", "y"]
LON_COLS = ["LONGITUDE", "lon", "longitude", "X", "x"]
STATE_COLS = ["STATE", "state", "STATE_ABBR"]
YEAR_COLS = ["FIRE_YEAR", "fire_year", "YEAR"]
NAME_COLS = ["FIRE_NAME", "fire_name", "INCIDENT_NAME"]


def _find_col(columns, candidates):
    for c in candidates:
        if c in columns:
            return c
    return None


def find_fod_file() -> Path | None:
    """Return the first FPA-FOD file found in data/raw/."""
    for name in FPA_FOD_CANDIDATES:
        p = DATA_RAW / name
        if p.exists():
            return p
    # Also do a glob search
    for pattern in ["*.gpkg", "*.gdb", "FPA_FOD*.csv", "RDS*.zip"]:
        matches = list(DATA_RAW.glob(pattern))
        if matches:
            return matches[0]
    return None


def load_fod(path: Path) -> gpd.GeoDataFrame:
    """Load FPA-FOD from GeoPackage, GDB, or CSV."""
    suffix = path.suffix.lower()
    log.info("Loading FPA-FOD from %s", path)

    if suffix in (".gpkg", ".gdb"):
        gdf = gpd.read_file(path)
        return gdf
    elif suffix == ".csv":
        df = pd.read_csv(path, low_memory=False)
        lat_col = _find_col(df.columns, LAT_COLS)
        lon_col = _find_col(df.columns, LON_COLS)
        if lat_col is None or lon_col is None:
            raise ValueError(f"Cannot find lat/lon columns in CSV. Columns: {list(df.columns)[:20]}")
        df = df.dropna(subset=[lat_col, lon_col])
        geometry = [Point(xy) for xy in zip(df[lon_col], df[lat_col])]
        gdf = gpd.GeoDataFrame(df, geometry=geometry, crs=CRS_GEO)
        return gdf
    elif suffix == ".zip":
        log.info("ZIP file detected — attempting to read via geopandas.")
        gdf = gpd.read_file(f"zip://{path}")
        return gdf
    else:
        raise ValueError(f"Unsupported file type: {suffix}")


def filter_fod(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Filter to Oregon 2020 records."""
    cols = list(gdf.columns)

    state_col = _find_col(cols, STATE_COLS)
    year_col = _find_col(cols, YEAR_COLS)

    if state_col:
        gdf = gdf[gdf[state_col].str.upper() == STATE_ABBR.upper()]
        log.info("After STATE filter (%s): %d records", STATE_ABBR, len(gdf))
    else:
        log.warning("No STATE column found — skipping state filter.")

    if year_col:
        gdf = gdf[gdf[year_col].astype(str) == str(FIRE_YEAR)]
        log.info("After FIRE_YEAR filter (%d): %d records", FIRE_YEAR, len(gdf))
    else:
        log.warning("No FIRE_YEAR column found — skipping year filter.")

    return gdf


def spatial_match(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Return records within 5 km of the ignition anchor."""
    if gdf.crs is None:
        gdf = gdf.set_crs(CRS_GEO)
    gdf_geo = gdf.to_crs(CRS_GEO)
    gdf_proj = gdf_geo.to_crs(CRS_PROJ)

    ignition_pt = gpd.GeoDataFrame(
        geometry=[Point(IGNITION_LON, IGNITION_LAT)], crs=CRS_GEO
    ).to_crs(CRS_PROJ)
    anchor = ignition_pt.geometry.values[0]

    max_buf = max(BUFFER_DISTANCES_M)
    gdf_proj["dist_to_ignition_m"] = gdf_proj.geometry.distance(anchor)
    matches = gdf_proj[gdf_proj["dist_to_ignition_m"] <= max_buf].copy()
    return matches.to_crs(CRS_GEO)


def run():
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)

    fod_path = find_fod_file()

    if fod_path is None:
        msg = (
            "\n"
            "=================================================================\n"
            "FPA-FOD FILE NOT FOUND — MANUAL DOWNLOAD REQUIRED\n"
            "=================================================================\n"
            "Download the FPA Fire Occurrence Database:\n"
            "  URL: https://www.fs.usda.gov/rds/archive/catalog/RDS-2013-0009.6\n"
            "  File: RDS-2013-0009.6_GPKG.zip  (GeoPackage, ~300 MB)\n"
            "  Place in: gridspark-ai/data/raw/\n"
            "  Then re-run: python scripts/verify_fire_labels.py\n"
            "================================================================="
        )
        log.error(msg)
        update_feasibility_field(
            "fpa_fod_ignition_status",
            "Manual Check",
            "FPA-FOD file not found in data/raw/. Manual download required.",
        )
        return

    try:
        gdf = load_fod(fod_path)
        log.info("Loaded %d total records from FPA-FOD.", len(gdf))

        gdf_or = filter_fod(gdf)
        matches = spatial_match(gdf_or)

        n = len(matches)
        log.info("FPA-FOD records within %d m of ignition anchor: %d", max(BUFFER_DISTANCES_M), n)

        # Log name column if available
        name_col = _find_col(list(matches.columns), NAME_COLS)
        if name_col and n > 0:
            log.info("Matching fire names: %s", matches[name_col].tolist())

        if n > 0:
            matches.to_file(FPA_FOD_OUT, driver="GeoJSON")
            log.info("Saved matches to %s", FPA_FOD_OUT)
            status = "Pass"
            notes = (
                f"{n} FPA-FOD record(s) within {max(BUFFER_DISTANCES_M)} m of ignition anchor. "
                "Treat coordinates as approximate labels only."
            )
        else:
            log.warning("No FPA-FOD records found near ignition anchor. "
                        "Holiday Farm may be in a different record or coordinates differ.")
            status = "Manual Check"
            notes = (
                "FPA-FOD loaded but 0 records within 5 km of ignition anchor. "
                "Holiday Farm Fire coordinates may differ from anchor — manual review needed."
            )

        update_feasibility_field("fpa_fod_ignition_status", status, notes)
        print(f"\nFPA-FOD status: {status}")
        print(f"Notes: {notes}")

    except Exception as exc:
        log.error("Failed to process FPA-FOD: %s", exc)
        update_feasibility_field(
            "fpa_fod_ignition_status",
            "Fail",
            f"Error processing FPA-FOD: {exc}",
        )


if __name__ == "__main__":
    run()
