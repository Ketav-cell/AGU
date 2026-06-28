"""
generate_aoi.py – Create 1 km, 3 km, and 5 km buffer polygons around
the Holiday Farm Fire ignition anchor and export to GeoJSON.
"""

import sys
import json
import logging
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point, mapping

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (
    IGNITION_LAT, IGNITION_LON,
    BUFFER_DISTANCES_M, CRS_GEO, CRS_PROJ,
    OUTPUTS, AOI_GEOJSON, FIRE_NAME, COUNTY,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


def run():
    OUTPUTS.mkdir(parents=True, exist_ok=True)

    pt = gpd.GeoDataFrame(
        [{"geometry": Point(IGNITION_LON, IGNITION_LAT),
          "name": "ignition_anchor",
          "description": f"{FIRE_NAME} approximate ignition point",
          "lat": IGNITION_LAT,
          "lon": IGNITION_LON}],
        crs=CRS_GEO,
    )
    pt_proj = pt.to_crs(CRS_PROJ)

    features = []

    # Ignition point
    pt_geo = pt.to_crs(CRS_GEO)
    features.append({
        "type": "Feature",
        "properties": {
            "name": "ignition_anchor",
            "fire": FIRE_NAME,
            "county": COUNTY,
            "lat": IGNITION_LAT,
            "lon": IGNITION_LON,
            "buffer_m": 0,
            "note": "Approximate ignition anchor — not a certified exact point",
        },
        "geometry": mapping(pt_geo.geometry.values[0]),
    })

    # Buffer polygons
    for buf_m in BUFFER_DISTANCES_M:
        buf_proj = pt_proj.copy()
        buf_proj["geometry"] = buf_proj.buffer(buf_m)
        buf_geo = buf_proj.to_crs(CRS_GEO)
        poly = buf_geo.geometry.values[0]

        features.append({
            "type": "Feature",
            "properties": {
                "name": f"aoi_{buf_m}m",
                "fire": FIRE_NAME,
                "county": COUNTY,
                "buffer_m": buf_m,
                "buffer_km": buf_m / 1000,
            },
            "geometry": mapping(poly),
        })
        log.info("Buffer %d m: %d vertices", buf_m, len(poly.exterior.coords))

    geojson = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "features": features,
    }

    with open(AOI_GEOJSON, "w") as f:
        json.dump(geojson, f, indent=2)

    log.info("AOI GeoJSON saved to %s  (%d features)", AOI_GEOJSON, len(features))
    print(f"\nAOI GeoJSON: {AOI_GEOJSON}")
    print(f"Features: {len(features)} (1 anchor point + {len(BUFFER_DISTANCES_M)} buffers)")


if __name__ == "__main__":
    run()
