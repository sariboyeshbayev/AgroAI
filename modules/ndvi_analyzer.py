"""
Модуль NDVI анализа через спутниковые данные
Использует Sentinel Hub API для получения спутниковых снимков
"""

import asyncio
import aiohttp
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Tuple
import config


class NDVIAnalyzer:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://services.sentinel-hub.com"

    async def get_sentinel_data(self, lat: float, lon: float, date_range: int = 10) -> Dict:
        """
        Получить спутниковые данные Sentinel-2
        """
        # Создание бокса вокруг координат (примерно 1км x 1км)
        bbox_size = 0.005
        bbox = [
            lon - bbox_size, lat - bbox_size,
            lon + bbox_size, lat + bbox_size
        ]

        # Временной диапазон
        end_date = datetime.now()
        start_date = end_date - timedelta(days=date_range)

        # Формирование запроса для NDVI
        # NDVI = (NIR - RED) / (NIR + RED)
        evalscript = """
        //VERSION=3
        function setup() {
            return {
                input: ["B04", "B08", "dataMask"],
                output: { bands: 3 }
            };
        }

        function evaluatePixel(sample) {
            let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
            return [ndvi, sample.B08, sample.B04];
        }
        """

        # Для демонстрации используем симуляцию данных
        # В продакшене нужен реальный API ключ Sentinel Hub
        return await self._simulate_sentinel_data(lat, lon)

    async def _simulate_sentinel_data(self, lat: float, lon: float) -> Dict:
        """
        Симуляция спутниковых данных для демо
        В реальном проекте здесь будет запрос к Sentinel Hub API
        """
        await asyncio.sleep(1)  # Имитация задержки API

        # Симуляция NDVI данных на основе сезона и координат
        month = datetime.now().month

        # Базовый NDVI в зависимости от сезона
        if 3 <= month <= 5:  # Весна
            base_ndvi = 0.45
        elif 6 <= month <= 8:  # Лето
            base_ndvi = 0.65
        elif 9 <= month <= 11:  # Осень
            base_ndvi = 0.40
        else:  # Зима
            base_ndvi = 0.25

        # Добавляем вариативность
        ndvi = base_ndvi + np.random.uniform(-0.1, 0.1)

        return {
            'ndvi': ndvi,
            'nir': np.random.uniform(0.3, 0.8),
            'red': np.random.uniform(0.1, 0.4),
            'cloud_coverage': np.random.uniform(0, 30)
        }

    def calculate_health_status(self, ndvi: float) -> Tuple[str, str]:
        """
        Определить состояние здоровья растений по NDVI
        Возвращает статус на узбекском и русском
        """
        if ndvi >= config.NDVI_THRESHOLD_EXCELLENT:
            return "Juda yaxshi", "Отличное"
        elif ndvi >= config.NDVI_THRESHOLD_GOOD:
            return "Yaxshi", "Хорошее"
        elif ndvi >= config.NDVI_THRESHOLD_MODERATE:
            return "O'rtacha", "Среднее"
        else:
            return "Yomon", "Плохое"

    def generate_recommendations(self, ndvi: float, moisture: float, temp: float) -> Tuple[str, str]:
        """
        Генерация рекомендаций на основе NDVI и других параметров
        """
        rec_uz = []
        rec_ru = []

        # Рекомендации по NDVI
        if ndvi < config.NDVI_THRESHOLD_MODERATE:
            rec_uz.append("⚠️ O'simliklar stressda. Sug'orishni ko'paytiring.")
            rec_ru.append("⚠️ Растения в стрессе. Увеличьте полив.")

            rec_uz.append("🧪 Azotli o'g'itlar qo'shing.")
            rec_ru.append("🧪 Добавьте азотные удобрения.")

        elif ndvi < config.NDVI_THRESHOLD_GOOD:
            rec_uz.append("💧 Sug'orishni nazorat qiling.")
            rec_ru.append("💧 Контролируйте полив.")

        else:
            rec_uz.append("✅ O'simliklar yaxshi holatda.")
            rec_ru.append("✅ Растения в хорошем состоянии.")

        # Рекомендации по влажности
        if moisture < 30:
            rec_uz.append("💧 Namlik past. Darhol sug'oring.")
            rec_ru.append("💧 Влажность низкая. Срочно полейте.")
        elif moisture > 80:
            rec_uz.append("⚠️ Namlik yuqori. Sug'orishni kamaytiring.")
            rec_ru.append("⚠️ Влажность высокая. Уменьшите полив.")

        # Рекомендации по температуре
        if temp > 35:
            rec_uz.append("🌡 Harorat juda yuqori. Soyalab qo'ying.")
            rec_ru.append("🌡 Температура очень высокая. Обеспечьте тень.")
        elif temp < 5:
            rec_uz.append("❄️ Muzlash xavfi. O'simliklarni himoya qiling.")
            rec_ru.append("❄️ Опасность заморозков. Защитите растения.")

        return "\n".join(rec_uz), "\n".join(rec_ru)

    async def analyze(self, lat: float, lon: float) -> Dict:
        """
        Полный NDVI анализ для заданных координат
        """
        # Получение спутниковых данных
        sentinel_data = await self.get_sentinel_data(lat, lon)

        ndvi = sentinel_data['ndvi']

        # Симуляция дополнительных параметров
        moisture = np.random.uniform(20, 80)
        temperature = np.random.uniform(15, 35)

        # Определение состояния здоровья
        health_uz, health_ru = self.calculate_health_status(ndvi)

        # Генерация рекомендаций
        rec_uz, rec_ru = self.generate_recommendations(ndvi, moisture, temperature)

        return {
            'ndvi': ndvi,
            'health_uz': health_uz,
            'health_ru': health_ru,
            'moisture': round(moisture, 1),
            'temperature': round(temperature, 1),
            'recommendations_uz': rec_uz,
            'recommendations_ru': rec_ru,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'cloud_coverage': sentinel_data['cloud_coverage']
        }

    async def get_historical_ndvi(self, lat: float, lon: float, days: int = 30) -> list:
        """
        Получить исторические данные NDVI за период
        """
        historical_data = []

        for i in range(days):
            date = datetime.now() - timedelta(days=days - i)
            # Симуляция данных
            ndvi = 0.5 + 0.2 * np.sin(i * 2 * np.pi / 30)
            historical_data.append({
                'date': date.strftime('%Y-%m-%d'),
                'ndvi': round(ndvi, 3)
            })

        return historical_data

    def interpret_ndvi_trend(self, historical_data: list) -> Tuple[str, str]:
        """
        Интерпретация тренда NDVI
        """
        if len(historical_data) < 2:
            return "Ma'lumot yetarli emas", "Недостаточно данных"

        recent = np.mean([d['ndvi'] for d in historical_data[-7:]])
        previous = np.mean([d['ndvi'] for d in historical_data[-14:-7]])

        change = recent - previous

        if change > 0.05:
            return "📈 Yaxshilanmoqda", "📈 Улучшается"
        elif change < -0.05:
            return "📉 Yomonlashmoqda", "📉 Ухудшается"
        else:
            return "➡️ Barqaror", "➡️ Стабильно"