"""
Trade Logger - Логирование торговых операций
Ведёт журнал всех торговых операций с ограничением размера
"""

import os
import json
from datetime import datetime
from threading import Lock
from collections import deque
from typing import Dict, List, Optional


class TradeLogger:
    """Менеджер логов торговых операций"""
    
    MAX_LOG_ENTRIES = 10000  # Максимум записей в памяти и на диске
    LOG_FILE = "trade_logs.jsonl"  # JSONL формат (JSON Lines)
    
    def __init__(self):
        self.logs = deque(maxlen=self.MAX_LOG_ENTRIES)
        self.lock = Lock()
        self._load_logs()
    
    def _load_logs(self):
        """Загрузить логи из файла"""
        if not os.path.exists(self.LOG_FILE):
            return
        
        try:
            with open(self.LOG_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entry = json.loads(line)
                            self.logs.append(entry)
                        except json.JSONDecodeError:
                            continue
            
            print(f"[TRADE_LOGGER] Загружено {len(self.logs)} записей из лога")
        except Exception as e:
            print(f"[TRADE_LOGGER] Ошибка загрузки логов: {e}")
    
    def _save_log_entry(self, entry: dict):
        """Сохранить одну запись в файл (append)"""
        try:
            with open(self.LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"[TRADE_LOGGER] Ошибка записи в лог: {e}")
    
    def _trim_log_file(self):
        """Обрезать файл лога до MAX_LOG_ENTRIES записей"""
        try:
            if not os.path.exists(self.LOG_FILE):
                return
            
            # Читаем все записи
            entries = []
            with open(self.LOG_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            
            # Оставляем только последние MAX_LOG_ENTRIES
            if len(entries) > self.MAX_LOG_ENTRIES:
                entries = entries[-self.MAX_LOG_ENTRIES:]
                
                # Перезаписываем файл
                with open(self.LOG_FILE, 'w', encoding='utf-8') as f:
                    for entry in entries:
                        f.write(json.dumps(entry, ensure_ascii=False) + '\n')
                
                print(f"[TRADE_LOGGER] Файл лога обрезан до {len(entries)} записей")
        except Exception as e:
            print(f"[TRADE_LOGGER] Ошибка обрезки лога: {e}")
    
    def log_buy(self, currency: str, volume: float, price: float, 
                delta_percent: float, total_drop_percent: float, investment: float):
        """Логировать операцию покупки"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'time': datetime.now().strftime('%H:%M:%S'),
            'type': 'buy',
            'currency': currency,
            'volume': volume,
            'price': price,
            'delta_percent': delta_percent,
            'total_drop_percent': total_drop_percent,
            'investment': investment
        }
        
        with self.lock:
            self.logs.append(entry)
            self._save_log_entry(entry)
            
            # Периодически обрезаем файл (каждые 100 записей)
            if len(self.logs) % 100 == 0:
                self._trim_log_file()
        
        print(f"[TRADE_LOG] Buy {currency}: V={volume:.4f} P={price:.4f} ↓Δ%={delta_percent:.2f} ↓%={total_drop_percent:.2f} Inv={investment:.4f}")
    
    def log_sell(self, currency: str, volume: float, price: float, 
                 delta_percent: float, pnl: float):
        """Логировать операцию продажи"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'time': datetime.now().strftime('%H:%M:%S'),
            'type': 'sell',
            'currency': currency,
            'volume': volume,
            'price': price,
            'delta_percent': delta_percent,
            'pnl': pnl
        }
        
        with self.lock:
            self.logs.append(entry)
            self._save_log_entry(entry)
            
            # Периодически обрезаем файл (каждые 100 записей)
            if len(self.logs) % 100 == 0:
                self._trim_log_file()
        
        print(f"[TRADE_LOG] Sell {currency}: V={volume:.4f} P={price:.4f} ↑Δ%={delta_percent:.2f} PnL={pnl:.4f}")
    
    def get_logs(self, limit: Optional[int] = None, currency: Optional[str] = None) -> List[dict]:
        """Получить логи
        
        Args:
            limit: Максимальное количество записей (последние N)
            currency: Фильтр по валюте
        
        Returns:
            Список записей логов
        """
        with self.lock:
            logs_list = list(self.logs)
        
        # Фильтр по валюте
        if currency:
            logs_list = [log for log in logs_list if log.get('currency', '').upper() == currency.upper()]
        
        # Сортировка по времени (новые первыми)
        logs_list.reverse()
        
        # Ограничение количества
        if limit:
            logs_list = logs_list[:limit]
        
        return logs_list
    
    def get_formatted_logs(self, limit: Optional[int] = None, currency: Optional[str] = None) -> List[str]:
        """Получить логи в форматированном виде
        
        Returns:
            Список строк в формате:
            [17:19:39] Buy{Объем:44.7746; Курс:0.7745; ↓Δ%:0.96; ↓%:3.6; Инвест:85.9807}
        """
        logs = self.get_logs(limit, currency)
        formatted = []
        
        for log in logs:
            time_str = log.get('time', '??:??:??')
            log_type = log.get('type', '').capitalize()
            
            if log.get('type') == 'buy':
                # Формат для покупки
                line = (
                    f"[{time_str}] {log_type}{{"
                    f"Объем:{log.get('volume', 0):.4f}; "
                    f"Курс:{log.get('price', 0):.4f}; "
                    f"↓Δ%:{log.get('delta_percent', 0):.2f}; "
                    f"↓%:{log.get('total_drop_percent', 0):.2f}; "
                    f"Инвест:{log.get('investment', 0):.4f}}}"
                )
            else:  # sell
                # Формат для продажи
                line = (
                    f"[{time_str}] {log_type}{{"
                    f"Объем:{log.get('volume', 0):.4f}; "
                    f"Курс:{log.get('price', 0):.4f}; "
                    f"↑Δ%:{log.get('delta_percent', 0):.2f}; "
                    f"PnL:{log.get('pnl', 0):.4f}}}"
                )
            
            formatted.append(line)
        
        return formatted
    
    def clear_logs(self, currency: Optional[str] = None):
        """Очистить логи
        
        Args:
            currency: Если указана, очистить только логи для этой валюты
        """
        with self.lock:
            if currency:
                # Удаляем только логи для указанной валюты
                self.logs = deque(
                    (log for log in self.logs if log.get('currency', '').upper() != currency.upper()),
                    maxlen=self.MAX_LOG_ENTRIES
                )
            else:
                # Очистить все логи
                self.logs.clear()
            
            # Перезаписываем файл
            try:
                with open(self.LOG_FILE, 'w', encoding='utf-8') as f:
                    for entry in self.logs:
                        f.write(json.dumps(entry, ensure_ascii=False) + '\n')
                print(f"[TRADE_LOGGER] Логи очищены (осталось {len(self.logs)} записей)")
            except Exception as e:
                print(f"[TRADE_LOGGER] Ошибка очистки логов: {e}")
    
    def get_stats(self, currency: Optional[str] = None) -> Dict:
        """Получить статистику по логам"""
        logs = self.get_logs(currency=currency)
        
        total_buys = sum(1 for log in logs if log.get('type') == 'buy')
        total_sells = sum(1 for log in logs if log.get('type') == 'sell')
        
        total_investment = sum(log.get('investment', 0) for log in logs if log.get('type') == 'buy')
        total_pnl = sum(log.get('pnl', 0) for log in logs if log.get('type') == 'sell')
        
        return {
            'total_entries': len(logs),
            'total_buys': total_buys,
            'total_sells': total_sells,
            'total_investment': round(total_investment, 4),
            'total_pnl': round(total_pnl, 4),
            'currency': currency
        }


# Глобальный экземпляр логгера
_trade_logger = None


def get_trade_logger() -> TradeLogger:
    """Получить глобальный экземпляр логгера торговли"""
    global _trade_logger
    if _trade_logger is None:
        _trade_logger = TradeLogger()
    return _trade_logger
