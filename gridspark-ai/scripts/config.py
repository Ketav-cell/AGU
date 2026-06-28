"""
GridSpark AI – Central configuration for Holiday Farm Fire feasibility prototype.

All coordinates, dates, and paths are defined here so every script and
notebook can import a single source of truth.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Project root
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Ignition anchor – Holiday Farm Fire, Lane County OR
# Source: InciWeb / IRWIN / FPA-FOD approximate
# ---------------------------------------------------------------------------
IGNITION_LAT = 44.172
IGNITION_LON = -122.231
IGNITION_DATE = "2020-09-07"
IGNITION_TIME_LOCAL = "20:20 PDT"

COUNTY = "Lane County"
STATE = "Oregon"
STATE_ABBR = "OR"
FIRE_NAME = "Holiday Farm Fire"
FIRE_YEAR = 2020

# ---------------------------------------------------------------------------
# Area-of-interest buffers (meters, EPSG:3857 / UTM)
# ---------------------------------------------------------------------------
BUFFER_DISTANCES_M = [1000, 3000, 5000]

# ---------------------------------------------------------------------------
# Sentinel-2 pre-fire window
# ---------------------------------------------------------------------------
S2_START_DATE = "2020-08-20"
S2_END_DATE = "2020-09-06"          # exclusive end for GEE
S2_CLOUD_PCT_MAX = 10               # percent

# ---------------------------------------------------------------------------
# NOAA ISD
# ---------------------------------------------------------------------------
# Eugene Airport (EUG) – WBAN 24221 / USAF 726930  (~56 km from ignition)
# Closest reliable full-record station.
NOAA_ISD_STATION_ID = "726930-24221"
NOAA_ISD_YEAR = 2020
NOAA_ISD_MONTH_START = 8
NOAA_ISD_MONTH_END = 9

# ---------------------------------------------------------------------------
# HIFLD
# ---------------------------------------------------------------------------
HIFLD_TRANSMISSION_URL = (
    "https://services1.arcgis.com/Hp6G80Pky0om7QvQ/arcgis/rest/services/"
    "Electric_Power_Transmission_Lines/FeatureServer/0/query"
)

# ---------------------------------------------------------------------------
# FPA-FOD expected filename(s) in data/raw/
# ---------------------------------------------------------------------------
FPA_FOD_CANDIDATES = [
    "FPA_FOD_20221014.gpkg",
    "FPA_FOD_20221014.gdb",
    "FPA_FOD_20210617.gpkg",
    "FPA_FOD_20210617.gdb",
    "FPA_FOD.csv",
    "RDS-2013-0009.5_GPKG.zip",
]

# ---------------------------------------------------------------------------
# Fire perimeter expected filename(s) in data/raw/
# ---------------------------------------------------------------------------
PERIMETER_CANDIDATES = [
    "mtbs_perims_DD.shp",
    "mtbs_perims_DD.geojson",
    "wfigs_perimeters.geojson",
    "wfigs_perimeters.gpkg",
    "holiday_farm_perimeter.shp",
    "holiday_farm_perimeter.geojson",
]

# ---------------------------------------------------------------------------
# Output paths
# ---------------------------------------------------------------------------
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
OUTPUTS = PROJECT_ROOT / "outputs"
FIGURES = OUTPUTS / "figures"

FEASIBILITY_CSV = OUTPUTS / "feasibility_matrix.csv"
FEASIBILITY_MD = OUTPUTS / "feasibility_matrix.md"
AOI_GEOJSON = OUTPUTS / "lane_county_aoi.geojson"
MODEL_SCHEMA_CSV = OUTPUTS / "model_table_schema.csv"

HIFLD_OUT = DATA_PROCESSED / "hifld_lines_lane.geojson"
FPA_FOD_OUT = DATA_PROCESSED / "fpa_fod_lane_2020_matches.geojson"
PERIMETER_OUT = DATA_PROCESSED / "holiday_farm_perimeter.geojson"
NOAA_OUT = DATA_PROCESSED / "noaa_isd_holiday_farm_sep2020.csv"
S2_FEATURES_OUT = DATA_PROCESSED / "sentinel2_prefire_features.csv"

# ---------------------------------------------------------------------------
# Coordinate reference systems
# ---------------------------------------------------------------------------
CRS_GEO = "EPSG:4326"
CRS_PROJ = "EPSG:32610"             # UTM Zone 10N – Oregon
