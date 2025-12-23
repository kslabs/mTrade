"""
DEBUG PANEL Logger для автотрейдера
Отправляет торговые события в DEBUG PANEL через WebSocket/HTTP
"""

import time
from typing import Optional, Dict, Any

class DebugPanelLogger:
    """Логгер для отправки торговых событий в DEBUG PANEL"""
    
    def __init__(self):
        self.enabled = True
        self.last_messages = []  # История последних сообщений
        self.max_history = 100
        
    def log_trade_decision(self, base: str, decision: str, details: Dict[str, Any]):
        """
        Логировать торговое решение
        
        Args:
            base: Базовая валюта (например, BTC)
            decision: Тип решения (threshold_exceeded, buy_requested, sell_requested, etc.)
            details: Детали решения (цена, объем, время и т.д.)
        """
        if not self.enabled:
            return
            
        timestamp = time.time()
        
        # Форматируем сообщение в зависимости от типа решения
        if decision == 'threshold_exceeded':
            msg = self._format_threshold_message(base, details)
        elif decision == 'buy_requested':
            msg = self._format_buy_request_message(base, details)
        elif decision == 'sell_requested':
            msg = self._format_sell_request_message(base, details)
        elif decision == 'order_response':
            msg = self._format_order_response_message(base, details)
        elif decision == 'cycle_start':
            msg = self._format_cycle_start_message(base, details)
        elif decision == 'cycle_complete':
            msg = self._format_cycle_complete_message(base, details)
        else:
            msg = f"[{base}] {decision}: {details}"
            
        # Добавляем в историю
        self.last_messages.append({
            'timestamp': timestamp,
            'base': base,
            'decision': decision,
            'message': msg,
            'details': details
        })
        
        # Ограничиваем историю
        if len(self.last_messages) > self.max_history:
            self.last_messages = self.last_messages[-self.max_history:]
            
        # Выводим в консоль (будет подхвачено DEBUG PANEL через stdout)
        print(f"[DEBUG_PANEL] {msg}")
        
    def _format_threshold_message(self, base: str, details: Dict[str, Any]) -> str:
        """Форматирование сообщения о превышении порога"""
        direction = details.get('direction', 'unknown')
        current_price = details.get('current_price', 0)
        threshold_price = details.get('threshold_price', 0)
        delta_pct = details.get('delta_pct', 0)
        
        if direction == 'buy':
            return f"⬇️ {base}: Цена упала на {abs(delta_pct):.2f}% (текущая: {current_price:.8f}, порог: {threshold_price:.8f}) → ПОКУПКА"
        elif direction == 'sell':
            return f"⬆️ {base}: Цена выросла на {delta_pct:.2f}% (текущая: {current_price:.8f}, порог: {threshold_price:.8f}) → ПРОДАЖА"
        else:
            return f"📊 {base}: Порог превышен ({delta_pct:.2f}%)"
            
    def _format_buy_request_message(self, base: str, details: Dict[str, Any]) -> str:
        """Форматирование сообщения о запросе на покупку"""
        step = details.get('step', 0)
        amount = details.get('amount', 0)
        price = details.get('price', 0)
        usd_value = details.get('usd_value', 0)
        order_type = details.get('order_type', 'limit')
        
        return f"🛒 {base} ШАГ {step}: Запрос покупки {amount:.8f} {base} по {price:.8f} ({usd_value:.2f} USDT) [{order_type.upper()}]"
        
    def _format_sell_request_message(self, base: str, details: Dict[str, Any]) -> str:
        """Форматирование сообщения о запросе на продажу"""
        amount = details.get('amount', 0)
        price = details.get('price', 0)
        usd_value = details.get('usd_value', 0)
        profit_pct = details.get('profit_pct', 0)
        order_type = details.get('order_type', 'limit')
        
        return f"💰 {base}: Запрос продажи {amount:.8f} {base} по {price:.8f} ({usd_value:.2f} USDT) [ПРИБЫЛЬ: {profit_pct:.2f}%] [{order_type.upper()}]"
        
    def _format_order_response_message(self, base: str, details: Dict[str, Any]) -> str:
        """Форматирование сообщения об ответе на ордер"""
        side = details.get('side', 'unknown')
        success = details.get('success', False)
        filled = details.get('filled', 0)
        response_time = details.get('response_time', 0)
        error = details.get('error', None)
        
        if success:
            return f"✅ {base}: Ордер {side.upper()} исполнен! Объем: {filled:.8f} {base} (время: {response_time:.3f}с)"
        else:
            error_msg = f" [{error}]" if error else ""
            return f"❌ {base}: Ордер {side.upper()} НЕ исполнен{error_msg} (время: {response_time:.3f}с)"
            
    def _format_cycle_start_message(self, base: str, details: Dict[str, Any]) -> str:
        """Форматирование сообщения о старте цикла"""
        start_price = details.get('start_price', 0)
        amount = details.get('amount', 0)
        invested = details.get('invested', 0)
        
        return f"🚀 {base}: СТАРТ ЦИКЛА! Цена: {start_price:.8f}, Объем: {amount:.8f} {base}, Инвестировано: {invested:.2f} USDT"
        
    def _format_cycle_complete_message(self, base: str, details: Dict[str, Any]) -> str:
        """Форматирование сообщения о завершении цикла"""
        profit = details.get('profit', 0)
        profit_pct = details.get('profit_pct', 0)
        duration = details.get('duration', 0)
        steps = details.get('steps', 0)
        
        return f"🎯 {base}: ЦИКЛ ЗАВЕРШЕН! Прибыль: {profit:.2f} USDT ({profit_pct:.2f}%), Шагов: {steps}, Время: {duration:.0f}с"
        
    def get_recent_messages(self, limit: int = 50) -> list:
        """Получить последние сообщения"""
        return self.last_messages[-limit:]
        
    def clear_history(self):
        """Очистить историю сообщений"""
        self.last_messages = []


# Глобальный экземпляр логгера
_debug_logger = None

def get_debug_logger() -> DebugPanelLogger:
    """Получить глобальный экземпляр логгера"""
    global _debug_logger
    if _debug_logger is None:
        _debug_logger = DebugPanelLogger()
    return _debug_logger
