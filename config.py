import os
from dotenv import load_dotenv
from pathlib import Path

if os.path.exists(".env"):
    load_dotenv()

# =====================================
# 2) Директории
# =====================================
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

# создаём папки при необходимости
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# =====================================
# 3) Загружаем ключи из .env
# =====================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
SATELLITE_API_KEY = os.getenv("SATELLITE_API_KEY")

# =====================================
# 4) Проверка ключей
# =====================================
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден! Добавь его в Render → Environment Variables.")

if not ANTHROPIC_API_KEY:
    raise ValueError("❌ ANTHROPIC_API_KEY не найден! Добавь его в Render → Environment Variables.")
else:
    print(f"✅ ANTHROPIC_API_KEY настроен: {ANTHROPIC_API_KEY[:15]}...")

# =====================================
# 5) Конфигурации
# =====================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
DATABASE_PATH = DATA_DIR / "agroai.db"

LOG_FILE = LOGS_DIR / "agroai.log"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

NDVI_THRESHOLD_EXCELLENT = 0.6
NDVI_THRESHOLD_GOOD = 0.4
NDVI_THRESHOLD_MODERATE = 0.2
NDVI_THRESHOLD_POOR = 0.0

# кредитные рейтинги
CREDIT_EXCELLENT = 80
CREDIT_GOOD = 60
CREDIT_MODERATE = 40
CREDIT_POOR = 20

# банки API
BANK_API_ENDPOINTS = {
    'ipoteka': 'https://api.ipotekabank.uz',
    'nbu': 'https://api.nbu.uz',
    'agro': 'https://api.agrobank.uz'
}

# языки
DEFAULT_LANGUAGE = "uz"
SUPPORTED_LANGUAGES = ["uz", "ru"]

# категория советов
ADVICE_CATEGORIES = {
    'crops': ['пшеница', 'хлопок', 'овощи', 'фрукты', 'виноград'],
    'irrigation': ['капельное', 'дождевание', 'борозды', 'затопление'],
    'fertilizer': ['азотные', 'фосфорные', 'калийные', 'органические'],
    'pest': ['насекомые', 'болезни', 'сорняки', 'грызуны'],
    'weather': ['температура', 'осадки', 'засуха', 'заморозки']
}

# локация по умолчанию
DEFAULT_LOCATION = {
    'latitude': 41.2995,
    'longitude': 69.2401
}

# информация о боте
BOT_INFO = {
    'name': 'AgroAI',
    'version': '2.0.0',
    'description': 'Умный помощник для фермеров Узбекистана',
    'author': 'AgroAI Team',
    'support_email': 'support@agroai.uz'
}

print(f"✅ Конфигурация загружена: {BOT_INFO['name']} v{BOT_INFO['version']}")
