"""
AgroAI - Умный Telegram-бот для агрономии
Версия: 3.0.0 (ПРАВИЛЬНАЯ АРХИТЕКТУРА)
Python 3.12.7

АРХИТЕКТУРА:
1. 📸 Анализ Растения - фото → Claude Vision → рекомендации
2. 🛰 NDVI Анализ - координаты → Satellite → Claude AI советы
3. 💳 Кредит - данные → скоринг
4. 💡 AI Советы - категория → Claude советы
"""
from dotenv import load_dotenv

load_dotenv()
import asyncio
import logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from config import BOT_TOKEN, ANTHROPIC_API_KEY, SATELLITE_API_KEY
from modules.crop_analyzer import CropAnalyzer
from modules.ai_advisor import AIAdvisor
from modules.credit_analyzer import CreditAnalyzer
from modules.database import Database
from io import BytesIO

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Тексты интерфейса
TEXTS = {
    'uz': {
        'welcome': "🌾 AgroAI ga xush kelibsiz!\n\nQishloq xo'jaligi uchun AI yordamchisi.",
        'menu': "📱 Asosiy menyu:",

        # Главные кнопки
        'plant_analysis': "📸 O'simlik Tahlili",
        'ndvi_analysis': "🛰 NDVI Tahlili",
        'credit': "💳 Kredit",
        'advice': "💡 AI Maslahat",
        'settings': "⚙️ Sozlamalar",

        # Запросы
        'send_photo': "📸 O'simlik rasmini yuboring\n\n✅ Aniq rasm chiqaring\n✅ Yorug'likda suratga oling\n✅ Barg yoki butun o'simlikni ko'rsating",
        'send_coordinates': "📍 Dala koordinatalarini yuboring:\n\n**Format 1** (nuqta):\n41.2995, 69.2401\n\n**Format 2** (maydon):\n41.29, 69.24, 41.30, 69.25\n\nYoki 'Joylashuv yuborish' tugmasini bosing 👇",
        'send_location_btn': "📍 Joylashuv yuborish",
        'back': "◀️ Orqaga",

        # Процессы
        'analyzing_photo': "🔍 Rasmni tahlil qilmoqda...\n⏳ 10-15 soniya",
        'loading_satellite': "🛰 Sun'iy yo'ldosh ma'lumotlari yuklanmoqda...\n⏳ 5-10 soniya",
        'generating_advice': "🤖 AI tavsiyalar tayyorlanmoqda...",

        # Кредит
        'send_credit_data': "💰 Kredit uchun ma'lumotlarni kiriting:\n\n📝 Format:\nDaromad: 10000000\nYer: 15 gektar\nTajriba: 5 yil\nKredit tarixi: yaxshi",

        # Советы
        'choose_category': "📚 Kategoriya tanlang:",
        'crops': "🌾 Ekinlar",
        'irrigation': "💧 Sug'orish",
        'fertilizer': "🧪 O'g'itlar",
        'pest': "🐛 Zararkunandalar",
        'weather': "🌤 Ob-havo",

        # Сообщения
        'error': "❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.",
        'invalid_coords': "❌ Koordinatalar noto'g'ri!\n\n✅ To'g'ri format:\n41.2995, 69.2401",
        'success': "✅ Tayyor!",
        'language': "🌐 Til",
        'language_changed': "✅ Til o'zgartirildi!"
    },
    'ru': {
        'welcome': "🌾 Добро пожаловать в AgroAI!\n\nИскусственный интеллект для сельского хозяйства.",
        'menu': "📱 Главное меню:",

        # Главные кнопки
        'plant_analysis': "📸 Анализ Растения",
        'ndvi_analysis': "🛰 NDVI Анализ",
        'credit': "💳 Кредит",
        'advice': "💡 AI Советы",
        'settings': "⚙️ Настройки",

        # Запросы
        'send_photo': "📸 Отправьте фото растения\n\n✅ Сделайте четкое фото\n✅ Снимайте при хорошем освещении\n✅ Покажите листья или все растение",
        'send_coordinates': "📍 Отправьте координаты поля:\n\n**Формат 1** (точка):\n41.2995, 69.2401\n\n**Формат 2** (площадь):\n41.29, 69.24, 41.30, 69.25\n\nИли нажмите 'Отправить локацию' 👇",
        'send_location_btn': "📍 Отправить локацию",
        'back': "◀️ Назад",

        # Процессы
        'analyzing_photo': "🔍 Анализируем фото...\n⏳ 10-15 секунд",
        'loading_satellite': "🛰 Загружаем спутниковые данные...\n⏳ 5-10 секунд",
        'generating_advice': "🤖 Генерируем AI рекомендации...",

        # Кредит
        'send_credit_data': "💰 Введите данные для кредита:\n\n📝 Формат:\nДоход: 10000000\nЗемля: 15 гектар\nСтаж: 5 лет\nКредитная история: хорошая",

        # Советы
        'choose_category': "📚 Выберите категорию:",
        'crops': "🌾 Культуры",
        'irrigation': "💧 Орошение",
        'fertilizer': "🧪 Удобрения",
        'pest': "🐛 Вредители",
        'weather': "🌤 Погода",

        # Сообщения
        'error': "❌ Произошла ошибка. Попробуйте снова.",
        'invalid_coords': "❌ Неверные координаты!\n\n✅ Правильный формат:\n41.2995, 69.2401",
        'success': "✅ Готово!",
        'language': "🌐 Язык",
        'language_changed': "✅ Язык изменен!"
    }
}


