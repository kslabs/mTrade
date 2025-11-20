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
import logging

logging.basicConfig(filename='system_trader.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')


class TradeLogger:
    """Менеджер логов торговых операций (per-currency)"""
    
    MAX_LOG_ENTRIES = 10000  # Максимум записей в памяти и на диске для каждой валюты
    LOG_DIR = "trade_logs"  # Директория для хранения логов
    
    def __init__(self):
        # Словарь логов по валютам: {currency: deque()}
        self.logs_by_currency = {}
        self.lock = Lock()
        
        # Общая объём инвестиций и профита по валютам
        self.total_invested = {}  # {currency: float}
        self.total_pnl = {}       # {currency: float}
        
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
        volume_quote = volume * price  # Объём в котируемой валюте
        
        # Обновляем общую сумму инвестиций
        if currency not in self.total_invested:
            self.total_invested[currency] = 0.0
        self.total_invested[currency] += investment
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'time': datetime.now().strftime('%H:%M:%S'),
            'type': 'buy',
            'currency': currency,
            'volume': volume,
            'volume_quote': volume_quote,
            'price': price,
            'delta_percent': delta_percent,
            'total_drop_percent': total_drop_percent,
            'investment': investment,
            'total_invested': self.total_invested[currency]
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
        
        # Лог только в котируемой валюте:
        print(f"[{entry['time']}] [{currency}] Buy{{USDT:{volume_quote:.4f}; Курс:{price:.4f}; ↓Δ%:{delta_percent:.2f}; ↓%:{total_drop_percent:.2f}; Инвест:{investment:.4f}; ВсегоИнвест:{self.total_invested[currency]:.4f}}}")
        logging.info(f"BUY: currency={currency}, volume={volume}, price={price}, delta_percent={delta_percent}, total_drop_percent={total_drop_percent}, investment={investment}")
    
    def log_sell(self, currency: str, volume: float, price: float, 
                 delta_percent: float, pnl: float):
        """Логировать операцию продажи (в файл конкретной валюты)"""
        currency = currency.upper()
        volume_quote = volume * price  # Объём в котируемой валюте
        
        # Обновляем профит и уменьшаем инвестиции
        if currency not in self.total_invested:
            self.total_invested[currency] = 0.0
        if currency not in self.total_pnl:
            self.total_pnl[currency] = 0.0
        self.total_pnl[currency] += pnl
        self.total_invested[currency] -= volume_quote  # считаем, что продаём весь объём
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'time': datetime.now().strftime('%H:%M:%S'),
            'type': 'sell',
            'currency': currency,
            'volume': volume,
            'volume_quote': volume_quote,
            'price': price,
            'delta_percent': delta_percent,
            'pnl': pnl,
            'total_pnl': self.total_pnl[currency],
            'total_invested': self.total_invested[currency]
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
        
        # Лог только в котируемой валюте:
        print(f"[{entry['time']}] [{currency}] Sell{{{currency}; USDT:{volume_quote:.4f}; Курс:{price:.4f}; ↑Δ%:{delta_percent:.2f}; PnL:{pnl:.4f}; СуммПрофит:{self.total_pnl[currency]:.4f}; ОстИнвест:{self.total_invested[currency]:.4f}}}")
        logging.info(f"SELL: currency={currency}, volume={volume}, price={price}, delta_percent={delta_percent}, pnl={pnl}")
    
    def log_sell_diagnostics(self, currency: str, price: float, sell_level: float, volume: float, active_step: int, cycle_state: str, last_buy: dict, reason: str):
        """
        Логировать диагностику попытки продажи: параметры и причину отказа
        """
        currency = currency.upper()
        time_str = datetime.now().strftime('%H:%M:%S')
        line = (
            f"[{time_str}] [{currency}] Sell-DIAG{{"
            f"Цена:{price:.4f}; Sell-уровень:{sell_level:.4f}; Объём:{volume:.4f}; "
            f"Шаг:{active_step}; Состояние:{cycle_state}; ПоследняяПокупка:{last_buy}; "
            f"Причина: {reason}}}"
        )
        print(line)
        logging.info(f"SELL-DIAG: currency={currency}, price={price}, sell_level={sell_level}, volume={volume}, active_step={active_step}, cycle_state={cycle_state}, last_buy={last_buy}, reason={reason}")
        # Можно добавить запись в отдельный диагностический лог-файл при необходимости
    
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
                # Защита: не возвращать объединённые логи всех валют
                print("[TRADE_LOGGER] ВНИМАНИЕ: Для получения логов укажите валюту! Объединённые логи не возвращаются.")
                return []
        # Ограничение количества
        if limit and len(logs_list) > limit:
            logs_list = logs_list[:limit]
        return logs_list
    
    def get_formatted_logs(self, limit: Optional[int] = None, currency: Optional[str] = None) -> List[str]:
        """
        Форматированный вывод логов для UI/консоли
        Все расчёты (инвестиции, профит, остаток) ведутся по истории логов данной валюты.
        """
        if not currency:
            print("[TRADE_LOGGER] ВНИМАНИЕ: Для отображения логов укажите валюту! Объединённые логи не выводятся.")
            return []
        logs = self.get_logs(limit, currency)
        formatted = []
        # Для расчёта динамики по валюте
        invested = 0.0
        pnl_sum = 0.0
        for log in logs:
            time_str = log.get('time', '??:??:??')
            currency_str = log.get('currency', '')
            log_type = log.get('type', '').capitalize()
            volume_quote = log.get('volume_quote', log.get('volume', 0) * log.get('price', 0))
            if log.get('type') == 'buy':
                invested += log.get('investment', 0)
                line = (
                    f"[{time_str}] [{currency_str}] {log_type}{{"
                    f"USDT:{volume_quote:.4f}; "
                    f"Курс:{log.get('price', 0):.4f}; "
                    f"↓Δ%:{log.get('delta_percent', 0):.2f}; "
                    f"↓%:{log.get('total_drop_percent', 0):.2f}; "
                    f"Инвест:{log.get('investment', 0):.4f}; "
                    f"ВсегоИнвест:{invested:.4f}}}"
                )
            else:  # sell
                pnl_sum += log.get('pnl', 0)
                invested -= volume_quote
                line = (
                    f"[{time_str}] [{currency_str}] {log_type}{{"
                    f"USDT:{volume_quote:.4f}; "
                    f"Курс:{log.get('price', 0):.4f}; "
                    f"↑Δ%:{log.get('delta_percent', 0):.2f}; "
                    f"PnL:{log.get('pnl', 0):.4f}; "
                    f"СуммПрофит:{pnl_sum:.4f}; "
                    f"ОстИнвест:{invested:.4f}}}"
                )
            formatted.append(line)
        
        print(f"[TRADE_LOGGER] get_formatted_logs: {len(logs)} записей, валюта: {currency}")
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
                print("[TRADE_LOGGER] ВНИМАНИЕ: Для удаления логов укажите валюту! Удаление всех логов запрещено.")
    
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
