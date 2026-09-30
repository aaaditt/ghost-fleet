"""Sentinel-1 RTC imagery from Microsoft Planetary Computer, read as small chips.

Scenes are never downloaded whole. `scenes()` caches STAC search results per
corridor and quarter (unsigned item JSON); `read_chip()` signs the VV/VH COG
URLs and reads one window around a point. RTC products are radiometrically
terrain-corrected gamma0 in linear power, 10 m pixels, projected to UTM.

Attribution: contains modified Copernicus Sentinel data, processed by ESA and
Microsoft Planetary Computer (RTC). Access is anonymous.
"""

import json
import os
from functools import lru_cache

import numpy as np
import planetary_computer
import pystac
import pystac_client
import rasterio
from rasterio.warp import transform as warp_transform
from rasterio.windows import Window
from shapely.geometry import Point, shape

from ml import CACHE

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "sentinel-1-rtc"
STAC_CACHE = CACHE / "stac"
CHIP = 160  # pixels at 10 m: covers a 0.01-degree GFW cell with margin

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("GDAL_HTTP_MERGE_CONSECUTIVE_RANGES", "YES")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "4")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "2")
os.environ.setdefault("VSI_CACHE", "TRUE")


@lru_cache(maxsize=1)
def _client():
    return pystac_client.Client.open(STAC_URL)


def scenes(corridor_id, bbox, start, end):
    """All RTC scenes intersecting bbox between start and end (dates), cached."""
    path = STAC_CACHE / f"{corridor_id}_{start}_{end}.json"
    if path.exists():
        feats = json.loads(path.read_text())
    else:
        items = _client().search(collections=[COLLECTION], bbox=bbox, datetime=f"{start}/{end}").item_collection()
        feats = [it.to_dict() for it in items]
        STAC_CACHE.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(feats))
    out = []
    for f in feats:
        out.append({
            "id": f["id"],
            "datetime": f["properties"]["datetime"],
            "date": f["properties"]["datetime"][:10],
            "footprint": shape(f["geometry"]),
            "item": f,
        })
    return out


def scene_for(scene_list, lat, lon, date):
    """The scene acquired on `date` whose footprint contains the point, if any."""
    p = Point(lon, lat)
    hits = [s for s in scene_list if s["date"] == date and s["footprint"].contains(p)]
    return hits[0] if hits else None


def read_chip(scene, lat, lon, size=CHIP):
    """(2, size, size) float32 [VV, VH] around the point, plus geo helpers.

    Returns None if the window falls outside the image. Pixels with no data are NaN.
    """
    item = planetary_computer.sign(pystac.Item.from_dict(scene["item"]))
    bands = []
    meta = None
    for pol in ("vv", "vh"):
        if pol not in item.assets:
            return None
        with rasterio.open(item.assets[pol].href) as src:
            xs, ys = warp_transform("EPSG:4326", src.crs, [lon], [lat])
            row, col = src.index(xs[0], ys[0])
            win = Window(col - size // 2, row - size // 2, size, size)
            arr = src.read(1, window=win, boundless=True, fill_value=0).astype(np.float32)
            nodata = src.nodata
            if nodata is not None:
                arr[arr == nodata] = np.nan
            arr[arr <= 0] = np.nan
            if meta is None:
                meta = {"crs": src.crs.to_string(), "transform": list(src.window_transform(win))[:6]}
            bands.append(arr)
    chip = np.stack(bands)
    if np.isnan(chip[0]).mean() > 0.5:
        return None
    return chip, meta


def pixel_to_lonlat(meta, row, col):
    a, b, c, d, e, f = meta["transform"]
    x = c + a * (col + 0.5) + b * (row + 0.5)
    y = f + d * (col + 0.5) + e * (row + 0.5)
    lons, lats = warp_transform(meta["crs"], "EPSG:4326", [x], [y])
    return lats[0], lons[0]


def to_db(chip):
    """Linear power to decibels, NaN-safe, clipped to a sensible SAR range."""
    with np.errstate(divide="ignore", invalid="ignore"):
        db = 10 * np.log10(chip)
    return np.clip(np.nan_to_num(db, nan=-30.0), -30.0, 10.0)
