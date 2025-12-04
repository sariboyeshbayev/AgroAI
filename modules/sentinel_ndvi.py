"""
Модуль реального NDVI анализа через Sentinel Hub API
Версия: 1.0
"""
import httpx
import asyncio
from typing import Dict, Optional
from datetime import datetime, timedelta
import logging

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
        # Проверка кеша
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
                # Токен действует 1 час, ставим 50 минут для безопасности
                self._token_expires = datetime.now() + timedelta(minutes=50)

                logger.info("✅ Sentinel Hub token obtained")
                return self._token

        except Exception as e:
            logger.error(f"❌ Token error: {e}")
            return None

    async def get_ndvi(self, lat: float, lon: float, days: int = 30) -> Dict:
        """
        Получение реального NDVI со спутника Sentinel-2

        Args:
            lat: широта
            lon: долгота
            days: период поиска снимков (по умолчанию 30 дней)

        Returns:
            Dict с NDVI данными или ошибкой
        """
        token = await self.get_access_token()
        if not token:
            return {'success': False, 'error': 'Не удалось авторизоваться'}

        # Создаем bbox 1x1 км вокруг точки
        offset = 0.0045  # ~500 метров
        bbox = [
            lon - offset, lat - offset,
            lon + offset, lat + offset
        ]

        # Временной диапазон
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # Evalscript для расчета NDVI
        evalscript = """
        //VERSION=3
        function setup() {
            return {
                input: [{
                    bands: ["B04", "B08", "SCL"],
                    units: "DN"
                }],
                output: [
                    {
                        id: "ndvi",
                        bands: 1,
                        sampleType: "FLOAT32"
                    },
                    {
                        id: "dataMask",
                        bands: 1
                    }
                ]
            };
        }

        function evaluatePixel(sample) {
            // Фильтрация облаков и теней
            if (sample.SCL == 3 || sample.SCL == 8 || sample.SCL == 9 || 
                sample.SCL == 10 || sample.SCL == 11) {
                return {
                    ndvi: [0],
                    dataMask: [0]
                };
            }

            let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);

            return {
                ndvi: [ndvi],
                dataMask: [1]
            };
        }
        """

        # Запрос к API
        url = f"{self.BASE_URL}/api/v1/process"
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

        payload = {
            "input": {
                "bounds": {
                    "bbox": bbox,
                    "properties": {
                        "crs": "http://www.opengis.net/def/crs/EPSG/0/4326"
                    }
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
                    "format": {"type": "application/json"}
                }]
            },
            "evalscript": evalscript
        }

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(url, headers=headers, json=payload)

                if response.status_code == 400:
                    # Нет данных за период - пробуем расширить
                    logger.warning(f"No data for {days} days, trying {days * 2}")
                    return await self.get_ndvi(lat, lon, days=min(days * 2, 90))

                response.raise_for_status()

                # Статистика через Statistical API
                stats = await self._get_statistics(bbox, start_date, end_date, token)

                if stats:
                    return {
                        'success': True,
                        'ndvi_value': stats['mean'],
                        'min': stats['min'],
                        'max': stats['max'],
                        'std': stats['stdev'],
                        'date': stats['date'],
                        'status': self._interpret_ndvi(stats['mean'])
                    }
                else:
                    return {
                        'success': False,
                        'error': 'Не удалось получить статистику'
                    }

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP error: {e.response.status_code}")
            return {
                'success': False,
                'error': f'API вернул код {e.response.status_code}'
            }
        except Exception as e:
            logger.error(f"❌ NDVI error: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def _get_statistics(self, bbox: list, start_date: datetime,
                              end_date: datetime, token: str) -> Optional[Dict]:
        """Получение статистики NDVI через Statistical API"""

        url = f"{self.BASE_URL}/api/v1/statistics"
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

        evalscript = """
        //VERSION=3
        function setup() {
            return {
                input: [{
                    bands: ["B04", "B08", "SCL"]
                }],
                output: [{
                    id: "ndvi",
                    bands: 1
                }]
            };
        }

        function evaluatePixel(sample) {
            if (sample.SCL == 3 || sample.SCL == 8 || sample.SCL == 9 || 
                sample.SCL == 10 || sample.SCL == 11) {
                return [null];
            }

            let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
            return [ndvi];
        }
        """

        payload = {
            "input": {
                "bounds": {
                    "bbox": bbox,
                    "properties": {
                        "crs": "http://www.opengis.net/def/crs/EPSG/0/4326"
                    }
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
            "aggregation": {
                "timeRange": {
                    "from": start_date.strftime('%Y-%m-%dT00:00:00Z'),
                    "to": end_date.strftime('%Y-%m-%dT23:59:59Z')
                },
                "aggregationInterval": {
                    "of": "P1D"
                },
                "evalscript": evalscript,
                "resx": 10,
                "resy": 10
            },
            "calculations": {
                "ndvi": {
                    "statistics": {
                        "default": {
                            "percentiles": {
                                "k": [25, 50, 75]
                            }
                        }
                    }
                }
            }
        }

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()

                data = response.json()

                # Берем последний доступный снимок
                if data.get('data') and len(data['data']) > 0:
                    latest = data['data'][-1]
                    outputs = latest.get('outputs', {}).get('ndvi', {})
                    bands = outputs.get('bands', {}).get('B0', {})
                    stats = bands.get('stats', {})

                    if stats.get('mean') is not None:
                        return {
                            'mean': float(stats['mean']),
                            'min': float(stats.get('min', 0)),
                            'max': float(stats.get('max', 1)),
                            'stdev': float(stats.get('stDev', 0)),
                            'date': latest['interval']['from'][:10]
                        }

                return None

        except Exception as e:
            logger.error(f"Statistics error: {e}")
            return None

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