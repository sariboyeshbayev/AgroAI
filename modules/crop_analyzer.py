"""
Crop Analyzer - Модуль анализа растений и NDVI
Версия 3.1 - Интеграция с Sentinel Hub API

1. analyze_plant_only() - ТОЛЬКО фото → Claude Vision
2. analyze_ndvi_only() - ТОЛЬКО координаты → Sentinel Hub → Planetary Computer (fallback)
3. generate_ndvi_advice() - NDVI данные → Claude AI советы
"""
import numpy as np
from PIL import Image
from io import BytesIO
import httpx
import planetary_computer
from pystac_client import Client
import logging
import asyncio
import base64
import json
from typing import Dict, Optional
from datetime import datetime, timedelta
from anthropic import AsyncAnthropic
from config import ANTHROPIC_API_KEY, SENTINEL_CLIENT_ID, SENTINEL_CLIENT_SECRET
from modules.sentinel_ndvi import SentinelNDVI

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# ЯЗЫКОВЫЕ СООБЩЕНИЯ
# ═══════════════════════════════════════════════════════════════

MESSAGES = {
    "ndvi_excellent": {
        "uz": "🌟 NDVI a'lo! O'simliklar juda sog'lom.",
        "ru": "🌟 NDVI отличный! Растения очень здоровы."
    },
    "ndvi_good": {
        "uz": "📈 NDVI yaxshi. Normal holat.",
        "ru": "📈 NDVI хороший. Нормальное состояние."
    },
    "ndvi_medium": {
        "uz": "⚠️ NDVI o'rtacha. Nazorat qiling.",
        "ru": "⚠️ NDVI средний. Следите за полем."
    },
    "ndvi_bad": {
        "uz": "🔴 NDVI past! Stress yoki kasallik!",
        "ru": "🔴 NDVI низкий! Стресс или болезнь!"
    },
    "no_data": {
        "uz": "❌ Satellite ma'lumotlari topilmadi.",
        "ru": "❌ Спутниковые данные не найдены."
    }
}

# ═══════════════════════════════════════════════════════════════
# ОСНОВНОЙ КЛАСС CROP ANALYZER
# ═══════════════════════════════════════════════════════════════

