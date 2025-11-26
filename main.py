"""
AgroAI - Умный Telegram-бот для агрономии
Версия: 2.0.0 (интеграция с Planetary Computer + Open-Meteo)
Python 3.12.7
"""

import logging
import json
from io import BytesIO
from datetime import datetime

from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

# Модули
from config import BOT_TOKEN, ANTHROPIC_API_KEY
from modules.database import Database
from modules.crop_analyzer import CropAnalyzer
from modules.credit_analyzer import CreditAnalyzer
from modules.ai_advisor import AIAdvisor
from modules.fields_manager import FieldsManager

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ========================== ТЕКСТЫ ===============================

TEXTS = {
    'uz': {
        'welcome': "🌾 AgroAI ga xush kelibsiz!\n\nSun'iy intellekt yordamidagi qishloq xo'jalik assistenti.",
        'menu': "📱 Asosiy menyu:",
        'full_analysis': "🔬 To‘liq Tahlil",
        'my_fields': "🗺 Mening Dalalarim",
        'add_field': "➕ Dala Qo‘shish",
        'ndvi': "🛰 NDVI Tahlili",
        'plant': "🌱 O‘simlik Tahlili",
        'credit': "💳 Kredit Tahlili",
        'advice': "💡 AI Maslahat",
        'settings': "⚙️ Sozlamalar",
        'language': "🌐 Til",
        'send_location': "📍 Joylashuvni yuboring yoki koordinatalarni kiriting",
        'send_photo': "📸 O‘simlik fotosuratini yuboring",
        'send_credit_data': "💰 Ma'lumotlarni kiriting:\nDaromad:...\nYer:...\nTajriba:...",
        'choose_category': "Maslahat turini tanlang:",
        'processing': "⏳ Tahlil qilinmoqda...",
        'full_analysis_desc': "Fotosurat va koordinatalarni yuboring — to‘liq tahlil olasiz!",
        'stats': "📊 Statistika",
        'history': "📜 Tarix"
    },
    'ru': {
        'welcome': "🌾 Добро пожаловать в AgroAI!\n\nИИ ассистент для сельского хозяйства.",
        'menu': "📱 Главное меню:",
        'full_analysis': "🔬 Полный Анализ",
        'my_fields': "🗺 Мои Поля",
        'add_field': "➕ Добавить Поле",
        'ndvi': "🛰 NDVI Анализ",
        'plant': "🌱 Анализ Растений",
        'credit': "💳 Кредитный Анализ",
        'advice': "💡 AI Советы",
        'settings': "⚙️ Настройки",
        'language': "🌐 Язык",
        'send_location': "📍 Отправьте локацию или координаты",
        'send_photo': "📸 Отправьте фото растения",
        'send_credit_data': "💰 Введите данные:\nДоход...\nЗемля...\nСтаж...",
        'choose_category': "Выберите категорию:",
        'processing': "⏳ Обрабатывается...",
        'full_analysis_desc': "Фото + координаты — и получите полный анализ!",
        'stats': "📊 Статистика",
        'history': "📜 История"
    }
}


# ========================== BOT CLASS ===============================

