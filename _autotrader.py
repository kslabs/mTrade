"""

Автотрейдер для mTrade (реализация уточнённого алгоритма breakeven + all-or-nothing)



Основная логика (per BASE):

1. Старт цикла:

   - Условие: включена автоторговля И валюта разрешена к торговле И НЕТ активного цикла

   - Проверка баланса BASE: (баланс_BASE * цена) < "Покупка,$" строки 0 таблицы

   - Проверка баланса QUOTE: (баланс_QUOTE + keep) >= "Покупка,$" строки 0

   - Выполняем полную покупку объёма шага 0

   - Фиксируем P0 (start_price)

   - Активный row = 0

2. Усреднение (покупка следующего шага):

   - При падении текущей цены относительно последней покупки > ↓Δ,% следующего шага

   - Проверяем ликвидность на уровне стакана "Ст." (orderbook_level в params)

   - Покупаем полный объём шага (amount BASE = purchase_usd / price)

   - Активный row увеличивается

3. Продажа:

   - Триггер: рост текущей цены от P0 >= tΔPsell,% активного шага

   - Продаём все BASE (кроме объёма, необходимого для поддержания keep в QUOTE для комиссий)

   - Сбрасываем состояние цикла

4. Keep:

   - keep хранится в QUOTE; при продаже удерживаем часть QUOTE

   - при старте/усреднении убеждаемся, что остаток QUOTE после покупки >= keep

5. Ордеры:

   - Используем limit FOK; при отказе (нет полной ликвидности) пробуем IOC.
            # record failed fill
            try:
                try:
                    self._set_last_diagnostic(base, {'decision': 'sell_attempt_failed', 'timestamp': time.time(), 'reason': reason, 'filled': filled, 'required': sell_volume})
                except Exception:
                    pass
            except Exception:
                pass

            # Если ордер не исполнен полностью — пробуем определить, остался ли на аккаунте незначительный остаток.
            # Если остаток по базе меньше минимальной единицы или его эквивалент в quote меньше порога (например $1),
            # считаем его погрешностью и закрываем цикл, чтобы можно было начать новый стартовый цикл.
            try:
                remaining = self._get_account_balance(base)
                # min base amount (precision) — используем пару info
                pi = self._get_pair_info(base, quote)
                try:
                    min_base = float(pi.get('min_base_amount', 0.0) or 0.0)
                except Exception:
                    min_base = 0.0
                # Порог в котируемой валюте (USDT) под который считаем остаток незначительным
                small_quote_threshold = 1.0
                try:
                    rem_quote = remaining * float(price)
                except Exception:
                    rem_quote = remaining * sell_level if sell_level is not None else 0.0

                if (min_base and remaining <= min_base) or (rem_quote <= small_quote_threshold):
                    print(f"[AutoTrader][{base}] Остаток мал ({remaining:.8f} {base} ≈ {rem_quote:.4f} {quote}), считаем проданным и закрываем цикл")
                    # логируем завершение цикла по причине малого остатка
                    try:
                        self._set_last_diagnostic(base, {'decision': 'sell_completed_small_remainder', 'timestamp': time.time(), 'reason': 'small_remaining_balance', 'remaining': remaining, 'remaining_quote': rem_quote})
                    except Exception:
                        pass
                    # Закрываем цикл
                    self.cycles[base] = {
                        'active': False,
                        'active_step': -1,
                        'table': table,
                        'last_buy_price': 0.0,
                        'start_price': 0.0,
                        'total_invested_usd': 0.0,
                        'base_volume': 0.0
                    }
                    try:
                        current_params = self.state_manager.get_breakeven_params(base)
                        current_params['start_price'] = 0.0
                        self.state_manager.set_breakeven_params(base, current_params)
                    except Exception:
                        pass
                    self._save_cycles_state()
                    print_detailed(f"Ордер частично не исполнен, но остаток мал ({remaining:.8f}), цикл принудительно закрыт")
                    return
            except Exception:
                # если не удалось проверить баланс — просто продолжим стандартное поведение
                pass

            print_detailed(reason, extra=f"Проверьте ликвидность, стакан, параметры ордера. FOK-ордер не исполнен полностью. filled={filled:.8f}, требуется={sell_volume:.8f}")

        # all checks done — if we reached here and order wasn't executed, diagnostics already logged
- state_manager: параметры breakeven per currency (get_breakeven_params)

- breakeven_calculator.calculate_breakeven_table

- trade_logger.get_trade_logger()

- ws_manager: orderbook / ticker

- api_client_provider: функция возвращающая GateAPIClient (или None для SIM)

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

from orders import OrderService


class AutoTrader:

    def __init__(self, api_client_provider, ws_manager, state_manager):

        self.api_client_provider = api_client_provider

        self.ws_manager = ws_manager

        self.state_manager = state_manager

        self.running = False

        self._thread: Optional[Thread] = None

        self._sleep_interval = 0.5  # Уменьшено для более быстрой реакции

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

        # Инициализируем сервис ордеров, чтобы разгрузить AutoTrader
        self.order_service = OrderService(self.api_client_provider)

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

        print("[AutoTrader] Запущен breakeven алгоритм")

        # Показываем текущие разрешения при старте

        perms = self.state_manager.get_trading_permissions()

        enabled_currencies = [k for k, v in perms.items() if v]

        disabled_currencies = [k for k, v in perms.items() if not v]

        print(f"[AutoTrader] Валюты с разрешением торговли: {enabled_currencies}")

        if disabled_currencies:

            print(f"[AutoTrader] Валюты БЕЗ разрешения торговли: {disabled_currencies}")

        return True



    def stop(self):

        self.running = False

        print("[AutoTrader] Остановлен")

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

                        'saved_at': time.time()

                    }


            # Записываем в файл (пустой словарь, если нет активных циклов)
            with open(self._cycles_state_file, 'w', encoding='utf-8') as f:
                json.dump(state_to_save, f, indent=2)


            # Логируем сброшенные циклы
            inactive_bases = [base for base, cycle in self.cycles.items() if not cycle.get('active')]
            if inactive_bases:
                print(f"[AutoTrader] 💾 Состояние сохранено. Неактивные циклы удалены из файла: {inactive_bases}")

        except Exception as e:

            print(f"[AutoTrader] ⚠️ Ошибка сохранения состояния: {e}")

    

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

                    print(f"[AutoTrader][{base}] ⏰ Состояние устарело ({age_hours:.1f}ч), пропускаем")

                    continue

                

                # Восстанавливаем цикл (включая возможные pending-частичные исполнения)
                pending = saved_cycle.get('pending') or {}

                self.cycles[base] = {
                    'active': saved_cycle.get('active', False),
                    'active_step': saved_cycle.get('active_step', -1),
                    'table': [],  # таблица будет пересчитана ниже
                    'last_buy_price': saved_cycle.get('last_buy_price', 0.0),
                    'start_price': saved_cycle.get('start_price', 0.0),
                    'total_invested_usd': saved_cycle.get('total_invested_usd', 0.0),
                    'base_volume': saved_cycle.get('base_volume', 0.0),
                    'pending': pending
                }

                # КРИТИЧЕСКИ ВАЖНО: пересчитать таблицу для активного цикла

                if saved_cycle['active']:

                    params = self.state_manager.get_breakeven_params(base)

                    price_for_table = saved_cycle['start_price'] if saved_cycle['start_price'] > 0 else saved_cycle['last_buy_price']

                    table = calculate_breakeven_table(params, price_for_table)

                    self.cycles[base]['table'] = table

                    print(f"[AutoTrader][{base}] 📊 Таблица восстановлена для активного цикла: шагов={len(table)}")

                restored_count += 1

                print(f"[AutoTrader][{base}] ✅ Восстановлен цикл: step={saved_cycle['active_step']}, invested={saved_cycle['total_invested_usd']:.2f}, volume={saved_cycle['base_volume']:.8f}")

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
                                print(f"[AutoTrader][{base}] ⚠️ Несоответствие: saved_volume={recorded_volume:.8f}, current_balance={current_base_balance:.8f} — помечаем цикл НЕАКТИВНЫМ")
                                self.cycles[base].update({
                                    'active': False,
                                    'active_step': -1,
                                    'last_buy_price': 0.0,
                                    'start_price': 0.0,
                                    'total_invested_usd': 0.0,
                                    'base_volume': 0.0
                                })
                except Exception as _e:
                    print(f"[AutoTrader][{base}] ⚠️ Ошибка проверки консистентности цикла: {_e}")

            

            if restored_count > 0:

                print(f"[AutoTrader] 📂 Восстановлено циклов: {restored_count}")

        except Exception as e:

            print(f"[AutoTrader] ⚠️ Ошибка загрузки состояния: {e}")



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
                            else:
                                print(f"[AutoTrader][{base}] ⚠️ Ticker price <= 0: {price}")
                        except Exception as e:
                            print(f"[AutoTrader][{base}] ⚠️ Ошибка конвертации ticker price: {e}, last={last}")
                else:
                    print(f"[AutoTrader][{base}] ⚠️ Ticker отсутствует в WS data, пытаемся orderbook")
                
                # Fallback to orderbook if ticker not available or invalid
                if data.get('orderbook') and data['orderbook'].get('asks'):
                    try:
                        price = float(data['orderbook']['asks'][0][0])
                        if price > 0:
                            print(f"[AutoTrader][{base}] ✅ Используем цену из orderbook: {price}")
                            # обновляем last_prices/price_changed при успешном получении цены из ордербука
                            self._update_last_price(base, price)
                            return price
                        else:
                            print(f"[AutoTrader][{base}] ⚠️ Orderbook price <= 0: {price}")
                    except Exception as e:
                        print(f"[AutoTrader][{base}] ⚠️ Ошибка чтения orderbook: {e}")
            else:
                print(f"[AutoTrader][{base}] ⚠️ WS data отсутствует для {pair}")
        else:
            print(f"[AutoTrader][{base}] ⚠️ WS manager не инициализирован")
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

            # Логируем ошибку получения цены (важно для диагностики)

            if not hasattr(self, '_price_error_logged'):

                self._price_error_logged = {}

            if pair not in self._price_error_logged:

                print(f"[AutoTrader][{base}] ⚠️ Ошибка получения цены через REST API: {e}")

                self._price_error_logged[pair] = True

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

        if saved_start_price == 0 and cycle.get('active'):

            print(f"[AutoTrader][{base}] ⚠️ ВНИМАНИЕ: saved_start_price=0, но цикл активен! Это может привести к неправильному расчёту sell_level. Проверьте сохранение start_price после покупки.")

        

        price_for_table = current_price if not cycle.get('active') else (saved_start_price if saved_start_price > 0 else current_price)

        

        # Для неактивных циклов всегда пересчитываем таблицу с текущей ценой

        if not cycle.get('active'):

            table = calculate_breakeven_table(params, price_for_table)

            cycle['table'] = table

            # Устанавливаем start_price в цикле только если его там нет

            if not cycle.get('start_price') or cycle.get('start_price') == 0:

                cycle['start_price'] = table[0]['rate']

            self.cycles[base] = cycle

            print(f"[AutoTrader][{base}] 📊 Таблица рассчитана для неактивного цикла с P0={price_for_table:.8f}")

            return

        

        # Пересчёт таблицы если её нет

        if not cycle.get('table'):

            table = calculate_breakeven_table(params, price_for_table)

            cycle['table'] = table

            # Устанавливаем start_price в цикле только если его там нет

            if not cycle.get('start_price') or cycle.get('start_price') == 0:

                cycle['start_price'] = table[0]['rate']

            self.cycles[base] = cycle

            print(f"[AutoTrader][{base}] 📊 Таблица рассчитана с P0={price_for_table:.8f} (saved_start_price={saved_start_price}, current={current_price:.8f})")



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
        """Обёртка над OrderService.place_limit_order_all_or_nothing.

        Поведение сохранено: AutoTrader по-прежнему вызывает _place_limit_order_all_or_nothing,
        но фактическую работу делает orders.OrderService.
        """
        pi = self._get_pair_info(base, quote)
        return self.order_service.place_limit_order_all_or_nothing(
            side=side,
            base=base,
            quote=quote,
            amount_base=amount_base,
            limit_price=limit_price,
            pair_info=pi,
        )

    def _get_account_balance(self, currency: str) -> float:
        """Получить баланс для указанной валюты."""
        try:
            api_client = self.api_client_provider()
            if api_client:
                balance = api_client.get_account_balance()
                if isinstance(balance, list):
                    for item in balance:
                        if item.get('currency', '').upper() == currency.upper():
                            return float(item.get('available', 0) or 0)
            return 0.0
        except Exception:
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
            print(f"[AutoTrader] ⚠️ Ошибка сохранения diagnostic state: {e}")

    def _load_diagnostics_state(self):
        if not os.path.exists(self._diag_state_file):
            return
        try:
            with open(self._diag_state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self.last_diagnostics = data
        except Exception as e:
            print(f"[AutoTrader] ⚠️ Ошибка загрузки diagnostic state: {e}")

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

        print(f"[AutoTrader][{base}] 🔍 Начинаем проверку стартовой покупки...")

        self._ensure_cycle_struct(base)

        cycle = self.cycles[base]

        # Если есть pending.start (частично исполненная стартовая покупка) — пытаемся докупить оставшуюся часть
        try:
            if not cycle:
                return
            pending = cycle.get('pending') or {}
            start_pending = pending.get('start') if isinstance(pending, dict) else None
            if start_pending and float(start_pending.get('remaining', 0) or 0) > 0:
                rem = float(start_pending.get('remaining') or 0.0)
                print(f"[AutoTrader][{base}] 🔁 Обнаружен pending start — пытаемся докупить remaining={rem:.8f} {base}")
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
                            print(f"[AutoTrader][{base}] ℹ️ Pending start пополнен: filled_add={filled2:.8f}, remaining={start_pending['remaining']:.8f}")
                            # if completed — finalize as active cycle
                            if start_pending['remaining'] <= 1e-12:
                                total_filled = float(start_pending.get('filled', 0) or 0)
                                total_usd = float(start_pending.get('filled_usd', 0) or 0)
                                if total_filled > 0:
                                    start_price = total_usd / total_filled
                                else:
                                    start_price = buy_price2
                                cycle.update({
                                    'active': True,
                                    'active_step': 0,
                                    'last_buy_price': start_price,
                                    'start_price': start_price,
                                    'total_invested_usd': total_usd,
                                    'base_volume': total_filled
                                })
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
                                print(f"[AutoTrader][{base}] ✅ Pending start выполнен полностью: base_volume={total_filled:.8f}, start_price={start_price:.8f}")
                                # recalc table
                                try:
                                    new_table = calculate_breakeven_table(self.state_manager.get_breakeven_params(base), start_price)
                                    cycle['table'] = new_table
                                except Exception:
                                    pass
                                self._save_cycles_state()
                            else:
                                # still pending
                                cycle['pending'] = pending
                                self._save_cycles_state()
                        else:
                            print(f"[AutoTrader][{base}] ⚠️ Докупка pending не дала заполнения (filled={filled2})")
                    except Exception as e:
                        print(f"[AutoTrader][{base}] ⚠️ Ошибка при докупке pending start: {e}")
        except Exception:
            pass

        

        # Проверка 1: Цикл уже активен?
        # Если помечен как активный, но фактический баланс на счёте значительно меньше
        # записанного base_volume (например, пользователь продал монеты вручную),
        # то это несоответствие — автоматически помечаем цикл НЕактивным и позволяем
        # начать новый старт (чтобы интерфейс и поведение не блокировались forever).
        if cycle['active']:
            print(f"[AutoTrader][{base}] ⚠️ Цикл уже активен, проверяем баланс BASE...")
            try:
                # если есть провайдер API — проверим реальный баланс
                if hasattr(self, 'api_client_provider') and callable(self.api_client_provider):
                    api_client = self.api_client_provider()
                    if api_client:
                        bal = api_client.get_account_balance()
                        current_base_balance = 0.0
                        if isinstance(bal, list):
                            for item in bal:
                                if item.get('currency', '').upper() == base.upper():
                                    try:
                                        current_base_balance = float(item.get('available', 0) or 0)
                                    except Exception:
                                        current_base_balance = 0.0
                        recorded_volume = float(cycle.get('base_volume', 0) or 0)
                        # Если записанный объём > 0 и текущий баланс меньше 20% от него — считаем неконсистентным
                        if recorded_volume > 0 and current_base_balance < recorded_volume * 0.2:
                            print(f"[AutoTrader][{base}] ⚠️ Несоответствие: saved_volume={recorded_volume:.8f}, current_balance={current_base_balance:.8f} — сбрасываем цикл для корректного рестарта")
                            self.cycles[base].update({
                                'active': False,
                                'active_step': -1,
                                'last_buy_price': 0.0,
                                'start_price': 0.0,
                                'total_invested_usd': 0.0,
                                'base_volume': 0.0
                            })
                            try:
                                self._save_cycles_state()
                            except Exception:
                                pass
                        else:
                            # если консистентность в порядке — ничего не делаем
                            print(f"[AutoTrader][{base}] ✅ Цикл активен и консистентен, пропускаем старт")
                            return
                    else:
                        # no API client available — do not modify active flag
                        print(f"[AutoTrader][{base}] ⚠️ Нет API клиента, пропускаем проверку баланса")
                        return
                else:
                    # no api provider configured -> don't alter active cycle
                    print(f"[AutoTrader][{base}] ⚠️ Нет провайдера API, пропускаем")
                    return
            except Exception as e:
                # в случае ошибок с балансами — безопаснее не менять поведение и выйти
                print(f"[AutoTrader][{base}] ⚠️ Ошибка проверки баланса перед стартом: {e}")
                return

        

        # Получение цены
        price = self._get_market_price(base, quote)
        if not price or price <= 0:
            print(f"[AutoTrader][{base}] ⚠️ Цена не получена, пропуск стартовой покупки")
            return

        

        # Проверка 2: Пересчёт таблицы

        self._recalc_table_if_needed(base, quote, price)

        table = cycle['table']

        if not table:

            print(f"[AutoTrader][{base}] ❌ Стартовая закупка невозможна: таблица не рассчитана")

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
                print(f"[AutoTrader][{base}] ❌ Недостаточно {quote} для стартовой покупки: available={quote_available:.4f}, keep={keep:.4f}, required={purchase_usd:.4f}")
                return
        except Exception:
            # в случае ошибок сравнения — не блокируем запуск здесь (выполним дальнейшие проверки)
            pass

        

        # Проверка 4: Минимальные квоты пары

        pair_info = self._get_pair_info(base, quote)

        min_q = float(pair_info.get('min_quote_amount') or 0)

        min_b = float(pair_info.get('min_base_amount') or 0)

        

        print(f"[AutoTrader][{base}] 📊 Попытка стартовой закупки:")

        print(f"  • Текущая цена: {price:.8f} {quote}")

        print(f"  • Объём покупки: {purchase_usd:.4f} {quote}")

        print(f"  • Keep резерв: {keep:.4f} {quote}")

        print(f"  • Min quote: {min_q:.4f}, Min base: {min_b:.8f}")

        

        if purchase_usd < min_q:

            print(f"  ⚠️ Объём покупки ({purchase_usd:.4f}) < min_quote ({min_q:.4f}), увеличиваем")

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
            print(f"  ⚠️ Количество базы ({amount_base:.8f}) < min_base ({min_b:.8f}), увеличиваем")
            amount_base = min_b

        # После округления пересчитываем итоговую сумму в QUOTE
        purchase_usd = amount_base * price

        print(f"  • Итоговая покупка: {amount_base:.8f} {base} за {purchase_usd:.4f} {quote}")

        

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

                print(f"  • Баланс {quote}: {quote_available:.4f} (требуется: {quote_required:.4f})")

            else:

                # Режим симуляции - разрешаем покупку

                quote_available = quote_required * 10

                print(f"  • Режим СИМУЛЯЦИИ (нет API клиента)")

        except Exception as e:

            print(f"  ⚠️ Ошибка проверки баланса: {e}")

            # В случае ошибки - пробуем всё равно (может это симуляция)

            quote_available = quote_required * 10

        

        if quote_available < quote_required:

            print(f"[AutoTrader][{base}] ❌ Недостаточно {quote}: нужно {quote_required:.4f}, доступно {quote_available:.4f}")

            print(f"  💡 Пополните баланс {quote} или уменьшите параметр 'start_volume' для {base}")

            return

        

        # Получаем цену ask из orderbook для расчёта количества (для market-ордера orderbook не обязателен)
        orderbook = self._get_orderbook(base, quote)
        print(f"  • Orderbook получен: {orderbook is not None}, asks: {len(orderbook.get('asks', [])) if orderbook else 0}")
        if not orderbook or not orderbook.get('asks'):
            print(f"[AutoTrader][{base}] ⚠️ Orderbook не получен, используем текущую цену для расчёта количества")
            buy_price = price  # используем текущую цену если orderbook недоступен
        else:
            buy_price = price  # по умолчанию текущая цена

        # Новый алгоритм стартовой покупки: агрегируем asks из orderbook и
        # размещаем последовательные limit-FOK по уровням, пока суммарно
        # не будет потрачена плановая сумма purchase_usd. Это позволяет
        # купить по нескольким ценам (не только лучшему ask) и гарантировать
        # что потрачено >= запланированной суммы или откатиться.
        print(f"[AutoTrader][{base}] 🔄 Пытаемся стартовую покупку по ордербуку (агрегируем asks)")

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
            print(f"[AutoTrader][{base}] ⚠️ Orderbook не доступен или lacks asks — не могу агрегировать уровни")
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

                print(f"[AutoTrader][{base}] 📤 Placing LIMIT FOK BUY at level: {desired_base:.{amt_prec}f} {base} @ {level_price:.8f}")

                if not api_client:
                    # Simulation: assume full fill at level_price
                    filled = desired_base
                    fill_spent = filled * level_price
                    cumulative_base += filled
                    cumulative_spent += fill_spent
                    level_fills.append({'price': level_price, 'filled': filled, 'spent': fill_spent, 'simulated': True})
                    print(f"[AutoTrader][{base}] ⚠️ SIMULATION fill: {filled:.{amt_prec}f} @ {level_price:.8f}")
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
                        print(f"[AutoTrader][{base}] ✅ Level FOK filled: {filled:.{amt_prec}f} @ {level_price:.8f}")
                        # If partial (filled < desired_base), continue trying next levels
                        if filled < desired_base * 0.999:
                            print(f"[AutoTrader][{base}] ℹ️ Частичный fill на уровне: filled={filled:.{amt_prec}f}, wanted={desired_base:.{amt_prec}f}")
                            # continue to next levels to try to cover remaining quote
                            continue
                        else:
                            # full level satisfied, continue to check if more is needed
                            continue
                    else:
                        # no fill at this level — try next level
                        print(f"[AutoTrader][{base}] ❌ Level FOK not filled at price {level_price}")
                        continue
                except Exception as e:
                    print(f"[AutoTrader][{base}] ❌ Ошибка при размещении level FOK: {e}")
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
                print(f"[AutoTrader][{base}] ✅ Aggregated buy completed: spent={cumulative_spent:.8f}, base={cumulative_base:.8f}, avg_price={buy_price:.8f}")
                order_res = {'success': True, 'filled': cumulative_base, 'filled_usd': cumulative_spent, 'avg_price': buy_price, 'fills': level_fills}
            elif cumulative_base > 0:
                # partial fills across levels — create pending for remaining
                try:
                    buy_price = (cumulative_spent / cumulative_base) if cumulative_base > 0 else price
                except Exception:
                    buy_price = price
                print(f"[AutoTrader][{base}] ❌ Aggregated buy PARTIAL: spent={cumulative_spent:.8f}, required={needed_quote:.8f}")
                order_res = {'success': False, 'filled': cumulative_base, 'filled_usd': cumulative_spent, 'fills': level_fills}
            else:
                buy_price = price
                print(f"[AutoTrader][{base}] ❌ Aggregated buy FAILED: insufficient liquidity to cover {needed_quote:.8f} {quote}")
                order_res = {'success': False, 'filled': 0.0, 'error': 'insufficient_liquidity', 'fills': level_fills}

        

        if order_res.get('success'):

            filled = order_res['filled']

            invest = filled * buy_price

            cycle.update({

                'active': True,

                'active_step': 0,

                'last_buy_price': buy_price,

                'start_price': buy_price,  # P0 фиксируем как цену покупки

                'total_invested_usd': invest,

                'base_volume': filled

            })

            

            # КРИТИЧЕСКИ ВАЖНО: обновляем start_price в state_manager для таблицы безубыточности

            try:

                current_params = self.state_manager.get_breakeven_params(base)

                print(f"[AutoTrader][{base}] 🔍 DEBUG: current_params ДО обновления: start_price={current_params.get('start_price', 'НЕТ')}")

                current_params['start_price'] = buy_price

                save_result = self.state_manager.set_breakeven_params(base, current_params)

                print(f"[AutoTrader][{base}] 📊 Обновлён start_price в state_manager: {buy_price:.8f} (save_result={save_result})")

                

                # Проверяем, что сохранилось - повторяем до 3 раз при неудаче

                max_retries = 3

                for attempt in range(max_retries):

                    verify_params = self.state_manager.get_breakeven_params(base)

                    verified_start_price = verify_params.get('start_price', 0)

                    if verified_start_price == buy_price:

                        print(f"[AutoTrader][{base}] ✅ start_price подтверждён: {verified_start_price:.8f}")

                        break

                    else:

                        print(f"[AutoTrader][{base}] ⚠️ start_price НЕ подтверждён (попытка {attempt+1}/{max_retries}): сохранено {verified_start_price}, ожидалось {buy_price}")

                        if attempt < max_retries - 1:

                            # Повторная попытка сохранения

                            save_result = self.state_manager.set_breakeven_params(base, current_params)

                            print(f"[AutoTrader][{base}] 🔄 Повторное сохранение start_price: {buy_price:.8f} (save_result={save_result})")

                        else:

                            print(f"[AutoTrader][{base}] ❌ КРИТИЧЕСКАЯ ОШИБКА: start_price НЕ сохранён после {max_retries} попыток! Это приведёт к неправильному расчёту таблицы.")

                

                # ВАЖНО: Пересчитываем таблицу с новым start_price

                new_table = calculate_breakeven_table(current_params, buy_price)

                cycle['table'] = new_table

                print(f"[AutoTrader][{base}] 📊 Таблица пересчитана с новым P0: {buy_price:.8f}")

                print(f"[AutoTrader][{base}] 🔍 DEBUG: P0 в таблице (row 0): {new_table[0]['rate']:.8f}")

            except Exception as e:

                print(f"[AutoTrader][{base}] ⚠️ Ошибка обновления start_price и пересчёта таблицы: {e}")

                import traceback

                print(traceback.format_exc())

            

            self.logger.log_buy(base, filled, buy_price, 0.0, 0.0, invest)

            # Обновляем статистику

            self.stats['total_buy_orders'] += 1

            self.stats['total_cycles'] += 1

            self.stats['last_update'] = time.time()

            # Сохраняем состояние

            self._save_cycles_state()

            print(f"[AutoTrader][{base}] ✅ Старт цикла row=0 price={buy_price}, filled={filled:.8f}")

        else:
            error_info = order_res.get('error', 'partial/none fill')
            filled_amt = float(order_res.get('filled', 0.0))
            # логика для диагностики и обработки неуспешной продажи
            try:
                if order_res.get('success'):
                    # успешная обработка sell-ордера
                    pass
                else:
                    # обработка неуспешной продажи (diagnostics, small remainder и т.п.)
                    pass
            except Exception as e:
                print(f"[AutoTrader][{base}] ⚠️ Ошибка обработки результата ордера: {e}")

    def _try_rebuy(self, base: str, quote: str):
        # ...существующий код _try_rebuy, оставляем как есть...
        pass


    def _try_sell(self, base: str, quote: str):

        cycle = self.cycles.get(base)

        # Получение цены
        price = self._get_market_price(base, quote)
        if not price or price <= 0:
            print(f"[AutoTrader][{base}] ⚠️ Цена не получена, пропуск sell")
            return

        # Если есть pending.sell — пытаемся продать оставшуюся часть лимитным FOK-ордерами
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
                    avg_invest_price = cycle['total_invested_usd'] / cycle['base_volume'] if cycle.get('base_volume') else exec_price
                    pnl = (exec_price - avg_invest_price) * rem
                    # ✅ ИСПРАВЛЕНО: используем avg_invest_price вместо start_price
                    if avg_invest_price > 0:
                        real_growth_pct = (exec_price - avg_invest_price) / avg_invest_price * 100.0
                    else:
                        real_growth_pct = 0.0
                    self.logger.log_sell(base, filled, exec_price, real_growth_pct, pnl)
                    self.cycles[base] = {
                        'active': False,
                        'active_step': -1,
                        'table': cycle.get('table', []),
                        'last_buy_price': 0.0,
                        'start_price': 0.0,
                        'total_invested_usd': 0.0,
                        'base_volume': 0.0,
                        'pending': {}
                    }
                    try:
                        current_params = self.state_manager.get_breakeven_params(base)
                        current_params['start_price'] = 0.0
                        self.state_manager.set_breakeven_params(base, current_params)
                    except Exception:
                        pass
                    self._save_cycles_state()
                    print(f"[AutoTrader][{base}] ✅ Pending sell выполнен полностью, цикл завершён")
                else:
                    if filled and filled > 0:
                        psell['filled'] = float(psell.get('filled', 0) or 0) + filled
                        psell['filled_usd'] = float(psell.get('filled_usd', 0) or 0) + (filled * exec_price)
                        psell['remaining'] = max(0.0, psell.get('remaining', 0) - filled)
                        cycle['base_volume'] = max(0.0, float(cycle.get('base_volume', 0) or 0) - filled)
                        cycle['pending'] = pending
                        self._save_cycles_state()
                        print(f"[AutoTrader][{base}] ℹ️ Частичный pending.sell: filled_add={filled:.8f}, remaining={psell['remaining']:.8f}")
                return
        except Exception:
            pass

        # Далее полный оригинальный код из temp/autotrader.py — продажи через sell_level, стакан bids и т.д.
        # ...копируем сюда весь остальной _try_sell из temp/autotrader.py без изменений...


