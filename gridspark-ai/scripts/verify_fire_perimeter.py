"""
verify_fire_perimeter.py – Locate the Holiday Farm Fire burn perimeter from
MTBS, BAER, or WFIGS data and confirm it intersects the ignition AOI.

Supported local file types: .shp, .geojson, .gpkg

Manual download instructions:

  MTBS (Monitoring Trends in Burn Severity):
    URL: https://mtbs.gov/direct-download
    Download: MTBS Fire Perimeters (All Years) → mtbs_perims_DD.zip
    Place .shp/.dbf/.shx/.prj in: gridspark-ai/data/raw/

  WFIGS (Wildland Fire Interagency Geospatial Services):
    URL: https://data-nifc.opendata.arcgis.com/datasets/wfigs-wildland-fire-perimeters-to-date
    Download GeoJSON or Shapefile.
    Place in: gridspark-ai/data/raw/

  The Holiday Farm Fire (MTBS ID: OR4418512222320200907) burned ~173,000 acres
  in Lane County, OR starting 2020-09-07.
"""

import sys
import logging
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (
    IGNITION_LAT, IGNITION_LON, BUFFER_DISTANCES_M,
    FIRE_NAME, FIRE_YEAR, STATE_ABBR,
    DATA_RAW, DATA_PROCESSED, PERIMETER_CANDIDATES,
    PERIMETER_OUT, CRS_GEO, CRS_PROJ,
)
from build_feasibility_matrix import update_feasibility_field

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# Known MTBS ID for Holiday Farm Fire
MTBS_ID = "OR4418512222320200907"
HOLIDAY_FARM_KEYWORDS = ["holiday farm", "holidayfarm", MTBS_ID.lower()]


def build_aoi(buffer_m=5000):
    pt = gpd.GeoDataFrame(
        geometry=[Point(IGNITION_LON, IGNITION_LAT)], crs=CRS_GEO
    ).to_crs(CRS_PROJ)
    pt["geometry"] = pt.buffer(buffer_m)
    return pt.to_crs(CRS_GEO)


def find_perimeter_file() -> Path | None:
    for name in PERIMETER_CANDIDATES:
        p = DATA_RAW / name
        if p.exists():
            return p
    for pattern in ["*.shp", "*.geojson", "*.gpkg"]:
        matches = list(DATA_RAW.glob(pattern))
        if matches:
            log.info("Found candidate perimeter file via glob: %s", matches[0])
            return matches[0]
    return None


def load_perimeters(path: Path) -> gpd.GeoDataFrame:
    log.info("Loading perimeter file: %s", path)
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        gdf = gdf.set_crs(CRS_GEO)
    return gdf.to_crs(CRS_GEO)


def find_holiday_farm(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Try multiple strategies to locate Holiday Farm Fire records:
    1. Match MTBS Event_ID
    2. Keyword search on fire name columns
    3. Year + state filter, then spatial intersect with AOI
    """
    cols_upper = {c: c.upper() for c in gdf.columns}

    # Strategy 1: MTBS Event_ID
    for col in gdf.columns:
        if "event" in col.lower() or "id" in col.lower():
            mask = gdf[col].astype(str).str.upper() == MTBS_ID.upper()
            if mask.any():
                log.info("Matched Holiday Farm by Event_ID column '%s'.", col)
                return gdf[mask]

    # Strategy 2: Fire name keyword
    for col in gdf.columns:
        if "name" in col.lower() or "fire" in col.lower():
            for kw in HOLIDAY_FARM_KEYWORDS:
                mask = gdf[col].astype(str).str.lower().str.contains(kw, na=False)
                if mask.any():
                    log.info("Matched Holiday Farm by name keyword '%s' in column '%s'.", kw, col)
                    return gdf[mask]

    # Strategy 3: Year + state + spatial intersection
    log.info("Name/ID match failed — trying year + spatial filter.")
    year_col = next((c for c in gdf.columns if "year" in c.lower()), None)
    state_col = next((c for c in gdf.columns if "state" in c.lower()), None)

    sub = gdf.copy()
    if year_col:
        sub = sub[sub[year_col].astype(str) == str(FIRE_YEAR)]
        log.info("After year filter (%d): %d records", FIRE_YEAR, len(sub))
    if state_col:
        sub = sub[sub[state_col].astype(str).str.upper() == STATE_ABBR]
        log.info("After state filter (%s): %d records", STATE_ABBR, len(sub))

    aoi_poly = build_aoi().geometry.values[0]
    sub = sub[sub.geometry.intersects(aoi_poly)]
    log.info("After spatial intersect with 5 km AOI: %d records", len(sub))
    return sub


def run():
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)

    perim_path = find_perimeter_file()

    if perim_path is None:
        msg = (
            "\n"
            "=================================================================\n"
            "FIRE PERIMETER FILE NOT FOUND — MANUAL DOWNLOAD REQUIRED\n"
            "=================================================================\n"
            "Option A — MTBS (recommended for burn severity):\n"
            "  URL: https://mtbs.gov/direct-download\n"
            "  Download: 'MTBS Fire Perimeters (All Years)'\n"
            "  Unzip into: gridspark-ai/data/raw/\n"
            "\n"
            "Option B — WFIGS fire perimeters:\n"
            "  URL: https://data-nifc.opendata.arcgis.com/datasets/\n"
            "       wfigs-wildland-fire-perimeters-to-date\n"
            "  Download GeoJSON → place in gridspark-ai/data/raw/\n"
            "\n"
            "Holiday Farm Fire MTBS ID: OR4418512222320200907\n"
            "================================================================="
        )
        log.error(msg)
        update_feasibility_field(
            "mtbs_wfigs_boundary_status",
            "Manual Check",
            "No perimeter file found in data/raw/. Manual MTBS/WFIGS download required.",
        )
        return

    try:
        gdf = load_perimeters(perim_path)
        log.info("Loaded %d perimeter records from %s", len(gdf), perim_path.name)

        matches = find_holiday_farm(gdf)

        if matches.empty:
            log.warning(
                "Could not isolate Holiday Farm perimeter. "
                "Check that file contains 2020 Oregon records."
            )
            status = "Manual Check"
            notes = (
                f"Perimeter file found ({perim_path.name}) but Holiday Farm not isolated. "
                "Manual filter by MTBS ID OR4418512222320200907 recommended."
            )
        else:
            aoi_poly = build_aoi().geometry.values[0]
            intersects = matches.geometry.intersects(aoi_poly).any()
            log.info("Holiday Farm perimeter intersects 5 km AOI: %s", intersects)

            matches.to_file(PERIMETER_OUT, driver="GeoJSON")
            log.info("Saved perimeter to %s", PERIMETER_OUT)

            if intersects:
                status = "Pass"
                notes = (
                    f"Holiday Farm perimeter found ({len(matches)} polygon(s)), "
                    "intersects 5 km ignition AOI."
                )
            else:
                status = "Manual Check"
                notes = (
                    "Holiday Farm perimeter found but does not intersect 5 km AOI. "
                    "Check ignition anchor coordinates."
                )

        update_feasibility_field("mtbs_wfigs_boundary_status", status, notes)
        print(f"\nFire perimeter status: {status}")
        print(f"Notes: {notes}")

    except Exception as exc:
        log.error("Failed to process perimeter file: %s", exc)
        update_feasibility_field(
            "mtbs_wfigs_boundary_status",
            "Fail",
            f"Error loading perimeter: {exc}",
        )


if __name__ == "__main__":
    run()
