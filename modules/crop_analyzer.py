# modules/crop_analyzer.py
import asyncio
from datetime import datetime, timedelta
from io import BytesIO
from typing import List, Tuple, Dict

import numpy as np
from PIL import Image
from shapely.geometry import Polygon
import rasterio
import rasterio.windows
import rasterio.enums
import planetary_computer
from pystac_client import Client
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"

def ndvi_to_rgb_array(ndvi_arr: np.ndarray) -> np.ndarray:
    """
    Convert NDVI array (-1..1) to RGB uint8 array HxWx3.
    Uses a simple green-yellow-red ramp.
    """
    nd = np.clip(ndvi_arr, -0.2, 0.8)
    nd = (nd + 0.2) / 1.0  # 0..1
    h, w = nd.shape
    rgb = np.zeros((h, w, 3), dtype=np.uint8)

    # vectorized ramp: below 0.33 -> red->yellow, above -> yellow->green
    # compute channels
    r = np.zeros_like(nd)
    g = np.zeros_like(nd)
    b = np.zeros_like(nd)

    # red->yellow (0..0.5): red decreases, green increases
    mask1 = nd <= 0.5
    r[mask1] = 255
    g[mask1] = (nd[mask1] / 0.5 * 200).astype(np.uint8) + 40  # 40..240

    # yellow->green (0.5..1): red decreases to 0, green increases to 255
    mask2 = nd > 0.5
    r[mask2] = ((1 - (nd[mask2] - 0.5) / 0.5) * 120).astype(np.uint8)
    g[mask2] = (150 + (nd[mask2] - 0.5) / 0.5 * 105).astype(np.uint8)

    rgb[:, :, 0] = r
    rgb[:, :, 1] = g
    rgb[:, :, 2] = b
    return rgb

