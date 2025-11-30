"""
Модуль управления базой данных AgroAI
Версия 3.0 - Совместимость с новой архитектурой
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
        self._auto_migrate()  # Автоматическая миграция

    def _auto_migrate(self):
        """Автоматическое добавление недостающих колонок"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Миграция для plant_analyses
            cursor.execute("PRAGMA table_info(plant_analyses)")
            existing_plant = {row[1] for row in cursor.fetchall()}

            plant_cols = {
                'plant_type': 'TEXT',
                'plant_type_en': 'TEXT',
                'confidence': 'INTEGER',
                'health_status': 'TEXT',
                'health_score': 'INTEGER',
                'disease_name': 'TEXT',
                'disease_name_en': 'TEXT',
                'symptoms': 'TEXT',
                'causes': 'TEXT',
                'treatment': 'TEXT',
                'fertilizer': 'TEXT',
                'watering': 'TEXT',
                'prevention': 'TEXT',
                'recovery_time': 'TEXT'
            }

            for col, typ in plant_cols.items():
                if col not in existing_plant:
                    cursor.execute(f"ALTER TABLE plant_analyses ADD COLUMN {col} {typ}")
                    logger.info(f"✅ Добавлена колонка plant_analyses.{col}")

            # Миграция для ndvi_analyses
            cursor.execute("PRAGMA table_info(ndvi_analyses)")
            existing_ndvi = {row[1] for row in cursor.fetchall()}

            ndvi_cols = {
                'ndvi_status': 'TEXT',
                'ndvi_min': 'REAL',
                'ndvi_max': 'REAL',
                'ndvi_std': 'REAL'
            }

            for col, typ in ndvi_cols.items():
                if col not in existing_ndvi:
                    cursor.execute(f"ALTER TABLE ndvi_analyses ADD COLUMN {col} {typ}")
                    logger.info(f"✅ Добавлена колонка ndvi_analyses.{col}")

            conn.commit()
            logger.info("✅ Миграция БД завершена")

        except Exception as e:
            logger.error(f"❌ Ошибка миграции БД: {e}")
        finally:
            conn.close()

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
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                language TEXT DEFAULT 'uz',
                state TEXT,
                registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица NDVI анализов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ndvi_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                latitude REAL,
                longitude REAL,
                ndvi_value REAL,
                ndvi_status TEXT,
                ndvi_date TEXT,
                ndvi_min REAL,
                ndvi_max REAL,
                ndvi_std REAL,
                ai_advice TEXT,
                analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Таблица анализов растений (ОБНОВЛЕНО)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS plant_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                plant_type TEXT,
                plant_type_en TEXT,
                confidence REAL,
                health_status TEXT,
                health_score INTEGER,
                disease_name TEXT,
                symptoms TEXT,
                treatment TEXT,
                recovery_time TEXT,
                analysis_json TEXT,
                analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Таблица кредитных анализов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS credit_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                credit_score INTEGER,
                status TEXT,
                max_credit REAL,
                recommended_term INTEGER,
                monthly_payment REAL,
                recommendations TEXT,
                analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Таблица истории советов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS advice_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                category TEXT,
                question TEXT,
                advice TEXT,
                request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
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
            SET language = ?, last_activity = CURRENT_TIMESTAMP
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
            SET state = ?, last_activity = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (state, user_id))
        conn.commit()
        conn.close()

    # ═══════════════════════════════════════════════════════════════
    # СОХРАНЕНИЕ NDVI АНАЛИЗА (НОВЫЙ ФОРМАТ)
    # ═══════════════════════════════════════════════════════════════

    def save_ndvi_analysis(self, user_id: int, latitude: float, longitude: float, result: Dict):
        """
        Сохранить результат NDVI анализа

        result = {
            'ndvi_value': 0.456,
            'status': 'medium',
            'summary': '...',
            'date': '2025-11-29',
            'min': 0.2,
            'max': 0.7,
            'std': 0.15
        }
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO ndvi_analyses
                (user_id, latitude, longitude, ndvi_value, ndvi_status, ndvi_date, 
                 ndvi_min, ndvi_max, ndvi_std)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                latitude,
                longitude,
                result.get('ndvi_value', 0.0),
                result.get('status', 'unknown'),
                result.get('date', datetime.now().strftime('%Y-%m-%d')),
                result.get('min', 0.0),
                result.get('max', 0.0),
                result.get('std', 0.0)
            ))
            conn.commit()
        except Exception as e:
            print(f"❌ Error saving NDVI analysis: {e}")
        finally:
            conn.close()

    # ═══════════════════════════════════════════════════════════════
    # СОХРАНЕНИЕ АНАЛИЗА РАСТЕНИЯ (НОВЫЙ ФОРМАТ)
    # ═══════════════════════════════════════════════════════════════

    def save_plant_analysis(self, user_id: int, result: Dict):
        """
        Сохранить результат анализа растения

        result = {
            'plant_type': 'Виноград',
            'plant_type_en': 'Grape',
            'confidence': 85,
            'health_status': 'sick',
            'health_score': 60,
            'disease_name': 'Мучнистая роса',
            'symptoms': '...',
            'treatment': '...',
            'recovery_time': '2-3 недели'
        }
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO plant_analyses
                (user_id, plant_type, plant_type_en, confidence, health_status, 
                 health_score, disease_name, symptoms, treatment, recovery_time, analysis_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                result.get('plant_type', 'Неизвестно'),
                result.get('plant_type_en', 'Unknown'),
                result.get('confidence', 0),
                result.get('health_status', 'unknown'),
                result.get('health_score', 0),
                result.get('disease_name', ''),
                result.get('symptoms', ''),
                result.get('treatment', ''),
                result.get('recovery_time', ''),
                json.dumps(result, ensure_ascii=False)
            ))
            conn.commit()
        except Exception as e:
            print(f"❌ Error saving plant analysis: {e}")
            import traceback
            traceback.print_exc()
        finally:
            conn.close()

    # ═══════════════════════════════════════════════════════════════
    # СОХРАНЕНИЕ КРЕДИТНОГО АНАЛИЗА
    # ═══════════════════════════════════════════════════════════════

    def save_credit_analysis(self, user_id: int, result: Dict):
        """Сохранить результат кредитного анализа"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO credit_analyses
                (user_id, credit_score, status, max_credit, recommended_term, 
                 monthly_payment, recommendations)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                result['score'],
                result['status_ru'],
                result['max_credit'],
                result['recommended_term'],
                result['monthly_payment'],
                json.dumps({
                    'uz': result['recommendations_uz'],
                    'ru': result['recommendations_ru']
                })
            ))
            conn.commit()
        except Exception as e:
            print(f"❌ Error saving credit analysis: {e}")
        finally:
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

    # ═══════════════════════════════════════════════════════════════
    # СТАТИСТИКА И ИСТОРИЯ
    # ═══════════════════════════════════════════════════════════════

    def get_user_statistics(self, user_id: int) -> Dict:
        """Получить статистику пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()

        stats = {}

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

    def get_plant_history(self, user_id: int, limit: int = 5) -> List[Dict]:
        """Получить историю анализов растений"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                plant_type,
                health_status,
                health_score,
                disease_name,
                analysis_date
            FROM plant_analyses
            WHERE user_id = ?
            ORDER BY analysis_date DESC
            LIMIT ?
        """, (user_id, limit))

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_ndvi_history(self, user_id: int, limit: int = 5) -> List[Dict]:
        """Получить историю NDVI анализов"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                latitude,
                longitude,
                ndvi_value,
                ndvi_status,
                ndvi_date,
                analysis_date
            FROM ndvi_analyses
            WHERE user_id = ?
            ORDER BY analysis_date DESC
            LIMIT ?
        """, (user_id, limit))

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results