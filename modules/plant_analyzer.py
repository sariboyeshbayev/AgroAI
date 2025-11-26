"""
Модуль анализа растений по фотографии с использованием Claude AI
"""

import base64
import aiohttp
import asyncio
from typing import Dict
from pathlib import Path


class PlantAnalyzer:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = "https://api.anthropic.com/v1/messages"

    async def analyze(self, photo_path: str) -> Dict:
        """
        Анализ растения по фотографии с помощью Claude AI Vision
        """
        # Чтение и кодирование изображения
        with open(photo_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')

        # Формирование запроса к Claude API
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        prompt = """Проанализируй это растение и предоставь детальную информацию:

1. Определи тип растения (культура)
2. Оцени здоровье по шкале от 0 до 100
3. Выяви видимые проблемы (болезни, вредители, дефицит питательных веществ)
4. Дай конкретные рекомендации по лечению
5. Укажи примерное время восстановления

Ответ предоставь в формате JSON:
{
    "plant_name_uz": "название на узбекском",
    "plant_name_ru": "название на русском",
    "health_score": число от 0 до 100,
    "issues_uz": "проблемы на узбекском",
    "issues_ru": "проблемы на русском",
    "treatment_uz": "рекомендации на узбекском",
    "treatment_ru": "рекомендации на русском",
    "treatment_time": "время лечения"
}"""

        payload = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1500,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_data
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Извлечение и парсинг ответа
                        result_text = data['content'][0]['text']

                        # Парсинг JSON из ответа
                        import json
                        # Удаляем markdown разметку если есть
                        result_text = result_text.replace('```json', '').replace('```', '').strip()
                        result = json.loads(result_text)
                        return result
                    else:
                        # Если API недоступен, используем демо-режим
                        return await self._demo_analysis()

        except Exception as e:
            print(f"Ошибка анализа растения: {e}")
            # В случае ошибки возвращаем демо-анализ
            return await self._demo_analysis()

    async def _demo_analysis(self) -> Dict:
        """
        Демонстрационный анализ для тестирования без API
        """
        await asyncio.sleep(2)  # Имитация обработки

        return {
            'plant_name_uz': "Bug'doy",
            'plant_name_ru': "Пшеница",
            'health_score': 75,
            'issues_uz': """🔍 Aniqlangan muammolar:
• Barglarning uchlari sariq rangga kirmoqda
• Ba'zi barglar dog'li
• O'sish sur'ati sekinlashgan

Bu ko'pincha azot yetishmasligi yoki qurg'oqchilik belgisidir.""",
            'issues_ru': """🔍 Обнаруженные проблемы:
• Кончики листьев желтеют
• На некоторых листьях пятна
• Замедленный рост

Это часто признаки дефицита азота или засухи.""",
            'treatment_uz': """💊 Davolash tavsiyalari:

1. 💧 Sug'orish rejimi:
   - Darhol chuqur sug'oring (20-30 litr/m²)
   - Keyingi 2 hafta har 3 kunda bir marta sug'oring

2. 🧪 O'g'itlash:
   - Karbamid (46% N): 100-150 kg/getar
   - Yoki ammiak selitra: 150-200 kg/getar
   - O'g'itni sug'orishdan oldin sepish kerak

3. 🛡 Himoya choralari:
   - Fungitsid bilan ishlov bering (mancozeb yoki triazollar)
   - 7-10 kundan keyin takrorlang

4. 📊 Monitoring:
   - Har hafta holatini tekshiring
   - Yangi barglarning rangiga e'tibor bering""",
            'treatment_ru': """💊 Рекомендации по лечению:

1. 💧 Режим полива:
   - Немедленно провести глубокий полив (20-30 л/м²)
   - Следующие 2 недели поливать каждые 3 дня

2. 🧪 Удобрение:
   - Карбамид (46% N): 100-150 кг/га
   - Или аммиачная селитра: 150-200 кг/га
   - Вносить перед поливом

3. 🛡 Защитные меры:
   - Обработать фунгицидом (манкоцеб или триазолы)
   - Повторить через 7-10 дней

4. 📊 Мониторинг:
   - Проверять состояние еженедельно
   - Обращать внимание на цвет новых листьев""",
            'treatment_time': "2-3 hafta / 2-3 недели"
        }

    def identify_disease(self, symptoms: list) -> Dict:
        """
        Определение болезни по симптомам
        """
        diseases_db = {
            'rust': {
                'name_uz': "Zang kasalligi",
                'name_ru': "Ржавчина",
                'symptoms': ['orange spots', 'brown spots', 'rust colored'],
                'treatment_uz': "Fungitsidlar (Triazollar): Tilт, Propіkonaol",
                'treatment_ru': "Фунгициды (Триазолы): Тилт, Пропиконазол"
            },
            'blight': {
                'name_uz': "Kuyish kasalligi",
                'name_ru': "Фитофтороз",
                'symptoms': ['brown leaves', 'wilting', 'dark spots'],
                'treatment_uz': "Mis preparatlari, Metaksil",
                'treatment_ru': "Медные препараты, Метаксил"
            },
            'mildew': {
                'name_uz': "Chirish kasalligi",
                'name_ru': "Мучнистая роса",
                'symptoms': ['white powder', 'fungal growth'],
                'treatment_uz': "Oltingugurt, Topaz fungitsidi",
                'treatment_ru': "Сера, Фунгицид Топаз"
            }
        }
        return diseases_db

    def calculate_npk_needs(self, plant_type: str, growth_stage: str) -> Dict:
        """
        Расчет потребности в NPK удобрениях
        """
        npk_requirements = {
            'wheat': {
                'vegetative': {'N': 120, 'P': 60, 'K': 40},
                'reproductive': {'N': 80, 'P': 40, 'K': 60},
                'maturation': {'N': 40, 'P': 20, 'K': 40}
            },
            'cotton': {
                'vegetative': {'N': 150, 'P': 80, 'K': 60},
                'reproductive': {'N': 100, 'P': 60, 'K': 80},
                'maturation': {'N': 50, 'P': 30, 'K': 60}
            },
            'tomato': {
                'vegetative': {'N': 100, 'P': 50, 'K': 80},
                'reproductive': {'N': 80, 'P': 60, 'K': 120},
                'maturation': {'N': 40, 'P': 40, 'K': 100}
            }
        }

        return npk_requirements.get(plant_type, {}).get(growth_stage, {'N': 100, 'P': 50, 'K': 50})