class CropAnalyzer:
    def __init__(self, api_key: str):
        """Инициализация"""
        self.api_key = api_key

        # Инициализация Sentinel Hub (приоритет)
        if SENTINEL_CLIENT_ID and SENTINEL_CLIENT_SECRET:

            self.sentinel = SentinelNDVI(SENTINEL_CLIENT_ID, SENTINEL_CLIENT_SECRET)
            logger.info("✅ Sentinel Hub NDVI initialized")

        else:
            self.sentinel = None
            logger.warning("⚠️ Sentinel Hub не настроен (используем Planetary Computer)")

        # Planetary Computer STAC как резервный вариант
        try:
            self.stac = Client.open("https://planetarycomputer.microsoft.com/api/stac/v1")
            logger.info("✅ Planetary Computer initialized (fallback)")
        except Exception as e:
            logger.error(f"❌ STAC init error: {e}")
            self.stac = None

    # ═══════════════════════════════════════════════════════════════
    # 1️⃣ АНАЛИЗ РАСТЕНИЯ (ТОЛЬКО ФОТО)
    # ═══════════════════════════════════════════════════════════════

    async def analyze_plant_only(self, image_bytes: bytes, lang: str,
                                 chat_id: int = None, bot=None) -> Dict:
        """
        Анализ ТОЛЬКО по фото через Claude Vision
        Возвращает: диагноз + рекомендации по лечению
        """
        # Typing indicator
        if chat_id and bot:
            asyncio.create_task(bot.send_chat_action(chat_id=chat_id, action="typing"))

        # Проверка API ключа
        if not self.api_key or "sk-" not in self.api_key:
            logger.warning("⚠️ ANTHROPIC_API_KEY not configured")
            return await self._heuristic_analysis(image_bytes, lang)

        try:
            # Оптимизация изображения
            img = Image.open(BytesIO(image_bytes))
            if img.mode != "RGB":
                img = img.convert("RGB")

            # Resize для скорости
            max_size = 768
            if max(img.size) > max_size:
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

            # Конвертация в base64
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=85, optimize=True)
            img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

            logger.info(f"📸 Image prepared: {img.size}")

            # Промпт для Claude
            prompt = self._get_plant_analysis_prompt(lang)

            # Вызов Claude Vision
            client = AsyncAnthropic(api_key=self.api_key)

            response = await client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
                temperature=0.3,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": img_b64
                            }
                        },
                        {"type": "text", "text": prompt}
                    ]
                }]
            )

            # Парсинг ответа
            text = response.content[0].text.strip()

            # Удаление markdown
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            # Парсинг JSON
            result = json.loads(text)

            logger.info(f"✅ Plant analysis complete: {result.get('plant_type', 'unknown')}")

            # Форматирование ответа
            return self._format_plant_result(result, lang)

        except Exception as e:
            logger.error(f"❌ Claude Vision error: {e}")
            import traceback
            traceback.print_exc()
            return await self._heuristic_analysis(image_bytes, lang)

    def _get_plant_analysis_prompt(self, lang: str) -> str:
        """Промпт для анализа растения"""
        if lang == "uz":
            return """Rasmni tahlil qiling va FAQAT JSON qaytaring:

{
  "plant_type": "O'simlik nomi (uz)",
  "plant_type_en": "Plant name (eng)",
  "confidence": 85,
  "health_status": "healthy/sick/stressed",
  "health_score": 75,
  "disease_name": "Kasallik nomi (agar bor bo'lsa)",
  "disease_name_en": "Disease name",
  "symptoms": "Ko'rinadigan alomatlar",
  "causes": "Sabablari",
  "treatment": "Davolash usullari (batafsil)",
  "fertilizer": "Kerakli o'g'itlar (NPK)",
  "watering": "Sug'orish rejimi",
  "prevention": "Oldini olish choralari",
  "recovery_time": "Tuzalish muddati"
}

Batafsil va amaliy maslahatlar bering!"""
        else:
            return """Проанализируй растение и верни ТОЛЬКО JSON:

{
  "plant_type": "Название растения (рус)",
  "plant_type_en": "Plant name (eng)",
  "confidence": 85,
  "health_status": "healthy/sick/stressed",
  "health_score": 75,
  "disease_name": "Название болезни (если есть)",
  "disease_name_en": "Disease name",
  "symptoms": "Видимые симптомы",
  "causes": "Причины",
  "treatment": "Методы лечения (подробно)",
  "fertilizer": "Необходимые удобрения (NPK)",
  "watering": "Режим полива",
  "prevention": "Меры профилактики",
  "recovery_time": "Время восстановления"
}

Дай детальные практические рекомендации!"""

    def _format_plant_result(self, ai_result: dict, lang: str) -> Dict:
        """Форматирование результата анализа растения"""
        health_emoji = {
            "healthy": "🌿",
            "sick": "🔴",
            "stressed": "⚠️"
        }

        status = ai_result.get("health_status", "unknown")
        emoji = health_emoji.get(status, "❓")

        if lang == "uz":
            text = f"""📸 **O'simlik Tahlili**

🪴 **O'simlik:** {ai_result.get('plant_type', 'Noma\'lum')}
{emoji} **Holat:** {status.upper()} ({ai_result.get('health_score', 0)}/100)
🎯 **Ishonch:** {ai_result.get('confidence', 0)}%

"""
            if ai_result.get('disease_name'):
                text += f"""🦠 **Kasallik:** {ai_result['disease_name']}

📋 **Alomatlar:**
{ai_result.get('symptoms', 'Ma\'lumot yo\'q')}

🔍 **Sabablari:**
{ai_result.get('causes', 'Aniqlanmadi')}

"""

            text += f"""💊 **Davolash:**
{ai_result.get('treatment', 'Kerak emas')}

🧪 **O'g'itlar:**
{ai_result.get('fertilizer', 'Standart NPK')}

💧 **Sug'orish:**
{ai_result.get('watering', 'Muntazam')}

🛡 **Oldini olish:**
{ai_result.get('prevention', 'Tozalik va nazorat')}

⏱ **Tuzalish:** {ai_result.get('recovery_time', '2-3 hafta')}"""

        else:
            text = f"""📸 **Анализ Растения**

🪴 **Растение:** {ai_result.get('plant_type', 'Неизвестно')}
{emoji} **Состояние:** {status.upper()} ({ai_result.get('health_score', 0)}/100)
🎯 **Уверенность:** {ai_result.get('confidence', 0)}%

"""
            if ai_result.get('disease_name'):
                text += f"""🦠 **Болезнь:** {ai_result['disease_name']}

📋 **Симптомы:**
{ai_result.get('symptoms', 'Нет данных')}

🔍 **Причины:**
{ai_result.get('causes', 'Не определены')}

"""

            text += f"""💊 **Лечение:**
{ai_result.get('treatment', 'Не требуется')}

🧪 **Удобрения:**
{ai_result.get('fertilizer', 'Стандартные NPK')}

💧 **Полив:**
{ai_result.get('watering', 'Регулярный')}

🛡 **Профилактика:**
{ai_result.get('prevention', 'Чистота и контроль')}

⏱ **Восстановление:** {ai_result.get('recovery_time', '2-3 недели')}"""

        return {
            'text': text,
            'analysis': ai_result
        }

    # ═══════════════════════════════════════════════════════════════
    # 2️⃣ NDVI АНАЛИЗ (СНАЧАЛА SENTINEL HUB, ПОТОМ PLANETARY COMPUTER)
    # ═══════════════════════════════════════════════════════════════

    async def analyze_ndvi_only(self, lat: float, lon: float, lang: str) -> Dict:
        """
        Получение NDVI данных со спутника
        Приоритет: Sentinel Hub → Planetary Computer → демо
        """

        # ПОПЫТКА 1: Sentinel Hub (РЕАЛЬНЫЕ СВЕЖИЕ ДАННЫЕ)
        if self.sentinel:
            logger.info(f"🛰️ Trying Sentinel Hub for {lat:.4f}, {lon:.4f}")
            result = await self.sentinel.get_ndvi(lat, lon)

            if result['success']:
                ndvi = result['ndvi_value']
                status = result['status']

                # Интерпретация
                if status == 'excellent':
                    status_key = "ndvi_excellent"
                elif status == 'good':
                    status_key = "ndvi_good"
                elif status == 'medium':
                    status_key = "ndvi_medium"
                else:
                    status_key = "ndvi_bad"

                summary = f"""📅 **Sana / Дата:** {result['date']}
📊 **NDVI:** {ndvi:.3f}
{MESSAGES[status_key][lang]}

📈 **Min:** {result['min']:.3f} | **Max:** {result['max']:.3f}"""

                logger.info(f"✅ Sentinel Hub NDVI: {ndvi:.3f} ({status})")

                return {
                    'ndvi_value': ndvi,
                    'status': status,
                    'summary': summary,
                    'date': result['date'],
                    'min': result['min'],
                    'max': result['max'],
                    'std': result['std']
                }
            else:
                logger.warning(f"⚠️ Sentinel Hub failed: {result['error']}")

        # ПОПЫТКА 2: Planetary Computer (РЕЗЕРВ)
        logger.info(f"🛰️ Trying Planetary Computer for {lat:.4f}, {lon:.4f}")

        if not self.stac:
            return {
                'ndvi_value': 0.0,
                'status': 'error',
                'summary': MESSAGES['no_data'][lang],
                'date': None
            }

        try:
            # Поиск снимков Sentinel-2
            search = self.stac.search(
                collections=["sentinel-2-l2a"],
                intersects={"type": "Point", "coordinates": [lon, lat]},
                datetime="2024-01-01/2025-12-31",
                limit=10,
                sortby="-properties.datetime"
            )

            items = list(search.items())
            if not items:
                logger.warning("No Sentinel-2 data found")
                return {
                    'ndvi_value': 0.0,
                    'status': 'no_data',
                    'summary': MESSAGES['no_data'][lang],
                    'date': None
                }

            # Пробуем несколько снимков
            for item in items[:3]:
                try:
                    date = item.properties["datetime"][:10]
                    logger.info(f"Trying NDVI for date: {date}")

                    # Получение NIR (B08) и RED (B04) bands
                    nir_href = item.assets["B08"].href
                    red_href = item.assets["B04"].href

                    # Подписываем URL
                    nir_url = planetary_computer.sign(nir_href)
                    red_url = planetary_computer.sign(red_href)

                    logger.info(f"Downloading bands...")

                    # Загрузка данных
                    async with httpx.AsyncClient(timeout=120) as client:
                        try:
                            nir_response = await client.get(nir_url)
                            nir_response.raise_for_status()

                            red_response = await client.get(red_url)
                            red_response.raise_for_status()
                        except httpx.HTTPStatusError as e:
                            logger.warning(f"HTTP error for {date}: {e}")
                            continue

                    # Вычисление NDVI
                    try:
                        nir = np.array(Image.open(BytesIO(nir_response.content)).convert('L'), dtype=np.float32)
                        red = np.array(Image.open(BytesIO(red_response.content)).convert('L'), dtype=np.float32)
                    except Exception as img_err:
                        logger.warning(f"Image error for {date}: {img_err}")
                        continue

                    # Уменьшаем размер
                    if nir.shape[0] > 1000:
                        from PIL import Image as PILImage
                        nir_img = PILImage.fromarray(nir).resize((500, 500))
                        red_img = PILImage.fromarray(red).resize((500, 500))
                        nir = np.array(nir_img, dtype=np.float32)
                        red = np.array(red_img, dtype=np.float32)

                    # NDVI формула
                    ndvi = (nir - red) / (nir + red + 1e-6)
                    ndvi = np.clip(ndvi, -1, 1)

                    # Фильтрация
                    valid_mask = (ndvi > -0.5) & (ndvi < 1.0)
                    if valid_mask.sum() == 0:
                        logger.warning(f"No valid NDVI for {date}")
                        continue

                    mean_ndvi = float(ndvi[valid_mask].mean())

                    # Интерпретация
                    if mean_ndvi > 0.6:
                        status_key = "ndvi_excellent"
                        status = "excellent"
                    elif mean_ndvi > 0.4:
                        status_key = "ndvi_good"
                        status = "good"
                    elif mean_ndvi > 0.2:
                        status_key = "ndvi_medium"
                        status = "medium"
                    else:
                        status_key = "ndvi_bad"
                        status = "bad"

                    summary = f"""📅 **Sana / Дата:** {date}
📊 **NDVI:** {mean_ndvi:.3f}
{MESSAGES[status_key][lang]}"""

                    logger.info(f"✅ Planetary Computer NDVI: {mean_ndvi:.3f} ({status})")

                    return {
                        'ndvi_value': mean_ndvi,
                        'status': status,
                        'summary': summary,
                        'date': date,
                        'min': float(ndvi[valid_mask].min()),
                        'max': float(ndvi[valid_mask].max()),
                        'std': float(ndvi[valid_mask].std())
                    }

                except Exception as e:
                    logger.warning(f"Error for {date}: {e}")
                    continue

            # Все снимки не сработали
            logger.error("All items failed")
            return {
                'ndvi_value': 0.0,
                'status': 'error',
                'summary': MESSAGES['no_data'][lang],
                'date': None
            }

        except Exception as e:
            logger.error(f"❌ NDVI error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'ndvi_value': 0.0,
                'status': 'error',
                'summary': MESSAGES['no_data'][lang],
                'date': None
            }

    # ═══════════════════════════════════════════════════════════════
    # 3️⃣ ГЕНЕРАЦИЯ AI СОВЕТОВ НА ОСНОВЕ NDVI
    # ═══════════════════════════════════════════════════════════════

    async def generate_ndvi_advice(self, ndvi_data: Dict, lat: float,
                                   lon: float, lang: str) -> str:
        """
        Генерация AI советов на основе реальных NDVI данных
        """
        if not self.api_key:
            return self._get_fallback_ndvi_advice(ndvi_data, lang)

        try:
            # Получение погоды
            weather = await self.get_weather(lat, lon, lang)

            # Промпт для Claude
            prompt = self._get_ndvi_advice_prompt(ndvi_data, weather, lang)

            # Вызов Claude
            client = AsyncAnthropic(api_key=self.api_key)

            response = await client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
                temperature=0.5,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            advice = response.content[0].text.strip()

            logger.info(f"✅ AI advice generated for NDVI={ndvi_data['ndvi_value']:.3f}")

            return advice

        except Exception as e:
            logger.error(f"❌ AI advice error: {e}")
            return self._get_fallback_ndvi_advice(ndvi_data, lang)

    def _get_ndvi_advice_prompt(self, ndvi_data: Dict, weather: str, lang: str) -> str:
        """Промпт для генерации советов по NDVI"""
        ndvi = ndvi_data['ndvi_value']
        status = ndvi_data['status']
        date = ndvi_data.get('date', 'unknown')

        if lang == "uz":
            return f"""Sen tajribali agronom. NDVI sun'iy yo'ldosh ma'lumotlariga qarab aniq tavsiyalar ber:

📊 **NDVI MA'LUMOTLARI:**
- NDVI qiymati: {ndvi:.3f}
- Holat: {status}
- Sana: {date}
- Min: {ndvi_data.get('min', 0):.3f}
- Max: {ndvi_data.get('max', 0):.3f}

🌦 **OB-HAVO:**
{weather}

📝 **TOPSHIRIQ:**
Quyidagi formatda javob ber:

**🔍 DIAGNOZ:**
(NDVI qiymatiga ko'ra dalaning holati)

**💡 TAVSIYALAR:**
1. Sug'orish rejimi
2. O'g'itlar (aniq miqdorlar)
3. Zararkunandalar nazorati
4. Qo'shimcha tadbirlar

**📅 HARAKATLAR JADVALI:**
(Keyingi 2 haftalik plan)

**⚠️ OGOHLANTIRISH:**
(Mumkin bo'lgan xavflar)

ANIQ, AMALIY VA QISQA JAVOB BER!"""
        else:
            return f"""Ты опытный агроном. Дай точные рекомендации на основе спутниковых данных NDVI:

📊 **ДАННЫЕ NDVI:**
- Значение NDVI: {ndvi:.3f}
- Статус: {status}
- Дата: {date}
- Мин: {ndvi_data.get('min', 0):.3f}
- Макс: {ndvi_data.get('max', 0):.3f}

🌦 **ПОГОДА:**
{weather}

📝 **ЗАДАЧА:**
Ответь в следующем формате:

**🔍 ДИАГНОЗ:**
(Состояние поля по NDVI)

**💡 РЕКОМЕНДАЦИИ:**
1. Режим полива
2. Удобрения (точные дозы)
3. Контроль вредителей
4. Дополнительные меры

**📅 ПЛАН ДЕЙСТВИЙ:**
(План на ближайшие 2 недели)

**⚠️ ПРЕДУПРЕЖДЕНИЕ:**
(Возможные риски)

ДАВАЙ КОНКРЕТНЫЙ, ПРАКТИЧНЫЙ И КРАТКИЙ ОТВЕТ!"""

    def _get_fallback_ndvi_advice(self, ndvi_data: Dict, lang: str) -> str:
        """Резервные советы без Claude API"""
        ndvi = ndvi_data['ndvi_value']

        if lang == "uz":
            if ndvi > 0.6:
                return """🌟 **Dala a'lo holatda!**

✅ Hozirgi rejimni davom ettiring
💧 Sug'orish: standart rejim
🧪 O'g'it: minimal (50 kg/ha N)
🔍 Nazorat: muntazam

📅 **Keyingi tekshirish:** 2 hafta"""
            elif ndvi > 0.4:
                return """📈 **Dala yaxshi holatda**

💧 Sug'orish: haftasiga 2-3 marta
🧪 O'g'it: azot 100 kg/ha
🔍 Barcha qismlarni tekshiring

📅 **Keyingi tekshirish:** 1 hafta"""
            elif ndvi > 0.2:
                return """⚠️ **EHTIYOT! O'rtacha holat**

💧 Sug'orish: DARHOL
🧪 O'g'it: NPK kompleks
🐛 Zararkunandalarni tekshiring
🔬 Tuproq tahlili qiling

📅 **Keyingi tekshirish:** 3 kun"""
            else:
                return """🔴 **XAVF! Jiddiy muammo!**

🚨 TEZKOR CHORALAR:
1. Darhol chuqur sug'oring
2. Azot o'g'it: 150 kg/ha
3. Mutaxassis chaqiring
4. Kasallik va zararkunandalarni tekshiring

📞 **DARHOL HARAKAT QILING!**"""
        else:
            if ndvi > 0.6:
                return """🌟 **Поле в отличном состоянии!**

✅ Продолжайте текущий режим
💧 Полив: стандартный режим
🧪 Удобрения: минимальные (50 кг/га N)
🔍 Контроль: регулярный

📅 **Следующая проверка:** 2 недели"""
            elif ndvi > 0.4:
                return """📈 **Поле в хорошем состоянии**

💧 Полив: 2-3 раза в неделю
🧪 Удобрения: азот 100 кг/га
🔍 Проверьте все участки

📅 **Следующая проверка:** 1 неделя"""
            elif ndvi > 0.2:
                return """⚠️ **ВНИМАНИЕ! Среднее состояние**

💧 Полив: СРОЧНО
🧪 Удобрения: комплекс NPK
🐛 Проверьте вредителей
🔬 Сделайте анализ почвы

📅 **Следующая проверка:** 3 дня"""
            else:
                return """🔴 **ОПАСНОСТЬ! Серьезная проблема!**

🚨 СРОЧНЫЕ МЕРЫ:
1. Немедленно глубокий полив
2. Азотные удобрения: 150 кг/га
3. Вызовите специалиста
4. Проверьте болезни и вредителей

📞 **ДЕЙСТВУЙТЕ НЕМЕДЛЕННО!**"""

    # ═══════════════════════════════════════════════════════════════
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ═══════════════════════════════════════════════════════════════

    async def get_weather(self, lat: float, lon: float, lang: str) -> str:
        """Получение прогноза погоды"""
        try:
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": lat,
                "longitude": lon,
                "daily": "temperature_2m_min,temperature_2m_max,precipitation_sum",
                "timezone": "auto",
                "forecast_days": 7
            }

            async with httpx.AsyncClient() as client:
                r = await client.get(url, params=params)
                data = r.json()

            lines = []
            for i in range(min(3, len(data["daily"]["time"]))):
                day = data["daily"]["time"][i]
                tmin = data["daily"]["temperature_2m_min"][i]
                tmax = data["daily"]["temperature_2m_max"][i]
                precip = data["daily"]["precipitation_sum"][i]

                lines.append(f"📅 {day}: 🌡 {tmin}°...{tmax}°C | 💧 {precip}mm")

            return "\n".join(lines)

        except:
            return "❌ Ma'lumot topilmadi / Данные недоступны"

    async def _heuristic_analysis(self, image_bytes: bytes, lang: str) -> Dict:
        """Простой анализ без AI (fallback)"""
        try:
            img = Image.open(BytesIO(image_bytes)).convert("RGB")
            arr = np.array(img.resize((256, 256)))

            r, g, b = arr[:, :, 0] / 255, arr[:, :, 1] / 255, arr[:, :, 2] / 255

            green_mask = (g > r) & (g > b) & (g > 0.3)
            bad_mask = (r > 0.5) | (g < 0.2)

            green_ratio = green_mask.sum() / arr.shape[0] / arr.shape[1]
            bad_ratio = bad_mask.sum() / arr.shape[0] / arr.shape[1]

            if green_ratio < 0.1:
                health = 0
                status = "no_plant"
            elif bad_ratio < 0.05:
                health = 90
                status = "healthy"
            elif bad_ratio < 0.15:
                health = 70
                status = "stressed"
            else:
                health = 40
                status = "sick"

            if lang == "uz":
                text = f"""📸 **O'simlik Tahlili** (Sodda)

⚠️ AI mavjud emas. Asosiy tahlil.

🪴 **Holat:** {status.upper()}
📊 **Sog'liq:** {health}/100

💡 **Tavsiya:**
Aniq tahlil uchun ANTHROPIC_API_KEY sozlang."""
            else:
                text = f"""📸 **Анализ Растения** (Упрощенный)

⚠️ AI недоступен. Базовый анализ.

🪴 **Состояние:** {status.upper()}
📊 **Здоровье:** {health}/100

💡 **Совет:**
Для точного анализа настройте ANTHROPIC_API_KEY."""

            return {
                'text': text,
                'analysis': {
                    'health_status': status,
                    'health_score': health
                }
            }

        except Exception as e:
            logger.error(f"Heuristic error: {e}")
            return {
                'text': "❌ Ошибка анализа / Tahlil xatosi",
                'analysis': {}
            }