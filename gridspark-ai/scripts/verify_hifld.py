"""
verify_hifld.py – Download and spatially filter HIFLD electric transmission
lines for the Holiday Farm Fire AOI (Lane County, OR).

HIFLD Open Data: Electric Power Transmission Lines
https://hifld-geoplatform.opendata.arcgis.com/datasets/electric-power-transmission-lines

NOTE: HIFLD transmission lines represent bulk power infrastructure
(138 kV+). They do NOT represent local distribution poles or service
conductors. Do not infer pole-level modelling from this dataset.
"""

import sys
import json
import time
import logging
from pathlib import Path

import requests
import geopandas as gpd
from shapely.geometry import Point, mapping

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (
    IGNITION_LAT, IGNITION_LON, BUFFER_DISTANCES_M,
    HIFLD_TRANSMISSION_URL, CRS_GEO, CRS_PROJ,
    DATA_RAW, DATA_PROCESSED, HIFLD_OUT, FEASIBILITY_CSV,
)
from build_feasibility_matrix import update_feasibility_field

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# ArcGIS Feature Service page size
PAGE_SIZE = 1000

# Max distance to query (km bounding box)
BBOX_BUFFER_DEG = 0.1  # ~11 km at this latitude


def build_aoi_gdf(buffer_m: int = 5000) -> gpd.GeoDataFrame:
    """Return a GeoDataFrame with a single buffered polygon around ignition."""
    pt = Point(IGNITION_LON, IGNITION_LAT)
    gdf = gpd.GeoDataFrame(geometry=[pt], crs=CRS_GEO)
    gdf_proj = gdf.to_crs(CRS_PROJ)
    gdf_proj["geometry"] = gdf_proj.buffer(buffer_m)
    return gdf_proj.to_crs(CRS_GEO)


def query_hifld_arcgis(aoi_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame | None:
    """
    Query the HIFLD ArcGIS Feature Service using a bounding box spatial filter.
    Returns a GeoDataFrame or None on failure.
    """
    bounds = aoi_gdf.total_bounds  # minx, miny, maxx, maxy
    # Expand envelope by ~0.5 deg in each direction to ensure line endpoints
    # outside the buffer circle but crossing it are included in the query.
    pad = 0.5
    geometry_envelope = {
        "xmin": bounds[0] - pad,
        "ymin": bounds[1] - pad,
        "xmax": bounds[2] + pad,
        "ymax": bounds[3] + pad,
        "spatialReference": {"wkid": 4326},
    }

    # ArcGIS REST accepts comma-separated bbox more reliably than JSON envelope
    bbox = (
        f"{geometry_envelope['xmin']},{geometry_envelope['ymin']},"
        f"{geometry_envelope['xmax']},{geometry_envelope['ymax']}"
    )
    params = {
        "where": "1=1",
        "geometry": bbox,
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "outSR": "4326",
        "f": "geojson",
        "resultOffset": 0,
        "resultRecordCount": PAGE_SIZE,
    }

    all_features = []
    offset = 0
    max_pages = 10

    log.info("Querying HIFLD ArcGIS Feature Service …")
    for page in range(max_pages):
        params["resultOffset"] = offset
        try:
            resp = requests.get(
                HIFLD_TRANSMISSION_URL, params=params, timeout=60
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as exc:
            log.warning("HIFLD request failed: %s", exc)
            return None

        features = data.get("features", [])
        all_features.extend(features)
        log.info("  Page %d: %d features (total so far: %d)", page + 1, len(features), len(all_features))

        if len(features) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        time.sleep(0.5)

    if not all_features:
        log.warning("HIFLD query returned 0 features. May be outside coverage or service down.")
        return None

    gdf = gpd.GeoDataFrame.from_features(all_features, crs=CRS_GEO)
    return gdf


def run():
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)

    aoi_gdf = build_aoi_gdf(buffer_m=5000)
    log.info("AOI built: 5 km buffer around ignition (%.4f, %.4f)", IGNITION_LAT, IGNITION_LON)

    # --- Primary path: ArcGIS REST ---
    gdf = query_hifld_arcgis(aoi_gdf)

    if gdf is not None and not gdf.empty:
        # Clip to the 5 km buffer polygon
        aoi_poly = aoi_gdf.geometry.values[0]
        gdf_clip = gdf[gdf.geometry.intersects(aoi_poly)].copy()
        n = len(gdf_clip)
        log.info("Transmission line segments intersecting 5 km AOI: %d", n)

        if n > 0:
            gdf_clip.to_file(HIFLD_OUT, driver="GeoJSON")
            log.info("Saved to %s", HIFLD_OUT)
            status = "Pass"
            notes = (
                f"{n} HIFLD transmission line segments found within 5 km AOI. "
                "These are bulk-power transmission lines (not distribution poles)."
            )
        else:
            log.warning("No transmission lines within 5 km AOI — check wider area.")
            # Save the wider result anyway
            gdf.to_file(HIFLD_OUT, driver="GeoJSON")
            status = "Pass (no lines in 5 km)"
            notes = (
                "HIFLD API reachable but 0 segments in 5 km AOI. "
                f"Wider bounding-box returned {len(gdf)} features — saved for inspection."
            )
    else:
        log.error(
            "\n"
            "=====================================================================\n"
            "HIFLD AUTO-DOWNLOAD FAILED — MANUAL FALLBACK\n"
            "=====================================================================\n"
            "Download the Electric Power Transmission Lines shapefile manually:\n"
            "  URL: https://hifld-geoplatform.opendata.arcgis.com/datasets/"
            "electric-power-transmission-lines\n"
            "  Click 'Download' → Shapefile or GeoJSON.\n"
            "  Place the file(s) in:  gridspark-ai/data/raw/\n"
            "  Then re-run this script.\n"
            "====================================================================="
        )
        status = "Manual Check"
        notes = "HIFLD ArcGIS REST API unreachable. Manual download required."

    # Update feasibility matrix
    try:
        update_feasibility_field("hifld_grid_status", status, notes)
        log.info("Feasibility matrix updated: hifld_grid_status = %s", status)
    except Exception as exc:
        log.warning("Could not update feasibility matrix: %s", exc)

    print(f"\nHIFLD status: {status}")
    print(f"Notes: {notes}")


if __name__ == "__main__":
    run()
