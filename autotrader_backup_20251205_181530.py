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
        
        # КРИТИЧЕСКАЯ ЗАЩИТА: Lock для предотвращения параллельных стартовых покупок
        from threading import Lock
        self._start_cycle_locks: Dict[str, Lock] = {}  # Lock для каждой валюты отдельно
        self._locks_creation_lock = Lock()  # МАСТЕР-LOCK для атомарного создания Lock'ов валют

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

                # Save active cycles or cycles that have pending partial executions
                pending = cycle.get('pending') or {}
                has_pending = False
                try:
                    # check for any non-zero remaining pending amounts
                    for k, v in pending.items():
                        if isinstance(v, dict) and float(v.get('remaining', 0) or 0) > 0:
                            has_pending = True
                            break
                except Exception:
                    has_pending = False

                if cycle.get('active') or has_pending:

                    state_to_save[base] = {

                        'active': cycle.get('active', False),

                        'active_step': cycle.get('active_step', -1),

                        'last_buy_price': cycle.get('last_buy_price', 0.0),

                        'start_price': cycle.get('start_price', 0.0),

                        'total_invested_usd': cycle.get('total_invested_usd', 0.0),

                        'base_volume': cycle.get('base_volume', 0.0),

                        'pending': pending,

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

                

                # Восстанавливаем цикл (включая возможные pending-частичные исполнения)
                pending = saved_cycle.get('pending') or {}

                # ИСПРАВЛЕНИЕ: Загружаем таблицу из файла, если она есть
                saved_table = saved_cycle.get('table', [])

                self.cycles[base] = {
                    'active': saved_cycle.get('active', False),
                    'active_step': saved_cycle.get('active_step', -1),
                    'table': saved_table,  # загружаем сохраненную таблицу
                    'last_buy_price': saved_cycle.get('last_buy_price', 0.0),
                    'start_price': saved_cycle.get('start_price', 0.0),
                    'total_invested_usd': saved_cycle.get('total_invested_usd', 0.0),
                    'base_volume': saved_cycle.get('base_volume', 0.0),
                    'pending': pending
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
                                    'pending_start': False,  # КРИТИЧНО: Сбрасываем флаг
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
            # pending holds partial execution info for start/rebuy/sell
            'pending': {}

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
        """Попытка запустить новый торговый цикл (стартовая покупка).
        
        Минимальные проверки для надёжной работы:
        1. Цикл не должен быть активен (active=False)
        2. Не должна идти другая покупка (pending_start=False)
        3. Атомарная блокировка через Lock
        """
        self._ensure_cycle_struct(base)
        cycle = self.cycles.get(base, {})
        
        # Проверка 1: Цикл активен?
        if cycle.get('active'):
            return
        
        # Проверка 2: Покупка уже идёт?
        if cycle.get('pending_start'):
            return
        
        # ====== АТОМАРНАЯ БЛОКИРОВКА: Только один поток может выполнять стартовую покупку ======
        # КРИТИЧНО: Создание Lock'а для валюты должно быть атомарным!
        # Используем мастер-Lock для защиты от race condition при создании Lock'ов
        with self._locks_creation_lock:
            if base not in self._start_cycle_locks:
                from threading import Lock
                self._start_cycle_locks[base] = Lock()
                print(f"[LOCK_INIT][{base}] Создан новый Lock для валюты")

        # Пытаемся захватить Lock (неблокирующая попытка)
        acquired = self._start_cycle_locks[base].acquire(blocking=False)
        if not acquired:
            print(f"[LOCK_PROTECTION][{base}] БЛОКИРОВКА: другой поток уже выполняет стартовую покупку")
            return

        try:
            # ПОВТОРНАЯ ПРОВЕРКА ПОСЛЕ ЗАХВАТА LOCK (double-check locking pattern)
            cycle = self.cycles.get(base, {})
            if cycle.get('active'):
                print(f"[PROTECTION][{base}] ОТКАЗ: цикл стал активным во время ожидания lock")
                return
            
            if cycle.get('pending_start'):
                print(f"[PROTECTION][{base}] ОТКАЗ: pending_start=True во время ожидания lock")
                return
            
            # Lock захвачен и все проверки пройдены — выполняем стартовую покупку
            print(f"[START_CYCLE][{base}] ✅ Все проверки пройдены, запускаем стартовую покупку")
            self._try_start_cycle_impl(base, quote)
        except Exception as e:
            print(f"[ERROR][{base}] Ошибка в _try_start_cycle: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # ОБЯЗАТЕЛЬНО освобождаем Lock в конце
            self._start_cycle_locks[base].release()
            print(f"[LOCK_PROTECTION][{base}] Lock освобождён")

    def _try_start_cycle_impl(self, base: str, quote: str):
        """Выполнение стартовой покупки. Вызывается только после успешного захвата Lock в _try_start_cycle."""
        print(f"[START_CYCLE][{base}] Выполнение стартовой покупки...")
        self._ensure_cycle_struct(base)
        cycle = self.cycles[base]
        
        # ====== КРИТИЧНО: УСТАНАВЛИВАЕМ pending_start=True НЕМЕДЛЕННО ======
        # Это блокирует ВСЕ другие попытки стартовой покупки до завершения текущей
        # НО НЕ УСТАНАВЛИВАЕМ active=True до успешной покупки!
        cycle['pending_start'] = True
        cycle['last_start_attempt'] = time.time()
        
        # ====== СОХРАНЯЕМ СОСТОЯНИЕ СРАЗУ В ПАМЯТЬ ======
        # ВАЖНО: Сохраняем в self.cycles ДО вызова _save_cycles_state()
        self.cycles[base] = cycle
        
        # Сохраняем состояние НЕМЕДЛЕННО в файл
        try:
            self._save_cycles_state()
            print(f"[PROTECTION][{base}] ⚠️ ФЛАГ pending_start=True УСТАНОВЛЕН И СОХРАНЁН")
            print(f"[PROTECTION][{base}] Это блокирует повторные старты до завершения покупки")
            print(f"[PROTECTION][{base}] active=False останется до успешной покупки")
        except Exception as e:
            print(f"[PROTECTION_ERROR][{base}] Не удалось сохранить: {e}")
        
        # === ФИНАЛЬНАЯ ПРОВЕРКА: Цикл НЕ должен быть активен ===
        # Перечитываем из памяти (может быть изменён другим потоком)
        cycle = self.cycles.get(base, {})
        if cycle.get('active'):
            print(f"[PROTECTION][{base}] ⚠️ ПРОВЕРКА: цикл стал активным! Отменяем стартовую покупку")
            cycle['pending_start'] = False
            self.cycles[base] = cycle
            self._save_cycles_state()
            return

        # Если есть pending.start (частично исполненная стартовая покупка) — пытаемся докупить оставшуюся часть
        try:
            if not cycle:
                cycle['pending_start'] = False
                return
            pending = cycle.get('pending') or {}
            start_pending = pending.get('start') if isinstance(pending, dict) else None
            if start_pending and float(start_pending.get('remaining', 0) or 0) > 0:
                rem = float(start_pending.get('remaining') or 0.0)
                api_client = self.api_client_provider()
                if api_client and rem > 0:
                    # ensure min base amount
                    pi = self._get_pair_info(base, quote)
                    try:
                        amt_prec = int(pi.get('amount_precision', 8))
                    except Exception:
                        amt_prec = 8
                    try:
                        result = api_client.create_spot_order(
                            currency_pair=f"{base}_{quote}".upper(),
                            side='buy',
                            amount=f"{rem:.{amt_prec}f}",
                            order_type='market'
                        )
                        filled2 = self._parse_filled_amount(result)
                        buy_price2 = float(result.get('avg_deal_price') or self._get_market_price(base, quote) or 0)
                        if filled2 and filled2 > 0:
                            # update pending filled and remaining
                            start_pending['filled'] = float(start_pending.get('filled', 0) or 0) + filled2
                            start_pending['filled_usd'] = float(start_pending.get('filled_usd', 0) or 0) + (filled2 * buy_price2)
                            start_pending['remaining'] = max(0.0, float(start_pending.get('remaining', 0) or 0) - filled2)
                            cycle['base_volume'] = float(cycle.get('base_volume', 0) or 0) + filled2
                            # if completed — finalize as active cycle
                            if start_pending['remaining'] <= 1e-12:
                                total_filled = float(start_pending.get('filled', 0) or 0)
                                total_usd = float(start_pending.get('filled_usd', 0) or 0)
                                if total_filled > 0:
                                    start_price = total_usd / total_filled
                                else:
                                    start_price = buy_price2
                                
                                # ====== КРИТИЧНО: СНАЧАЛА АКТИВИРУЕМ ЦИКЛ, ПОТОМ СБРАСЫВАЕМ ФЛАГ ======
                                cycle.update({
                                    'active': True,
                                    'active_step': 0,
                                    'last_buy_price': start_price,
                                    'start_price': start_price,
                                    'total_invested_usd': total_usd,
                                    'base_volume': total_filled
                                })
                                
                                # ====== СБРАСЫВАЕМ ФЛАГИ ЗАЩИТЫ ПОСЛЕ АКТИВАЦИИ ЦИКЛА ======
                                cycle['pending_start'] = False
                                cycle['last_sell_time'] = 0
                                # persist start_price
                                try:
                                    current_params = self.state_manager.get_breakeven_params(base)
                                    current_params['start_price'] = start_price
                                    self.state_manager.set_breakeven_params(base, current_params)
                                except Exception:
                                    pass
                                # clear pending start
                                pending.pop('start', None)
                                cycle['pending'] = pending
                                # recalc table
                                try:
                                    new_table = calculate_breakeven_table(self.state_manager.get_breakeven_params(base), start_price)
                                    cycle['table'] = new_table
                                except Exception as e:
                                    pass
                                self._save_cycles_state()
                            else:
                                # still pending
                                cycle['pending'] = pending
                                self._save_cycles_state()
                    except Exception as e:
                        pass
        except Exception:
            pass

        # Получение цены
        price = self._get_market_price(base, quote)
        if not price or price <= 0:
            cycle['pending_start'] = False
            return

        

        # Проверка 2: Пересчёт таблицы

        self._recalc_table_if_needed(base, quote, price)

        table = cycle['table']

        if not table:
            cycle['pending_start'] = False
            return

        

        first_row = table[0]

        purchase_usd = float(first_row['purchase_usd'])

        params = self.state_manager.get_breakeven_params(base)

        keep = float(params.get('keep', 0.0))

        

        # Проверка 3: Баланс BASE валюты в пересчете на QUOTE

        # Если баланс BASE (в USDT) >= purchase_usd → НЕ начинаем новый цикл

        base_balance = 0.0

        try:

            api_client = self.api_client_provider()

            if api_client:

                balance = api_client.get_account_balance()

                if isinstance(balance, list):

                    for item in balance:

                        if item.get('currency', '').upper() == base.upper():

                            base_balance = float(item.get('available', 0))

                            break

        except Exception as e:

            # В случае ошибки - продолжаем (может быть симуляция)

            pass

        

        # Рассчитываем стоимость баланса BASE в QUOTE

        base_balance_in_quote = base_balance * price

        
        # ====== КРИТИЧЕСКАЯ ПРОВЕРКА: Баланс BASE >= минимального ордера ======
        # Если баланс BASE (в USD) >= purchase_usd → НЕ начинаем новый цикл!
        # Новый цикл запускается ТОЛЬКО если остаток баланса BASE меньше минимального ордера
        if base_balance_in_quote >= purchase_usd:
            print(f"[{base}] Блокировка старта: баланс BASE ({base_balance_in_quote:.2f} USD) >= мин.ордера ({purchase_usd:.2f} USD)")
            cycle['pending_start'] = False
            self.cycles[base] = cycle
            self._save_cycles_state()
            return
        
        print(f"[{base}] Старт разрешён: баланс BASE ({base_balance_in_quote:.2f}) < мин.ордера ({purchase_usd:.2f})")

        
        # Получим доступный баланс котируемой валюты (quote), чтобы точно проверить,
        # хватает ли средств для стартовой покупки (с учётом keep).
        quote_available = 0.0
        try:
            api_client = self.api_client_provider()
            if api_client:
                bal = api_client.get_account_balance()
                if isinstance(bal, list):
                    for item in bal:
                        if item.get('currency', '').upper() == quote.upper():
                            try:
                                quote_available = float(item.get('available', 0) or 0)
                            except Exception:
                                quote_available = 0.0
                            break
        except Exception:
            quote_available = 0.0

        # Если доступный баланс в котируемой валюте за вычетом keep меньше чем требуется для
        # стартовой покупки — не начинаем цикл.
        try:
            if (quote_available - keep) < purchase_usd:
                print(f"[{base}] Блокировка: недостаточно QUOTE (доступно={quote_available:.2f}, keep={keep:.2f}, требуется={purchase_usd:.2f})")
                cycle['pending_start'] = False
                self.cycles[base] = cycle
                self._save_cycles_state()
                return
        except Exception:
            pass

        

        # Проверка 4: Минимальные квоты пары

        pair_info = self._get_pair_info(base, quote)

        min_q = float(pair_info.get('min_quote_amount') or 0)

        min_b = float(pair_info.get('min_base_amount') or 0)

        

        if purchase_usd < min_q:

            purchase_usd = min_q

        

        amount_base = purchase_usd / price if price > 0 else 0
        # Округляем объём базы ВВЕРХ до шага точности пары (amount_precision),
        # чтобы обеспечить, что фактическая сумма в QUOTE будет >= запланированной purchase_usd.
        try:
            amt_prec = int(pair_info.get('amount_precision', 8))
        except Exception:
            amt_prec = 8
        unit = 1.0 / (10 ** amt_prec)

        if amount_base and amount_base > 0:
            amount_base = math.ceil(amount_base / unit) * unit

        if amount_base < min_b:
            amount_base = min_b

        # После округления пересчитываем итоговую сумму в QUOTE
        purchase_usd = amount_base * price

        

        # Проверка баланса QUOTE (реальная проверка через API)

        quote_required = purchase_usd + keep

        quote_available = 0.0

        

        try:

            api_client = self.api_client_provider()

            if api_client:

                balance = api_client.get_account_balance()

                if isinstance(balance, list):

                    for item in balance:

                        if item.get('currency', '').upper() == quote.upper():

                            quote_available = float(item.get('available', 0))

                            break

            else:

                # Режим симуляции - разрешаем покупку

                quote_available = quote_required * 10

        except Exception as e:

            # В случае ошибки - пробуем всё равно (может это симуляция)

            quote_available = quote_required * 10

        

        if quote_available < quote_required:
            # Недостаточно средств - сбрасываем флаг
            cycle['pending_start'] = False
            return

        # Получаем цену ask из orderbook для расчёта количества (для market-ордера orderbook не обязателен)
        orderbook = self._get_orderbook(base, quote)
        if not orderbook or not orderbook.get('asks'):
            buy_price = price  # используем текущую цену если orderbook недоступен
        else:
            buy_price = price  # по умолчанию текущая цена

        try:
            api_client_check = self.api_client_provider()
            if api_client_check:
                balance_check = api_client_check.get_account_balance()
                if isinstance(balance_check, list):
                    for item in balance_check:
                        if item.get('currency', '').upper() == base.upper():
                            current_base = float(item.get('available', 0))
                            current_base_usd = current_base * price
                            if current_base_usd >= purchase_usd * 0.9:
                                print(f"[{base}] БЛОКИРОВКА: баланс BASE уже есть ({current_base:.8f} = ${current_base_usd:.2f})")
                                cycle['pending_start'] = False
                                self.cycles[base] = cycle
                                self._save_cycles_state()
                                return
        except Exception as e:
            print(f"[{base}] Ошибка проверки баланса перед покупкой: {e}")

        # Новый алгоритм стартовой покупки: агрегируем asks из orderbook и
        # размещаем последовательные limit-FOK по уровням, пока суммарно
        # не будет потрачена плановая сумма purchase_usd. Это позволяет
        # купить по нескольким ценам (не только лучшему ask) и гарантировать
        # что потрачено >= запланированной суммы или откатиться.
        api_client = self.api_client_provider()
        currency_pair = f"{base}_{quote}".upper()
        pi = self._get_pair_info(base, quote)
        try:
            amt_prec = int(pi.get('amount_precision', 8))
        except Exception:
            amt_prec = 8
        try:
            price_prec = int(pi.get('price_precision', 8))
        except Exception:
            price_prec = 8

        # Determine planned purchase in QUOTE (prefer table value if available)
        try:
            purchase_usd = float(cycle.get('table', [])[0].get('purchase_usd') or 0)
        except Exception:
            purchase_usd = float(amount_base * price)

        unit = 1.0 / (10 ** amt_prec)
        min_b = float(pi.get('min_base_amount') or 0)

        needed_quote = float(purchase_usd)
        cumulative_base = 0.0
        cumulative_spent = 0.0
        level_fills = []  # keep per-level fill info for diagnostics

        if not orderbook or not orderbook.get('asks'):
            order_res = {'success': False, 'filled': 0.0, 'error': 'no_orderbook'}
        else:
            asks = orderbook.get('asks') or []
            # Iterate asks from best (index 0) upward
            for a in asks:
                if cumulative_spent >= needed_quote:
                    break
                try:
                    level_price = float(a[0])
                    level_amount = float(a[1])
                except Exception:
                    continue

                remaining_quote = max(0.0, needed_quote - cumulative_spent)
                # Desired base at this price to cover remaining_quote
                desired_base = remaining_quote / level_price if level_price > 0 else 0.0

                # Cap desired_base to available at this level (respect pair precision)
                max_base_at_level = math.floor(level_amount / unit) * unit
                if max_base_at_level <= 0:
                    continue

                desired_base = min(desired_base, max_base_at_level)
                # Round up to ensure we don't underspend due to discretization
                desired_base = math.ceil(desired_base / unit) * unit
                if desired_base > max_base_at_level:
                    desired_base = max_base_at_level

                if desired_base < min_b:
                    if min_b <= max_base_at_level:
                        desired_base = min_b
                    else:
                        # cannot satisfy min base at this level
                        continue

                if desired_base <= 0:
                    continue

                if not api_client:
                    # Simulation: assume full fill at level_price
                    filled = desired_base
                    fill_spent = filled * level_price
                    cumulative_base += filled
                    cumulative_spent += fill_spent
                    level_fills.append({'price': level_price, 'filled': filled, 'spent': fill_spent, 'simulated': True})
                    continue

                # Real API: place limit FOK at this level
                try:
                    res = api_client.create_spot_order(
                        currency_pair=currency_pair,
                        side='buy',
                        amount=f"{desired_base:.{amt_prec}f}",
                        price=f"{level_price:.{price_prec}f}",
                        order_type='limit',
                        time_in_force='fok'
                    )
                    filled = self._parse_filled_amount(res)
                    if filled and filled > 0:
                        # record fill (partial fills may occur due to race conditions)
                        fill_spent = filled * level_price
                        cumulative_base += filled
                        cumulative_spent += fill_spent
                        level_fills.append({'price': level_price, 'filled': filled, 'spent': fill_spent, 'order': res})
                        # If partial (filled < desired_base), continue trying next levels
                        if filled < desired_base * 0.999:
                            # continue to next levels to try to cover remaining quote
                            continue
                        else:
                            # full level satisfied, continue to check if more is needed
                            continue
                    else:
                        # no fill at this level — try next level
                        continue
                except Exception as e:
                    # try next level
                    continue

            # End for asks
            # Evaluate aggregated result
            if cumulative_spent >= needed_quote * 0.999:
                # success: compute weighted average buy price
                try:
                    buy_price = (cumulative_spent / cumulative_base) if cumulative_base > 0 else price
                except Exception:
                    buy_price = price
                order_res = {'success': True, 'filled': cumulative_base, 'filled_usd': cumulative_spent, 'avg_price': buy_price, 'fills': level_fills}
            elif cumulative_base > 0:
                # partial fills across levels — create pending for remaining
                try:
                    buy_price = (cumulative_spent / cumulative_base) if cumulative_base > 0 else price
                except Exception:
                    buy_price = price
                order_res = {'success': False, 'filled': cumulative_base, 'filled_usd': cumulative_spent, 'fills': level_fills}
            else:
                buy_price = price
                order_res = {'success': False, 'filled': 0.0, 'error': 'insufficient_liquidity', 'fills': level_fills}

        

        if order_res.get('success'):

            filled = order_res['filled']
            
            # ⚠️ КРИТИЧЕСКИ ВАЖНО: используем РЕАЛЬНУЮ цену исполнения из ответа биржи!
            # Для агрегированной покупки используем avg_price, для обычной - avg_deal_price
            actual_buy_price = float(order_res.get('avg_price') or order_res.get('avg_deal_price') or order_res.get('filled_usd', 0) / filled if filled > 0 else buy_price)
            invest = float(order_res.get('filled_usd') or (filled * actual_buy_price))

            # ОПТИМИЗАЦИЯ: Инвалидируем кэш балансов после успешной покупки
            self.balance_cache.invalidate(reason=f"start_cycle_buy_{base}")

            # ====== ФИНАЛЬНАЯ ПРОВЕРКА ПЕРЕД АКТИВАЦИЕЙ: Цикл НЕ должен быть активен ======
            # Перечитываем цикл из памяти на случай, если другой поток уже активировал его
            cycle = self.cycles.get(base, {})
            if cycle.get('active'):
                print(f"[PROTECTION][{base}] ❌ ОТМЕНА: Цикл уже активен другим потоком!")
                print(f"[PROTECTION][{base}]   - active={cycle.get('active')}")
                print(f"[PROTECTION][{base}]   - base_volume={cycle.get('base_volume', 0):.8f}")
                print(f"[PROTECTION][{base}]   - Покупка отменяется, средства останутся на балансе")
                # Сбрасываем pending_start
                cycle['pending_start'] = False
                self.cycles[base] = cycle
                self._save_cycles_state()
                return

            print(f"[{base}] Успешная покупка: filled={filled:.8f}, price={actual_buy_price:.8f}, invested={invest:.4f}, fills={len(level_fills)} levels")

            cycle.update({
                'active': True,
                'active_step': 0,
                'last_buy_price': actual_buy_price,
                'start_price': actual_buy_price,
                'total_invested_usd': invest,
                'base_volume': filled
            })
            
            cycle['pending_start'] = False
            cycle['last_sell_time'] = 0
            
            print(f"[{base}] Цикл активирован: active=True, start_price={actual_buy_price:.8f}")

            try:
                cycle['just_started'] = True
            except Exception:
                pass

            self.cycles[base] = cycle
            self._save_cycles_state()
            
            try:
                self._set_last_diagnostic(base, {
                    'decision': 'cycle_started',
                    'timestamp': time.time(),
                    'reason': 'start_buy_completed',
                    'start_price': actual_buy_price,
                    'base_volume': filled
                })
            except Exception:
                pass

            

            # КРИТИЧЕСКИ ВАЖНО: обновляем start_price в state_manager для таблицы безубыточности

            try:

                current_params = self.state_manager.get_breakeven_params(base)

                current_params['start_price'] = actual_buy_price  # ← РЕАЛЬНАЯ ЦЕНА ИСПОЛНЕНИЯ

                save_result = self.state_manager.set_breakeven_params(base, current_params)

                

                # Проверяем, что сохранилось - повторяем до 3 раз при неудаче

                max_retries = 3

                for attempt in range(max_retries):

                    verify_params = self.state_manager.get_breakeven_params(base)

                    verified_start_price = verify_params.get('start_price', 0)

                    if verified_start_price == actual_buy_price:  # ← РЕАЛЬНАЯ ЦЕНА ИСПОЛНЕНИЯ

                        break

                    else:

                        if attempt < max_retries - 1:

                            # Повторная попытка сохранения

                            save_result = self.state_manager.set_breakeven_params(base, current_params)

                

                # ВАЖНО: Пересчитываем таблицу с новым start_price

                new_table = calculate_breakeven_table(current_params, actual_buy_price)  # ← РЕАЛЬНАЯ ЦЕНА ИСПОЛНЕНИЯ

                cycle['table'] = new_table

            except Exception as e:

                pass

            
            real_decrease_step_pct = 0.0
            real_cumulative_drop_pct = 0.0
            
            print(f"[{base}] Логирую стартовую покупку с 0% падения")
            
            self.logger.log_buy(base, filled, actual_buy_price, real_decrease_step_pct, real_cumulative_drop_pct, invest)

            # Обновляем статистику

            self.stats['total_buy_orders'] += 1

            self.stats['total_cycles'] += 1

            self.stats['last_update'] = time.time()

            # Состояние уже сохранено выше (сразу после active=True)

        else:
            # ====== СБРАСЫВАЕМ ФЛАГ PENDING_START В СЛУЧАЕ НЕУДАЧИ ======
            cycle['pending_start'] = False
            
            error_info = order_res.get('error', 'partial/none fill')
            filled_amt = float(order_res.get('filled', 0.0) or 0.0)
            # Если частично исполнено — сохраняем pending чтобы добрать остаток в следующих циклах
            try:
                diag = {
                    'decision': 'start_failed',
                    'timestamp': time.time(),
                    'reason': str(error_info),
                    'filled': filled_amt,
                    'order_res': order_res
                }
                if filled_amt and filled_amt > 0:
                    diag['decision'] = 'start_partial_filled'
                self._set_last_diagnostic(base, diag)
            except Exception:
                pass

            try:
                # Если было частичное исполнение — создаём или обновляем pending.start
                if filled_amt and filled_amt > 0:
                    # store what was filled and remaining to attempt later
                    pending = cycle.get('pending') or {}
                    # original planned amount (amount_base) may not be available here, compute from quote if possible
                    try:
                        planned_base = float(amount_base)
                    except Exception:
                        planned_base = filled_amt

                    remaining = max(0.0, planned_base - filled_amt)
                    # store invested USD for filled portion (approx)
                    invested = filled_amt * buy_price if buy_price else 0.0

                    pending['start'] = {
                        'remaining': remaining,
                        'total': planned_base,
                        'filled': filled_amt,
                        'filled_usd': invested
                    }

                    cycle['pending'] = pending
                    # reflect held amount (partial) in base_volume so balance-aware checks are correct
                    cycle['base_volume'] = filled_amt
                    # do not mark cycle active until full planned amount is acquired
                    try:
                        self._save_cycles_state()
                    except Exception:
                        pass
                else:
                    # полная неудача — нет fill
                    pass
            except Exception as e:
                pass



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

        # Если есть pending.rebuy — пытаемся выполнить остаток лимитным FOK-ордерами
        try:
            pending = cycle.get('pending') or {}
            reb = pending.get('rebuy') if isinstance(pending, dict) else None
            if reb and float(reb.get('remaining', 0) or 0) > 0:
                rem = float(reb.get('remaining') or 0.0)
                level_price = float(reb.get('level_price') or 0.0)
                step = int(reb.get('step', 0))
                order_res = self._place_limit_order_all_or_nothing('buy', base, quote, rem, level_price)
                filled = float(order_res.get('filled', 0.0) or 0.0)
                if order_res.get('success') and filled >= rem * 0.999:
                    # completed rebuy
                    # ОПТИМИЗАЦИЯ: Инвалидируем кэш балансов после успешной покупки
                    self.balance_cache.invalidate(reason=f"rebuy_pending_{base}")
                    
                    invest = filled * level_price
                    
                    # Рассчитываем РЕАЛЬНЫЕ значения падения для логов с УСИЛЕННОЙ ЗАЩИТОЙ
                    last_buy = cycle.get('last_buy_price', 0.0)
                    start_price = cycle.get('start_price', 0.0)
                    
                    # ЗАЩИТА: Если это первая покупка в цикле, инициализируем start_price
                    if start_price == 0.0:
                        start_price = level_price
                        cycle['start_price'] = start_price
                        print(f"[AutoTrader][{base}] ⚡ INITIALIZED start_price={start_price:.8f} (first buy in cycle)")
                    
                    # ЗАЩИТА: Если last_buy == 0, используем start_price для расчёта stepwise падения
                    if last_buy > 0:
                        real_decrease_step_pct = (last_buy - level_price) / last_buy * 100.0
                    else:
                        # Первая покупка в цикле - сравниваем со start_price
                        if start_price > 0 and start_price != level_price:
                            real_decrease_step_pct = (start_price - level_price) / start_price * 100.0
                            print(f"[AutoTrader][{base}] ⚡ Using start_price for step_pct: {real_decrease_step_pct:.2f}%")
                        else:
                            real_decrease_step_pct = 0.0
                    
                    # Cumulative падение всегда от start_price
                    if start_price > 0:
                        real_cumulative_drop_pct = (start_price - level_price) / start_price * 100.0
                    else:
                        real_cumulative_drop_pct = 0.0
                    
                    cycle['active_step'] = step
                    cycle['last_buy_price'] = level_price
                    cycle['total_invested_usd'] = float(cycle.get('total_invested_usd', 0) or 0) + invest
                    cycle['base_volume'] = float(cycle.get('base_volume', 0) or 0) + filled
                    pending.pop('rebuy', None)
                    cycle['pending'] = pending
                    # === DIAGNOSTIC: Values used in log_buy ===
                    print(f"[DIAG_LOG_BUY][{base}] filled={filled:.8f}, level_price={level_price:.8f}")
                    print(f"[DIAG_LOG_BUY][{base}] real_decrease_step_pct={real_decrease_step_pct:.4f}, real_cumulative_drop_pct={real_cumulative_drop_pct:.4f}")
                    print(f"[DIAG_LOG_BUY][{base}] total_invested_usd={cycle['total_invested_usd']:.4f}, last_buy={last_buy:.8f}, start_price={start_price:.8f}")
                    # ==========================================
                    self.logger.log_buy(base, filled, level_price, real_decrease_step_pct, real_cumulative_drop_pct, cycle['total_invested_usd'])
                    self._save_cycles_state()
                else:
                    # partial or none
                    if filled and filled > 0:
                        reb['filled'] = float(reb.get('filled', 0) or 0) + filled
                        reb['filled_usd'] = float(reb.get('filled_usd', 0) or 0) + (filled * level_price)
                        reb['remaining'] = max(0.0, reb.get('remaining', 0) - filled)
                        cycle['base_volume'] = float(cycle.get('base_volume', 0) or 0) + filled
                        cycle['pending'] = pending
                        self._save_cycles_state()
                return
        except Exception:
            pass

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
        
        # 3. Обработка pending.sell (если есть незавершённые ордера)
        try:
            pending = cycle.get('pending') or {}
            psell = pending.get('sell') if isinstance(pending, dict) else None
            if psell and float(psell.get('remaining', 0) or 0) > 0:
                rem = float(psell.get('remaining') or 0.0)
                exec_price = float(psell.get('exec_price') or price)
                print(f"[AutoTrader][{base}] 🔁 Повторный sell из pending: remaining={rem:.8f} at price={exec_price}")
                
                order_res = self._place_limit_order_all_or_nothing('sell', base, quote, rem, exec_price)
                filled = float(order_res.get('filled', 0.0) or 0.0)
                
                if order_res.get('success') and filled >= rem * 0.999:
                    # ПОЛНАЯ ПРОДАЖА pending
                    
                    # Инвалидация кэша
                    self.balance_cache.invalidate(reason=f"sell_pending_{base}")
                    
                    # Расчёт PnL
                    avg_invest_price = cycle['total_invested_usd'] / cycle['base_volume'] if cycle.get('base_volume') else exec_price
                    actual_exec_price = float(order_res.get('avg_deal_price', exec_price))
                    pnl = (actual_exec_price - avg_invest_price) * filled
                    
                    # Расчёт роста
                    start_price = cycle.get('start_price', 0.0)
                    if start_price > 0:
                        real_growth_pct = (actual_exec_price - start_price) / start_price * 100.0
                    else:
                        real_growth_pct = 0.0
                    
                    # Логирование
                    self.logger.log_sell(base, filled, actual_exec_price, real_growth_pct, pnl)
                    
                    # Закрытие цикла
                    table = cycle.get('table', [])
                    current_time = time.time()
                    self.cycles[base] = {
                        'active': False,
                        'active_step': -1,
                        'table': table,
                        'last_buy_price': 0.0,
                        'start_price': 0.0,
                        'total_invested_usd': 0.0,
                        'base_volume': 0.0,
                        'pending': {},
                        'pending_start': False,
                        'last_sell_time': current_time
                    }
                    
                    # Обнуление start_price в state_manager
                    try:
                        current_params = self.state_manager.get_breakeven_params(base)
                        current_params['start_price'] = 0.0
                        self.state_manager.set_breakeven_params(base, current_params)
                    except Exception:
                        pass
                    
                    # Сохранение
                    self._save_cycles_state()
                    
                    # Статистика
                    self.stats['total_sell_orders'] += 1
                    self.stats['last_update'] = time.time()
                    
                    print(f"[AutoTrader][{base}] ✅ Pending sell выполнен полностью, цикл завершён")
                else:
                    # ЧАСТИЧНАЯ ПРОДАЖА pending
                    if filled > 0:
                        psell['filled'] = float(psell.get('filled', 0) or 0) + filled
                        psell['filled_usd'] = float(psell.get('filled_usd', 0) or 0) + (filled * exec_price)
                        psell['remaining'] = max(0.0, psell.get('remaining', 0) - filled)
                        cycle['base_volume'] = max(0.0, float(cycle.get('base_volume', 0) or 0) - filled)
                        cycle['pending'] = pending
                        self._save_cycles_state()
                        print(f"[AutoTrader][{base}] ℹ️ Частичный pending.sell: filled_add={filled:.8f}, remaining={psell['remaining']:.8f}")
                return
        except Exception as e:
            print(f"[AutoTrader][{base}] ⚠️ Ошибка обработки pending.sell: {e}")
        
        # 4. Получение параметров активного шага
        table = cycle.get('table', [])
        active_step = cycle.get('active_step', -1)
        
        if active_step < 0 or active_step >= len(table):
            return
        
        params_row = table[active_step]
        required_growth_pct = float(params_row.get('breakeven_pct', 0))
        
        # 5. Расчёт роста от start_price
        start_price = cycle.get('start_price', 0)
        if start_price <= 0:
            return
        
        current_growth_pct = ((price - start_price) / start_price) * 100.0
        
        # 6. Проверка условия продажи
        if current_growth_pct < required_growth_pct:
            # Недостаточный рост для продажи
            return
        
        print(f"[SELL_CHECK][{base}] ✅ Условие продажи выполнено:")
        print(f"[SELL_CHECK][{base}]   start_price={start_price:.8f}")
        print(f"[SELL_CHECK][{base}]   current_price={price:.8f}")
        print(f"[SELL_CHECK][{base}]   current_growth={current_growth_pct:.4f}% >= required={required_growth_pct:.4f}%")
        
        # 7. Получение цены продажи из orderbook
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
                'pending': {},
                'pending_start': False,
                'last_sell_time': current_time
            }
            
            # Обнуление start_price в state_manager
            try:
                current_params = self.state_manager.get_breakeven_params(base)
                current_params['start_price'] = 0.0
                self.state_manager.set_breakeven_params(base, current_params)
            except Exception:
                pass
            
            # Сохранение
            self._save_cycles_state()
            
            # Статистика
            self.stats['total_sell_orders'] += 1
            self.stats['last_update'] = time.time()
            
            print(f"[AutoTrader][{base}] ✅ Продажа выполнена: filled={filled:.8f}, price={actual_exec_price:.8f}, PnL={pnl:.4f} USDT")
            print(f"[AutoTrader][{base}] 🎉 Цикл завершён, прибыль зафиксирована")
        
        else:
            # ЧАСТИЧНАЯ ПРОДАЖА или НЕУДАЧА
            
            if filled > 0:
                # Сохранить остаток в pending.sell
                pending = cycle.get('pending', {})
                pending['sell'] = {
                    'filled': filled,
                    'filled_usd': filled * exec_price,
                    'remaining': sell_volume - filled,
                    'exec_price': exec_price
                }
                cycle['base_volume'] = sell_volume - filled
                cycle['pending'] = pending
                self._save_cycles_state()
                
                print(f"[AutoTrader][{base}] ℹ️ Частичная продажа: filled={filled:.8f}, remaining={sell_volume - filled:.8f}")
            else:
                # Ордер не исполнен
                print(f"[AutoTrader][{base}] ❌ Продажа не выполнена: {order_res.get('error', 'unknown')}")


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

                # Получаем список валют для торговли

                for base in perms:

                    try:

                        # Проверка наличия данных WS

                        self._ensure_ws_subscription(base, quote)

                        # Получить цену рынка

                        price = self._get_market_price(base, quote)

                        if not price or price <= 0:

                            continue

                        # ====== КРИТИЧЕСКАЯ ЗАЩИТА: Проверяем состояние цикла ======
                        # ВАЖНО: Стартовая покупка (_try_start_cycle) вызывается ТОЛЬКО если цикл НЕактивен!
                        # Усреднение (_try_rebuy) вызывается ТОЛЬКО если цикл активен!
                        self._ensure_cycle_struct(base)
                        cycle = self.cycles.get(base, {})
                        
                        if cycle.get('active'):
                            # Цикл АКТИВЕН - проверяем продажу и усреднение
                            self._try_sell(base, quote)  # Проверка условий продажи
                            self._try_rebuy(base, quote)  # Усреднение при падении
                        else:
                            # Цикл НЕ активен - пытаемся начать новый цикл (start_cycle)
                            self._try_start_cycle(base, quote)

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

# Конец файла


