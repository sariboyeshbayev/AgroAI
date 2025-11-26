"""
Тестовый скрипт для AgroAI v2.0
Проверка интеграции с Planetary Computer и Open-Meteo
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def test_imports():
    """Тест 1: Проверка импортов"""
    print("\n🔍 Тест 1: Проверка библиотек...")

    required = {
        'telegram': 'python-telegram-bot',
        'httpx': 'httpx',
        'numpy': 'numpy',
        'PIL': 'Pillow',
        'planetary_computer': 'planetary-computer',
        'pystac_client': 'pystac-client'
    }

    missing = []
    for module, package in required.items():
        try:
            __import__(module)
            print(f"✅ {package} установлен")
        except ImportError:
            print(f"❌ {package} НЕ установлен")
            missing.append(package)

    if missing:
        print(f"\n⚠️  Установите: pip install {' '.join(missing)}")
        return False

    return True


def test_config():
    """Тест 2: Проверка конфигурации"""
    print("\n🔍 Тест 2: Проверка config.py...")

    try:
        import config
        print("✅ config.py загружен")

        if config.BOT_TOKEN and config.BOT_TOKEN != "YOUR_TELEGRAM_BOT_TOKEN":
            print(f"✅ BOT_TOKEN настроен")
        else:
            print("❌ BOT_TOKEN не настроен!")
            return False

        if config.ANTHROPIC_API_KEY:
            print("✅ ANTHROPIC_API_KEY настроен (AI советы включены)")
        else:
            print("⚠️  ANTHROPIC_API_KEY пустой (демо-режим советов)")

        print("✅ Planetary Computer не требует API ключа!")
        print("✅ Open-Meteo не требует API ключа!")

        return True

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


async def test_planetary_computer():
    """Тест 3: Проверка Planetary Computer"""
    print("\n🔍 Тест 3: Проверка Planetary Computer...")

    try:
        from pystac_client import Client
        import planetary_computer

        stac = Client.open("https://planetarycomputer.microsoft.com/api/stac/v1")
        print("✅ Подключение к Planetary Computer успешно")

        # Тестовый поиск
        lat, lon = 41.2995, 69.2401  # Ташкент

        search = stac.search(
            collections=["sentinel-2-l2a"],
            intersects={"type": "Point", "coordinates": [lon, lat]},
            limit=1
        )

        items = list(search.items())

        if items:
            print(f"✅ Найдены спутниковые снимки для координат {lat}, {lon}")
            item = items[0]
            date = item.properties.get('datetime', 'Unknown')[:10]
            print(f"   Последний снимок: {date}")
            return True
        else:
            print("⚠️  Снимки не найдены (попробуйте другие координаты)")
            return True  # Не критично

    except Exception as e:
        print(f"❌ Ошибка Planetary Computer: {e}")
        return False


async def test_open_meteo():
    """Тест 4: Проверка Open-Meteo"""
    print("\n🔍 Тест 4: Проверка Open-Meteo API...")

    try:
        import httpx

        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": 41.2995,
            "longitude": 69.2401,
            "daily": "temperature_2m_max,temperature_2m_min",
            "timezone": "auto",
            "forecast_days": 3
        }

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, params=params)

        if response.status_code == 200:
            data = response.json()
            temps = data.get("daily", {}).get("temperature_2m_max", [])

            if temps:
                print(f"✅ Open-Meteo работает")
                print(f"   Прогноз температуры: {temps[0]}°C")
                return True
            else:
                print("⚠️  Нет данных погоды")
                return True
        else:
            print(f"❌ Open-Meteo ошибка: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Ошибка Open-Meteo: {e}")
        return False


async def test_crop_analyzer():
    """Тест 5: Проверка CropAnalyzer"""
    print("\n🔍 Тест 5: Проверка crop_analyzer.py...")

    try:
        from modules.crop_analyzer import CropAnalyzer

        analyzer = CropAnalyzer()
        print("✅ CropAnalyzer создан")

        # Тест NDVI
        lat, lon = 41.2995, 69.2401
        print(f"   Запрос NDVI для {lat}, {lon}...")

        result = await analyzer.get_ndvi(lat, lon, "ru")

        if result['status'] != 'error':
            print(f"✅ NDVI анализ работает")
            print(f"   NDVI: {result.get('value', 'N/A')}")
            print(f"   Статус: {result.get('status', 'N/A')}")
        else:
            print("⚠️  NDVI анализ: нет данных (попробуйте другие координаты)")

        # Тест погоды
        print(f"   Запрос погоды...")
        weather = await analyzer.get_weather(lat, lon, "ru")

        if weather and "❌" not in weather:
            print(f"✅ Погода работает")
            lines = weather.split('\n')
            print(f"   {lines[0] if lines else 'OK'}")
        else:
            print("⚠️  Погода: ошибка")

        return True

    except Exception as e:
        print(f"❌ Ошибка CropAnalyzer: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_database():
    """Тест 6: Проверка базы данных"""
    print("\n🔍 Тест 6: Проверка database.py...")

    try:
        from modules.database import Database

        db = Database()
        print("✅ База данных инициализирована")

        # Тест регистрации
        test_user_id = 999999999
        db.register_user(test_user_id, "test_user", "ru")
        print("✅ Регистрация пользователя работает")

        # Тест статистики
        stats = db.get_user_statistics(test_user_id)
        print(f"✅ Статистика получена: {stats}")

        return True

    except Exception as e:
        print(f"❌ Ошибка БД: {e}")
        return False


async def test_photo_analysis():
    """Тест 7: Тест анализа фото (без реального фото)"""
    print("\n🔍 Тест 7: Проверка анализа фото...")

    try:
        from modules.crop_analyzer import CropAnalyzer
        from PIL import Image
        import numpy as np
        from io import BytesIO

        analyzer = CropAnalyzer()

        # Создаем тестовое изображение (зеленое с коричневыми пятнами)
        img_array = np.zeros((512, 512, 3), dtype=np.uint8)
        img_array[:, :, 1] = 150  # Зеленый канал
        img_array[100:200, 100:200] = [139, 69, 19]  # Коричневое пятно

        img = Image.fromarray(img_array, 'RGB')
        bio = BytesIO()
        img.save(bio, 'PNG')
        bio.seek(0)

        result = await analyzer.analyze_photo(bio.read())

        print(f"✅ Анализ фото работает")
        print(f"   Диагноз: {result.get('label', 'unknown')}")
        print(f"   Уверенность: {result.get('confidence', 0) * 100:.1f}%")

        return True

    except Exception as e:
        print(f"❌ Ошибка анализа фото: {e}")
        return False


def print_summary(results):
    """Итоги тестирования"""
    print("\n" + "=" * 70)
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ AgroAI v2.0")
    print("=" * 70)

    total = len(results)
    passed = sum(results.values())

    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status} - {test_name}")

    print("=" * 70)
    print(f"Пройдено: {passed}/{total} тестов ({passed / total * 100:.0f}%)")

    if passed == total:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("\n✅ Planetary Computer подключен")
        print("✅ Open-Meteo работает")
        print("✅ Анализ растений готов")
        print("\n📝 Следующий шаг: python main.py")
    elif passed >= total * 0.7:
        print("\n⚠️  Большинство тестов пройдено - бот должен работать")
        print("   Проверьте проваленные тесты выше")
    else:
        print("\n❌ Много ошибок - исправьте перед запуском")
        print("\n📚 Помощь:")
        print("   1. pip install -r requirements.txt")
        print("   2. Проверьте config.py (BOT_TOKEN)")
        print("   3. Проверьте интернет-соединение")

    print("=" * 70)


async def run_tests():
    """Запуск всех тестов"""
    print("=" * 70)
    print("🚀 ТЕСТИРОВАНИЕ AgroAI Bot v2.0")
    print("   с Planetary Computer + Open-Meteo")
    print("=" * 70)

    results = {}

    # Синхронные тесты
    results["1. Библиотеки"] = test_imports()
    results["2. Конфигурация"] = test_config()

    # Асинхронные тесты
    results["3. Planetary Computer"] = await test_planetary_computer()
    results["4. Open-Meteo"] = await test_open_meteo()
    results["5. Crop Analyzer"] = await test_crop_analyzer()
    results["6. База данных"] = await test_database()
    results["7. Анализ фото"] = await test_photo_analysis()

    # Итоги
    print_summary(results)


if __name__ == "__main__":
    print("\n🧪 Тестовый скрипт AgroAI Bot v2.0")
    print("   Проверка Planetary Computer интеграции...\n")

    try:
        asyncio.run(run_tests())
    except KeyboardInterrupt:
        print("\n\n⚠️  Тестирование прервано")
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {e}")
        import traceback

        traceback.print_exc()