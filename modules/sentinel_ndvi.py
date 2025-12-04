"""
Исправленный модуль для запроса NDVI через Sentinel Hub Process API.
Основные правки:
 - Правильная генерация bbox (не точка)
 - Корректная структура запроса (payload) и evalscript
 - Получение токена OAuth и повторное использование при необходимости
 - Подробное логирование ошибок 400/прочих
 - Возвращает numpy array NDVI или None при ошибке

Зависимости: httpx, numpy, rasterio (только если нужно читать GeoTIFF), typing, datetime
"""
import logging
import math
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any

import httpx
import numpy as np

logger = logging.getLogger(__name__)


class SentinelHubError(Exception):
    pass


class SentinelNDVI:
    BASE_URL = "https://services.sentinel-hub.com"
    OAUTH_URL = BASE_URL + "/oauth/token"
    PROCESS_URL = BASE_URL + "/api/v1/process"

    def __init__(self, client_id: str, client_secret: str, instance_id: Optional[str] = None, timeout: int = 30):
        """
        :param client_id: OAuth client id (Sentinel Hub application)
        :param client_secret: OAuth client secret
        :param instance_id: optional custom instance id (if using sentinel-hub instance-based requests)
        :param timeout: HTTP timeout seconds
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.instance_id = instance_id
        self.timeout = timeout
        self._token: Optional[Dict[str, Any]] = None
        self._token_expires_at: Optional[datetime] = None
        self._http = httpx.Client(timeout=self.timeout)

    def close(self) -> None:
        try:
            self._http.close()
        except Exception:
            pass

    def _get_oauth_token(self) -> str:
        """Получить (или переиспользовать) OAuth токен от Sentinel Hub.
        Сохраняем expiry и повторно используем токен, пока он действителен.
        """
        if self._token and self._token_expires_at and datetime.utcnow() < self._token_expires_at - timedelta(seconds=10):
            return self._token.get("access_token")

        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        try:
            r = self._http.post(self.OAUTH_URL, data=payload)
        except Exception as e:
            logger.exception("Ошибка при запросе OAuth токена")
            raise SentinelHubError("OAuth request failed: %s" % e)

        if r.status_code != 200:
            logger.error("OAuth token endpoint returned status %s: %s", r.status_code, r.text)
            raise SentinelHubError(f"OAuth token endpoint returned {r.status_code}: {r.text}")

        j = r.json()
        token = j.get("access_token")
        expires_in = j.get("expires_in", 3600)
        if not token:
            logger.error("OAuth response does not contain access_token: %s", j)
            raise SentinelHubError("OAuth response missing access_token")

        self._token = j
        self._token_expires_at = datetime.utcnow() + timedelta(seconds=int(expires_in))
        logger.info("Sentinel Hub token obtained. Expires at %s", self._token_expires_at.isoformat())
        return token

    @staticmethod
    def _make_bbox(lon: float, lat: float, size_meters: float = 50.0) -> Tuple[float, float, float, float]:
        """Сделать bbox вокруг точки (lon, lat) с приблизительным размером в метрах.
        Для небольших delta используем приближение: 1 deg lat ~= 111320 m
        1 deg lon ~= 111320 * cos(lat)
        Возвращает [lon_min, lat_min, lon_max, lat_max]
        """
        if size_meters <= 0:
            raise ValueError("size_meters must be > 0")

        lat_deg_per_m = 1.0 / 111320.0
        lon_deg_per_m = 1.0 / (111320.0 * math.cos(math.radians(lat)))

        half_lat = (size_meters / 2.0) * lat_deg_per_m
        half_lon = (size_meters / 2.0) * lon_deg_per_m

        return (lon - half_lon, lat - half_lat, lon + half_lon, lat + half_lat)

    @staticmethod
    def _default_evalscript() -> str:
        return """
//VERSION=3
function setup() {
  return {
    input: [
      { bands: ["B04", "B08"], units: "REFLECTANCE" }
    ],
    output: { id: "ndvi", bands: 1, sampleType: "FLOAT32" }
  };
}

