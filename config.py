from dotenv import load_dotenv
import os
from pathlib import Path

# Загружаем .env
load_dotenv()

# Базовые пути
BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = BASE_DIR / "temp"
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

# Создание директорий
TEMP_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# API Keys (Загружаются из .env)
BOT_TOKEN = os.getenv("BOT_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
SATELLITE_API_KEY = os.getenv("SATELLITE_API_KEY")

# Настройки базы данных
DATABASE_PATH = DATA_DIR / "agroai.db"

# Настройки NDVI
NDVI_THRESHOLD_EXCELLENT = 0.6
NDVI_THRESHOLD_GOOD = 0.4
NDVI_THRESHOLD_MODERATE = 0.2
NDVI_THRESHOLD_POOR = 0.0

# Кредитные пороги
CREDIT_EXCELLENT = 80
CREDIT_GOOD = 60
CREDIT_MODERATE = 40
CREDIT_POOR = 20

# Банковские API
BANK_API_ENDPOINTS = {
    'ipoteka': 'https://api.ipotekabank.uz',
    'nbu': 'https://api.nbu.uz',
    'agro': 'https://api.agrobank.uz'
}

# Логирование
LOG_FILE = LOGS_DIR / "agroai.log"
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Лимиты
MAX_PHOTO_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_ANALYSIS_PER_DAY = 50
REQUEST_TIMEOUT = 30

# Языки
DEFAULT_LANGUAGE = "uz"
SUPPORTED_LANGUAGES = ["uz", "ru"]

# Категории советов
ADVICE_CATEGORIES = {
    'crops': ['пшеница', 'хлопок', 'овощи', 'фрукты', 'виноград'],
    'irrigation': ['капельное', 'дождевание', 'борозды', 'затопление'],
    'fertilizer': ['азотные', 'фосфорные', 'калийные', 'органические'],
    'pest': ['насекомые', 'болезни', 'сорняки', 'грызуны'],
    'weather': ['температура', 'осадки', 'засуха', 'заморозки']
}

# Локация по умолчанию
DEFAULT_LOCATION = {
    'latitude': 41.2995,
    'longitude': 69.2401
}

# Информация о боте
BOT_INFO = {
    'name': 'AgroAI',
    'version': '1.0.0',
    'description': 'Умный помощник для фермеров Узбекистана',
    'author': 'AgroAI Team',
    'support_email': 'support@agroai.uz'
}

print(f"✅ Конфигурация загружена: {BOT_INFO['name']} v{BOT_INFO['version']}")
