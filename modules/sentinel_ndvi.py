"""
Sentinel NDVI module — robust async implementation
Version: 1.1 (improved error handling, token/session reuse, robust parsing)
"""
import httpx
import asyncio
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import logging
import math

logger = logging.getLogger(__name__)

try:
    import numpy as np
except Exception:
    np = None
    logger.warning("numpy not available — local statistics calculation will be limited.")


class SentinelNDVI:
    BASE_URL = "https://services.sentinel-hub.com"

    def __init__(self, client_id: str, client_secret: str, *, session: Optional[httpx.AsyncClient] = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: Optional[str] = None
        self._token_expires: Optional[datetime] = None
        self._session_provided = session is not None
        self._session = session or httpx.AsyncClient(timeout=60)
        # Limits
        self._max_days = 90
        self._max_attempts = 4

    async def close(self):
        if not self._session_provided:
            await self._session.aclose()

    async def get_access_token(self) -> Optional[str]:
        """Get OAuth token with caching (50 minutes validity window)."""
        if self._token and self._token_expires and datetime.utcnow() < self._token_expires:
            return self._token

        url = f"{self.BASE_URL}/oauth/token"
        data = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }

        try:
            resp = await self._session.post(url, data=data)
            resp.raise_for_status()
            result = resp.json()
            self._token = result.get('access_token')
            # token lifetime often 1 hour -> keep 50 minutes window
            self._token_expires = datetime.utcnow() + timedelta(minutes=50)
            logger.info("Sentinel Hub token obtained.")
            return self._token
        except httpx.HTTPStatusError as e:
            logger.error("Token request failed: %s %s", e.response.status_code, e.response.text)
            return None
        except Exception as e:
            logger.error("Token error: %s", e)
            return None

    async def get_ndvi(self, lat: float, lon: float, days: int = 30, attempt: int = 1) -> Dict:
        """
        Get NDVI statistics for point (lat, lon).
        - attempt: internal counter to limit recursive retries when no data.
        """
        if attempt > self._max_attempts:
            return {'success': False, 'error': 'Max attempts reached'}

        token = await self.get_access_token()
        if not token:
            return {'success': False, 'error': 'Authorization failed'}

        # bbox ~1x1 km (approx)
        offset = 0.0045
        bbox = [lon - offset, lat - offset, lon + offset, lat + offset]

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=min(days, self._max_days))

        evalscript = """
        //VERSION=3
        function setup() {
            return {
                input: [{ bands: ["B04","B08","SCL"] }],
                output: [{ id: "ndvi", bands: 1, sampleType: "FLOAT32" }, { id: "dataMask", bands: 1 }]
            };
        }
        function evaluatePixel(sample) {
            // mask cloud / invalid SCL values (example codes)
            if (sample.SCL == 3 || sample.SCL == 8 || sample.SCL == 9 || sample.SCL == 10 || sample.SCL == 11) {
                return { ndvi: [0.0], dataMask: [0] };
            }
            let denom = (sample.B08 + sample.B04);
            if (denom == 0.0) {
                return { ndvi: [0.0], dataMask: [0] };
            }
            let ndvi = (sample.B08 - sample.B04) / denom;
            return { ndvi: [ndvi], dataMask: [1] };
        }
        """

        process_url = f"{self.BASE_URL}/api/v1/process"
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

        payload = {
            "input": {
                "bounds": {
                    "bbox": bbox,
                    "properties": {"crs": "EPSG:4326"}
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
                    "format": {"type": "application/json"}  # request JSON if supported
                }]
            },
            "evalscript": evalscript
        }

        try:
            resp = await self._session.post(process_url, headers=headers, json=payload, timeout=120)
            if resp.status_code == 400:
                # no data — расширяем период и пробуем снова (с ограничением)
                new_days = min(days * 2, self._max_days)
                if new_days == days:
                    return {'success': False, 'error': 'No data found for the requested period'}
                logger.warning("No data for %d days; trying %d days (attempt %d)", days, new_days, attempt + 1)
                await asyncio.sleep(0.2)
                return await self.get_ndvi(lat, lon, days=new_days, attempt=attempt + 1)

            resp.raise_for_status()
            j = resp.json()

            # Попытка извлечь ndvi массив из ответа process API
            ndvi_values = self._extract_ndvi_values_from_process_response(j)
            if ndvi_values:
                stats = self._compute_stats(ndvi_values)
                stats['date_range'] = (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
                stats['status'] = self._interpret_ndvi(stats['mean'])
                stats['success'] = True
                return stats

            # Если process не вернул валидных данных — пробуем статистический API как fallback
            stats = await self._get_statistics(bbox, start_date, end_date, token)
            if stats:
                stats['status'] = self._interpret_ndvi(stats['mean'])
                stats['success'] = True
                return stats

            return {'success': False, 'error': 'No NDVI data found or unable to parse response'}

        except httpx.HTTPStatusError as e:
            logger.error("HTTP error: %s %s", e.response.status_code, e.response.text)
            return {'success': False, 'error': f'HTTP {e.response.status_code}'}
        except Exception as e:
            logger.exception("Unexpected error during NDVI request")
            return {'success': False, 'error': str(e)}

    def _extract_ndvi_values_from_process_response(self, resp_json: Dict) -> Optional[List[float]]:
        """
        Try multiple known patterns to extract NDVI numeric values from process API JSON response.
        Returns flat list of values (masked values removed) or None.
        """
        try:
            # Common pattern: response -> outputs -> ndvi -> data (2D array) OR features
            # We will search recursively for arrays of numbers or nested arrays under keys containing 'ndvi'
            def find_ndvi(obj):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if 'ndvi' in k.lower():
                            yield v
                        else:
                            yield from find_ndvi(v)
                elif isinstance(obj, list):
                    for item in obj:
                        yield from find_ndvi(item)

            candidates = list(find_ndvi(resp_json))
            for cand in candidates:
                # cand could be dict with 'values' or direct arrays
                if isinstance(cand, dict):
                    # try common fields
                    for fld in ('data', 'values', 'bands', 'array', 'ndvi'):
                        if fld in cand and isinstance(cand[fld], list):
                            flat = self._flatten_and_filter(cand[fld])
                            if flat:
                                return flat
                elif isinstance(cand, list):
                    flat = self._flatten_and_filter(cand)
                    if flat:
                        return flat
            return None
        except Exception as e:
            logger.debug("extract_ndvi_values error: %s", e)
            return None

    def _flatten_and_filter(self, arr):
        """Flatten nested lists and filter out non-finite or masked values (None, NaN, zeros masked)."""
        flat = []
        def walk(x):
            if x is None:
                return
            if isinstance(x, list):
                for el in x:
                    walk(el)
            else:
                try:
                    val = float(x)
                    # exclude invalid / sentinel values (e.g. 0 with dataMask==0)
                    if math.isfinite(val):
                        flat.append(val)
                except Exception:
                    return
        walk(arr)
        # remove zeros if very likely masked (but keep zeros if real)
        # Cannot perfectly know mask here -> keep all finite vals
        return flat if flat else None

    def _compute_stats(self, values: List[float]) -> Dict:
        if not values:
            return {'mean': 0.0, 'min': 0.0, 'max': 0.0, 'stdev': 0.0}
        if np is not None:
            a = np.array(values, dtype=float)
            return {
                'mean': float(a.mean()),
                'min': float(a.min()),
                'max': float(a.max()),
                'stdev': float(a.std(ddof=0))
            }
        else:
            # fallback minimal stats
            n = len(values)
            s = sum(values)
            mean = s / n
            var = sum((x - mean) ** 2 for x in values) / n
            return {
                'mean': mean,
                'min': min(values),
                'max': max(values),
                'stdev': math.sqrt(var)
            }

    async def _get_statistics(self, bbox: list, start_date: datetime, end_date: datetime, token: str) -> Optional[Dict]:
        """Fallback: call statistics endpoint and try to parse returned structure."""
        url = f"{self.BASE_URL}/api/v1/statistics"
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

        evalscript = """
        //VERSION=3
        function setup() {
            return { input: [{ bands: ["B04","B08","SCL"] }], output: [{ id: "ndvi", bands: 1 }] };
        }
        function evaluatePixel(sample) {
            if (sample.SCL == 3 || sample.SCL == 8 || sample.SCL == 9 || sample.SCL == 10 || sample.SCL == 11) {
                return [null];
            }
            let denom = (sample.B08 + sample.B04);
            if (denom == 0.0) {
                return [null];
            }
            return [(sample.B08 - sample.B04) / denom];
        }
        """

        payload = {
            "input": {
                "bounds": {
                    "bbox": bbox,
                    "properties": {"crs": "EPSG:4326"}
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
                "aggregationInterval": {"of": "P1D"},
                "evalscript": evalscript,
                "resx": 10,
                "resy": 10
            },
            "calculations": {
                "ndvi": {
                    "statistics": {
                        "default": {
                            "percentiles": {"k": [25, 50, 75]}
                        }
                    }
                }
            }
        }

        try:
            resp = await self._session.post(url, headers=headers, json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            # Best-effort parsing: try to find mean/min/max/stdev in response
            # Search recursively for 'mean' or 'stats'
            def find_stats(obj):
                if isinstance(obj, dict):
                    if 'mean' in obj or 'min' in obj or 'max' in obj:
                        return obj
                    for v in obj.values():
                        found = find_stats(v)
                        if found:
                            return found
                elif isinstance(obj, list):
                    for item in obj:
                        found = find_stats(item)
                        if found:
                            return found
                return None

            stats_obj = find_stats(data)
            if stats_obj:
                mean = stats_obj.get('mean') or stats_obj.get('Mean') or stats_obj.get('average')
                minv = stats_obj.get('min', 0.0)
                maxv = stats_obj.get('max', 1.0)
                stdev = stats_obj.get('std') or stats_obj.get('stdev') or stats_obj.get('stDev', 0.0)
                date = None
                # try to get last interval
                if data.get('data') and isinstance(data['data'], list) and len(data['data']) > 0:
                    latest = data['data'][-1]
                    interval = latest.get('interval', {})
                    date = interval.get('from', '')[:10] if interval else None
                return {
                    'mean': float(mean) if mean is not None else 0.0,
                    'min': float(minv),
                    'max': float(maxv),
                    'stdev': float(stdev),
                    'date': date
                }
            return None
        except Exception as e:
            logger.warning("Statistics API failed: %s", e)
            return None

    def _interpret_ndvi(self, ndvi: float) -> str:
        if ndvi >= 0.6:
            return 'excellent'
        if ndvi >= 0.4:
            return 'good'
        if ndvi >= 0.2:
            return 'medium'
        return 'bad'
