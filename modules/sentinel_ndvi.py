import httpx
import asyncio
from typing import Dict, Optional
from datetime import datetime, timedelta
import logging
import numpy as np
from PIL import Image
from io import BytesIO

logger = logging.getLogger(__name__)


class SentinelNDVI:
    """Работа с реальными спутниковыми данными Sentinel Hub"""

    BASE_URL = "https://services.sentinel-hub.com"

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self._token = None
        self._token_expires = None

    async def get_access_token(self) -> Optional[str]:
        """Получение OAuth токена с кешированием"""
        if self._token and self._token_expires and datetime.now() < self._token_expires:
            return self._token

        url = f"{self.BASE_URL}/oauth/token"
        data = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(url, data=data)
                response.raise_for_status()
                result = response.json()
                self._token = result['access_token']
                self._token_expires = datetime.now() + timedelta(minutes=50)
                logger.info("✅ Sentinel Hub token obtained")
                return self._token
        except Exception as e:
            logger.error(f"❌ Token error: {e}")
            return None

    async def get_ndvi(self, lat: float, lon: float, days: int = 30, retries: int = 3) -> Dict:
        """
        Получение реального NDVI со спутника Sentinel-2
        ИСПРАВЛЕНО: используем image/tiff вместо application/json
        """
        token = await self.get_access_token()
        if not token:
            return {'success': False, 'error': 'Не удалось авторизоваться'}

        offset = 0.0045  # ~500 метров
        bbox = [lon - offset, lat - offset, lon + offset, lat + offset]

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        evalscript = """
//VERSION=3
function setup() {
  return {
    input: [{ bands: ["B04", "B08", "SCL"], units: "DN" }],
    output: [
      { id: "ndvi", bands: 1, sampleType: "FLOAT32" },
      { id: "dataMask", bands: 1 }
    ]
  };
}
function evaluatePixel(sample) {
  if ([3,8,9,10,11].includes(sample.SCL)) {
    return { ndvi: [0], dataMask: [0] };
  }
  let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
  return { ndvi: [ndvi], dataMask: [1] };
}
"""

        url = f"{self.BASE_URL}/api/v1/process"
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

        payload = {
            "input": {
                "bounds": {
                    "bbox": bbox,
                    "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"}
                },
                "data": [{
                    "type": "sentinel-2-l2a",
                    "dataFilter": {
                        "timeRange": {
                            "from": start_date.strftime('%Y-%m-%dT00:00:00Z'),
                            "to": end_date.strftime('%Y-%m-%dT23:59:59Z')
                        },
                        "maxCloudCoverage": 30
                    }
                }]
            },
            "output": {
                "resx": 10,
                "resy": 10,
                "responses": [{
                    "identifier": "ndvi",
                    "format": {"type": "image/tiff"}  # ИСПРАВЛЕНО: было application/json
                }]
            },
            "evalscript": evalscript
        }

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(url, headers=headers, json=payload)

                if response.status_code == 400:
                    error_text = response.text
                    logger.warning(f"⚠️ API вернул 400: {error_text}")

                    if retries > 0 and days < 90:
                        logger.info(f"🔄 Увеличиваем диапазон до {days * 2} дней")
                        return await self.get_ndvi(lat, lon, days=min(days * 2, 90), retries=retries - 1)
                    else:
                        return {'success': False, 'error': f'API 400: {error_text}'}

                response.raise_for_status()

                # Обработка TIFF изображения
                try:
                    img = Image.open(BytesIO(response.content))
                    ndvi_array = np.array(img, dtype=np.float32)

                    # Фильтрация валидных значений
                    valid_mask = (ndvi_array > -1) & (ndvi_array < 1)
                    valid_count = valid_mask.sum()

                    if valid_count < 100:
                        logger.warning(f"⚠️ Too few valid pixels: {valid_count}")
                        if retries > 0 and days < 90:
                            return await self.get_ndvi(lat, lon, days=min(days * 2, 90), retries=retries - 1)
                        return {'success': False, 'error': 'Недостаточно валидных данных'}

                    mean_ndvi = float(ndvi_array[valid_mask].mean())
                    min_ndvi = float(ndvi_array[valid_mask].min())
                    max_ndvi = float(ndvi_array[valid_mask].max())
                    std_ndvi = float(ndvi_array[valid_mask].std())

                    logger.info(f"✅ Sentinel Hub NDVI: {mean_ndvi:.3f}")

                    return {
                        'success': True,
                        'ndvi_value': mean_ndvi,
                        'min': min_ndvi,
                        'max': max_ndvi,
                        'std': std_ndvi,
                        'date': datetime.now().strftime('%Y-%m-%d'),
                        'status': self._interpret_ndvi(mean_ndvi)
                    }

                except Exception as img_err:
                    logger.error(f"❌ Image processing error: {img_err}")
                    return {'success': False, 'error': f'Ошибка обработки изображения: {img_err}'}

        except httpx.HTTPStatusError as e:
            return {'success': False, 'error': f'HTTP error {e.response.status_code}: {e.response.text}'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _interpret_ndvi(self, ndvi: float) -> str:
        """Интерпретация значения NDVI"""
        if ndvi >= 0.6:
            return 'excellent'
        elif ndvi >= 0.4:
            return 'good'
        elif ndvi >= 0.2:
            return 'medium'
        else:
            return 'bad'