"""
Trade Logger - Логирование торговых операций
Ведёт журнал всех торговых операций с ограничением размера
Per-currency логи: каждая валюта имеет свой файл логов
"""

import os
import json
from datetime import datetime
from threading import Lock
from collections import deque
from typing import Dict, List, Optional


class TradeLogger:
    """Менеджер логов торговых операций (per-currency)"""
    
    MAX_LOG_ENTRIES = 10000  # Максимум записей в памяти и на диске для каждой валюты
    LOG_DIR = "trade_logs"  # Директория для хранения логов
    
    def __init__(self):
        # Словарь логов по валютам: {currency: deque()}
        self.logs_by_currency = {}
        self.lock = Lock()
        
        # Создаём директорию для логов если её нет
        if not os.path.exists(self.LOG_DIR):
            os.makedirs(self.LOG_DIR)
            print(f"[TRADE_LOGGER] Создана директория для логов: {self.LOG_DIR}")
        
        # Загружаем существующие логи
        self._load_all_logs()
    
    def _get_log_file_path(self, currency: str) -> str:
        """Получить путь к файлу логов для валюты"""
        return os.path.join(self.LOG_DIR, f"{currency.upper()}_logs.jsonl")
    
    def _load_logs_for_currency(self, currency: str):
        """Загрузить логи для конкретной валюты"""
        currency = currency.upper()
        log_file = self._get_log_file_path(currency)
        
        if not os.path.exists(log_file):
            return
        
        try:
            logs = deque(maxlen=self.MAX_LOG_ENTRIES)
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entry = json.loads(line)
                            logs.append(entry)
                        except json.JSONDecodeError:
                            continue
            
            self.logs_by_currency[currency] = logs
            print(f"[TRADE_LOGGER] Загружено {len(logs)} записей для {currency}")
        except Exception as e:
            print(f"[TRADE_LOGGER] Ошибка загрузки логов для {currency}: {e}")
    
    def _load_all_logs(self):
        """Загрузить логи для всех валют из директории"""
        try:
            if not os.path.exists(self.LOG_DIR):
                return
            
            # Ищем все файлы логов (*_logs.jsonl)
            for filename in os.listdir(self.LOG_DIR):
                if filename.endswith('_logs.jsonl'):
                    # Извлекаем название валюты из имени файла
                    currency = filename.replace('_logs.jsonl', '')
                    self._load_logs_for_currency(currency)
            
            total_logs = sum(len(logs) for logs in self.logs_by_currency.values())
            print(f"[TRADE_LOGGER] Всего загружено {total_logs} записей для {len(self.logs_by_currency)} валют")
        except Exception as e:
            print(f"[TRADE_LOGGER] Ошибка загрузки логов: {e}")
    
    def _ensure_currency_logs(self, currency: str):
        """Убедиться что для валюты существует контейнер логов"""
        currency = currency.upper()
        if currency not in self.logs_by_currency:
            self.logs_by_currency[currency] = deque(maxlen=self.MAX_LOG_ENTRIES)
    
    def _save_log_entry(self, currency: str, entry: dict):
        """Сохранить одну запись в файл валюты (append)"""
        currency = currency.upper()
        log_file = self._get_log_file_path(currency)
        
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"[TRADE_LOGGER] Ошибка записи в лог {currency}: {e}")
    
    def _trim_log_file(self, currency: str):
        """Обрезать файл лога валюты до MAX_LOG_ENTRIES записей"""
        currency = currency.upper()
        log_file = self._get_log_file_path(currency)
        
        try:
            if not os.path.exists(log_file):
                return
            
            # Читаем все записи
            entries = []
            with open(log_file, 'r', encoding='utf-8') as f:
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
                with open(log_file, 'w', encoding='utf-8') as f:
                    for entry in entries:
                        f.write(json.dumps(entry, ensure_ascii=False) + '\n')
                
                print(f"[TRADE_LOGGER] Файл лога {currency} обрезан до {len(entries)} записей")
        except Exception as e:
            print(f"[TRADE_LOGGER] Ошибка обрезки лога {currency}: {e}")
    
    def log_buy(self, currency: str, volume: float, price: float, 
                delta_percent: float, total_drop_percent: float, investment: float):
        """Логировать операцию покупки (в файл конкретной валюты)"""
        currency = currency.upper()
        
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
            # Убедиться что для валюты есть контейнер
            self._ensure_currency_logs(currency)
            
            # Добавить в память
            self.logs_by_currency[currency].append(entry)
            
            # Сохранить в файл валюты
            self._save_log_entry(currency, entry)
            
            # Периодически обрезаем файл (каждые 100 записей для данной валюты)
            if len(self.logs_by_currency[currency]) % 100 == 0:
                self._trim_log_file(currency)
        
        print(f"[TRADE_LOG] {currency} Buy: V={volume:.4f} P={price:.4f} ↓Δ%={delta_percent:.2f} ↓%={total_drop_percent:.2f} Inv={investment:.4f}")
    
    def log_sell(self, currency: str, volume: float, price: float, 
                 delta_percent: float, pnl: float):
        """Логировать операцию продажи (в файл конкретной валюты)"""
        currency = currency.upper()
        
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
            # Убедиться что для валюты есть контейнер
            self._ensure_currency_logs(currency)
            
            # Добавить в память
            self.logs_by_currency[currency].append(entry)
            
            # Сохранить в файл валюты
            self._save_log_entry(currency, entry)
            
            # Периодически обрезаем файл (каждые 100 записей для данной валюты)
            if len(self.logs_by_currency[currency]) % 100 == 0:
                self._trim_log_file(currency)
        
        print(f"[TRADE_LOG] {currency} Sell: V={volume:.4f} P={price:.4f} ↑Δ%={delta_percent:.2f} PnL={pnl:.4f}")
    
    def get_logs(self, limit: Optional[int] = None, currency: Optional[str] = None) -> List[dict]:
        """Получить логи
        
        Args:
            limit: Максимальное количество записей (последние N)
            currency: Валюта (если не указана - все валюты)
        
        Returns:
            Список записей логов
        """
        with self.lock:
            if currency:
                # Логи только для одной валюты
                currency = currency.upper()
                if currency in self.logs_by_currency:
                    logs_list = list(self.logs_by_currency[currency])
                else:
                    logs_list = []
            else:
                # Логи для всех валют (объединяем и сортируем по времени)
                logs_list = []
                for curr_logs in self.logs_by_currency.values():
                    logs_list.extend(list(curr_logs))
                # Сортируем по timestamp
                logs_list.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Ограничение количества
        if limit and len(logs_list) > limit:
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
            currency: Если указана, очистить только логи для этой валюты, иначе все валюты
        """
        with self.lock:
            if currency:
                # Очистить логи для одной валюты
                currency = currency.upper()
                if currency in self.logs_by_currency:
                    self.logs_by_currency[currency].clear()
                
                # Удалить файл валюты
                log_file = self._get_log_file_path(currency)
                try:
                    if os.path.exists(log_file):
                        os.remove(log_file)
                        print(f"[TRADE_LOGGER] Логи для {currency} очищены")
                except Exception as e:
                    print(f"[TRADE_LOGGER] Ошибка удаления файла логов {currency}: {e}")
            else:
                # Очистить все логи всех валют
                for currency in list(self.logs_by_currency.keys()):
                    self.logs_by_currency[currency].clear()
                    
                    # Удалить файл
                    log_file = self._get_log_file_path(currency)
                    try:
                        if os.path.exists(log_file):
                            os.remove(log_file)
                    except Exception as e:
                        print(f"[TRADE_LOGGER] Ошибка удаления файла логов {currency}: {e}")
                
                self.logs_by_currency.clear()
                print(f"[TRADE_LOGGER] Все логи очищены")
    
    def get_stats(self, currency: Optional[str] = None) -> Dict:
        """Получить статистику по логам
        
        Args:
            currency: Валюта (если не указана - статистика по всем валютам)
        """
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
            'currency': currency,
            'currencies_count': len(self.logs_by_currency) if not currency else 1
        }
    
    def get_currencies_with_logs(self) -> List[str]:
        """Получить список валют, для которых есть логи"""
        with self.lock:
            return sorted(list(self.logs_by_currency.keys()))


# Глобальный экземпляр логгера
_trade_logger = None


def get_trade_logger() -> TradeLogger:
    """Получить глобальный экземпляр логгера торговли"""
    global _trade_logger
    if _trade_logger is None:
        _trade_logger = TradeLogger()
    return _trade_logger
