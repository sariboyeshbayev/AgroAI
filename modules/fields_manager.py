"""
modules/fields_manager.py

Модуль управления полями фермера
Позволяет сохранять и управлять несколькими полями с координатами
"""

import json
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class FieldsManager:
    """Менеджер полей пользователя"""

    def __init__(self, db):
        self.db = db
        self._init_fields_table()

    def _init_fields_table(self):
        """Инициализация таблицы полей в БД"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_fields (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                field_name TEXT,
                latitude REAL,
                longitude REAL,
                area_hectares REAL,
                crop_type TEXT,
                notes TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_analysis_date TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)

        conn.commit()
        conn.close()
        logger.info("✅ Таблица полей инициализирована")

    # ----------------------------------------------------------------------
    #  POLYGON PARSER — YANGI UNIVERSAL FUNKSIYA
    # ----------------------------------------------------------------------
    def parse_polygon_coordinates(self, text: str):
        """
        Foydalanuvchi kiritgan matndan 4 ta burchak koordinatalarini ajratish.
        Qabul qilinadigan formatlar:
        - Har qatorda: 39.70..., 67.06...
        - Nuqta-vergul: lat,lon; lat,lon
        - 1) lat, lon
        - [lat, lon]
        - 67060461 kabi uzun sonlarni avtomatik tuzatadi

        Return:
            list[(lat, lon)] — agar polygon bo'lsa
            None — agar topilmasa
        """

        # Barcha belgilarni tozalaymiz
        clean = (
            text.replace("\n", " ")
            .replace("\t", " ")
            .replace("(", " ")
            .replace(")", " ")
            .replace("[", " ")
            .replace("]", " ")
            .replace(";", " ")
            .replace("=", " ")
            .replace(":", " ")
        )

        parts = clean.split()
        numbers = []

        # Faqat sonlarni yig'amiz
        for p in parts:
            p = p.replace(",", ".")
            try:
                numbers.append(float(p))
            except:
                continue

        # Polygon uchun kamida 8 ta son bo‘lishi shart
        if len(numbers) < 8:
            return None

        nums = numbers[:8]  # faqat birinchi 4 juftlik
        coords = []

        for i in range(0, 8, 2):
            lat = nums[i]
            lon = nums[i + 1]

            # Haddan katta sonlarni avtomatik tuzatish (67.060461)
            if abs(lon) > 180:
                lon = lon / 1_000_000
            if abs(lat) > 90:
                lat = lat / 1_000_000

            coords.append((lat, lon))

        if len(coords) != 4:
            return None

        return coords

    # ----------------------------------------------------------------------
    #  FIELD MANAGEMENT
    # ----------------------------------------------------------------------

    def add_field(
            self,
            user_id: int,
            field_name: str,
            latitude: float,
            longitude: float,
            area_hectares: float = 0,
            crop_type: str = "",
            notes: str = ""
    ) -> int:
        """Добавить новое поле"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO user_fields
            (user_id, field_name, latitude, longitude, area_hectares, crop_type, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, field_name, latitude, longitude, area_hectares, crop_type, notes))

        field_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.info(f"✅ Поле '{field_name}' добавлено (ID: {field_id})")
        return field_id

    def get_user_fields(self, user_id: int, active_only: bool = True) -> List[Dict]:
        """Получить все поля пользователя"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        if active_only:
            cursor.execute("""
                SELECT id, field_name, latitude, longitude, area_hectares,
                       crop_type, notes, last_analysis_date
                FROM user_fields
                WHERE user_id = ? AND is_active = 1
                ORDER BY field_name
            """, (user_id,))
        else:
            cursor.execute("""
                SELECT id, field_name, latitude, longitude, area_hectares,
                       crop_type, notes, last_analysis_date, is_active
                FROM user_fields
                WHERE user_id = ?
                ORDER BY field_name
            """, (user_id,))

        rows = cursor.fetchall()
        conn.close()

        fields = []
        for row in rows:
            fields.append({
                'id': row[0],
                'name': row[1],
                'lat': row[2],
                'lon': row[3],
                'area': row[4],
                'crop': row[5],
                'notes': row[6],
                'last_analysis': row[7],
                'active': row[8] if not active_only else True
            })

        return fields

    def get_field_by_id(self, field_id: int) -> Optional[Dict]:
        """Получить поле по ID"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, field_name, latitude, longitude, area_hectares,
                   crop_type, notes, last_analysis_date, user_id
            FROM user_fields
            WHERE id = ?
        """, (field_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            'id': row[0],
            'name': row[1],
            'lat': row[2],
            'lon': row[3],
            'area': row[4],
            'crop': row[5],
            'notes': row[6],
            'last_analysis': row[7],
            'user_id': row[8]
        }

    def update_field(self, field_id: int, **kwargs) -> bool:
        """Обновить информацию о поле"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        updates = []
        values = []

        for key, value in kwargs.items():
            if value is not None:
                updates.append(f"{key} = ?")
                values.append(value)

        if not updates:
            return False

        values.append(field_id)
        query = f"UPDATE user_fields SET {', '.join(updates)} WHERE id = ?"

        cursor.execute(query, values)
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()

        return success

    def delete_field(self, field_id: int, soft_delete: bool = True) -> bool:
        """Удалить поле"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        if soft_delete:
            cursor.execute("UPDATE user_fields SET is_active = 0 WHERE id = ?", (field_id,))
        else:
            cursor.execute("DELETE FROM user_fields WHERE id = ?", (field_id,))

        conn.commit()
        success = cursor.rowcount > 0
        conn.close()

        return success

    def update_last_analysis(self, field_id: int):
        """Обновить дату последнего анализа"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE user_fields
            SET last_analysis_date = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (field_id,))

        conn.commit()
        conn.close()

    def get_field_statistics(self, field_id: int) -> Dict:
        """Получить статистику анализов поля"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        field = self.get_field_by_id(field_id)
        if not field:
            return {}

        lat, lon = field['lat'], field['lon']
        stats = {}

        cursor.execute("""
            SELECT COUNT(*)
            FROM full_analyses
            WHERE user_id = ?
              AND ABS(latitude - ?) < 0.001
              AND ABS(longitude - ?) < 0.001
        """, (field['user_id'], lat, lon))
        stats['full_analyses'] = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*)
            FROM ndvi_analyses
            WHERE user_id = ?
              AND ABS(latitude - ?) < 0.001
              AND ABS(longitude - ?) < 0.001
        """, (field['user_id'], lat, lon))
        stats['ndvi_analyses'] = cursor.fetchone()[0]

        cursor.execute("""
            SELECT ndvi_value, analysis_date
            FROM ndvi_analyses
            WHERE user_id = ?
              AND ABS(latitude - ?) < 0.001
              AND ABS(longitude - ?) < 0.001
            ORDER BY analysis_date DESC LIMIT 1
        """, (field['user_id'], lat, lon))

        last_ndvi = cursor.fetchone()
        if last_ndvi:
            stats['last_ndvi'] = last_ndvi[0]
            stats['last_ndvi_date'] = last_ndvi[1]

        conn.close()
        return stats

    # ----------------------------------------------------------------------
    #  FIELD LIST FORMATTER
    # ----------------------------------------------------------------------

    def format_field_list(self, user_id: int, lang: str = "ru") -> str:
        """Форматированное отображение списка полей"""
        fields = self.get_user_fields(user_id)

        if not fields:
            return (
                "📭 Sizda hali dalalar yo'q.\n'Dala qo'shish' tugmasini bosing."
                if lang == "uz"
                else "📭 У вас пока нет полей.\nНажмите 'Добавить Поле'."
            )

        text = (
            f"🌾 **Sizning dalalaringiz ({len(fields)}):**\n\n"
            if lang == "uz"
            else f"🌾 **Ваши поля ({len(fields)}):**\n\n"
        )

        for i, f in enumerate(fields, 1):
            emoji = self._get_crop_emoji(f['crop'])

            text += (
                f"{i}. {emoji} **{f['name']}**\n"
                f"   📍 {f['lat']:.4f}, {f['lon']:.4f}\n"
            )

            if f['area']:
                text += f"   📏 {f['area']} ga\n" if lang == "uz" else f"   📏 {f['area']} га\n"
            if f['crop']:
                text += f"   🌱 {f['crop']}\n"
            if f['last_analysis']:
                date = f['last_analysis'][:10]
                text += (
                    f"   📅 Oxirgi tahlil: {date}\n"
                    if lang == "uz"
                    else f"   📅 Последний анализ: {date}\n"
                )

            text += "\n"

        return text

    # ----------------------------------------------------------------------
    #  INTERNAL HELPERS
    # ----------------------------------------------------------------------

    def _get_crop_emoji(self, crop_type: str) -> str:
        crop_emojis = {
            'пшеница': '🌾', 'bug\'doy': '🌾', 'wheat': '🌾',
            'хлопок': '☁️', 'paxta': '☁️', 'cotton': '☁️',
            'томаты': '🍅', 'pomidor': '🍅', 'tomato': '🍅',
            'картофель': '🥔', 'картошка': '🥔',
            'морковь': '🥕', 'sabzi': '🥕',
            'виноград': '🍇', 'uzum': '🍇',
            'яблоки': '🍎', 'olma': '🍎'
        }
        crop_lower = crop_type.lower()
        for key, emoji in crop_emojis.items():
            if key in crop_lower:
                return emoji
        return '🌱'

    # ----------------------------------------------------------------------
    #  OLD PARSER (lat/lon, name, area, crop)
    # ----------------------------------------------------------------------

    def parse_field_from_text(self, text: str, lang: str = "ru") -> Optional[Dict]:
        """
        Классический парсер данных поля:
        Название:
        Координаты:
        Площадь:
        Культура:
        """
        lines = text.strip().split('\n')
        field_data = {}

        keywords = {
            'name': ['название', 'имя', 'name', 'nom', 'nomi'],
            'coords': ['координаты', 'координата', 'coords', 'koordinatalar'],
            'area': ['площадь', 'area', 'maydon', 'га', 'ga'],
            'crop': ['культура', 'crop', 'ekin']
        }

        for line in lines:
            l = line.lower()

            if any(k in l for k in keywords['name']):
                field_data['name'] = line.split(':', 1)[1].strip() if ":" in line else line.strip()

            elif any(k in l for k in keywords['coords']):
                coords_str = line.split(':', 1)[1] if ':' in line else line
                coords = coords_str.replace(",", " ").split()
                if len(coords) >= 2:
                    try:
                        field_data['lat'] = float(coords[0])
                        field_data['lon'] = float(coords[1])
                    except:
                        pass

            elif any(k in l for k in keywords['area']):
                import re
                nums = re.findall(r"\d+\.?\d*", line)
                if nums:
                    field_data['area'] = float(nums[0])

            elif any(k in l for k in keywords['crop']):
                field_data['crop'] = line.split(':', 1)[1].strip()

        if 'name' in field_data and 'lat' in field_data and 'lon' in field_data:
            return field_data

        return None
