"""
Модуль для управления очередью торговых событий
Используется для отображения событий в DEBUG PANEL
"""

from collections import deque
from threading import Lock
from datetime import datetime
from typing import Dict, List, Optional

# Глобальная очередь событий (ограничена по размеру)
_trade_events = deque(maxlen=100)
_events_lock = Lock()

def add_trade_event(event_type: str, currency: str, message: str, details: Optional[Dict] = None):
    """
    Добавляет торговое событие в очередь
    
    Args:
        event_type: Тип события (buy, sell, error, info и т.д.)
        currency: Валюта
        message: Описание события
        details: Дополнительные детали события
    """
    with _events_lock:
        event = {
            'timestamp': datetime.now().isoformat(),
            'type': event_type,
            'currency': currency,
            'message': message,
            'details': details or {}
        }
        _trade_events.append(event)

def get_trade_events(limit: int = 50) -> List[Dict]:
    """
    Получает последние торговые события
    
    Args:
        limit: Максимальное количество событий
        
    Returns:
        Список событий (от новых к старым)
    """
    with _events_lock:
        # Возвращаем копию последних событий в обратном порядке
        events_list = list(_trade_events)
        events_list.reverse()
        return events_list[:limit]

def clear_trade_events():
    """Очищает все торговые события"""
    with _events_lock:
        _trade_events.clear()

def get_events_count() -> int:
    """Возвращает количество событий в очереди"""
    with _events_lock:
        return len(_trade_events)