class CropAnalyzer:
    def __init__(self):
        try:
            # STAC client with planetary_computer modifier to sign assets on demand
            self.stac = Client.open(STAC_URL, modifier=planetary_computer.sign_inplace)
            logger.info("Planetary Computer STAC initialized")
        except Exception as e:
            logger.error("Failed to init STAC client: %s", e)
            self.stac = None

    async def get_ndvi_polygon(self, coords: List[Tuple[float, float]], lang: str = "uz") -> Dict:
        """
        coords: list of (lat, lon) tuples (4 corners or more)
        returns: dict with keys:
          - text (Markdown-ready)
          - ndvi_png (PIL.Image)  -> small real mini-image (optional)
          - ndvi_mean, ndvi_median, ndvi_std, stress_pct, healthy_pct, cloud_coverage
          - source_item_id
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_ndvi_polygon_sync, coords, lang)

    def _get_ndvi_polygon_sync(self, coords: List[Tuple[float, float]], lang: str = "uz") -> Dict:
        if not self.stac:
            txt = "❌ Planetary Computer STAC not initialized." if lang != "uz" else "❌ STAC klient ishga tushmadi."
            return {"text": txt}

        try:
            # 1) Build polygon and bbox
            poly = Polygon([(lon, lat) for lat, lon in coords])
            minx, miny, maxx, maxy = poly.bounds  # lon_min, lat_min, lon_max, lat_max

            # 2) STAC search (last 14 days, prefer low cloud)
            end = datetime.utcnow()
            start = end - timedelta(days=14)
            time_range = f"{start.strftime('%Y-%m-%d')}/{end.strftime('%Y-%m-%d')}"

            search = self.stac.search(
                collections=["sentinel-2-l2a"],
                bbox=[minx, miny, maxx, maxy],
                datetime=time_range,
                query={"eo:cloud_cover": {"lte": 60}},
                max_items=8
            )
            items = list(search.get_items())

            if not items:
                # No items found
                msg = ("❌ Sun'iy yo'ldosh tasvirlari topilmadi (oxirgi 14 kun)." if lang == "uz"
                       else "❌ No satellite imagery found (last 14 days).")
                return {"text": msg}

            # choose best by eo:cloud_cover
            best_item = min(items, key=lambda it: float(it.properties.get("eo:cloud_cover", 100.0)))
            cloud_cov = float(best_item.properties.get("eo:cloud_cover", 0.0))
            item_datetime = best_item.properties.get("datetime", "")[:19]

            # ensure B04/B08 present
            assets = best_item.assets
            if "B04" not in assets or "B08" not in assets:
                msg = ("❌ Kerakli bantlar topilmadi." if lang == "uz" else "❌ Required bands (B04/B08) not found.")
                return {"text": msg}

            # sign URLs
            b04_href = planetary_computer.sign(assets["B04"].href)
            b08_href = planetary_computer.sign(assets["B08"].href)

            # 3) Read minimal window covering polygon using rasterio
            with rasterio.Env():
                with rasterio.open(b08_href) as src_nir:
                    with rasterio.open(b04_href) as src_red:
                        # transform polygon lon/lat to dataset CRS using src bounds and transform if needed
                        # We'll compute window by mapping lon/lat to dataset coords via index() (which expects x=lon,y=lat)
                        # Buffer a bit (0.0005 deg) to ensure coverage
                        buffer_deg = max((maxx - minx), (maxy - miny)) * 0.05
                        left = minx - buffer_deg
                        right = maxx + buffer_deg
                        top = maxy + buffer_deg
                        bottom = miny - buffer_deg

                        # get row/col for corners
                        try:
                            row1, col1 = src_nir.index(left, top)
                            row2, col2 = src_nir.index(right, bottom)
                        except Exception:
                            # fallback: use full scene
                            row1, col1 = 0, 0
                            row2, col2 = src_nir.height, src_nir.width

                        row_start, row_stop = sorted([row1, row2])
                        col_start, col_stop = sorted([col1, col2])

                        n_rows = row_stop - row_start
                        n_cols = col_stop - col_start

                        if n_rows <= 0 or n_cols <= 0:
                            raise ValueError("Computed reading window is empty.")

                        # downsample factor to target max dimension ~ 512
                        max_dim = 512
                        decimate = max(1, int(max(n_rows, n_cols) / max_dim))

                        out_rows = max(1, int(n_rows / decimate))
                        out_cols = max(1, int(n_cols / decimate))

                        window = rasterio.windows.Window(col_start, row_start, n_cols, n_rows)

                        nir = src_nir.read(1,
                                           out_shape=(out_rows, out_cols),
                                           window=window,
                                           resampling=rasterio.enums.Resampling.bilinear).astype('float32')
                        red = src_red.read(1,
                                           out_shape=nir.shape,
                                           window=window,
                                           resampling=rasterio.enums.Resampling.bilinear).astype('float32')

                        # 4) compute NDVI
                        np.seterr(divide='ignore', invalid='ignore')
                        denom = (nir + red)
                        denom[denom == 0] = np.nan
                        ndvi = (nir - red) / denom
                        ndvi = np.nan_to_num(ndvi, nan=-1.0)

                        # 5) stats
                        ndvi_mean = float(np.nanmean(ndvi))
                        ndvi_median = float(np.nanmedian(ndvi))
                        ndvi_std = float(np.nanstd(ndvi))

                        # class percentages: healthy (>0.4), moderate (0.2-0.4), stress (<0.2)
                        healthy_mask = ndvi >= 0.4
                        moderate_mask = (ndvi >= 0.2) & (ndvi < 0.4)
                        stress_mask = ndvi < 0.2

                        total_px = ndvi.size
                        healthy_pct = float(np.count_nonzero(healthy_mask)) / total_px * 100.0
                        moderate_pct = float(np.count_nonzero(moderate_mask)) / total_px * 100.0
                        stress_pct = float(np.count_nonzero(stress_mask)) / total_px * 100.0

                        # 6) create mini real image (convert ndvi to RGB)
                        rgb = ndvi_to_rgb_array(ndvi)
                        pil_img = Image.fromarray(rgb)
                        # resize to small square (200x200) for telegram
                        pil_img_small = pil_img.resize((200, 200), Image.BILINEAR)

                        # 7) Build text (Markdown)
                        if lang == "uz":
                            health_label = self._health_label_uz(ndvi_mean)
                            text = (
                                f"🛰 *NDVI Poligon Tahlili*\n\n"
                                f"📅 Sana (tasvir): {item_datetime}\n"
                                f"🌱 O'rtacha NDVI: *{ndvi_mean:.3f}* ({health_label})\n\n"
                                f"📊 Statistika: median={ndvi_median:.3f}, std={ndvi_std:.3f}\n"
                                f"🟩 Sog'liq: {healthy_pct:.1f}%   🟨 O'rtacha: {moderate_pct:.1f}%   🟥 Stress: {stress_pct:.1f}%\n"
                                f"☁ Bulutlilik (scene): {cloud_cov:.1f}%\n\n"
                                f"📌 Agronom tavsiya:\n{self._recommendations_uz(ndvi_mean, stress_pct, cloud_cov)}"
                            )
                        else:
                            health_label = self._health_label_ru(ndvi_mean)
                            text = (
                                f"🛰 *NDVI Polygon Analysis*\n\n"
                                f"📅 Date (scene): {item_datetime}\n"
                                f"🌱 Mean NDVI: *{ndvi_mean:.3f}* ({health_label})\n\n"
                                f"📊 Stats: median={ndvi_median:.3f}, std={ndvi_std:.3f}\n"
                                f"🟩 Healthy: {healthy_pct:.1f}%   🟨 Moderate: {moderate_pct:.1f}%   🟥 Stress: {stress_pct:.1f}%\n"
                                f"☁ Cloud cover (scene): {cloud_cov:.1f}%\n\n"
                                f"📌 Agronomic recommendation:\n{self._recommendations_ru(ndvi_mean, stress_pct, cloud_cov)}"
                            )

                        return {
                            "text": text,
                            "ndvi_png": pil_img_small,
                            "ndvi_mean": ndvi_mean,
                            "ndvi_median": ndvi_median,
                            "ndvi_std": ndvi_std,
                            "healthy_pct": healthy_pct,
                            "moderate_pct": moderate_pct,
                            "stress_pct": stress_pct,
                            "cloud_coverage": cloud_cov,
                            "source_item_id": best_item.id
                        }

        except Exception as e:
            logger.exception("NDVI error")
            msg = ("❌ NDVI hisoblashda xatolik: " + str(e)) if lang == "uz" else ("❌ NDVI calculation error: " + str(e))
            return {"text": msg}

    # ---------------- helpers ----------------
    def _health_label_uz(self, ndvi):
        if ndvi >= 0.6:
            return "Juda yaxshi"
        elif ndvi >= 0.4:
            return "Yaxshi"
        elif ndvi >= 0.2:
            return "O'rtacha"
        else:
            return "Yomon"

    def _health_label_ru(self, ndvi):
        if ndvi >= 0.6:
            return "Excellent"
        elif ndvi >= 0.4:
            return "Good"
        elif ndvi >= 0.2:
            return "Moderate"
        else:
            return "Poor"

    def _recommendations_uz(self, ndvi_mean, stress_pct, cloud_cov):
        recs = []
        if ndvi_mean < 0.2 or stress_pct > 30:
            recs.append("⚠️ NDVI juda past yoki stress zonalari katta — maydonni joyida tekshirish, zararkunanda va kasalliklarni aniqlash.")
            recs.append("🧪 Tuproq va foliar test o‘tkazing, zarur bo‘lsa azotli o‘g‘itlar kiriting.")
        elif ndvi_mean < 0.4:
            recs.append("💧 NDVI o'rtacha — sug'orishni sozlang va kuzatuvni davom ettiring.")
        else:
            recs.append("✅ O‘simliklar yaxshi holatda. Rejalarni davom ettiring.")
        if cloud_cov > 30:
            recs.append("☁ Tasvirdagi bulutlilik >30% — natijani ehtiyotkorlik bilan talqin qiling.")
        return "\n".join(recs)

    def _recommendations_ru(self, ndvi_mean, stress_pct, cloud_cov):
        recs = []
        if ndvi_mean < 0.2 or stress_pct > 30:
            recs.append("⚠️ NDVI very low or large stress areas — inspect field on-site for pests/diseases.")
            recs.append("🧪 Perform soil and foliar tests, consider N-fertilization.")
        elif ndvi_mean < 0.4:
            recs.append("💧 NDVI moderate — adjust irrigation and monitor.")
        else:
            recs.append("✅ Vegetation in good state. Continue management.")
        if cloud_cov > 30:
            recs.append("☁ Scene cloud cover >30% — interpret results carefully.")
        return "\n".join(recs)
