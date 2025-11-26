"""
Модуль AI-советника с использованием Claude API
Предоставляет умные, точные советы по сельскому хозяйству
"""

import aiohttp
import asyncio
from typing import Dict
from datetime import datetime


class AIAdvisor:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = "https://api.anthropic.com/v1/messages"

    async def get_advice(self, category: str, language: str, custom_question: str = None) -> str:
        """
        Получить AI-совет по категории
        """
        # Формирование промпта в зависимости от категории
        prompt = self._build_prompt(category, language, custom_question)

        # Запрос к Claude API
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        payload = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 2000,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        advice = data['content'][0]['text']
                        return advice
                    else:
                        # Если API недоступен, используем встроенные советы
                        return self._get_fallback_advice(category, language)
        except Exception as e:
            print(f"Ошибка AI советника: {e}")
            return self._get_fallback_advice(category, language)

    def _build_prompt(self, category: str, language: str, custom_question: str = None) -> str:
        """
        Формирование промпта для Claude AI
        """
        lang_instruction = "на узбекском языке" if language == 'uz' else "на русском языке"

        base_context = f"""Ты - опытный агроном с 20-летним стажем работы в Узбекистане. 
Ты специализируешься на выращивании хлопка, пшеницы, овощей и фруктов в условиях континентального климата.
Твои советы должны быть:
- Конкретными и применимыми на практике
- Адаптированными к климату Узбекистана
- Учитывать текущий сезон ({datetime.now().strftime('%B %Y')})
- Включать точные цифры и рекомендации
- Основаны на научных данных

Ответь {lang_instruction}, используя эмодзи для наглядности."""

        prompts = {
            'crops': f"""{base_context}

Дай детальный совет по выращиванию культур:
- Какие культуры лучше сажать в этом сезоне
- Оптимальные сроки посадки
- Рекомендуемые сорта для Узбекистана
- Севооборот и совместимость культур
- Прогнозируемая урожайность

{f'Конкретный вопрос фермера: {custom_question}' if custom_question else ''}""",

            'irrigation': f"""{base_context}

Дай рекомендации по орошению:
- Оптимальные нормы полива для текущего сезона
- Частота полива разных культур
- Признаки недостатка/избытка влаги
- Методы экономии воды
- Оптимальное время полива

{f'Конкретный вопрос: {custom_question}' if custom_question else ''}""",

            'fertilizer': f"""{base_context}

Дай советы по удобрениям:
- Какие удобрения применять сейчас
- Дозировки для основных культур (NPK)
- Сроки внесения удобрений
- Признаки дефицита питательных элементов
- Органические vs минеральные удобрения

{f'Конкретный вопрос: {custom_question}' if custom_question else ''}""",

            'pest': f"""{base_context}

Дай рекомендации по защите растений:
- Основные вредители и болезни сезона
- Методы профилактики
- Биологические и химические средства защиты
- График обработок
- Безопасность применения пестицидов

{f'Конкретный вопрос: {custom_question}' if custom_question else ''}""",

            'weather': f"""{base_context}

Дай советы с учетом погодных условий:
- Как подготовиться к предстоящим погодным условиям
- Защита от неблагоприятных условий
- Оптимальное использование погоды для полевых работ
- Риски и их минимизация

{f'Конкретный вопрос: {custom_question}' if custom_question else ''}"""
        }

        return prompts.get(category, prompts['crops'])

    def _get_fallback_advice(self, category: str, language: str) -> str:
        """
        Резервные советы на случай недоступности API
        """
        current_month = datetime.now().month

        advice_uz = {
            'crops': f"""🌾 **Maslahat: Ekinlar bo'yicha**

📅 **Hozirgi mavsum uchun ({datetime.now().strftime('%B')})**

{self._get_seasonal_advice_uz(current_month, 'crops')}

🌱 **Tavsiya etilgan navlar:**
• Bug'doy: Kroshka, Odesskaya 267
• Paxta: S-6524, Bukhara-8
• Pomidor: Volgograd, Rio Grande
• Sabzi: Nantes, Shantane

📊 **Kutilayotgan hosildorlik:**
• Bug'doy: 45-60 ts/ga
• Paxta: 30-40 ts/ga
• Pomidor: 60-80 ts/ga

💡 **Muhim eslatma:** Har 3-4 yilda ekinlarni almashtiring.""",

            'irrigation': f"""💧 **Maslahat: Sug'orish bo'yicha**

{self._get_seasonal_advice_uz(current_month, 'irrigation')}

⏰ **Sug'orish jadvali:**
• Bug'doy: 5-6 marta, har 12-15 kunda
• Paxta: 6-8 marta, har 10-12 kunda
• Pomidor: har 5-7 kunda
• Sabzi: har 7-10 kunda

💧 **Suv me'yori:**
• Bug'doy: 400-500 m³/ga
• Paxta: 600-800 m³/ga
• Pomidor: 300-400 m³/ga

🔍 **Nazorat:** Tuproq namligini muntazam tekshiring.""",

            'fertilizer': f"""🧪 **Maslahat: O'g'itlar bo'yicha**

{self._get_seasonal_advice_uz(current_month, 'fertilizer')}

📊 **NPK me'yori (kg/ga):**
• Bug'doy: N-120, P-60, K-40
• Paxta: N-200, P-140, K-100
• Pomidor: N-100, P-80, K-120

📅 **Kiritish muddatlari:**
1. Asosiy: ekilishdan oldin
2. Qo'shimcha: o'sish davrida 2-3 marta

🌿 **Organik o'g'itlar:** Go'ng (20-30 t/ga) yillik""",

            'pest': f"""🐛 **Maslahat: Zararkunandalar bo'yicha**

{self._get_seasonal_advice_uz(current_month, 'pest')}

⚠️ **Asosiy zararkunandalar:**
• Paxta qurti
• Shiralar (aphids)
• Qandala kasalligi
• Chirish kasalligi

🛡 **Himoya choralari:**
1. Profilaktika: dalaни tozalash
2. Biologik: Trichoderma, foydali hasharotlar
3. Kimyoviy: zarurat bo'yicha

⏰ **Ishlov berish:** erta tongda yoki kechqurun""",

            'weather': f"""🌤 **Maslahat: Ob-havo bo'yicha**

{self._get_seasonal_advice_uz(current_month, 'weather')}

🌡 **Hozirgi sharoit:**
• Harorat: o'rtacha {self._get_avg_temp(current_month)}°C
• Yog'ingarchilik: {self._get_precipitation(current_month)}

📋 **Tavsiyalar:**
• Ob-havo prognozini kuzating
• Issiq kunlarda sug'orishni ko'paytiring
• Sovuq oldidan himoya choralari"""
        }

        advice_ru = {
            'crops': f"""🌾 **Совет: По культурам**

📅 **Для текущего сезона ({datetime.now().strftime('%B')})**

{self._get_seasonal_advice_ru(current_month, 'crops')}

🌱 **Рекомендуемые сорта:**
• Пшеница: Крошка, Одесская 267
• Хлопок: С-6524, Бухара-8
• Томаты: Волгоград, Рио Гранде
• Морковь: Нантская, Шантане

📊 **Ожидаемая урожайность:**
• Пшеница: 45-60 ц/га
• Хлопок: 30-40 ц/га
• Томаты: 60-80 ц/га

💡 **Важно:** Соблюдайте севооборот каждые 3-4 года.""",

            'irrigation': f"""💧 **Совет: По орошению**

{self._get_seasonal_advice_ru(current_month, 'irrigation')}

⏰ **График полива:**
• Пшеница: 5-6 раз, каждые 12-15 дней
• Хлопок: 6-8 раз, каждые 10-12 дней
• Томаты: каждые 5-7 дней
• Морковь: каждые 7-10 дней

💧 **Нормы воды:**
• Пшеница: 400-500 м³/га
• Хлопок: 600-800 м³/га
• Томаты: 300-400 м³/га

🔍 **Контроль:** Регулярно проверяйте влажность почвы.""",

            'fertilizer': f"""🧪 **Совет: По удобрениям**

{self._get_seasonal_advice_ru(current_month, 'fertilizer')}

📊 **Нормы NPK (кг/га):**
• Пшеница: N-120, P-60, K-40
• Хлопок: N-200, P-140, K-100
• Томаты: N-100, P-80, K-120

📅 **Сроки внесения:**
1. Основное: перед посевом
2. Подкормка: 2-3 раза за сезон

🌿 **Органика:** Навоз (20-30 т/га) ежегодно""",

            'pest': f"""🐛 **Совет: По вредителям**

{self._get_seasonal_advice_ru(current_month, 'pest')}

⚠️ **Основные вредители:**
• Хлопковая совка
• Тля (aphids)
• Ржавчина
• Фитофтороз

🛡 **Меры защиты:**
1. Профилактика: очистка полей
2. Биологические: Trichoderma, энтомофаги
3. Химические: по необходимости

⏰ **Обработка:** рано утром или вечером""",

            'weather': f"""🌤 **Совет: По погоде**

{self._get_seasonal_advice_ru(current_month, 'weather')}

🌡 **Текущие условия:**
• Температура: средняя {self._get_avg_temp(current_month)}°C
• Осадки: {self._get_precipitation(current_month)}

📋 **Рекомендации:**
• Следите за прогнозом погоды
• В жару увеличьте полив
• Готовьтесь к заморозкам заранее"""
        }

        return advice_uz.get(category, advice_uz['crops']) if language == 'uz' else advice_ru.get(category,
                                                                                                  advice_ru['crops'])

    def _get_seasonal_advice_uz(self, month: int, category: str) -> str:
        """Сезонные советы на узбекском"""
        season_advice = {
            1: "❄️ Qish: Yer tayyorlash, o'g'it sepish",
            2: "🌱 Qish oxiri: Bahor ekinlari uchun tayyorgarlik",
            3: "🌸 Bahor boshi: Bug'doy sepish, bog' parvarishi",
            4: "☀️ Bahor: Yoz ekinlarini ekish, sug'orish",
            5: "🌾 Bahor oxiri: O'sishni nazorat qilish",
            6: "☀️ Yoz boshi: Muntazam sug'orish va parvarish",
            7: "🌡 Yoz: Ko'p sug'orish, zararkunandalarga qarshi kurash",
            8: "🌾 Yoz oxiri: Hosil yig'ish boshlash",
            9: "🍂 Kuz boshi: Hosil yig'ish davom etishi",
            10: "🍁 Kuz: Kuzgi ekishni boshlash",
            11: "🍂 Kuz oxiri: Yer tayyorlash, qishki ekinlar",
            12: "❄️ Qish boshi: Qishki parvarish choralari"
        }
        return season_advice.get(month, "")

    def _get_seasonal_advice_ru(self, month: int, category: str) -> str:
        """Сезонные советы на русском"""
        season_advice = {
            1: "❄️ Зима: Подготовка почвы, внесение удобрений",
            2: "🌱 Конец зимы: Подготовка к весенним работам",
            3: "🌸 Начало весны: Сев пшеницы, уход за садами",
            4: "☀️ Весна: Посев летних культур, начало полива",
            5: "🌾 Конец весны: Контроль роста растений",
            6: "☀️ Начало лета: Регулярный полив и уход",
            7: "🌡 Лето: Интенсивный полив, борьба с вредителями",
            8: "🌾 Конец лета: Начало уборки урожая",
            9: "🍂 Начало осени: Продолжение уборки",
            10: "🍁 Осень: Начало осеннего сева",
            11: "🍂 Конец осени: Подготовка почвы, озимые",
            12: "❄️ Начало зимы: Зимний уход"
        }
        return season_advice.get(month, "")

    def _get_avg_temp(self, month: int) -> int:
        """Средняя температура по месяцам для Узбекистана"""
        temps = {1: 0, 2: 3, 3: 10, 4: 17, 5: 23, 6: 28,
                 7: 30, 8: 28, 9: 23, 10: 15, 11: 8, 12: 2}
        return temps.get(month, 15)

    def _get_precipitation(self, month: int) -> str:
        """Информация об осадках"""
        if month in [12, 1, 2, 3]:
            return "Ko'p / Умеренные"
        elif month in [4, 5, 10, 11]:
            return "O'rtacha / Средние"
        else:
            return "Kam / Низкие"