class AgroAIBot:
    def __init__(self):
        self.db = Database()
        self.crop_analyzer = CropAnalyzer(api_key=ANTHROPIC_API_KEY)
        self.credit_analyzer = CreditAnalyzer()
        self.ai_advisor = AIAdvisor(ANTHROPIC_API_KEY)

    def get_text(self, user_id: int, key: str) -> str:
        """Получить текст на языке пользователя"""
        lang = self.db.get_user_language(user_id)
        return TEXTS[lang].get(key, key)

    def get_main_keyboard(self, user_id: int):
        """Главная клавиатура - 4 кнопки"""
        lang = self.db.get_user_language(user_id)
        keyboard = [
            [KeyboardButton(TEXTS[lang]['plant_analysis'])],
            [KeyboardButton(TEXTS[lang]['ndvi_analysis'])],
            [KeyboardButton(TEXTS[lang]['credit']), KeyboardButton(TEXTS[lang]['advice'])],
            [KeyboardButton(TEXTS[lang]['settings'])]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    def get_location_keyboard(self, user_id: int):
        """Клавиатура с кнопкой геолокации"""
        lang = self.db.get_user_language(user_id)
        keyboard = [
            [KeyboardButton(TEXTS[lang]['send_location_btn'], request_location=True)],
            [KeyboardButton(TEXTS[lang]['back'])]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        user_id = update.effective_user.id

        if not self.db.user_exists(user_id):
            # Выбор языка для новых пользователей
            keyboard = [
                [InlineKeyboardButton("O'zbekcha 🇺🇿", callback_data="lang_uz")],
                [InlineKeyboardButton("Русский 🇷🇺", callback_data="lang_ru")]
            ]
            await update.message.reply_text(
                "Tilni tanlang / Выберите язык:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text(
                self.get_text(user_id, 'welcome'),
                reply_markup=self.get_main_keyboard(user_id)
            )

    async def language_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выбор языка"""
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        lang = query.data.split('_')[1]

        self.db.register_user(user_id, query.from_user.username, lang)
        await query.edit_message_text(TEXTS[lang]['welcome'])

        await context.bot.send_message(
            chat_id=user_id,
            text=TEXTS[lang]['menu'],
            reply_markup=self.get_main_keyboard(user_id)
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик всех текстовых сообщений"""
        user_id = update.effective_user.id
        text = update.message.text
        state = self.db.get_user_state(user_id)

        # ═══════════════════════════════════════════════════════
        # ГЛАВНОЕ МЕНЮ
        # ═══════════════════════════════════════════════════════

        # 1️⃣ АНАЛИЗ РАСТЕНИЯ (только фото)
        if text == self.get_text(user_id, 'plant_analysis'):
            self.db.set_user_state(user_id, 'awaiting_plant_photo')
            await update.message.reply_text(
                self.get_text(user_id, 'send_photo'),
                reply_markup=self.get_main_keyboard(user_id)
            )

        # 2️⃣ NDVI АНАЛИЗ (только координаты)
        elif text == self.get_text(user_id, 'ndvi_analysis'):
            self.db.set_user_state(user_id, 'awaiting_ndvi_coords')
            await update.message.reply_text(
                self.get_text(user_id, 'send_coordinates'),
                reply_markup=self.get_location_keyboard(user_id)
            )

        # 3️⃣ КРЕДИТ
        elif text == self.get_text(user_id, 'credit'):
            self.db.set_user_state(user_id, 'awaiting_credit')
            await update.message.reply_text(
                self.get_text(user_id, 'send_credit_data'),
                reply_markup=self.get_main_keyboard(user_id)
            )

        # 4️⃣ AI СОВЕТЫ
        elif text == self.get_text(user_id, 'advice'):
            await self.show_advice_categories(update, user_id)

        # ⚙️ НАСТРОЙКИ
        elif text == self.get_text(user_id, 'settings'):
            await self.show_settings(update, user_id)

        # ◀️ НАЗАД
        elif text == self.get_text(user_id, 'back'):
            self.db.set_user_state(user_id, None)
            await update.message.reply_text(
                self.get_text(user_id, 'menu'),
                reply_markup=self.get_main_keyboard(user_id)
            )

        # ═══════════════════════════════════════════════════════
        # ОБРАБОТКА СОСТОЯНИЙ
        # ═══════════════════════════════════════════════════════

        elif state == 'awaiting_ndvi_coords':
            await self.process_ndvi_coordinates(update, context, user_id, text)

        elif state == 'awaiting_credit':
            await self.process_credit_data(update, context, user_id, text)
            
        elif state == 'awaiting_advice_question':
             await self.process_advice_question(update, context, user_id, text)

    # ═══════════════════════════════════════════════════════════════
    # 1️⃣ АНАЛИЗ РАСТЕНИЯ (ФОТО → CLAUDE VISION → РЕКОМЕНДАЦИИ)
    # ═══════════════════════════════════════════════════════════════

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка фото растения"""
        user_id = update.effective_user.id
        state = self.db.get_user_state(user_id)

        if state != 'awaiting_plant_photo':
            return

        lang = self.db.get_user_language(user_id)
        chat_id = update.effective_chat.id

        # Сообщение о начале анализа
        msg = await update.message.reply_text(
            self.get_text(user_id, 'analyzing_photo')
        )

        try:
            # Скачивание фото
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)

            photo_bytes = BytesIO()
            await file.download_to_memory(photo_bytes)
            photo_bytes.seek(0)
            image_bytes = photo_bytes.read()

            # АНАЛИЗ ТОЛЬКО ФОТО через Claude Vision
            logger.info(f"[PLANT] Analyzing photo for user {user_id}")

            result = await self.crop_analyzer.analyze_plant_only(
                image_bytes=image_bytes,
                lang=lang,
                chat_id=chat_id,
                bot=context.bot
            )

            await msg.delete()

            # Отправка результата
            await update.message.reply_text(
                result['text'],
                parse_mode='Markdown',
                reply_markup=self.get_main_keyboard(user_id)
            )

            # Сохранение в БД
            self.db.save_plant_analysis(user_id, result['analysis'])

            # Сброс состояния
            self.db.set_user_state(user_id, None)

        except Exception as e:
            logger.error(f"[PLANT] Error: {e}")
            import traceback
            traceback.print_exc()

            try:
                await msg.delete()
            except:
                pass

            await update.message.reply_text(
                self.get_text(user_id, 'error') + f"\n\n{str(e)[:100]}",
                reply_markup=self.get_main_keyboard(user_id)
            )

    # ═══════════════════════════════════════════════════════════════
    # 2️⃣ NDVI АНАЛИЗ (КООРДИНАТЫ → SATELLITE → CLAUDE AI СОВЕТЫ)
    # ═══════════════════════════════════════════════════════════════

    async def handle_location(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка геолокации"""
        user_id = update.effective_user.id
        state = self.db.get_user_state(user_id)

        if state == 'awaiting_ndvi_coords':
            location = update.message.location
            coords_text = f"{location.latitude}, {location.longitude}"
            await self.process_ndvi_coordinates(update, context, user_id, coords_text)

    async def process_ndvi_coordinates(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                       user_id: int, text: str):
        """Обработка координат для NDVI анализа"""
        lang = self.db.get_user_language(user_id)

        try:
            # Парсинг координат
            coords = text.replace(',', ' ').replace(';', ' ').split()
            coords = [float(c) for c in coords if c.replace('.', '').replace('-', '').isdigit()]

            if len(coords) == 2:
                # Одна точка
                lat, lon = coords[0], coords[1]
                bbox = None
            elif len(coords) == 4:
                # Ограничивающий прямоугольник (BBOX) или две точки? 
                # Предполагаем bbox: min_lat, min_lon, max_lat, max_lon
                # Нормаизуем
                lats = [coords[0], coords[2]]
                lons = [coords[1], coords[3]]
                lat = sum(lats) / 2
                lon = sum(lons) / 2
                bbox = [min(lons), min(lats), max(lons), max(lats)]
                logger.info(f"📍 BBox detected: {bbox}")
            elif len(coords) >= 6 and len(coords) % 2 == 0:
                # Полигон (3+ точки)
                # Извлекаем lats и lons
                lats = coords[0::2]
                lons = coords[1::2]
                
                # Центр
                lat = sum(lats) / len(lats)
                lon = sum(lons) / len(lons)
                
                # BBox из всех точек
                bbox = [min(lons), min(lats), max(lons), max(lats)]
                logger.info(f"📍 Polygon detected ({len(lats)} points). BBox: {bbox}")
            else:
                raise ValueError("Invalid format")

            # Валидация
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError("Out of range")

            # Сообщение о загрузке
            msg = await update.message.reply_text(
                self.get_text(user_id, 'loading_satellite')
            )

            # ПОЛУЧЕНИЕ NDVI ДАННЫХ
            logger.info(f"[NDVI] Getting satellite data for {lat}, {lon}")

            ndvi_result = await self.crop_analyzer.analyze_ndvi_only(
                lat=lat,
                lon=lon,
                lang=lang,
                bbox=bbox
            )

            await msg.edit_text(self.get_text(user_id, 'generating_advice'))

            # ГЕНЕРАЦИЯ AI СОВЕТОВ на основе РЕАЛЬНЫХ данных NDVI
            logger.info(f"[NDVI] Generating AI advice based on NDVI={ndvi_result['ndvi_value']:.3f}")

            ai_advice = await self.crop_analyzer.generate_ndvi_advice(
                ndvi_data=ndvi_result,
                lat=lat,
                lon=lon,
                lang=lang
            )

            await msg.delete()

            # ФИНАЛЬНЫЙ ОТВЕТ
            response = (
                f"🛰 **NDVI Tahlili / NDVI Анализ**\n\n"
                f"📍 **Koordinatalar / Координаты:**\n"
                f"`{lat:.6f}, {lon:.6f}`\n\n"
                f"{ndvi_result['summary']}\n\n"
                f"{'─' * 30}\n\n"
                f"🤖 **AI Tavsiyalar / AI Рекомендации:**\n\n"
                f"{ai_advice}"
            )

            await update.message.reply_text(
                response,
                parse_mode='Markdown',
                reply_markup=self.get_main_keyboard(user_id)
            )

            # Сохранение в БД
            self.db.save_ndvi_analysis(user_id, lat, lon, ndvi_result)

            # Сброс состояния
            self.db.set_user_state(user_id, None)

        except ValueError as e:
            logger.error(f"[NDVI] Invalid coordinates: {e}")
            await update.message.reply_text(
                self.get_text(user_id, 'invalid_coords'),
                reply_markup=self.get_location_keyboard(user_id)
            )
        except Exception as e:
            logger.error(f"[NDVI] Error: {e}")
            import traceback
            traceback.print_exc()

            try:
                if 'msg' in locals():
                    await msg.delete()
            except:
                pass

            await update.message.reply_text(
                self.get_text(user_id, 'error'),
                reply_markup=self.get_main_keyboard(user_id)
            )

    # ═══════════════════════════════════════════════════════════════
    # 3️⃣ КРЕДИТНЫЙ АНАЛИЗ
    # ═══════════════════════════════════════════════════════════════

    async def process_credit_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                  user_id: int, data_text: str):
        """Обработка кредитных данных"""
        lang = self.db.get_user_language(user_id)

        try:
            msg = await update.message.reply_text("⏳ Обрабатываем..." if lang == 'ru' else "⏳ Qayta ishlanmoqda...")

            result = await self.credit_analyzer.analyze(data_text)

            await msg.delete()

            response = self.format_credit_result(result, lang)
            await update.message.reply_text(
                response,
                parse_mode='Markdown',
                reply_markup=self.get_main_keyboard(user_id)
            )

            self.db.save_credit_analysis(user_id, result)
            self.db.set_user_state(user_id, None)

        except Exception as e:
            logger.error(f"[CREDIT] Error: {e}")
            await update.message.reply_text(
                self.get_text(user_id, 'error'),
                reply_markup=self.get_main_keyboard(user_id)
            )

    def format_credit_result(self, result: dict, lang: str) -> str:
        """Форматирование кредитного результата"""
        if lang == 'uz':
            return f"""💳 **Kredit Tahlili**

📊 Reyting: {result['score']}/100
✅ {result['status_uz']}

💰 Maks kredit: {result['max_credit']:,.0f} so'm
📅 Muddat: {result['recommended_term']} oy
💵 Oylik: {result['monthly_payment']:,.0f} so'm
💹 Stavka: {result['interest_rate']}%

📝 **Tavsiyalar:**
{result['recommendations_uz']}"""
        else:
            return f"""💳 **Кредитный Анализ**

📊 Рейтинг: {result['score']}/100
✅ {result['status_ru']}

💰 Макс кредит: {result['max_credit']:,.0f} сум
📅 Срок: {result['recommended_term']} мес
💵 Платеж: {result['monthly_payment']:,.0f} сум
💹 Ставка: {result['interest_rate']}%

📝 **Рекомендации:**
{result['recommendations_ru']}"""

    # ═══════════════════════════════════════════════════════════════
    # 4️⃣ AI СОВЕТЫ
    # ═══════════════════════════════════════════════════════════════

    async def show_advice_categories(self, update: Update, user_id: int):
        """Категории советов"""
        lang = self.db.get_user_language(user_id)
        keyboard = [
            [InlineKeyboardButton(TEXTS[lang]['crops'], callback_data="advice_crops")],
            [InlineKeyboardButton(TEXTS[lang]['irrigation'], callback_data="advice_irrigation")],
            [InlineKeyboardButton(TEXTS[lang]['fertilizer'], callback_data="advice_fertilizer")],
            [InlineKeyboardButton(TEXTS[lang]['pest'], callback_data="advice_pest")],
            [InlineKeyboardButton(TEXTS[lang]['weather'], callback_data="advice_weather")]
        ]
        await update.message.reply_text(
            self.get_text(user_id, 'choose_category') + "\n\n⌨️ Yoki savolingizni yozing / Или напишите свой вопрос:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        # Устанавливаем состояние ожидания вопроса
        self.db.set_user_state(user_id, 'awaiting_advice_question')

    async def process_advice_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str):
        """Обработка свободного вопроса AI"""
        lang = self.db.get_user_language(user_id)
        
        msg = await update.message.reply_text("🤖..." if lang == 'ru' else "🤖...")
        
        try:
            advice = await self.ai_advisor.get_advice("crops", lang, custom_question=text)
            await msg.delete()
            
            await update.message.reply_text(
                f"🤖 **AI Javob / Ответ:**\n\n{advice}",
                parse_mode='Markdown',
                reply_markup=self.get_main_keyboard(user_id)
            )
            self.db.set_user_state(user_id, None)
            
        except Exception as e:
            logger.error(f"AI Q&A error: {e}")
            await msg.edit_text("Error")

    async def advice_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка запроса советов"""
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        category = query.data.split('_')[1]
        lang = self.db.get_user_language(user_id)

        await query.edit_message_text("⏳ Генерируем советы..." if lang == 'ru' else "⏳ Maslahatlar tayyorlanmoqda...")

        advice = await self.ai_advisor.get_advice(category, lang)
        await query.edit_message_text(advice, parse_mode='Markdown')

    # ═══════════════════════════════════════════════════════════════
    # ⚙️ НАСТРОЙКИ
    # ═══════════════════════════════════════════════════════════════

    async def show_settings(self, update: Update, user_id: int):
        """Настройки"""
        keyboard = [
            [InlineKeyboardButton(self.get_text(user_id, 'language'), callback_data="change_lang")]
        ]
        await update.message.reply_text(
            self.get_text(user_id, 'settings'),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def change_language_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Смена языка"""
        query = update.callback_query
        await query.answer()

        keyboard = [
            [InlineKeyboardButton("O'zbekcha 🇺🇿", callback_data="setlang_uz")],
            [InlineKeyboardButton("Русский 🇷🇺", callback_data="setlang_ru")]
        ]
        await query.edit_message_text(
            "Tilni tanlang / Выберите язык:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def set_language_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Установка языка"""
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        new_lang = query.data.split('_')[1]

        self.db.set_user_language(user_id, new_lang)
        await query.edit_message_text(TEXTS[new_lang]['language_changed'])

        await context.bot.send_message(
            chat_id=user_id,
            text=TEXTS[new_lang]['menu'],
            reply_markup=self.get_main_keyboard(user_id)
        )


def main():
    """Запуск бота"""
    bot = AgroAIBot()
    application = Application.builder().token(BOT_TOKEN).build()

    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CallbackQueryHandler(bot.language_callback, pattern="^lang_"))
    application.add_handler(CallbackQueryHandler(bot.change_language_callback, pattern="^change_lang$"))
    application.add_handler(CallbackQueryHandler(bot.set_language_callback, pattern="^setlang_"))
    application.add_handler(CallbackQueryHandler(bot.advice_callback, pattern="^advice_"))
    application.add_handler(MessageHandler(filters.LOCATION, bot.handle_location))
    application.add_handler(MessageHandler(filters.PHOTO, bot.handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))

    logger.info("🚀 AgroAI Bot v3.0 запущен!")
    logger.info(f"✅ Claude AI: {'Активен' if ANTHROPIC_API_KEY else '❌ НЕ НАСТРОЕН'}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()