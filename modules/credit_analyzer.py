"""
Модуль анализа кредитоспособности фермеров
Интеграция с банковскими системами
"""

import asyncio
import json
import aiohttp
from typing import Dict, Optional
from datetime import datetime
import config


class CreditAnalyzer:
    def __init__(self):
        self.bank_endpoints = config.BANK_API_ENDPOINTS

    async def analyze(self, data_text: str) -> Dict:
        """
        Анализ кредитоспособности на основе предоставленных данных
        """
        # Парсинг входных данных
        credit_data = self._parse_credit_data(data_text)

        # Расчет кредитного скоринга
        score = await self._calculate_credit_score(credit_data)

        # Определение максимального кредита
        max_credit = self._calculate_max_credit(score, credit_data)

        # Рекомендуемые условия
        terms = self._calculate_terms(max_credit, score)

        # Статус одобрения
        status_uz, status_ru = self._get_approval_status(score)

        # Генерация рекомендаций
        rec_uz, rec_ru = self._generate_recommendations(score, credit_data)

        return {
            'score': score,
            'status_uz': status_uz,
            'status_ru': status_ru,
            'max_credit': max_credit,
            'recommended_term': terms['term'],
            'monthly_payment': terms['monthly_payment'],
            'recommendations_uz': rec_uz,
            'recommendations_ru': rec_ru,
            'interest_rate': terms['interest_rate']
        }

    def _parse_credit_data(self, data_text: str) -> Dict:
        """
        Парсинг кредитных данных из текста
        Ожидаемый формат: доход, земля, стаж, кредитная история
        """
        lines = data_text.strip().split('\n')

        # Значения по умолчанию
        data = {
            'monthly_income': 5000000,  # сум
            'land_area': 10,  # гектар
            'experience_years': 5,
            'credit_history': 'good',  # good/bad/none
            'collateral_value': 50000000,  # сум
            'existing_loans': 0
        }

        # Простой парсинг
        for line in lines:
            line_lower = line.lower()

            # Доход
            if 'доход' in line_lower or 'daromad' in line_lower or 'income' in line_lower:
                numbers = ''.join(filter(str.isdigit, line))
                if numbers:
                    data['monthly_income'] = int(numbers)

            # Площадь земли
            elif 'земля' in line_lower or 'yer' in line_lower or 'land' in line_lower or 'га' in line_lower:
                numbers = ''.join(filter(str.isdigit, line))
                if numbers:
                    data['land_area'] = int(numbers)

            # Стаж
            elif 'стаж' in line_lower or 'taj' in line_lower or 'experience' in line_lower:
                numbers = ''.join(filter(str.isdigit, line))
                if numbers:
                    data['experience_years'] = int(numbers)

            # Кредитная история
            elif 'история' in line_lower or 'tarix' in line_lower or 'history' in line_lower:
                if 'плох' in line_lower or 'yomon' in line_lower or 'bad' in line_lower:
                    data['credit_history'] = 'bad'
                elif 'нет' in line_lower or 'yo\'q' in line_lower or 'none' in line_lower:
                    data['credit_history'] = 'none'
                else:
                    data['credit_history'] = 'good'

        return data

    async def _calculate_credit_score(self, data: Dict) -> int:
        """
        Расчет кредитного скоринга (0-100)
        """
        await asyncio.sleep(1)  # Имитация обработки

        score = 0

        # Доход (максимум 30 баллов)
        income_score = min(30, (data['monthly_income'] / 10000000) * 30)
        score += income_score

        # Площадь земли (максимум 25 баллов)
        land_score = min(25, (data['land_area'] / 50) * 25)
        score += land_score

        # Стаж (максимум 20 баллов)
        experience_score = min(20, (data['experience_years'] / 10) * 20)
        score += experience_score

        # Кредитная история (максимум 25 баллов)
        if data['credit_history'] == 'good':
            history_score = 25
        elif data['credit_history'] == 'none':
            history_score = 15
        else:
            history_score = 5
        score += history_score

        return int(min(100, score))

    def _calculate_max_credit(self, score: int, data: Dict) -> float:
        """
        Расчет максимальной суммы кредита
        """
        # Базовая формула: доход * 60 месяцев * коэффициент скоринга
        base_credit = data['monthly_income'] * 60 * (score / 100)

        # Учет залога (земля)
        collateral_credit = data['land_area'] * 50000000  # 50 млн сум за гектар

        # Максимум - меньшее из двух значений
        max_credit = min(base_credit, collateral_credit * 0.7)

        return round(max_credit, -6)  # Округление до миллионов

    def _calculate_terms(self, max_credit: float, score: int) -> Dict:
        """
        Расчет условий кредита
        """
        # Процентная ставка в зависимости от скоринга
        if score >= config.CREDIT_EXCELLENT:
            interest_rate = 12  # 12% годовых
            recommended_term = 60  # 5 лет
        elif score >= config.CREDIT_GOOD:
            interest_rate = 15
            recommended_term = 48  # 4 года
        elif score >= config.CREDIT_MODERATE:
            interest_rate = 18
            recommended_term = 36  # 3 года
        else:
            interest_rate = 22
            recommended_term = 24  # 2 года

        # Расчет ежемесячного платежа (аннуитет)
        monthly_rate = interest_rate / 12 / 100
        monthly_payment = max_credit * (monthly_rate * (1 + monthly_rate) ** recommended_term) / \
                          ((1 + monthly_rate) ** recommended_term - 1)

        return {
            'interest_rate': interest_rate,
            'term': recommended_term,
            'monthly_payment': round(monthly_payment, -3)
        }

    def _get_approval_status(self, score: int) -> tuple:
        """
        Определение статуса одобрения
        """
        if score >= config.CREDIT_EXCELLENT:
            return "✅ Tasdiqlangan (A'lo)", "✅ Одобрено (Отлично)"
        elif score >= config.CREDIT_GOOD:
            return "✅ Tasdiqlangan (Yaxshi)", "✅ Одобрено (Хорошо)"
        elif score >= config.CREDIT_MODERATE:
            return "⚠️ Shartli tasdiqlangan", "⚠️ Условно одобрено"
        else:
            return "❌ Qo'shimcha hujjatlar kerak", "❌ Требуются доп. документы"

    def _generate_recommendations(self, score: int, data: Dict) -> tuple:
        """
        Генерация рекомендаций для улучшения кредитоспособности
        """
        rec_uz = []
        rec_ru = []

        if score < config.CREDIT_EXCELLENT:
            if data['monthly_income'] < 10000000:
                rec_uz.append("💰 Daromadni oshiring: qo'shimcha mahsulotlar eking")
                rec_ru.append("💰 Увеличьте доход: выращивайте дополнительные культуры")

            if data['land_area'] < 20:
                rec_uz.append("🌾 Yer maydonini kengaytiring yoki ijara oling")
                rec_ru.append("🌾 Расширьте земельные угодья или арендуйте")

            if data['credit_history'] != 'good':
                rec_uz.append("📊 Kichik kredit olib, o'z vaqtida to'lang")
                rec_ru.append("📊 Возьмите небольшой кредит и вовремя погашайте")

            if data['experience_years'] < 5:
                rec_uz.append("📚 Tajriba ortiring, kurslar o'ting")
                rec_ru.append("📚 Набирайтесь опыта, проходите курсы")

        # Общие рекомендации
        rec_uz.append("\n🏦 Tavsiya etilgan banklar:")
        rec_uz.append("• Ipoteka Bank - qishloq xo'jalik krediti")
        rec_uz.append("• Agrobank - maxsus dasturlar")
        rec_uz.append("• Xalq Bank - imtiyozli shartlar")

        rec_ru.append("\n🏦 Рекомендуемые банки:")
        rec_ru.append("• Ipoteka Bank - сельхоз кредит")
        rec_ru.append("• Agrobank - специальные программы")
        rec_ru.append("• Народный Банк - льготные условия")

        return "\n".join(rec_uz), "\n".join(rec_ru)

    async def check_bank_offers(self, credit_amount: float) -> list:
        """
        Проверка предложений от разных банков
        """
        offers = [
            {
                'bank': 'Ipoteka Bank',
                'rate': 12,
                'max_amount': 500000000,
                'term': 60
            },
            {
                'bank': 'Agrobank',
                'rate': 11,
                'max_amount': 300000000,
                'term': 48
            },
            {
                'bank': 'Xalq Bank',
                'rate': 13,
                'max_amount': 400000000,
                'term': 60
            }
        ]

        # Фильтрация подходящих предложений
        suitable_offers = [o for o in offers if o['max_amount'] >= credit_amount]

        return sorted(suitable_offers, key=lambda x: x['rate'])