class AgroAIBot:
    def __init__(self):
        self.db = Database()
        self.fields_manager = FieldsManager(self.db)
        self.crop_analyzer = CropAnalyzer()
        self.credit_analyzer = CreditAnalyzer()
        self.ai_advisor = AIAdvisor(ANTHROPIC_API_KEY)

        # Для полного анализа — временное хранилище
        self.temp_storage = {}

    # ----------------- UI helpers ---------------------

    def get_text(self, user_id, key):
        lang = self.db.get_user_language(user_id)
        return TEXTS[lang].get(key, key)

    def get_main_keyboard(self, user_id):
        lang = self.db.get_user_language(user_id)
        keyboard = [
            [TEXTS[lang]['full_analysis']],
            [TEXTS[lang]['my_fields'], TEXTS[lang]['add_field']],
            [TEXTS[lang]['ndvi'], TEXTS[lang]['plant']],
            [TEXTS[lang]['credit'], TEXTS[lang]['advice']],
            [TEXTS[lang]['stats'], TEXTS[lang]['settings']]
        ]
        return ReplyKeyboardMarkup([[KeyboardButton(x) for x in row] for row in keyboard],
                                   resize_keyboard=True)

    # ======================= START ============================

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id

        if not self.db.user_exists(user_id):
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("O'zbekcha 🇺🇿", callback_data="lang_uz")],
                [InlineKeyboardButton("Русский 🇷🇺", callback_data="lang_ru")]
            ])
            await update.message.reply_text("Tilni tanlang / Выберите язык:", reply_markup=keyboard)
        else:
            await update.message.reply_text(
                self.get_text(user_id, "welcome"),
                reply_markup=self.get_main_keyboard(user_id)
            )

    async def language_callback(self, update: Update, context):
        q = update.callback_query
        await q.answer()

        user_id = q.from_user.id
        lang = q.data.split("_")[1]

        self.db.register_user(user_id, q.from_user.username, lang)
        await q.edit_message_text(TEXTS[lang]["welcome"])
        await q.message.reply_text(TEXTS[lang]["menu"], reply_markup=self.get_main_keyboard(user_id))

    # ====================== MESSAGE HANDLER =====================

    async def handle_message(self, update: Update, context):
        user_id = update.effective_user.id
        text = update.message.text
        state = self.db.get_user_state(user_id)

        lang = self.db.get_user_language(user_id)

        # ------------ MAIN MENU ------------
        if text == TEXTS[lang]['add_field']:
            await self.start_add_field(update, user_id)
            return

        if text == TEXTS[lang]['my_fields']:
            await self.show_my_fields(update, user_id)
            return

        if text == TEXTS[lang]['ndvi']:
            self.db.set_user_state(user_id, "awaiting_ndvi_coords")
            await update.message.reply_text(TEXTS[lang]['send_location'])
            return

        if text == TEXTS[lang]['full_analysis']:
            self.db.set_user_state(user_id, "awaiting_full_coords")
            await update.message.reply_text(
                self.get_text(user_id, 'full_analysis_desc') + "\n\n" +
                TEXTS[lang]['send_location']
            )
            return

        if text == TEXTS[lang]['plant']:
            self.db.set_user_state(user_id, "awaiting_plant_photo")
            await update.message.reply_text(TEXTS[lang]['send_photo'])
            return

        if text == TEXTS[lang]['credit']:
            self.db.set_user_state(user_id, "awaiting_credit")
            await update.message.reply_text(TEXTS[lang]['send_credit_data'])
            return

        # ------------ STATES ------------
        if state == "awaiting_add_field":
            await self.process_add_field(update, context, user_id, text)
            return

        if state == "awaiting_ndvi_coords":
            await self.process_ndvi_coordinates(update, context, user_id, text)
            return

        if state == "awaiting_full_coords":
            await self.process_full_analysis_coords(update, context, user_id, text)
            return

        if state == "awaiting_credit":
            await self.process_credit_data(update, context, user_id, text)
            return

    # ====================== LOCATION ===========================

    async def handle_location(self, update: Update, context):
        user_id = update.effective_user.id
        lat = update.message.location.latitude
        lon = update.message.location.longitude

        state = self.db.get_user_state(user_id)

        coords_text = f"{lat}, {lon}"

        if state == "awaiting_full_coords":
            await self.process_full_analysis_coords(update, context, user_id, coords_text)

        if state == "awaiting_ndvi_coords":
            await self.process_ndvi_coordinates(update, context, user_id, coords_text)

    # ====================== NDVI ===============================

    async def process_ndvi_coordinates(self, update, context, user_id, coords_text):
        lang = self.db.get_user_language(user_id)
        try:
            # Agar bir nechta qator bo'lsa -> polygon
            lines = [ln.strip() for ln in coords_text.strip().splitlines() if ln.strip()]
            if len(lines) >= 4:
                # polygon parsing
                coords = []
                for line in lines:
                    parts = line.replace(",", " ").split()
                    if len(parts) < 2:
                        raise ValueError("Invalid coordinate line")
                    lat = float(parts[0])
                    lon = float(parts[1])
                    coords.append((lat, lon))

                await update.message.reply_text(TEXTS[lang]["processing"])

                result = await self.crop_analyzer.get_ndvi_polygon(coords, lang)

                await update.message.reply_text(result['text'], parse_mode="Markdown")

                if result.get("ndvi_png"):
                    bio = BytesIO()
                    result["ndvi_png"].save(bio, "PNG")
                    bio.seek(0)
                    await update.message.reply_photo(bio, caption="NDVI (mini)")

                # Save analysis
                self.db.save_ndvi_analysis(user_id, coords, result)
                self.db.set_user_state(user_id, None)
                return

            # otherwise fallback to single point (existing behavior)
            c = coords_text.replace(",", " ").split()
            lat, lon = float(c[0]), float(c[1])

            await update.message.reply_text(TEXTS[lang]["processing"])

            result = await self.crop_analyzer.get_ndvi(lat, lon, lang)
            await update.message.reply_text(result['text'], parse_mode="Markdown")

            if result.get("ndvi_png"):
                bio = BytesIO()
                result["ndvi_png"].save(bio, "PNG")
                bio.seek(0)
                await update.message.reply_photo(bio, caption="NDVI")

            self.db.save_ndvi_analysis(user_id, lat, lon, result)
            self.db.set_user_state(user_id, None)

        except Exception as e:
            logger.exception("Error in process_ndvi_coordinates")
            await update.message.reply_text("❌ Koordinatalar noto'g'ri / Неверные координаты")

    # ========== FULL ANALYSIS (1 — COORDS, 2 — PHOTO) ==========

    async def process_full_analysis_coords(self, update, context, user_id, coords_text):
        lang = self.db.get_user_language(user_id)
        try:
            c = coords_text.replace(",", " ").split()
            lat, lon = float(c[0]), float(c[1])

            self.temp_storage[user_id] = {"lat": lat, "lon": lon}
            self.db.set_user_state(user_id, "awaiting_full_photo")

            await update.message.reply_text("📸 Endi fotosurat yuboring!")

        except:
            await update.message.reply_text("❌ Koordinatalar noto‘g‘ri")

    async def handle_photo(self, update, context):
        user_id = update.effective_user.id
        state = self.db.get_user_state(user_id)
        lang = self.db.get_user_language(user_id)

        if state not in ["awaiting_plant_photo", "awaiting_full_photo"]:
            return

        await update.message.reply_text(TEXTS[lang]["processing"])

        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        img_bytes = await file.download_as_bytearray()

        if state == "awaiting_plant_photo":
            result = await self.crop_analyzer.analyze_photo(bytes(img_bytes))
            text = f"📸 O‘simlik: {result['label']}\nIshonch: {result['confidence']*100:.1f}%"
            await update.message.reply_text(text)
            self.db.save_plant_analysis(user_id, result)
            self.db.set_user_state(user_id, None)
            return

        if state == "awaiting_full_photo":
            coords = self.temp_storage[user_id]
            result = await self.crop_analyzer.analyze(
                coords["lat"], coords["lon"], bytes(img_bytes), lang
            )

            await update.message.reply_text(result['text'], parse_mode="Markdown")

            if result.get("ndvi_png"):
                bio = BytesIO()
                result["ndvi_png"].save(bio, "PNG")
                bio.seek(0)
                await update.message.reply_photo(bio)

            self.db.save_full_analysis(user_id, coords["lat"], coords["lon"], result)
            del self.temp_storage[user_id]
            self.db.set_user_state(user_id, None)

    # ====================== CREDIT ===============================

    async def process_credit_data(self, update, context, user_id, data_text):
        lang = self.db.get_user_language(user_id)
        await update.message.reply_text(TEXTS[lang]["processing"])

        result = await self.credit_analyzer.analyze(data_text)
        self.db.save_credit_analysis(user_id, result)

        txt = f"💳 Kredit ball: {result['score']}\n{result['status_uz' if lang=='uz' else 'status_ru']}"
        await update.message.reply_text(txt)
        self.db.set_user_state(user_id, None)

    # ====================== DALALAR ===============================

    async def start_add_field(self, update, user_id):
        lang = self.db.get_user_language(user_id)

        text = "➕ **Yangi dala**\n\nKoordinatalarni yoki to‘liq ma’lumotni yuboring.\n\n" \
               "Agar polygon bo‘lsa — 4 burchakni yuboring:\n\n" \
               "```\n41.29, 69.24\n41.30, 69.25\n41.28, 69.26\n41.27, 69.22\n```"

        self.db.set_user_state(user_id, "awaiting_add_field")
        await update.message.reply_text(text, parse_mode="Markdown")

    async def process_add_field(self, update, context, user_id, text):
        lang = self.db.get_user_language(user_id)

        # 1️⃣ POLYGON BORLIGINI TEKSHIRISH
        polygon = self.fields_manager.parse_polygon_coordinates(text)

        if polygon:
            # 1-nuqta markaz sifatida olinadi
            center_lat, center_lon = polygon[0]

            notes = json.dumps({"polygon": polygon})

            fid = self.fields_manager.add_field(
                user_id=user_id,
                field_name="Polygon dala",
                latitude=center_lat,
                longitude=center_lon,
                notes=notes
            )

            msg = "📐 Polygon qabul qilindi va dala yaratildi!" if lang == "uz" else \
                  "📐 Полигон принят и поле создано!"

            await update.message.reply_text(msg)
            self.db.set_user_state(user_id, None)
            return

        # 2️⃣ AGAR ODDIY MAYDON BO‘LSA
        field_data = self.fields_manager.parse_field_from_text(text, lang)

        if not field_data:
            await update.message.reply_text("❌ Ma'lumot noto‘g‘ri")
            return

        fid = self.fields_manager.add_field(
            user_id=user_id,
            field_name=field_data.get("name", "Yangi dala"),
            latitude=field_data["lat"],
            longitude=field_data["lon"],
            area_hectares=field_data.get("area", 0),
            crop_type=field_data.get("crop", ""),
            notes=field_data.get("notes", "")
        )

        await update.message.reply_text("✅ Dala qo‘shildi!")
        self.db.set_user_state(user_id, None)

    # ====================== DALALAR RO‘YXATI ===============================

    async def show_my_fields(self, update, user_id):
        lang = self.db.get_user_language(user_id)
        fields = self.fields_manager.get_user_fields(user_id)

        if not fields:
            msg = "📭 Sizda hali dala yo‘q." if lang == "uz" else "📭 У вас нет полей."
            await update.message.reply_text(msg)
            return

        text = self.fields_manager.format_field_list(user_id, lang)
        keyboard = [
            [InlineKeyboardButton(f"📍 {f['name']}", callback_data=f"field_{f['id']}")]
            for f in fields
        ]
        keyboard.append(
            [InlineKeyboardButton("➕ Qo‘shish", callback_data="add_new_field")]
            if lang == "uz"
            else [InlineKeyboardButton("➕ Добавить", callback_data="add_new_field")]
        )

        await update.message.reply_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def field_callback(self, update, context):
        q = update.callback_query
        await q.answer()

        user_id = q.from_user.id
        lang = self.db.get_user_language(user_id)

        if q.data == "add_new_field":
            await self.start_add_field(q, user_id)
            return

        field_id = int(q.data.split("_")[1])
        field = self.fields_manager.get_field_by_id(field_id)

        if not field:
            await q.edit_message_text("❌ Field not found")
            return

        crop_emoji = self.fields_manager._get_crop_emoji(field["crop"])

        text = f"{crop_emoji} **{field['name']}**\n\n" \
               f"📍 {field['lat']:.4f}, {field['lon']:.4f}\n"

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🛰 NDVI", callback_data=f"ndvi_{field_id}")
            ],
            [
                InlineKeyboardButton("🗑 O‘chirish", callback_data=f"delete_{field_id}")
                if lang == "uz"
                else InlineKeyboardButton("🗑 Удалить", callback_data=f"delete_{field_id}")
            ]
        ])

        await q.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")

    async def field_action_callback(self, update, context):
        q = update.callback_query
        await q.answer()

        user_id = q.from_user.id
        action, fid = q.data.split("_")
        fid = int(fid)

        field = self.fields_manager.get_field_by_id(fid)

        if action == "ndvi":
            lang = self.db.get_user_language(user_id)
            await q.edit_message_text("🛰 NDVI..." if lang == "uz" else "🛰 NDVI...")
            result = await self.crop_analyzer.get_ndvi(field["lat"], field["lon"], lang)
            await q.message.reply_text(result["text"], parse_mode="Markdown")

        if action == "delete":
            self.fields_manager.delete_field(fid)
            await q.edit_message_text("🗑 O‘chirildi!")


# ======================= MAIN ===========================

def main():
    logger.info("🚀 AgroAI Bot ishga tushdi!")

    bot = AgroAIBot()
    app = Application.builder().token(BOT_TOKEN).build()

    # HANDLERS
    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(CallbackQueryHandler(bot.language_callback, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(bot.field_callback, pattern="^field_\\d+$"))
    app.add_handler(CallbackQueryHandler(bot.field_callback, pattern="^add_new_field$"))
    app.add_handler(CallbackQueryHandler(bot.field_action_callback, pattern="^(ndvi|delete)_\\d+$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, bot.handle_photo))
    app.add_handler(MessageHandler(filters.LOCATION, bot.handle_location))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
