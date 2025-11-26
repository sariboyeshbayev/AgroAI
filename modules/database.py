"""
Модуль управления базой данных AgroAI
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, List
from config import DATABASE_PATH


class Database:
    def __init__(self):
        self.db_path = DATABASE_PATH
        self.init_database()

    def get_connection(self):
        """Создать подключение к БД"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_database(self):
        """Инициализация структуры базы данных"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Таблица пользователей
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS users
                       (
                           user_id
                           INTEGER
                           PRIMARY
                           KEY,
                           username
                           TEXT,
                           language
                           TEXT
                           DEFAULT
                           'uz',
                           state
                           TEXT,
                           registration_date
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP,
                           last_activity
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP
                       )
                       """)

        # Таблица NDVI анализов
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS ndvi_analyses
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           user_id
                           INTEGER,
                           latitude
                           REAL,
                           longitude
                           REAL,
                           ndvi_value
                           REAL,
                           health_status
                           TEXT,
                           moisture
                           REAL,
                           temperature
                           REAL,
                           recommendations
                           TEXT,
                           analysis_date
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP,
                           FOREIGN
                           KEY
                       (
                           user_id
                       ) REFERENCES users
                       (
                           user_id
                       )
                           )
                       """)

        # Таблица анализов растений
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS plant_analyses
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           user_id
                           INTEGER,
                           plant_name
                           TEXT,
                           health_score
                           INTEGER,
                           issues
                           TEXT,
                           treatment
                           TEXT,
                           treatment_time
                           TEXT,
                           photo_path
                           TEXT,
                           analysis_date
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP,
                           FOREIGN
                           KEY
                       (
                           user_id
                       ) REFERENCES users
                       (
                           user_id
                       )
                           )
                       """)

        # Таблица полных анализов (фото + NDVI + погода)
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS full_analyses
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           user_id
                           INTEGER,
                           latitude
                           REAL,
                           longitude
                           REAL,
                           photo_analysis
                           TEXT,
                           ndvi_value
                           REAL,
                           weather_data
                           TEXT,
                           yield_forecast
                           INTEGER,
                           recommendations
                           TEXT,
                           analysis_date
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP,
                           FOREIGN
                           KEY
                       (
                           user_id
                       ) REFERENCES users
                       (
                           user_id
                       )
                           )
                       """)

        # Таблица кредитных анализов
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS credit_analyses
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           user_id
                           INTEGER,
                           credit_score
                           INTEGER,
                           status
                           TEXT,
                           max_credit
                           REAL,
                           recommended_term
                           INTEGER,
                           monthly_payment
                           REAL,
                           recommendations
                           TEXT,
                           analysis_date
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP,
                           FOREIGN
                           KEY
                       (
                           user_id
                       ) REFERENCES users
                       (
                           user_id
                       )
                           )
                       """)

        # Таблица истории советов
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS advice_history
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           user_id
                           INTEGER,
                           category
                           TEXT,
                           question
                           TEXT,
                           advice
                           TEXT,
                           request_date
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP,
                           FOREIGN
                           KEY
                       (
                           user_id
                       ) REFERENCES users
                       (
                           user_id
                       )
                           )
                       """)

        conn.commit()
        conn.close()
        print("✅ База данных инициализирована")

    def user_exists(self, user_id: int) -> bool:
        """Проверка существования пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        exists = cursor.fetchone() is not None
        conn.close()
        return exists

    def register_user(self, user_id: int, username: str, language: str = 'uz'):
        """Регистрация нового пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO users (user_id, username, language)
            VALUES (?, ?, ?)
        """, (user_id, username, language))
        conn.commit()
        conn.close()

    def get_user_language(self, user_id: int) -> str:
        """Получить язык пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return row['language'] if row else 'uz'

    def set_user_language(self, user_id: int, language: str):
        """Установить язык пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
                       UPDATE users
                       SET language      = ?,
                           last_activity = CURRENT_TIMESTAMP
                       WHERE user_id = ?
                       """, (language, user_id))
        conn.commit()
        conn.close()

    def get_user_state(self, user_id: int) -> Optional[str]:
        """Получить текущее состояние пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT state FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return row['state'] if row else None

    def set_user_state(self, user_id: int, state: Optional[str]):
        """Установить состояние пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
                       UPDATE users
                       SET state         = ?,
                           last_activity = CURRENT_TIMESTAMP
                       WHERE user_id = ?
                       """, (state, user_id))
        conn.commit()
        conn.close()

    def save_ndvi_analysis(self, user_id: int, latitude: float, longitude: float, result: Dict):
        """Сохранить результат NDVI анализа"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
                       INSERT INTO ndvi_analyses
                       (user_id, latitude, longitude, ndvi_value, health_status, moisture, temperature, recommendations)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                       """, (
                           user_id, latitude, longitude, result['ndvi'],
                           result['health_ru'], result['moisture'], result['temperature'],
                           json.dumps({'uz': result['recommendations_uz'], 'ru': result['recommendations_ru']})
                       ))
        conn.commit()
        conn.close()

    def save_plant_analysis(self, user_id: int, result: Dict):
        """Сохранить результат анализа растения"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
                       INSERT INTO plant_analyses
                           (user_id, plant_name, health_score, issues, treatment, treatment_time)
                       VALUES (?, ?, ?, ?, ?, ?)
                       """, (
                           user_id, result['plant_name_ru'], result['health_score'],
                           json.dumps({'uz': result['issues_uz'], 'ru': result['issues_ru']}),
                           json.dumps({'uz': result['treatment_uz'], 'ru': result['treatment_ru']}),
                           result['treatment_time']
                       ))
        conn.commit()
        conn.close()

    def save_credit_analysis(self, user_id: int, result: Dict):
        """Сохранить результат кредитного анализа"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
                       INSERT INTO credit_analyses
                       (user_id, credit_score, status, max_credit, recommended_term, monthly_payment, recommendations)
                       VALUES (?, ?, ?, ?, ?, ?, ?)
                       """, (
                           user_id, result['score'], result['status_ru'],
                           result['max_credit'], result['recommended_term'],
                           result['monthly_payment'],
                           json.dumps({'uz': result['recommendations_uz'], 'ru': result['recommendations_ru']})
                       ))
        conn.commit()
        conn.close()

    def save_advice_request(self, user_id: int, category: str, question: str, advice: str):
        """Сохранить запрос совета"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
                       INSERT INTO advice_history (user_id, category, question, advice)
                       VALUES (?, ?, ?, ?)
                       """, (user_id, category, question, advice))
        conn.commit()
        conn.close()

    def get_user_statistics(self, user_id: int) -> Dict:
        """Получить статистику пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()

        stats = {}

        cursor.execute("SELECT COUNT(*) as count FROM full_analyses WHERE user_id = ?", (user_id,))
        stats['full_analyses'] = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM ndvi_analyses WHERE user_id = ?", (user_id,))
        stats['ndvi_analyses'] = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM plant_analyses WHERE user_id = ?", (user_id,))
        stats['plant_analyses'] = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM credit_analyses WHERE user_id = ?", (user_id,))
        stats['credit_analyses'] = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM advice_history WHERE user_id = ?", (user_id,))
        stats['advice_requests'] = cursor.fetchone()['count']

        conn.close()
        return stats

    def save_full_analysis(self, user_id: int, latitude: float, longitude: float, result: Dict):
        """Сохранить результат полного анализа"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
                       INSERT INTO full_analyses
                       (user_id, latitude, longitude, photo_analysis, ndvi_value, weather_data,
                        yield_forecast, recommendations)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                       """, (
                           user_id, latitude, longitude,
                           json.dumps(result.get('photo_analysis', {})),
                           result.get('ndvi_analysis', {}).get('value', 0.0),
                           result.get('weather', ''),
                           result.get('yield_forecast', {}).get('percentage', 0),
                           result.get('text', '')
                       ))
        conn.commit()
        conn.close()

    def get_recent_analyses(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Получить последние анализы пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
                       SELECT 'NDVI' as type, analysis_date, ndvi_value as value
                       FROM ndvi_analyses
                       WHERE user_id = ?
                       UNION ALL
                       SELECT 'Plant' as type, analysis_date, health_score as value
                       FROM plant_analyses
                       WHERE user_id = ?
                       UNION ALL
                       SELECT 'Credit' as type, analysis_date, credit_score as value
                       FROM credit_analyses
                       WHERE user_id = ?
                       ORDER BY analysis_date DESC LIMIT ?
                       """, (user_id, user_id, user_id, limit))

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results