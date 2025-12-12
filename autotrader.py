"""
Автотрейдер для mTrade с алгоритмом breakeven.

Основные функции:
- _try_start_cycle: Запуск нового торгового цикла
- _try_rebuy: Усреднение (докупка при падении)
- _try_sell: Продажа при достижении breakeven

Логика работы:
1. Старт цикла: покупка при отсутствии активного цикла
2. Усреднение: докупка при падении цены
3. Продажа: фиксация прибыли при достижении breakeven
"""

import time

import json

import os

from threading import Thread

from typing import Dict, Optional

from breakeven_calculator import calculate_breakeven_table

from trade_logger import get_trade_logger

from gate_api_client import GateAPIClient

import threading

from datetime import datetime

import math

import traceback

from balance_cache import get_balance_cache  # ОПТИМИЗАЦИЯ: кэширование балансов

from debug_panel_logger import get_debug_logger  # DEBUG PANEL логирование торговых событий

class AutoTrader:

    def __init__(self, api_client_provider, ws_manager, state_manager):

        self.api_client_provider = api_client_provider

        self.ws_manager = ws_manager

        self.state_manager = state_manager

        self.running = False

        self._thread: Optional[Thread] = None

        self._sleep_interval = 0.5  # Уменьшено для более быстрой реакции

        # ОПТИМИЗАЦИЯ: Кэш балансов (уменьшает запросы к API в 10-20 раз)
        self.balance_cache = get_balance_cache()

        # КРИТИЧЕСКАЯ ЗАЩИТА: Lock для атомарной проверки и установки cycle_start_state
        # Предотвращает race condition при множественных стартовых покупках
        self._cycle_locks: Dict[str, threading.Lock] = {}

        # Состояние по каждой базе

        # cycles[BASE] = {

        #   'active': bool,

        #   'active_step': int,

        #   'table': list[dict],

        #   'last_buy_price': float,

        #   'start_price': float,

        #   'total_invested_usd': float,

        #   'base_volume': float

        # }

        self.cycles: Dict[str, Dict] = {}

        # Кэш последних цен и флаги изменения цены по базовой валюте
        # last_prices[BASE] = float
        # price_changed[BASE] = bool (True, если с прошлого прохода цена изменилась)
        self.last_prices: Dict[str, float] = {}
        self.price_changed: Dict[str, bool] = {}

        self.logger = get_trade_logger()
        # last diagnostics per currency so UI can query last decision made by autotrader
        # Format: { 'SOL': {'decision': 'sell'|'buy'|'none'|'sell_attempt_failed', 'timestamp': 0.0, 'reason': str, 'meta': {...}} }
        self.last_diagnostics: Dict[str, Dict] = {}
        self._diag_state_file = 'autotrader_last_diagnostics.json'
        # load persisted diagnostics if available
        try:
            self._load_diagnostics_state()
        except Exception:
            # ignore load problems, start fresh
            pass

        self._pair_info_cache: Dict[str, dict] = {}

        self._cycles_state_file = 'autotrader_cycles_state.json'

        # Статистика для API

        self.stats = {

            'total_cycles': 0,

            'active_cycles': 0,

            'total_buy_orders': 0,

            'total_sell_orders': 0,

            'last_update': time.time()

        }

        # Загружаем сохранённое состояние циклов

        self._load_cycles_state()

        self._autosave_thread = threading.Thread(target=self._autosave_logs_loop, daemon=True)

        self._autosave_thread.start()

    def start(self):

        if self.running:

            return False

        self.running = True

        # Сброс флага логирования разрешений при перезапуске

        self._permissions_logged = False

        self._thread = Thread(target=self._run, daemon=True)

        self._thread.start()

        return True

    def stop(self):

        self.running = False

        return True

    # ------------------------ Сохранение/загрузка состояния ------------------------

    def _save_cycles_state(self):

        """Сохранить состояние циклов в файл."""

        try:
            # Фильтруем только активные циклы и важные данные
            state_to_save = {}

            for base, cycle in self.cycles.items():

                # Сохраняем только активные циклы
                if cycle.get('active'):

                    state_to_save[base] = {

                        'active': cycle.get('active', False),

                        'active_step': cycle.get('active_step', -1),

                        'last_buy_price': cycle.get('last_buy_price', 0.0),

                        'start_price': cycle.get('start_price', 0.0),

                        'total_invested_usd': cycle.get('total_invested_usd', 0.0),

                        'base_volume': cycle.get('base_volume', 0.0),

                        'table': cycle.get('table', []),

                        'saved_at': time.time()

                    }

            # Записываем в файл (пустой словарь, если нет активных циклов)
            with open(self._cycles_state_file, 'w', encoding='utf-8') as f:
                json.dump(state_to_save, f, indent=2)

        except Exception as e:

            pass

    

    def _load_cycles_state(self):

        """Загрузить сохранённое состояние циклов."""

        try:

            if not os.path.exists(self._cycles_state_file):

                return

            

            with open(self._cycles_state_file, 'r', encoding='utf-8') as f:

                saved_state = json.load(f)

            

            # Проверяем возраст сохранённого состояния (не старше 24 часов)

            current_time = time.time()

            restored_count = 0

            

            for base, saved_cycle in saved_state.items():

                saved_at = saved_cycle.get('saved_at', 0)

                age_hours = (current_time - saved_at) / 3600

                

                if age_hours > 24:

                    continue

                

                # ИСПРАВЛЕНИЕ: Загружаем таблицу из файла, если она есть
                saved_table = saved_cycle.get('table', [])

                self.cycles[base] = {
                    'active': saved_cycle.get('active', False),
                    'active_step': saved_cycle.get('active_step', -1),
                    'table': saved_table,  # загружаем сохраненную таблицу
                    'last_buy_price': saved_cycle.get('last_buy_price', 0.0),
                    'start_price': saved_cycle.get('start_price', 0.0),
                    'total_invested_usd': saved_cycle.get('total_invested_usd', 0.0),
                    'base_volume': saved_cycle.get('base_volume', 0.0)
                }

                # КРИТИЧЕСКИ ВАЖНО: пересчитать или загрузить таблицу для активного цикла
                if saved_cycle['active']:
                    # Если таблица уже загружена из файла и не пуста - используем её
                    if not saved_table or len(saved_table) == 0:
                        # Пересчитываем таблицу только если её нет
                        params = self.state_manager.get_breakeven_params(base)
                        price_for_table = saved_cycle['start_price'] if saved_cycle['start_price'] > 0 else saved_cycle['last_buy_price']
                        table = calculate_breakeven_table(params, price_for_table)
                        self.cycles[base]['table'] = table

                restored_count += 1

                # Проверим консистентность: если цикл помечен как active, но баланс в аккаунте
                # заметно меньше сохранённого base_volume — это несоответствие (пользователь мог перевести монеты).
                # В таком случае помечаем цикл как неактивный чтобы автоторговля могла выполнить стартовую покупку.
                try:
                    if saved_cycle.get('active') and hasattr(self, 'api_client_provider') and callable(self.api_client_provider):
                        api_client = self.api_client_provider()
                        if api_client:
                            bal = api_client.get_account_balance()
                            current_base_balance = 0.0
                            if isinstance(bal, list):
                                for item in bal:
                                    if item.get('currency','').upper() == base.upper():
                                        try:
                                            current_base_balance = float(item.get('available', 0))
                                        except Exception:
                                            current_base_balance = 0.0
                            recorded_volume = float(saved_cycle.get('base_volume', 0) or 0)
                            # Если фактический баланс меньше 80% записанного объёма — считаем неконсистентным
                            if recorded_volume > 0 and current_base_balance < recorded_volume * 0.8:
                                current_time = time.time()
                                self.cycles[base].update({
                                    'active': False,
                                    'active_step': -1,
                                    'last_buy_price': 0.0,
                                    'start_price': 0.0,
                                    'total_invested_usd': 0.0,
                                    'base_volume': 0.0,
                                    'last_sell_time': current_time,  # КРИТИЧНО: Устанавливаем метку времени
                                    'last_start_attempt': 0
                                })
                except Exception as _e:
                    pass

            

            if restored_count > 0:

                pass

        except Exception as e:

            pass

    # ------------------------ Вспомогательные методы ------------------------

    def _ensure_ws_subscription(self, base: str, quote: str):

        """Гарантировать подписку WS на пару, если менеджер доступен."""

        try:

            if self.ws_manager:

                self.ws_manager.create_connection(f"{base}_{quote}")

        except Exception:

            pass

    def _get_market_price(self, base: str, quote: str) -> Optional[float]:

        pair = f"{base}_{quote}".upper()

        # Сначала пробуем получить цену из кэша ws_manager

        if self.ws_manager:
            data = self.ws_manager.get_data(pair)
            if data:
                # Пытаемся получить из ticker
                if data.get('ticker'):
                    last = data['ticker'].get('last')
                    if last is not None:
                        try:
                            price = float(last)
                            if price > 0:
                                # обновляем last_prices/price_changed при успешном получении цены из тикера
                                self._update_last_price(base, price)
                                return price
                        except Exception as e:
                            pass
                else:
                    pass
                
                # Fallback to orderbook if ticker not available or invalid
                if data.get('orderbook') and data['orderbook'].get('asks'):
                    try:
                        price = float(data['orderbook']['asks'][0][0])
                        if price > 0:
                            # обновляем last_prices/price_changed при успешном получении цены из ордербука
                            self._update_last_price(base, price)
                            return price
                    except Exception as e:
                        pass
            else:
                pass
        else:
            pass
        # Если не удалось — только тогда делаем REST-запрос

        try:

            public_client = GateAPIClient(api_key=None, api_secret=None, network_mode='work')

            tick = public_client._request('GET', '/spot/tickers', params={'currency_pair': pair})

            if isinstance(tick, list) and tick:

                last = tick[0].get('last')

                if last is not None:

                    price = float(last)
                    if price > 0:
                        # обновляем last_prices/price_changed при успешном получении цены через REST
                        self._update_last_price(base, price)
                        return price

        except Exception as e:

            pass

        return None

    def _update_last_price(self, base: str, price: float) -> None:
        """Обновить кэш последней цены и флаг изменения."""
        try:
            base = base.upper()
            prev = self.last_prices.get(base)
            if prev is None:
                # первая цена — считаем, что изменилась, чтобы обработать сразу
                self.price_changed[base] = True
            else:
                # помечаем как изменившуюся только если действительно есть сдвиг
                if price != prev:
                    self.price_changed[base] = True
            self.last_prices[base] = price
        except Exception:
            pass

    def _get_orderbook(self, base: str, quote: str) -> Optional[dict]:
        pair = f"{base}_{quote}".upper()
        # Получаем стакан из ws_manager
        if self.ws_manager:
            data = self.ws_manager.get_data(pair)
            if data and data.get('orderbook'):
                return data['orderbook']
            else:
                # Если данных нет, подождём до 5 секунд, проверяя каждые 0.1 сек
                import time
                start_time = time.time()
                while time.time() - start_time < 5.0:
                    time.sleep(0.1)
                    data = self.ws_manager.get_data(pair)
                    if data and data.get('orderbook'):
                        return data['orderbook']
        return None

    def _recalc_table_if_needed(self, base: str, quote: str, current_price: float):

        params = self.state_manager.get_breakeven_params(base)

        cycle = self.cycles.get(base, {})

        

        # КРИТИЧЕСКИ ВАЖНО: Используем зафиксированный start_price из state_manager, если он есть

        # Это гарантирует, что P0 в таблице будет соответствовать цене первой покупки

        saved_start_price = params.get('start_price', 0)

        

        # Если start_price уже зафиксирован (есть активный или завершённый цикл), используем его

        # Если start_price = 0 (нет активного цикла), используем текущую рыночную цену для превью

        

        price_for_table = current_price if not cycle.get('active') else (saved_start_price if saved_start_price > 0 else current_price)

        

        # Для неактивных циклов всегда пересчитываем таблицу с текущей ценой

        if not cycle.get('active'):

            table = calculate_breakeven_table(params, price_for_table)

            cycle['table'] = table

            # Устанавливаем start_price в цикле только если его там нет

            if not cycle.get('start_price') or cycle.get('start_price') == 0:

                cycle['start_price'] = table[0]['rate']

            self.cycles[base] = cycle

            return

        

        # Пересчёт таблицы если её нет

        if not cycle.get('table'):

            table = calculate_breakeven_table(params, price_for_table)

            cycle['table'] = table

            # Устанавливаем start_price в цикле только если его там нет

            if not cycle.get('start_price') or cycle.get('start_price') == 0:

                cycle['start_price'] = table[0]['rate']

            self.cycles[base] = cycle

    def _ensure_cycle_struct(self, base: str):

        self.cycles.setdefault(base, {

            'active': False,

            'active_step': -1,

            'table': [],

            'last_buy_price': 0.0,

            'start_price': 0.0,

            'total_invested_usd': 0.0,

            'base_volume': 0.0,

            'last_start_attempt': 0,  # время последней попытки старта

            'cycle_activated_at': 0,   # время активации цикла

            'cycle_start_state': 0,  # 0=нет цикла, 1=покупка в процессе, 2=цикл активен

            'start_buy_result': None,  # Результат стартовой покупки (None/success/error)

            'start_buy_thread': None   # Поток стартовой покупки

        })

    def _place_limit_order_all_or_nothing(self, side: str, base: str, quote: str, amount_base: float, limit_price: float):
        # TIMING: Начало размещения ордера
        t_order_start = time.time()

        api_client = self.api_client_provider()

        currency_pair = f"{base}_{quote}".upper()

        if not api_client:

            # SIMULATION: считаем исполнено полностью

            return {'success': True, 'filled': amount_base, 'simulated': True}

        pi = self._get_pair_info(base, quote)
        try:
            amt_prec = int(pi.get('amount_precision', 8))
        except Exception:
            amt_prec = 8
        try:
            price_prec = int(pi.get('price_precision', 8))
        except Exception:
            price_prec = 8
        
        t_before_api = time.time()

        # Только FOK — не делаем fallback на IOC (чтобы избежать частичных исполнений как финального состояния)
        try:
            result_fok = api_client.create_spot_order(
                currency_pair=currency_pair,
                side=side,
                amount=f"{amount_base:.{amt_prec}f}",
                price=f"{limit_price:.{price_prec}f}",
                order_type='limit',
                time_in_force='fok'
            )
            t_after_api = time.time()
            api_duration_ms = (t_after_api - t_before_api) * 1000

            filled = self._parse_filled_amount(result_fok)

            if filled >= amount_base * 0.999:
                total_duration_ms = (t_after_api - t_order_start) * 1000
                return {'success': True, 'filled': filled, 'order': result_fok, 'tif': 'fok', 'timing': {'api_ms': api_duration_ms, 'total_ms': total_duration_ms}}
            else:
                # Не принимаем частичное исполнение как окончательное — вернём информацию о заполнении
                return {'success': False, 'filled': filled, 'order': result_fok, 'tif': 'fok_partial', 'timing': {'api_ms': api_duration_ms}}

        except Exception as e:
            t_error = time.time()
            error_duration_ms = (t_error - t_before_api) * 1000
            return {'success': False, 'filled': 0.0, 'error': str(e), 'timing': {'api_ms': error_duration_ms}}

    def _parse_filled_amount(self, order_result: dict) -> float:

        if not isinstance(order_result, dict):

            return 0.0

        try:

            order_type = order_result.get('type', '')

            if order_type == 'market':

                # For market orders, use filled_amount (base amount for both buy and sell)

                return float(order_result.get('filled_amount', 0))

            else:

                # For limit orders, amount - left

                amount = float(order_result.get('amount', 0))

                left = float(order_result.get('left', 0))

                filled = amount - left if amount > 0 else float(order_result.get('filled_total', 0))

                if filled < 0:

                    filled = 0.0

                return filled

        except Exception:

            return 0.0

    def _get_account_balance(self, currency: str, force_refresh: bool = False) -> float:
        """
        Получить баланс для указанной валюты (с кэшированием).
        
        ОПТИМИЗАЦИЯ: Используется кэш балансов (TTL=5сек).
        Это уменьшает количество API запросов в 10-20 раз!
        """
        try:
            api_client = self.api_client_provider()
            if not api_client:
                return 0.0
            
            # Устанавливаем API клиент в кэш (если ещё не установлен)
            if self.balance_cache.api_client is None:
                self.balance_cache.set_api_client(api_client)
            
            # Получаем баланс из кэша (один запрос для всех валют!)
            balance = self.balance_cache.get_balance(currency, force_refresh=force_refresh)
            
            # Если кэш вернул None (ошибка), пробуем напрямую
            if balance is None:
                balance_list = api_client.get_account_balance()
                if isinstance(balance_list, list):
                    for item in balance_list:
                        if item.get('currency', '').upper() == currency.upper():
                            return float(item.get('available', 0) or 0)
                return 0.0
            
            return balance
            
        except Exception as e:
            print(f"[AutoTrader] Ошибка получения баланса {currency}: {e}")
            return 0.0

    def _get_pair_info(self, base: str, quote: str) -> dict:
        """Получить min_quote_amount/min_base_amount/precision (кешируется)."""

        pair = f"{base}_{quote}".upper()

        if pair in self._pair_info_cache:

            return self._pair_info_cache[pair]

        info = {"min_quote_amount": 0.0, "min_base_amount": 0.0, "amount_precision": 8, "price_precision": 8}

        try:

            public = GateAPIClient(api_key=None, api_secret=None, network_mode='work')

            raw = public.get_currency_pair_details_exact(pair)

            if isinstance(raw, dict) and str(raw.get('id','')).upper() == pair:

                info["min_quote_amount"] = float(raw.get('min_quote_amount') or 0)
                info["min_base_amount"] = float(raw.get('min_base_amount') or 0)
                try:
                    info['amount_precision'] = int(raw.get('amount_precision', info['amount_precision']))
                except Exception:
                    pass
                try:
                    info['price_precision'] = int(raw.get('precision', info['price_precision']))
                except Exception:
                    pass

            else:

                # fallback через список

                lst = public.get_currency_pair_details(pair)

                if isinstance(lst, list):

                    for it in lst:

                        if str(it.get('id','')).upper() == pair:

                            info["min_quote_amount"] = float(it.get('min_quote_amount') or 0)
                            info["min_base_amount"] = float(it.get('min_base_amount') or 0)
                            try:
                                info['amount_precision'] = int(it.get('amount_precision', info['amount_precision']))
                            except Exception:
                                pass
                            try:
                                info['price_precision'] = int(it.get('precision', info['price_precision']))
                            except Exception:
                                pass

                            break

        except Exception:

            pass

        self._pair_info_cache[pair] = info

        return info

    # ------------------------ diagnostics persistence ------------------------
    def _save_diagnostics_state(self):
        try:
            with open(self._diag_state_file, 'w', encoding='utf-8') as f:
                json.dump(self.last_diagnostics, f, ensure_ascii=False, indent=2)
        except Exception as e:
            pass

    def _load_diagnostics_state(self):
        if not os.path.exists(self._diag_state_file):
            return
        try:
            with open(self._diag_state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self.last_diagnostics = data
        except Exception as e:
            pass

    def _set_last_diagnostic(self, base: str, payload: dict):
        """Store diagnostics in structured format and persist.

        Structure stored per base:
        {
          'last_detected': { 'sell': {...}, 'buy': {...} },
          'last_decision': {...}
        }
        If payload['decision'] ends with '_detected' it's stored in last_detected.<kind>.
        Otherwise stored as last_decision.
        """
        try:
            base = base.upper()

            entry = self.last_diagnostics.get(base, {})
            # ensure keys
            if 'last_detected' not in entry or not isinstance(entry['last_detected'], dict):
                entry['last_detected'] = {}

            decision = (payload.get('decision') or '').lower()
            if decision.endswith('_detected'):
                # sell_detected / buy_detected
                if decision.startswith('sell'):
                    entry['last_detected']['sell'] = payload
                elif decision.startswith('buy'):
                    entry['last_detected']['buy'] = payload
                else:
                    # unknown detected type - store under raw name
                    entry['last_detected'][decision] = payload
            else:
                # store last overall diagnostic decision
                entry['last_decision'] = payload

            self.last_diagnostics[base] = entry

            # save persistently
            try:
                self._save_diagnostics_state()
            except Exception:
                pass
        except Exception:
            pass

    # ------------------------ Логика цикла ------------------------

    def _try_start_cycle(self, base: str, quote: str):
        """
        DEPRECATED: Этот метод больше НЕ используется!
        
        Стартовая покупка теперь выполняется АВТОМАТИЧЕСКИ через главный цикл (_run).
        Ручной вызов этого метода игнорируется, чтобы избежать дублирующих покупок.
        
        Если нужна ручная покупка, используйте кнопку Quick Trade в веб-интерфейсе.
        """
        print(f"[DEPRECATED][{base}] _try_start_cycle вызван и ПРОИГНОРИРОВАН (используется async логика в главном цикле)")
        # Ничего не делаем - async логика работает в главном цикле
        pass

    def _try_start_cycle_impl(self, base: str, quote: str):
        """
        DEPRECATED: Этот метод больше не используется!
        Вся логика перенесена в _execute_start_buy() для async выполнения.
        """
        print(f"[DEPRECATED][{base}] _try_start_cycle_impl вызван (этот метод устарел!)")
        # Ничего не делаем - вся логика в _execute_start_buy()
        pass

    def try_start_cycle_sync(self, base: str, quote: str, timeout: float = 10.0) -> bool:
        """
        Безопасный синхронный метод для запуска стартовой покупки из внешних обработчиков.
        
        Этот метод:
        1. Проверяет, что цикл ещё не активен
        2. Запускает async покупку (если нужно)
        3. Ждёт завершения покупки с таймаутом
        4. Возвращает True если покупка успешна, False иначе
        
        Args:
            base: Базовая валюта (например, 'BTC')
            quote: Котируемая валюта (например, 'USDT')
            timeout: Максимальное время ожидания завершения покупки (секунды)
            
        Returns:
            True если покупка завершена успешно, False иначе
        """
        base = base.upper()
        lock = self._get_cycle_lock(base)
        
        # Проверяем текущее состояние под Lock'ом
        with lock:
            state = self._cycle_start_state.get(base, 0)
            cycle = self.cycles.get(base, {})
            
            # Если цикл уже активен или покупка в процессе, ничего не делаем
            if state != 0:
                print(f"[SYNC_START][{base}] Цикл уже в процессе/активен (state={state})")
                return state == 2  # Возвращаем True если цикл активен
            
            # Проверяем, что цикл действительно не активен
            if cycle.get('active'):
                print(f"[SYNC_START][{base}] Цикл уже активен")
                return True
            
            # Запускаем async покупку
            print(f"[SYNC_START][{base}] Запускаем стартовую покупку...")
            self._cycle_start_state[base] = 1
            cycle['start_buy_result'] = None
            cycle['start_buy_thread'] = None
            
            # Запускаем worker в отдельном потоке
            import threading
            thread = threading.Thread(
                target=self._start_buy_worker,
                args=(base, quote),
                daemon=True,
                name=f"StartBuy-{base}-sync"
            )
            cycle['start_buy_thread'] = thread
            thread.start()
        
        # Ждём завершения покупки вне Lock'а
        import time
        start_time = time.time()
        while time.time() - start_time < timeout:
            with lock:
                result = cycle.get('start_buy_result')
                if result is not None:
                    # Покупка завершена
                    success = result.get('success', False)
                    if success:
                        print(f"[SYNC_START][{base}] Покупка успешно завершена")
                        return True
                    else:
                        error = result.get('error', 'unknown')
                        print(f"[SYNC_START][{base}] Покупка завершена с ошибкой: {error}")
                        return False
            
            # Спим перед следующей проверкой
            time.sleep(0.1)
        
        # Таймаут
        print(f"[SYNC_START][{base}] Таймаут ожидания завершения покупки ({timeout}s)")
        return False

    def _try_rebuy(self, base: str, quote: str):

        cycle = self.cycles.get(base)

        if not cycle or not cycle.get('active'):
            reason = "Цикл неактивен или отсутствует"
            try:
                price = self._get_market_price(base, quote)
                self.logger.log_buy_diagnostics(base, price, 0.0, 0.0, -1, 'None', None, reason)
            except Exception:
                pass
            return

        table = cycle.get('table') or []
        if not table:
            return

        # Получение цены ticker (для информации)
        price = self._get_market_price(base, quote)
        if not price or price <= 0:
            return

        saved_step = cycle['active_step']
        next_step = saved_step + 1
        
        if next_step >= len(table):
            reason = f"Нет следующего шага в таблице (next_step={next_step}, steps={len(table)})"
            try:
                self.logger.log_buy_diagnostics(base, price, 0.0, 0.0, saved_step, str(cycle.get('active')), cycle.get('last_buy_price', None), reason)
            except Exception:
                pass
            return

        last_buy = cycle['last_buy_price']
        if last_buy <= 0:
            reason = "last_buy_price <= 0"
            try:
                self.logger.log_buy_diagnostics(base, price, 0.0, 0.0, saved_step, str(cycle.get('active')), cycle.get('last_buy_price', None), reason)
            except Exception:
                pass
            return

        params_row = table[next_step]
        start_price = cycle.get('start_price', 0)

        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Сначала получаем orderbook и level_price
        # Затем проверяем условие cumulative падения по РЕАЛЬНОЙ цене покупки

        # ШАГ 1: Получаем orderbook
        orderbook = self._get_orderbook(base, quote)

        if not orderbook:
            reason = "Нет данных orderbook для проверки ликвидности"
            try:
                self.logger.log_buy_diagnostics(base, price, level_param, 0.0, saved_step, str(cycle.get('active')), cycle.get('last_buy_price', None), reason)
            except Exception:
                pass
            return

        # orderbook_level supports both absolute index (>=1) and fractional part (0<x<1)
        raw_level = self.state_manager.get_breakeven_params(base).get('orderbook_level', 1)
        try:
            level_param = float(raw_level)
        except Exception:
            level_param = 1.0

        asks = orderbook.get('asks') or []

        # Compute actual index for asks (support fractional orderbook_level as fraction of depth)
        if level_param >= 1:
            level = int(level_param)
        else:
            level = max(1, int(math.ceil(len(asks) * level_param))) if len(asks) > 0 else 1

        if len(asks) < level:
            reason = f"Требуемый уровень asks ({level}) глубже, чем доступно ({len(asks)}), уменьшаем до доступной глубины"
            try:
                self.logger.log_buy_diagnostics(base, price, level_param, 0.0, saved_step, str(cycle.get('active')), cycle.get('last_buy_price', None), reason)
            except Exception:
                pass
            level = max(1, len(asks))

        level_price, level_amount = 0.0, 0.0

        try:
            # asks: [[price, amount], ...]
            level_price = float(asks[level - 1][0])
            level_amount = float(asks[level - 1][1])
        except Exception:
            reason = "Ошибка чтения уровня asks из orderbook"
            try:
                self.logger.log_buy_diagnostics(base, price, level_param, 0.0, saved_step, str(cycle.get('active')), cycle.get('last_buy_price', None), reason)
            except Exception:
                pass
            return

        # Проверяем условие докупки: цена должна упасть ниже порога
        # Получаем порог падения из таблицы для следующего шага
        # ВАЖНО: используем cumulative_decrease_pct, а не decrease_pct!
        required_drop_pct = abs(float(params_row.get('cumulative_decrease_pct', 0)))
        
        # Проверяем cumulative падение (от start_price)
        if start_price > 0:
            cumulative_drop_pct = ((start_price - level_price) / start_price) * 100.0
        else:
            cumulative_drop_pct = 0.0
        
        # Проверяем stepwise падение (от last_buy_price)
        if last_buy > 0:
            stepwise_drop_pct = ((last_buy - level_price) / last_buy) * 100.0
        else:
            stepwise_drop_pct = 0.0
        
        # ДИАГНОСТИКА: Выводим все значения для проверки
        print(f"[REBUY_CHECK][{base}] Проверка условия докупки для шага {next_step}:")
        print(f"[REBUY_CHECK][{base}]   start_price={start_price:.8f}, last_buy={last_buy:.8f}")
        print(f"[REBUY_CHECK][{base}]   level_price={level_price:.8f} (уровень {level} в orderbook)")
        print(f"[REBUY_CHECK][{base}]   cumulative_drop={cumulative_drop_pct:.4f}%, required_drop={required_drop_pct:.4f}%")
        print(f"[REBUY_CHECK][{base}]   stepwise_drop={stepwise_drop_pct:.4f}%")
        
        # Условие докупки: cumulative падение >= требуемого порога
        if cumulative_drop_pct < required_drop_pct:
            reason = f"Недостаточное падение: cumulative={cumulative_drop_pct:.2f}% < требуется={required_drop_pct:.2f}%"
            print(f"[REBUY_CHECK][{base}] ❌ ОТКАЗ: {reason}")
            try:
                self.logger.log_buy_diagnostics(base, price, level_price, cumulative_drop_pct, saved_step, str(cycle.get('active')), cycle.get('last_buy_price', None), reason)
            except Exception:
                pass
            return
        
        print(f"[REBUY_CHECK][{base}] ✅ УСЛОВИЕ ВЫПОЛНЕНО: cumulative_drop ({cumulative_drop_pct:.2f}%) >= required ({required_drop_pct:.2f}%)")
        
        # Условие выполнено - выполняем докупку
        purchase_usd = float(params_row.get('purchase_usd', 0))
        
        if purchase_usd <= 0:
            reason = f"Некорректная сумма докупки: {purchase_usd}"
            try:
                self.logger.log_buy_diagnostics(base, price, level_price, cumulative_drop_pct, saved_step, str(cycle.get('active')), cycle.get('last_buy_price', None), reason)
            except Exception:
                pass
            return
        
        # Рассчитываем объём для докупки
        amount_to_buy = purchase_usd / level_price if level_price > 0 else 0
        
        # Проверяем минимальные требования пары
        pair_info = self._get_pair_info(base, quote)
        min_base = float(pair_info.get('min_base_amount', 0))
        
        if amount_to_buy < min_base:
            amount_to_buy = min_base
            purchase_usd = amount_to_buy * level_price
        
        # Проверяем достаточность ликвидности на уровне
        if level_amount < amount_to_buy:
            reason = f"Недостаточная ликвидность на уровне {level}: доступно={level_amount:.8f}, требуется={amount_to_buy:.8f}"
            try:
                self.logger.log_buy_diagnostics(base, price, level_price, cumulative_drop_pct, saved_step, str(cycle.get('active')), cycle.get('last_buy_price', None), reason)
            except Exception:
                pass
            return
        
        # Выполняем ордер на докупку
        order_res = self._place_limit_order_all_or_nothing('buy', base, quote, amount_to_buy, level_price)
        
        if order_res.get('success'):
            filled = order_res['filled']
            invest = filled * level_price
            
            # ОПТИМИЗАЦИЯ: Инвалидируем кэш балансов после успешной покупки
            self.balance_cache.invalidate(reason=f"rebuy_{base}_step{next_step}")
            
            # Обновляем состояние цикла
            cycle['active_step'] = next_step
            cycle['last_buy_price'] = level_price
            cycle['total_invested_usd'] = float(cycle.get('total_invested_usd', 0)) + invest
            cycle['base_volume'] = float(cycle.get('base_volume', 0)) + filled
            
            self.cycles[base] = cycle
            self._save_cycles_state()
            
            # Логируем докупку
            self.logger.log_buy(base, filled, level_price, stepwise_drop_pct, cumulative_drop_pct, invest)
            
            # Обновляем статистику
            self.stats['total_buy_orders'] += 1
            self.stats['last_update'] = time.time()
            
            print(f"[REBUY][{base}] ✅ Докупка выполнена: step={next_step}, filled={filled:.8f}, price={level_price:.8f}, invested={invest:.4f}")
        else:
            reason = f"Не удалось выполнить докупку: {order_res.get('error', 'unknown')}"
            try:
                self.logger.log_buy_diagnostics(base, price, level_price, cumulative_drop_pct, saved_step, str(cycle.get('active')), cycle.get('last_buy_price', None), reason)
            except Exception:
                pass

    def _try_sell(self, base: str, quote: str):
        """
        Попытка продажи при достижении breakeven.
        
        Условия:
        - Цикл активен (active == True)
        - Цена выросла на требуемый процент (>= breakeven_pct)
        
        Действия:
        - Получить цену из orderbook (bids)
        - Продать весь объём base_volume
        - Закрыть цикл (active=False)
        - Залогировать продажу
        """
        
        # 1. Проверка цикла
        cycle = self.cycles.get(base)
        if not cycle or not cycle.get('active'):
            return
        
        # 2. Получение цены
        price = self._get_market_price(base, quote)
        if not price or price <= 0:
            return
        
        # 3. Получение параметров активного шага
        table = cycle.get('table', [])
        active_step = cycle.get('active_step', -1)
        
        if active_step < 0 or active_step >= len(table):
            return
        
        params_row = table[active_step]
        required_growth_pct = float(params_row.get('breakeven_pct', 0))
        
        # 4. Расчёт роста от start_price
        start_price = cycle.get('start_price', 0)
        if start_price <= 0:
            return
        
        current_growth_pct = ((price - start_price) / start_price) * 100.0
        
        # 5. Проверка условия продажи
        if current_growth_pct < required_growth_pct:
            # Недостаточный рост для продажи
            return
        
        print(f"[SELL_CHECK][{base}] ✅ Условие продажи выполнено:")
        print(f"[SELL_CHECK][{base}]   start_price={start_price:.8f}")
        print(f"[SELL_CHECK][{base}]   current_price={price:.8f}")
        print(f"[SELL_CHECK][{base}]   current_growth={current_growth_pct:.4f}% >= required={required_growth_pct:.4f}%")
        
        # 6. Получение цены продажи из orderbook
        orderbook = self._get_orderbook(base, quote)
        if not orderbook:
            print(f"[AutoTrader][{base}] ⚠️ Нет данных orderbook для продажи")
            return
        
        # Получение sell_level из параметров (по умолчанию 1)
        params = self.state_manager.get_breakeven_params(base)
        raw_level = params.get('orderbook_level', 1)
        try:
            level_param = float(raw_level)
        except Exception:
            level_param = 1.0
        
        bids = orderbook.get('bids', [])
        
        # Compute actual index for bids (support fractional orderbook_level)
        if level_param >= 1:
            sell_level = int(level_param)
        else:
            sell_level = max(1, int(math.ceil(len(bids) * level_param))) if len(bids) > 0 else 1
        
        if len(bids) < sell_level:
            print(f"[AutoTrader][{base}] ⚠️ Требуемый уровень bids ({sell_level}) глубже доступного ({len(bids)})")
            sell_level = max(1, len(bids))
        
        if sell_level < 1:
            print(f"[AutoTrader][{base}] ⚠️ Нет bids в orderbook")
            return
        
        try:
            exec_price = float(bids[sell_level - 1][0])
            bid_amount = float(bids[sell_level - 1][1])
        except Exception as e:
            print(f"[AutoTrader][{base}] ⚠️ Ошибка чтения уровня bids: {e}")
            return
        
        # 8. Расчёт объёма продажи
        sell_volume = cycle.get('base_volume', 0)
        if sell_volume <= 0:
            print(f"[AutoTrader][{base}] ⚠️ Нечего продавать: base_volume={sell_volume}")
            return
        
        # Проверка ликвидности на уровне
        if bid_amount < sell_volume:
            print(f"[AutoTrader][{base}] ⚠️ Недостаточная ликвидность на уровне {sell_level}: доступно={bid_amount:.8f}, требуется={sell_volume:.8f}")
            # Можно попробовать продать доступный объём или вернуться
            # Для безопасности пока пропускаем
            return
        
        # 9. Выполнение ордера на продажу
        print(f"[AutoTrader][{base}] 💰 Попытка продажи: volume={sell_volume:.8f}, price={exec_price:.8f}")
        
        order_res = self._place_limit_order_all_or_nothing('sell', base, quote, sell_volume, exec_price)
        
        filled = float(order_res.get('filled', 0))
        
        if order_res.get('success') and filled >= sell_volume * 0.999:
            # ПОЛНАЯ ПРОДАЖА
            
            # Инвалидация кэша балансов
            self.balance_cache.invalidate(reason=f"sell_{base}")
            
            # Расчёт PnL
            avg_invest_price = cycle['total_invested_usd'] / cycle['base_volume']
            actual_exec_price = float(order_res.get('avg_deal_price', exec_price))
            pnl = (actual_exec_price - avg_invest_price) * filled
            
            # Логирование
            self.logger.log_sell(base, filled, actual_exec_price, current_growth_pct, pnl)
            
            # Закрытие цикла
            current_time = time.time()
            self.cycles[base] = {
                'active': False,
                'active_step': -1,
                'table': table,
                'last_buy_price': 0.0,
                'start_price': 0.0,
                'total_invested_usd': 0.0,
                'base_volume': 0.0,
                'last_sell_time': current_time,
                'cycle_start_state': 0  # 0 = НЕТ ЦИКЛА (можно начинать новый)
            }
            
            # ====== КРИТИЧНО: НЕМЕДЛЕННОЕ СОХРАНЕНИЕ ======
            # Сохраняем СРАЗУ после установки cycle_start_state=0
            # чтобы другие итерации увидели это изменение!
            self._save_cycles_state()
            
            print(f"[{base}] 🔓 cycle_start_state=0 СОХРАНЕНО (цикл закрыт, можно начинать новый)")
            
            # Обнуление start_price в state_manager (может быть медленным - не критично)
            try:
                current_params = self.state_manager.get_breakeven_params(base)
                current_params['start_price'] = 0.0
                self.state_manager.set_breakeven_params(base, current_params)
            except Exception:
                pass
            
            # Сохранение УЖЕ выполнено выше!
            # self._save_cycles_state()  ← УБРАНО ДУБЛИРОВАНИЕ
            
            # Статистика
            self.stats['total_sell_orders'] += 1
            self.stats['last_update'] = time.time()
            
            print(f"[AutoTrader][{base}] ✅ Продажа выполнена: filled={filled:.8f}, price={actual_exec_price:.8f}, PnL={pnl:.4f} USDT")
            print(f"[AutoTrader][{base}] 🎉 Цикл завершён, прибыль зафиксирована")
        
        else:
            # НЕУДАЧА ПРОДАЖИ: FOK не сработал
            # С FOK ордерами частичное исполнение невозможно
            error_info = order_res.get('error', 'FOK failed')
            filled_amt = float(order_res.get('filled', 0.0) or 0.0)
            
            if filled_amt > 0:
                print(f"[WARNING][{base}] Частичное исполнение FOK ордера продажи (filled={filled_amt:.8f})! Это не должно происходить!")
            
            print(f"[{base}] Продажа не удалась: {error_info}")

    def _autosave_logs_loop(self):
        """Поток для автосохранения логов каждые 60 секунд."""
        while True:
            time.sleep(60)
            try:
                self.logger.save()
            except Exception:
                pass

    def _determine_step_from_price_drop(self, base: str, cumulative_drop_pct: float) -> int:
        """
        Определяет номер шага на основе кумулятивного падения цены.
        Используется для восстановления состояния цикла при перезапуске.
        """
        cycle = self.cycles.get(base, {})
        table = cycle.get('table', [])
        if not table:
            return -1
        
        # Проходим по таблице и находим последний шаг, для которого выполнено условие падения
        determined_step = -1
        for i, row in enumerate(table):
            required_drop = abs(row.get('cumulative_decrease_pct', 0))
            if cumulative_drop_pct >= required_drop:
                determined_step = i
            else:
                break
        
        return determined_step

    def _run(self):

        quote = self.state_manager.get_active_quote_currency()

        

        # Проверка API клиента при первом запуске

        if not hasattr(self, '_api_checked'):

            api_client = self.api_client_provider()

            self._api_checked = True

        

        while self.running:

            try:

                if not self.state_manager.get_auto_trade_enabled():

                    time.sleep(self._sleep_interval)

                    continue

                perms = self.state_manager.get_trading_permissions()

                if not hasattr(self, '_permissions_logged') or not self._permissions_logged:
                    self._permissions_logged = True

                if not perms:

                    time.sleep(self._sleep_interval)

                    continue

                # Получаем список валют для торговли (только с разрешением True)

                for base in perms:

                    # КРИТИЧНО: Проверяем, что торговля для этой валюты разрешена
                    if not perms.get(base, False):
                        continue

                    try:

                        # Проверка наличия данных WS

                        self._ensure_ws_subscription(base, quote)

                        # Получить цену рынка

                        price = self._get_market_price(base, quote)

                        if not price or price <= 0:

                            continue

                        # ====== КРИТИЧЕСКАЯ ЗАЩИТА: ПРОСТАЯ СИНХРОННАЯ ЛОГИКА ======
                        # ПРОСТОТА = НАДЁЖНОСТЬ!
                        # Проверяем и покупаем ВСЁ СИНХРОННО под одним Lock
                        if base not in self._cycle_locks:
                            self._cycle_locks[base] = threading.Lock()
                        
                        with self._cycle_locks[base]:
                            self._ensure_cycle_struct(base)
                            cycle = self.cycles.get(base, {})
                            
                            if cycle.get('active'):
                                # Цикл АКТИВЕН → торгуем
                                self._try_sell(base, quote)
                                self._try_rebuy(base, quote)
                            else:
                                # Цикл НЕ АКТИВЕН → проверяем, нужна ли стартовая покупка
                                self._try_start_buy_simple(base, quote)

                    except Exception:

                        pass

            except Exception:

                pass

            time.sleep(self._sleep_interval)

    def _determine_active_step_by_cumulative_drop(self, base: str, current_price: float) -> int:
        """
        Определяет активный шаг на основе кумулятивного падения цены.
        Используется для восстановления состояния цикла.
        """
        cycle = self.cycles.get(base, {})
        start_price = cycle.get('start_price', 0)
        if not start_price or start_price <= 0:
            return -1
        
        table = cycle.get('table', [])
        if not table:
            return -1
        
        # Вычисляем кумулятивное падение от стартовой цены
        cumulative_drop = ((start_price - current_price) / start_price) * 100
        
        # Находим последний шаг, для которого выполнено условие
        active_step = -1
        for i, row in enumerate(table):
            required_drop = abs(row.get('cumulative_decrease_pct', 0))
            if cumulative_drop >= required_drop:
                active_step = i
            else:
                break
        
        return active_step

    def _start_cycle_async(self, base: str, quote: str):
        """
        АСИНХРОННЫЙ запуск стартовой покупки.
        
        Устанавливает флаг cycle_start_state=1 и запускает покупку в отдельном потоке.
        Lock освобождается сразу, не блокируя главный цикл.
        """
        perms = self.state_manager.get_trading_permissions()
        if not perms or not perms.get(base, False):
            return
        
        self._ensure_cycle_struct(base)
        cycle = self.cycles.get(base, {})
        
        # Дополнительная защита
        if cycle.get('cycle_start_state', 0) != 0:
            return
        
        print(f"[START_ASYNC][{base}] ✅ Запускаем стартовую покупку в фоновом потоке")
        
        # ====== УСТАНОВКА ФЛАГА ПЕРЕД ЗАПУСКОМ ПОТОКА ======
        cycle['cycle_start_state'] = 1  # ПОКУПКА В ПРОЦЕССЕ
        cycle['last_start_attempt'] = time.time()
        cycle['start_buy_result'] = None  # Сбрасываем результат
        self.cycles[base] = cycle
        self._save_cycles_state()
        
        print(f"[START_ASYNC][{base}] 🔒 cycle_start_state=1 УСТАНОВЛЕН И СОХРАНЁН")
        
        # Запускаем покупку в отдельном потоке
        thread = threading.Thread(
            target=self._start_buy_worker,
            args=(base, quote),
            daemon=True,
            name=f"StartBuy-{base}"
        )
        cycle['start_buy_thread'] = thread
        thread.start()
        
        print(f"[START_ASYNC][{base}] 🚀 Поток стартовой покупки запущен (Lock освобождён)")
    
    def _start_buy_worker(self, base: str, quote: str):
        """
        WORKER для выполнения стартовой покупки в отдельном потоке.
        
        Записывает результат в cycle['start_buy_result']:
        - {'status': 'success', 'filled': ..., 'price': ..., ...}
        - {'status': 'error', 'error': ...}
        """
        try:
            print(f"[WORKER][{base}] 🔄 Начинаем выполнение стартовой покупки...")
            
            # Выполняем покупку (весь код из _try_start_cycle_impl)
            result = self._execute_start_buy(base, quote)
            
            # Сохраняем результат
            cycle = self.cycles.get(base, {})
            cycle['start_buy_result'] = result
            self.cycles[base] = cycle
            
            print(f"[WORKER][{base}] ✅ Результат записан: {result.get('status')}")
            
        except Exception as e:
            print(f"[WORKER][{base}] ❌ Исключение в worker: {e}")
            import traceback
            traceback.print_exc()
            
            # Записываем ошибку
            cycle = self.cycles.get(base, {})
            cycle['start_buy_result'] = {'status': 'error', 'error': str(e)}
            self.cycles[base] = cycle
    
    def _check_start_buy_result(self, base: str, quote: str):
        """
        Проверка результата стартовой покупки из фонового потока.
        
        Вызывается каждую итерацию, пока cycle_start_state=1:
        - Если result=None → покупка ещё идёт, пропускаем
        - Если result={'status': 'error'} → сбрасываем флаг в 0 (повтор)
        - Если result={'status': 'success'} → активируем цикл (=2)
        """
        cycle = self.cycles.get(base, {})
        result = cycle.get('start_buy_result')
        
        if result is None:
            # Покупка ещё не завершилась
            elapsed = time.time() - cycle.get('last_start_attempt', 0)
            if elapsed > 30:
                # Таймаут - сбрасываем
                print(f"[CHECK][{base}] ⏰ Таймаут стартовой покупки ({elapsed:.1f}s), сбрасываем флаг")
                cycle['cycle_start_state'] = 0
                cycle['start_buy_result'] = None
                self.cycles[base] = cycle
                self._save_cycles_state()
            return
        
        status = result.get('status')
        
        if status == 'error':
            # ОШИБКА: Сбрасываем флаг для повторной попытки
            error = result.get('error', 'unknown')
            print(f"[CHECK][{base}] ❌ Ошибка покупки: {error}, сбрасываем флаг")
            
            cycle['cycle_start_state'] = 0
            cycle['start_buy_result'] = None
            self.cycles[base] = cycle
            self._save_cycles_state()
            
        elif status == 'success':
            # УСПЕХ: Активируем цикл
            print(f"[CHECK][{base}] ✅ Покупка завершена, активируем цикл")
            
            filled = result.get('filled', 0)
            price = result.get('price', 0)
            invested = result.get('invested', 0)
            
            # Активируем цикл (код из _try_start_cycle_impl)
            cycle.update({
                'active': True,
                'active_step': 0,
                'last_buy_price': price,
                'start_price': price,
                'total_invested_usd': invested,
                'base_volume': filled,
                'cycle_activated_at': time.time(),
                'last_sell_time': 0,
                'just_started': True,
                'cycle_start_state': 2,  # ЦИКЛ АКТИВЕН
                'start_buy_result': None  # Очищаем результат
            })
            
            self.cycles[base] = cycle
            self._save_cycles_state()
            
            # Обновление state_manager и таблицы
            try:
                current_params = self.state_manager.get_breakeven_params(base)
                current_params['start_price'] = price
                self.state_manager.set_breakeven_params(base, current_params)
                new_table = calculate_breakeven_table(current_params, price)
                cycle['table'] = new_table
            except Exception:
                pass
            
            # Логирование
            self.logger.log_buy(base, filled, price, 0.0, 0.0, invested)
            self.stats['total_buy_orders'] += 1
            self.stats['total_cycles'] += 1
            self.stats['last_update'] = time.time()
            
            # Инвалидация кэша
            self.balance_cache.invalidate(reason=f"start_buy_buy_{base}")
            
            print(f"[CHECK][{base}] 🎯 Цикл активирован: price={price:.8f}, volume={filled:.8f}")

    def _execute_start_buy(self, base: str, quote: str) -> dict:
        """
        ИСПОЛНЕНИЕ стартовой покупки (вызывается из worker-потока).
        
        Возвращает:
        - {'status': 'success', 'filled': ..., 'price': ..., 'invested': ...}
        - {'status': 'error', 'error': ...}
        """
        try:
            # Проверка разрешения торговли
            perms = self.state_manager.get_trading_permissions()
            if not perms or not perms.get(base, False):
                return {'status': 'error', 'error': 'trading_disabled'}
            
            self._ensure_cycle_struct(base)
            cycle = self.cycles[base]
            
            if cycle.get('active'):
                return {'status': 'error', 'error': 'cycle_already_active'}
            
            # Получение цены
            price = self._get_market_price(base, quote)
            if not price or price <= 0:
                return {'status': 'error', 'error': 'no_price_data'}
            
            # Таблица
            self._recalc_table_if_needed(base, quote, price)
            table = cycle['table']
            if not table:
                return {'status': 'error', 'error': 'no_table'}
            
            # Параметры покупки
            first_row = table[0]
            purchase_usd = float(first_row['purchase_usd'])
            params = self.state_manager.get_breakeven_params(base)
            keep = float(params.get('keep', 0.0))
            
            # Проверка баланса BASE
            base_balance = self._get_account_balance(base)
            base_balance_in_quote = base_balance * price
            
            # Если баланс BASE уже достаточен - пропускаем покупку
            if base_balance_in_quote >= purchase_usd * 0.95:  # 95% для учёта комиссий
                return {'status': 'error', 'error': 'base_balance_sufficient'}
            
            # Проверяем баланс QUOTE
            quote_required = purchase_usd + keep
            quote_available = self._get_account_balance(quote)
            
            if quote_available < quote_required:
                return {'status': 'error', 'error': 'insufficient_quote'}
            
            # ВЫПОЛНЕНИЕ MARKET ОРДЕРА
            api_client = self.api_client_provider()
            currency_pair = f"{base}_{quote}".upper()
            
            if not api_client:
                # SIMULATION
                return {
                    'status': 'success',
                    'filled': amount_base,
                    'price': price,
                    'invested': purchase_usd,
                    'simulated': True
                }
            
            try:
                result = api_client.create_spot_order(
                    currency_pair=currency_pair,
                    side='buy',
                    amount=f"{purchase_usd:.8f}",
                    order_type='market'
                )
                
                filled = self._parse_filled_amount(result)
                if filled > 0:
                    spent_usd = float(result.get('filled_total', 0) or 0)
                    actual_price = spent_usd / filled if filled > 0 else price
                    
                    return {
                        'status': 'success',
                        'filled': filled,
                        'price': actual_price,
                        'invested': spent_usd,
                        'order': result
                    }
                else:
                    return {'status': 'error', 'error': 'market_order_failed', 'order': result}
            
            except Exception as e:
                return {'status': 'error', 'error': f'api_exception: {str(e)}'}
        
        except Exception as e:
            return {'status': 'error', 'error': f'execution_exception: {str(e)}'}
    
    # ------------------------ Логика цикла ------------------------

    def _try_start_buy_simple(self, base: str, quote: str):
        """
        ПРОСТАЯ СИНХРОННАЯ стартовая покупка.
        
        Вызывается ПОД LOCK, поэтому race condition НЕВОЗМОЖЕН!
        Всё происходит атомарно:
        1. Проверяем условия
        2. Делаем MARKET покупку (синхронно)
        3. Активируем цикл (active=True)
        4. Сохраняем состояние
        
        Lock НЕ освобождается до завершения всех операций!
        """
        # Проверка разрешения
        perms = self.state_manager.get_trading_permissions()
        if not perms or not perms.get(base, False):
            return
        
        cycle = self.cycles.get(base, {})
        
        # ВАЖНО: Проверяем, что цикл ДЕЙСТВИТЕЛЬНО не активен
        if cycle.get('active'):
            return
        
        # ====== КРИТИЧЕСКАЯ ЗАЩИТА #1: Не покупать слишком часто ======
        # Если последняя попытка покупки была менее 5 секунд назад - ПРОПУСКАЕМ
        last_attempt = cycle.get('last_start_attempt', 0)
        if last_attempt > 0 and (time.time() - last_attempt) < 5.0:
            return
        
        # ====== КРИТИЧЕСКАЯ ЗАЩИТА #2: Не покупать после недавней продажи ======
        # Если продажа была менее 3 секунд назад - ПРОПУСКАЕМ (даём время на обновление баланса)
        last_sell = cycle.get('last_sell_time', 0)
        if last_sell > 0 and (time.time() - last_sell) < 3.0:
            return
        
        # Проверяем баланс BASE - если достаточно, не покупаем
        price = self._get_market_price(base, quote)
        if not price or price <= 0:
            return
        
        # ====== КРИТИЧЕСКАЯ ЗАЩИТА #3: Принудительно обновляем кэш баланса ======
        # Это гарантирует, что мы видим актуальный баланс после предыдущей покупки
        base_balance = self._get_account_balance(base, force_refresh=True)
        
        # Получаем требуемую сумму из таблицы
        self._recalc_table_if_needed(base, quote, price)
        table = cycle.get('table', [])
        if not table:
            return
        
        first_row = table[0]
        purchase_usd = float(first_row['purchase_usd'])
        base_balance_in_quote = base_balance * price
        
        # ====== КРИТИЧЕСКАЯ ЗАЩИТА #4: Если баланс BASE уже достаточен - НЕ ПОКУПАЕМ! ======
        # Проверяем, что баланс меньше 80% требуемого (запас на комиссии и флуктуации)
        if base_balance_in_quote >= purchase_usd * 0.80:
            print(f"[START_SIMPLE][{base}] ⚠️ Баланс BASE уже достаточен: {base_balance:.8f} ({base_balance_in_quote:.2f} USDT) >= {purchase_usd * 0.80:.2f} USDT (80% от {purchase_usd:.2f})")
            return
        
        # Проверяем баланс QUOTE
        params = self.state_manager.get_breakeven_params(base)
        keep = float(params.get('keep', 0.0))
        quote_required = purchase_usd + keep
        quote_available = self._get_account_balance(quote)
        
        if quote_available < quote_required:
            return
        
        # ====== КРИТИЧЕСКАЯ ЗАЩИТА #5: Устанавливаем флаг ПЕРЕД покупкой ======
        # Это предотвращает повторные попытки пока идёт покупка
        cycle['last_start_attempt'] = time.time()
        self.cycles[base] = cycle
        
        # ВСЁ ОК - Выполняем СИНХРОННУЮ покупку
        print(f"[START_SIMPLE][{base}] 🚀 Выполняем СИНХРОННУЮ стартовую покупку...")
        print(f"[START_SIMPLE][{base}]   Баланс BASE: {base_balance:.8f} ({base_balance_in_quote:.2f} USDT)")
        print(f"[START_SIMPLE][{base}]   Требуется: {purchase_usd:.2f} USDT")
        print(f"[START_SIMPLE][{base}]   Баланс QUOTE: {quote_available:.2f} USDT")
        
        result = self._execute_start_buy(base, quote)
        
        if result.get('status') == 'success':
            # УСПЕХ - Активируем цикл НЕМЕДЛЕННО
            filled = result['filled']
            buy_price = result['price']
            invested = result['invested']
            
            print(f"[START_SIMPLE][{base}] ✅ Покупка успешна: {filled:.8f} @ {buy_price:.8f}")
            
            # АТОМАРНАЯ активация цикла
            cycle.update({
                'active': True,
                'active_step': 0,
                'last_buy_price': buy_price,
                'start_price': buy_price,
                'total_invested_usd': invested,
                'base_volume': filled,
                'cycle_activated_at': time.time(),
                'last_sell_time': 0
            })
            
            self.cycles[base] = cycle
            self._save_cycles_state()
            
            # Обновляем state_manager
            try:
                params['start_price'] = buy_price
                self.state_manager.set_breakeven_params(base, params)
                new_table = calculate_breakeven_table(params, buy_price)
                cycle['table'] = new_table
            except Exception:
                pass
            
            # Логируем
            self.logger.log_buy(base, filled, buy_price, 0.0, 0.0, invested)
            self.stats['total_buy_orders'] += 1
            self.stats['total_cycles'] += 1
            self.stats['last_update'] = time.time()
            self.balance_cache.invalidate(reason=f"start_buy_{base}")
            
            print(f"[START_SIMPLE][{base}] 🎯 Цикл АКТИВИРОВАН и СОХРАНЁН!")
        else:
            # ОШИБКА
            error = result.get('error', 'unknown')
            print(f"[START_SIMPLE][{base}] ❌ Ошибка покупки: {error}")
# Конец файла

