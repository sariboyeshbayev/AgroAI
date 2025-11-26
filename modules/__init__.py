"""
AgroAI Bot Modules
Инициализация модулей проекта
"""

from .database import Database
from .ndvi_analyzer import NDVIAnalyzer
from .plant_analyzer import PlantAnalyzer
from .credit_analyzer import CreditAnalyzer
from .ai_advisor import AIAdvisor

__all__ = [
    'Database',
    'NDVIAnalyzer',
    'PlantAnalyzer',
    'CreditAnalyzer',
    'AIAdvisor'
]

__version__ = '1.0.0'
__author__ = 'AgroAI Team'