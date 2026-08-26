from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from pathlib import Path

import tifffile
from PIL import Image

from app.schemas.input import ImageFormat, ImageModality

# GeoTIFF tag IDs
_TAG_MODEL_PIXEL_SCALE = 33550
_TAG_MODEL_TIEPOINT = 33922
_TAG_GEO_KEY_DIRECTORY = 34735


@dataclass(frozen=True)
class RasterProbe:
    width: int
    height: int
    band_count: int
    dtype: str
    band_names: list[str] | None
    georeferenced: bool
    crs: str | None
    bounds: list[float] | None
    resolution_x: float | None
    resolution_y: float | None


def extension_to_format(extension: str) -> ImageFormat | None:
    ext = extension.lower().lstrip(".")
    if ext in {"tif", "tiff", "geotiff"}:
        return ImageFormat.GEOTIFF
    if ext == "png":
        return ImageFormat.PNG
    if ext in {"jpg", "jpeg"}:
        return ImageFormat.JPEG
    return None


def sniff_mime(path: Path) -> str | None:
    mime, _ = mimetypes.guess_type(path.name)
    return mime


def _parse_geokeys(geokeys: tuple[int, ...] | list[int] | None) -> str | None:
    if not geokeys or len(geokeys) < 4:
        return None
    # GeoKeyDirectory: header then keys (KeyID, TIFFTagLocation, Count, Value_Offset)
    num_keys = geokeys[3]
    idx = 4
    projected_crs = None
    geographic_crs = None
    for _ in range(num_keys):
        if idx + 3 >= len(geokeys):
            break
        key_id = geokeys[idx]
        count = geokeys[idx + 2]
        value = geokeys[idx + 3]
        if key_id == 3072 and count == 1:  # ProjectedCSTypeGeoKey
            projected_crs = value
        if key_id == 2048 and count == 1:  # GeographicTypeGeoKey
            geographic_crs = value
        idx += 4
    code = projected_crs or geographic_crs
    if code:
        return f"EPSG:{code}"
    return None


def _bounds_from_geotags(
    pixel_scale: tuple[float, float, float] | None,
    tiepoints: tuple[float, ...] | None,
    width: int,
    height: int,
) -> tuple[list[float] | None, float | None, float | None]:
    if not pixel_scale or not tiepoints or len(tiepoints) < 6:
        return None, None, None
    scale_x, scale_y, _ = pixel_scale
    _, _, _, origin_x, origin_y, _ = tiepoints[:6]
    res_x = abs(scale_x)
    res_y = abs(scale_y)
    west = origin_x
    north = origin_y
    east = origin_x + width * scale_x
    south = origin_y + height * scale_y
    min_lon, max_lon = sorted((west, east))
    min_lat, max_lat = sorted((south, north))
    return [min_lon, min_lat, max_lon, max_lat], res_x, res_y


def probe_tiff(path: Path) -> RasterProbe:
    with tifffile.TiffFile(path) as tif:
        page = tif.pages[0]
        shape = page.shape
        if len(shape) == 2:
            height, width = shape
            band_count = 1
        elif len(shape) == 3:
            band_count, height, width = shape
        else:
            raise ValueError("Unsupported TIFF dimensionality")

        dtype = str(page.dtype)
        tags = page.tags

        pixel_scale = None
        tiepoints = None
        geokeys = None
        if _TAG_MODEL_PIXEL_SCALE in tags:
            pixel_scale = tags[_TAG_MODEL_PIXEL_SCALE].value
        if _TAG_MODEL_TIEPOINT in tags:
            tiepoints = tags[_TAG_MODEL_TIEPOINT].value
        if _TAG_GEO_KEY_DIRECTORY in tags:
            geokeys = tags[_TAG_GEO_KEY_DIRECTORY].value

        georeferenced = pixel_scale is not None and tiepoints is not None
        crs = _parse_geokeys(geokeys)
        bounds, res_x, res_y = _bounds_from_geotags(pixel_scale, tiepoints, width, height)

        band_names = None
        if band_count > 1:
            band_names = [f"band_{i + 1}" for i in range(band_count)]

        return RasterProbe(
            width=int(width),
            height=int(height),
            band_count=int(band_count),
            dtype=dtype,
            band_names=band_names,
            georeferenced=georeferenced,
            crs=crs,
            bounds=bounds,
            resolution_x=res_x,
            resolution_y=res_y,
        )


def probe_png_jpeg(path: Path) -> RasterProbe:
    with Image.open(path) as img:
        width, height = img.size
        bands = len(img.getbands()) if hasattr(img, "getbands") else 1
        return RasterProbe(
            width=width,
            height=height,
            band_count=bands,
            dtype="uint8",
            band_names=[f"band_{i + 1}" for i in range(bands)] if bands > 1 else None,
            georeferenced=False,
            crs=None,
            bounds=None,
            resolution_x=None,
            resolution_y=None,
        )


def probe_raster(path: Path, image_format: ImageFormat) -> RasterProbe:
    if image_format in (ImageFormat.GEOTIFF, ImageFormat.TIFF):
        return probe_tiff(path)
    if image_format in (ImageFormat.PNG, ImageFormat.JPEG):
        return probe_png_jpeg(path)
    raise ValueError(f"Unsupported format for probing: {image_format}")


def infer_modality(
    declared: ImageModality | None,
    band_count: int,
    image_format: ImageFormat,
) -> ImageModality:
    if declared is not None:
        return declared
    if band_count >= 4:
        return ImageModality.MULTISPECTRAL
    if image_format in (ImageFormat.PNG, ImageFormat.JPEG):
        return ImageModality.OPTICAL
    return ImageModality.OPTICAL


def is_valid_tiff_header(path: Path) -> bool:
    with path.open("rb") as f:
        header = f.read(4)
    if len(header) < 4:
        return False
    if header[:2] in (b"II", b"MM"):
        return True
    return False


def is_valid_png_header(path: Path) -> bool:
    with path.open("rb") as f:
        return f.read(8) == b"\x89PNG\r\n\x1a\n"


def is_valid_jpeg_header(path: Path) -> bool:
    with path.open("rb") as f:
        return f.read(2) == b"\xff\xd8"