function evaluatePixel(sample) {
  let b4 = sample.B04;
  let b8 = sample.B08;
  let ndvi = (b8 - b4) / (b8 + b4);
  if (!isFinite(ndvi)) {
    ndvi = -1.0;
  }
  return [ndvi];
}
"""

    def _build_payload(self, bbox: Tuple[float, float, float, float], from_date: str, to_date: str, evalscript: Optional[str] = None) -> Dict[str, Any]:
        if not evalscript:
            evalscript = self._default_evalscript()

        data_source = {
            "type": "SENTINEL2_L2A",
            # дополнительные параметры можно вставить сюда при необходимости
        }

        payload = {
            "input": {
                "bounds": {
                    "bbox": [bbox[0], bbox[1], bbox[2], bbox[3]]
                },
                "data": [
                    {
                        "type": "sentinel-2-l2a",
                        "dataFilter": {
                            "timeRange": {"from": from_date, "to": to_date}
                        }
                    }
                ]
            },
            "evalscript": evalscript,
            "output": {
                "width": 64,
                "height": 64,
                "responses": [
                    {"identifier": "ndvi", "format": {"type": "image/tiff"}}
                ]
            }
        }

        # Если у вас instance_id — добавить его
        if self.instance_id:
            payload["input"]["instanceId"] = self.instance_id

        return payload

    def get_ndvi(self, lon: float, lat: float, days: int = 30, size_meters: float = 50.0) -> Optional[np.ndarray]:
        """
        Получить NDVI как 2D numpy array (width x height) для bbox вокруг lon,lat.
        При ошибке вернёт None и задокументирует причину в логах.
        """
        # Рanges
        to_date = datetime.utcnow().date()
        from_date = to_date - timedelta(days=days)
        from_date_s = from_date.isoformat() + "T00:00:00Z"
        to_date_s = (to_date + timedelta(days=1)).isoformat() + "T00:00:00Z"  # exclusive

        bbox = self._make_bbox(lon, lat, size_meters=size_meters)
        logger.info("Requesting Sentinel Hub NDVI for bbox %s and dates %s - %s", bbox, from_date_s, to_date_s)

        payload = self._build_payload(bbox, from_date_s, to_date_s)

        token = self._get_oauth_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        try:
            r = self._http.post(self.PROCESS_URL, json=payload, headers=headers)
        except Exception as e:
            logger.exception("HTTP request to Sentinel Hub failed")
            return None

        if r.status_code == 400:
            # Логируем тело запроса и ответ сервера — это пригодится при отладке
            logger.error("Sentinel Hub returned 400 Bad Request. Response: %s", r.text)
            logger.debug("Payload sent: %s", payload)
            return None

        if r.status_code != 200:
            logger.error("Sentinel Hub returned status %s: %s", r.status_code, r.text)
            return None

        # Мы ожидаем GeoTIFF (image/tiff) — httpx вернёт байты
        content_type = r.headers.get("Content-Type", "")
        if "image/tiff" not in content_type and "application/octet-stream" not in content_type:
            logger.warning("Unexpected content-type from Sentinel Hub: %s", content_type)

        # Попытаться прочитать как TIFF в памяти — если пользователь не хочет rasterio, можно распарсить с помощью numpy
        try:
            # Читаем как array — используем rasterio, если доступен
            try:
                import rasterio
                from rasterio.io import MemoryFile

                with MemoryFile(r.content) as mem:
                    with mem.open() as src:
                        arr = src.read(1).astype(np.float32)
                        # Sentinel Hub может возвращать значения, масштабированные в 0..1 или -1..1
                        # Тут мы просто возвращаем массив как есть; пользователь может нормализовать
                        logger.info("NDVI image read: shape=%s, dtype=%s", arr.shape, arr.dtype)
                        return arr
            except Exception:
                # Fall back: try to parse raw bytes into numpy — подходит, если сервер вернул одиночный float32 raster
                logger.debug("rasterio not available or failed, trying numpy fallback")
                import tifffile
                arr = tifffile.imread(r.content).astype(np.float32)
                logger.info("NDVI image read via tifffile: shape=%s, dtype=%s", arr.shape, arr.dtype)
                return arr
        except Exception as e:
            logger.exception("Failed to parse NDVI GeoTIFF: %s", e)
            return None


if __name__ == "__main__":
    # Пример использования; не храните client_id/client_secret в коде в проде
    logging.basicConfig(level=logging.INFO)
    client_id = "SENTINEL_CLIENT_ID"
    client_secret = "SENTINEL_CLIENT_SECRET"

    ndvi = SentinelNDVI(client_id, client_secret)
    try:
        arr = ndvi.get_ndvi(69.245, 41.295, days=30, size_meters=80)
        if arr is None:
            logger.error("NDVI request failed")
        else:
            logger.info("NDVI array min/max: %s/%s", np.nanmin(arr), np.nanmax(arr))
    finally:
        ndvi.close()
