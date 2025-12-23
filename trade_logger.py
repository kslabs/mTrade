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

        

        # Общая объём инвестиций по валютам (НЕ накопительный между циклами!)
        self.total_invested = {}  # {currency: float}
        
        # DEPRECATED: Это поле больше не используется
        # Профиты теперь хранятся в логах (поле 'total_pnl' в каждой записи sell)
        # и не суммируются между циклами
        # self.total_pnl = {}       # {currency: float}

        

        # Создаём директорию для логов если её нет

        if not os.path.exists(self.LOG_DIR):

            os.makedirs(self.LOG_DIR)

            print(f"[TRADE_LOGGER] Создана директория для логов: {self.LOG_DIR}")

        

        # Загружаем существующие логи

        self._load_all_logs()

    

    def _get_log_file_path(self, currency: str) -> str:

        """Получить путь к файлу логов для валюты"""

        path = os.path.join(self.LOG_DIR, f"{currency.upper()}_logs.jsonl")
        return path

    def _get_diag_file_path(self, currency: str) -> str:
        """Получить путь к файлу диагностических логов для валюты"""
        return os.path.join(self.LOG_DIR, f"{currency.upper()}_diag.jsonl")

    

    def _load_logs_for_currency(self, currency: str):

        """Загрузить логи для конкретной валюты и восстановить total_invested"""

        currency = currency.upper()

        log_file = self._get_log_file_path(currency)

        

        if not os.path.exists(log_file):

            return

        

        try:

            logs = deque(maxlen=self.MAX_LOG_ENTRIES)

            last_total_invested = 0.0
            last_entry_time = None
            
            with open(log_file, 'r', encoding='utf-8') as f:

                for line in f:

                    line = line.strip()

                    if line:

                        try:

                            entry = json.loads(line)

                            logs.append(entry)
                            
                            # ✅ ПРАВИЛЬНОЕ ВОССТАНОВЛЕНИЕ: берём total_invested из САМОЙ ПОСЛЕДНЕЙ записи
                            # При загрузке логов мы идём по записям последовательно
                            # - Если встретили buy: берём его total_invested (уже накопленный)
                            # - Если встретили sell: обнуляем (цикл завершён)
                            if entry.get('type') == 'buy' and 'total_invested' in entry:
                                old_value = last_total_invested
                                last_total_invested = entry['total_invested']
                                last_entry_time = entry.get('timestamp')
                                print(f"[{currency}] 📖 ЗАГРУЗКА Buy: total_invested {old_value:.4f} → {last_total_invested:.4f}")
                            elif entry.get('type') == 'sell':
                                old_value = last_total_invested
                                # После продажи total_invested = 0 (цикл завершён)
                                last_total_invested = 0.0
                                last_entry_time = entry.get('timestamp')
                                print(f"[{currency}] 📖 ЗАГРУЗКА Sell: total_invested {old_value:.4f} → 0.0 (обнулён)")

                        except json.JSONDecodeError:

                            continue

            

            self.logs_by_currency[currency] = logs
            self.total_invested[currency] = last_total_invested

            print(f"[TRADE_LOGGER] Загружено {len(logs)} записей для {currency}, total_invested={last_total_invested:.4f} (последняя запись: {last_entry_time})")

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
            print(f"[{currency}] ❗ ИНИЦИАЛИЗАЦИЯ total_invested = 0.0")

        
        # 🔍 ОТЛАДКА: Выводим состояние ДО покупки
        print(f"[{currency}] 🔍 LOG_BUY ДО: total_invested={self.total_invested[currency]:.4f}, investment={investment:.4f}")
        
        self.total_invested[currency] += investment
        
        # 🔍 ОТЛАДКА: Выводим состояние ПОСЛЕ покупки
        print(f"[{currency}] ✅ LOG_BUY ПОСЛЕ: total_invested={self.total_invested[currency]:.4f}")
        
        # 🔍 ДИАГНОСТИКА: Проверяем разницу между пересчитанной и реальной суммой
        if abs(volume_quote - investment) > 0.0001:
            print(f"[{currency}] ⚠️ РАСХОЖДЕНИЕ: volume*price={volume_quote:.4f}, реальная сумма={investment:.4f}, разница={abs(volume_quote - investment):.4f}")

        

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
        # Все суммы в логах показываем в котируемой валюте (USDT)
        # ✅ ИСПРАВЛЕНО: Показываем РЕАЛЬНУЮ сумму инвестиции (investment), а не пересчитанную (volume_quote)
        # investment - это РЕАЛЬНАЯ сумма, потраченная на покупку (из ордера)
        # Инвест - показываем НАКОПИТЕЛЬНУЮ сумму инвестиций (total_invested)
        print(f"[{entry['time']}] [{currency}] 🟢 Buy{{{investment:.4f}; Курс:{price:.4f}; ↓Δ%:{delta_percent:.2f}; ↓%:{total_drop_percent:.2f}; Инвест:{self.total_invested[currency]:.4f}}}")
        logging.info(f"BUY: currency={currency}, volume={volume}, price={price}, delta_percent={delta_percent}, total_drop_percent={total_drop_percent}, investment={investment}, total_invested={self.total_invested[currency]}")
    def log_sell(self, currency: str, volume: float, price: float, 
                 delta_percent: float, pnl: float, source: str = "AUTO",
                 detection_time: float = None, completion_time: float = None,
                 operation_duration: float = None):
        """Логировать операцию продажи (в файл конкретной валюты)
        
        Args:
            source: "AUTO" для автоматических продаж из _try_sell, "MANUAL" для ручных
            detection_time: Unix timestamp момента детекции условия продажи
            completion_time: Unix timestamp момента завершения продажи
            operation_duration: Длительность операции в секундах
        
        ВАЖНО: Профит = (сумма от продажи) - (сумма всех инвестиций в цикле)
        
        🔥 УСИЛЕННАЯ ВЕРСИЯ: С подробной диагностикой и защитой от ошибок
        """
        try:
            currency = currency.upper()
            volume_quote = volume * price  # Сумма от продажи в котируемой валюте
            
            print(f"\n[{currency}] 🔒 === ВХОД В log_sell() === 🔒")
            print(f"[{currency}] 📝 Параметры: volume={volume:.8f}, price={price:.8f}, delta={delta_percent:.2f}%, pnl={pnl:.4f}")
            print(f"[{currency}] 📝 Source: {source}")
            
            # 🔍 ОТЛАДКА: Выводим состояние ДО расчёта
            if currency not in self.total_invested:
                self.total_invested[currency] = 0.0
                print(f"[{currency}] ❗ ИНИЦИАЛИЗАЦИЯ total_invested = 0.0 (в продаже)")
            
            print(f"[{currency}] 🔍 LOG_SELL ДО: total_invested={self.total_invested[currency]:.4f}, volume_quote={volume_quote:.4f}")
            
            # ✅ ПРАВИЛЬНЫЙ РАСЧЁТ ПРОФИТА:
            # Профит = (сумма от продажи) - (сумма всех инвестиций в цикле)
            cycle_profit = volume_quote - self.total_invested[currency]
            
            print(f"[{currency}] 💰 ПРОФИТ: {cycle_profit:.4f} = {volume_quote:.4f} - {self.total_invested[currency]:.4f}")
            
            # Сохраняем сумму инвестиций до обнуления (для отображения в логе)
            total_invested_before = self.total_invested[currency]
            
            # После продажи обнуляем инвестиции (цикл завершён)
            self.total_invested[currency] = 0.0
            
            print(f"[{currency}] ♻️ LOG_SELL ПОСЛЕ: total_invested ОБНУЛЁН = 0.0")
            
            # Форматируем временные метки
            detection_timestamp = None
            completion_timestamp = None
            time_from_detection = None
            
            try:
                if detection_time:
                    detection_timestamp = datetime.fromtimestamp(detection_time).strftime('%Y-%m-%d %H:%M:%S')
                if completion_time:
                    completion_timestamp = datetime.fromtimestamp(completion_time).strftime('%Y-%m-%d %H:%M:%S')
                if detection_time and completion_time:
                    time_from_detection = completion_time - detection_time
                print(f"[{currency}] 🕒 Временные метки обработаны: detection={detection_timestamp}, completion={completion_timestamp}")
            except Exception as time_error:
                print(f"[{currency}] ⚠️ Ошибка форматирования временных меток: {time_error}")
                # Продолжаем без временных меток, это не критично
            
            print(f"[{currency}] 📦 Создание entry...")
            entry = {
                'timestamp': datetime.now().isoformat(),
                'time': datetime.now().strftime('%H:%M:%S'),
                'type': 'sell',
                'currency': currency,
                'volume': volume,
                'volume_quote': volume_quote,
                'price': price,
                'delta_percent': delta_percent,
                'pnl': pnl,  # PnL от автотрейдера (может быть неточным)
                'total_pnl': cycle_profit,  # ✅ ПРАВИЛЬНЫЙ ПРОФИТ ЦИКЛА
                'total_invested': total_invested_before,  # Показываем сколько было инвестировано
                'detection_time': detection_timestamp,  # Время обнаружения условия
                'completion_time': completion_timestamp,  # Время завершения продажи
                'time_from_detection': time_from_detection,  # Время от детекции до завершения (секунды)
                'operation_duration': operation_duration  # Общая длительность операции (секунды)
            }
            print(f"[{currency}] ✅ Entry создан: {entry}")
            
            print(f"[{currency}] 🔒 Захват lock для записи в файл...")
            with self.lock:
                print(f"[{currency}] ✅ Lock захвачен")
                
                # Убедиться что для валюты есть контейнер
                print(f"[{currency}] 📂 _ensure_currency_logs()...")
                self._ensure_currency_logs(currency)
                print(f"[{currency}] ✅ Контейнер валюты готов")
                
                # Добавить в память
                print(f"[{currency}] 💾 Добавление в память (logs_by_currency)...")
                self.logs_by_currency[currency].append(entry)
                print(f"[{currency}] ✅ Добавлено в память (всего записей: {len(self.logs_by_currency[currency])})")
                
                # Сохранить в файл валюты
                print(f"[{currency}] 💾 Сохранение в файл (_save_log_entry)...")
                self._save_log_entry(currency, entry)
                print(f"[{currency}] ✅ Сохранено в файл")
                
                # Периодически обрезаем файл (каждые 100 записей для данной валюты)
                if len(self.logs_by_currency[currency]) % 100 == 0:
                    print(f"[{currency}] ✂️ Обрезка файла (_trim_log_file)...")
                    self._trim_log_file(currency)
                    print(f"[{currency}] ✅ Файл обрезан")
            
            print(f"[{currency}] 🔓 Lock освобождён")
            
            # Лог только в котируемой валюте:
            # Показываем суммы в котируемой валюте без текстового суффикса 'USDT' и без дублирования имени валюты
            # В формате продаж: показываем PnL и Профит (который теперь = сумма от продажи - инвестиции)
            # Окрасим числа профита в консоли: положительный — зелёный, отрицательный — красный
            try:
                # ANSI escape sequences
                RED = '\x1b[31m'
                GREEN = '\x1b[32m'
                RESET = '\x1b[0m'
                pnl_color = GREEN if pnl >= 0 else RED
                profit_color = GREEN if cycle_profit >= 0 else RED
                pnl_str = f"{pnl_color}{pnl:.4f}{RESET}"
                profit_str = f"{profit_color}{cycle_profit:.4f}{RESET}"
            except Exception:
                pnl_str = f"{pnl:.4f}"
                profit_str = f"{cycle_profit:.4f}"

            # Маркер источника продажи
            source_marker = "🟢[AUTO]" if source == "AUTO" else "🔴[MANUAL]"
        
            # Показываем: сумму продажи, курс, рост, PnL, ПРОФИТ (= сумма продажи - инвестиции)
            # Убрано поле "Инвест" — оно нужно только в покупках!
            print(f"[{entry['time']}] [{currency}] {source_marker} Sell{{{volume_quote:.4f}; Курс:{price:.4f}; ↑Δ%:{delta_percent:.2f}; PnL:{pnl_str}; Профит:{profit_str}}}")
            
            # Дополнительный вывод временных меток, если они доступны
            if detection_timestamp and completion_timestamp and time_from_detection is not None:
                print(f"[{entry['time']}] [{currency}] 🕒 Детекция: {detection_timestamp} | Завершение: {completion_timestamp} | Δt: {time_from_detection:.2f}s")
            
            logging.info(f"SELL[{source}]: currency={currency}, volume={volume}, price={price}, delta_percent={delta_percent}, pnl={pnl}, cycle_profit={cycle_profit}, detection={detection_timestamp}, completion={completion_timestamp}, time_delta={time_from_detection}s")
            
            print(f"[{currency}] 🔒 === ВЫХОД ИЗ log_sell() (УСПЕХ) === 🔒\n")
        
        except Exception as log_sell_error:
            print(f"\n[{currency}] ❌❌❌ КРИТИЧЕСКАЯ ОШИБКА В log_sell() ❌❌❌")
            print(f"[{currency}] ❌ Тип ошибки: {type(log_sell_error).__name__}")
            print(f"[{currency}] ❌ Сообщение: {log_sell_error}")
            print(f"[{currency}] ❌ Параметры вызова:")
            print(f"[{currency}] ❌   currency={currency}")
            print(f"[{currency}] ❌   volume={volume}")
            print(f"[{currency}] ❌   price={price}")
            print(f"[{currency}] ❌   delta_percent={delta_percent}")
            print(f"[{currency}] ❌   pnl={pnl}")
            print(f"[{currency}] ❌   source={source}")
            print(f"[{currency}] ❌   detection_time={detection_time}")
            print(f"[{currency}] ❌   completion_time={completion_time}")
            print(f"[{currency}] ❌   operation_duration={operation_duration}")
            
            import traceback
            print(f"[{currency}] ❌ ПОЛНАЯ ТРАССИРОВКА:")
            traceback.print_exc()
            
            print(f"[{currency}] 🔒 === ВЫХОД ИЗ log_sell() (ОШИБКА) === 🔒\n")
            
            # Пробрасываем исключение дальше, чтобы autotrader_v2 мог обработать
            raise


    

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

    def log_buy_diagnostics(self, currency: str, price: float, needed_level: float, amount_needed: float, active_step: int, cycle_state: str, last_buy: dict, reason: str):
        """
        Логировать диагностику попытки докупки/усреднения
        """
        currency = currency.upper()
        time_str = datetime.now().strftime('%H:%M:%S')
        line = (
            f"[{time_str}] [{currency}] Buy-DIAG{{"
            f"Цена:{price:.4f}; Needed-level:{needed_level:.4f}; AmountNeeded:{amount_needed:.4f}; "
            f"Шаг:{active_step}; Состояние:{cycle_state}; ПоследняяПокупка:{last_buy}; "
            f"Причина: {reason}}}"
        )
        print(line)
        logging.info(f"BUY-DIAG: currency={currency}, price={price}, needed_level={needed_level}, amount_needed={amount_needed}, active_step={active_step}, cycle_state={cycle_state}, last_buy={last_buy}, reason={reason}")

    

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

    

    def get_last_entry(self, currency: str, entry_type: str = None) -> Optional[dict]:
        """Получить последнюю запись для валюты
        
        Args:
            currency: Валюта
            entry_type: Тип записи ('buy', 'sell' или None для любого типа)
        
        Returns:
            Последняя запись или None, если записей нет
        """
        currency = currency.upper()
        
        with self.lock:
            if currency not in self.logs_by_currency:
                return None
            
            logs = self.logs_by_currency[currency]
            
            if not logs:
                return None
            
            # Если указан тип, ищем последнюю запись этого типа
            if entry_type:
                for entry in reversed(logs):
                    if entry.get('type') == entry_type:
                        return entry
                return None
            
            # Иначе возвращаем самую последнюю запись
            return logs[-1] if logs else None
    
    def get_formatted_logs(self, limit: Optional[int] = None, currency: Optional[str] = None) -> List[str]:

        """

        Форматированный вывод логов для UI/консоли

        Все расчёты (инвестиции, профит, остаток) ведутся по истории логов данной валюты.
        
        ✅ ИСПРАВЛЕНО: Профит каждого цикла независим, не накапливается между циклами.

        """

        if not currency:

            print("[TRADE_LOGGER] ВНИМАНИЕ: Для отображения логов укажите валюту! Объединённые логи не выводятся.")

            return []

        # Получаем все логи для валюты и затем отбираем последние `limit` записей
        # чтобы корректно вернуть последние N записей (а не первые N старых записей)
        logs = self.get_logs(currency=currency)
        if limit:
            # берём последние limit записей
            logs = logs[-limit:]

        # Переворачиваем — так чтобы в начале были НОВЕЙШИЕ записи
        logs = list(logs)[::-1]

        formatted = []

        for log in logs:

            time_str = log.get('time', '??:??:??')

            currency_str = log.get('currency', '')

            log_type = log.get('type', '').capitalize()

            volume_quote = log.get('volume_quote', log.get('volume', 0) * log.get('price', 0))

            if log.get('type') == 'buy':

                # Показываем суммы (уже в котируемой валюте) без суффикса 'USDT' и без дублирующего поля 'ВсегоИнвест'
                # ✅ ИСПРАВЛЕНО: Используем total_invested (накопленная сумма), а не investment (последняя покупка)
                line = (
                    f"[{time_str}] [{currency_str}] {log_type}{{"
                    f"{volume_quote:.4f}; "
                    f"Курс:{log.get('price', 0):.4f}; "
                    f"↓Δ%:{log.get('delta_percent', 0):.2f}; "
                    f"↓%:{log.get('total_drop_percent', 0):.2f}; "
                    f"Инвест:{log.get('total_invested', 0):.4f}}}"
                )

            else:  # sell

                # ✅ ИСПРАВЛЕНО: Используем total_pnl (профит ЭТОГО цикла), а не накопленный pnl_sum
                # Профит цикла = (сумма от продажи) - (сумма всех инвестиций в цикле)
                cycle_profit = log.get('total_pnl', 0)
                
                # Для продажи: показываем сумму продажи, курс, рост, PnL и профит ЦИКЛА
                # ✅ ИСПРАВЛЕНО: Убрано поле "Инвест" — оно нужно только в покупках!
                line = (
                    f"[{time_str}] [{currency_str}] {log_type}{{"
                    f"{volume_quote:.4f}; "
                    f"Курс:{log.get('price', 0):.4f}; "
                    f"↑Δ%:{log.get('delta_percent', 0):.2f}; "
                    f"PnL:{log.get('pnl', 0):.4f}; "
                    f"Профит:{cycle_profit:.4f}}}"
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
            
        Returns:
            Статистика с информацией о циклах и их профитах (каждый цикл независим)
        
        ✅ ИСПРАВЛЕНО: Профиты циклов не суммируются, показываются отдельно для каждого цикла.

        """

        logs = self.get_logs(currency=currency)

        

        total_buys = sum(1 for log in logs if log.get('type') == 'buy')

        total_sells = sum(1 for log in logs if log.get('type') == 'sell')

        

        total_investment = sum(log.get('investment', 0) for log in logs if log.get('type') == 'buy')

        
        # ✅ ИСПРАВЛЕНО: Собираем профиты по отдельным циклам (не суммируем)
        # Профит каждого цикла хранится в поле 'total_pnl' записи sell
        cycle_profits = [log.get('total_pnl', 0) for log in logs if log.get('type') == 'sell']
        
        # Для совместимости с API можем вернуть последний профит или среднее значение
        last_cycle_profit = cycle_profits[-1] if cycle_profits else 0.0
        avg_cycle_profit = sum(cycle_profits) / len(cycle_profits) if cycle_profits else 0.0
        

        return {

            'total_entries': len(logs),

            'total_buys': total_buys,

            'total_sells': total_sells,

            'total_investment': round(total_investment, 4),

            'last_cycle_profit': round(last_cycle_profit, 4),  # ✅ Профит последнего цикла
            'avg_cycle_profit': round(avg_cycle_profit, 4),    # ✅ Средний профит цикла
            'total_cycles': len(cycle_profits),                 # ✅ Количество завершённых циклов
            'cycle_profits': [round(p, 4) for p in cycle_profits],  # ✅ Список всех профитов циклов

            'currency': currency,

            'currencies_count': len(self.logs_by_currency) if not currency else 1

        }

    

    def get_currencies_with_logs(self) -> List[str]:

        """Получить список валют, для которых есть логи"""

        with self.lock:

            return sorted(list(self.logs_by_currency.keys()))
    
    def get_session_profit(self, currency: Optional[str] = None, session_start_time: Optional[datetime] = None) -> Dict[str, float]:
        """Получить прибыль с момента старта сессии
        
        Args:
            currency: Конкретная валюта (если None - все валюты)
            session_start_time: Время старта сессии (если None - считаем все логи)
            
        Returns:
            Dict[currency, profit] - прибыль по каждой валюте
        """
        profits = {}
        
        with self.lock:
            currencies = [currency.upper()] if currency else list(self.logs_by_currency.keys())
            
            for curr in currencies:
                if curr not in self.logs_by_currency:
                    profits[curr] = 0.0
                    continue
                
                total_profit = 0.0
                
                # Проходим по всем логам валюты
                for entry in self.logs_by_currency[curr]:
                    # Учитываем только продажи
                    if entry.get('type') != 'sell':
                        continue
                    
                    # Если указано время старта сессии, фильтруем
                    if session_start_time:
                        try:
                            entry_time = datetime.fromisoformat(entry.get('timestamp', ''))
                            if entry_time < session_start_time:
                                continue
                        except:
                            continue
                    
                    # Суммируем прибыль из поля total_pnl
                    profit = entry.get('total_pnl', 0.0)
                    total_profit += profit
                
                profits[curr] = total_profit
        
        return profits





# Глобальный экземпляр логгера

_trade_logger = None





def get_trade_logger() -> TradeLogger:

    """Получить глобальный экземпляр логгера торговли"""

    global _trade_logger

    if _trade_logger is None:

        _trade_logger = TradeLogger()

    return _trade_logger

