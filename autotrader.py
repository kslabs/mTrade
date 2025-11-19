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
   - "Всё или ничего" = если фактический исполненный объём < требуемого, считаем покупку не состоявшейся и НЕ записываем её.
6. Логирование:
   - Все попытки и результаты через trade_logger (buy/sell).

Требуемые зависимости:
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


class AutoTrader:
    def __init__(self, api_client_provider, ws_manager, state_manager):
        self.api_client_provider = api_client_provider
        self.ws_manager = ws_manager
        self.state_manager = state_manager
        self.running = False
        self._thread: Optional[Thread] = None
        self._sleep_interval = 1.0  # Уменьшен с 2.5 до 1.0 для более быстрой реакции
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
        self.logger = get_trade_logger()
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
                if cycle.get('active'):
                    state_to_save[base] = {
                        'active': cycle['active'],
                        'active_step': cycle['active_step'],
                        'last_buy_price': cycle['last_buy_price'],
                        'start_price': cycle['start_price'],
                        'total_invested_usd': cycle['total_invested_usd'],
                        'base_volume': cycle['base_volume'],
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
                
                # Восстанавливаем цикл
                self.cycles[base] = {
                    'active': saved_cycle['active'],
                    'active_step': saved_cycle['active_step'],
                    'table': [],  # таблица будет пересчитана
                    'last_buy_price': saved_cycle['last_buy_price'],
                    'start_price': saved_cycle['start_price'],
                    'total_invested_usd': saved_cycle['total_invested_usd'],
                    'base_volume': saved_cycle['base_volume']
                }
                restored_count += 1
                print(f"[AutoTrader][{base}] ✅ Восстановлен цикл: step={saved_cycle['active_step']}, "
                      f"invested={saved_cycle['total_invested_usd']:.2f}, volume={saved_cycle['base_volume']:.8f}")
            
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
        # Гарантируем подписку
        self._ensure_ws_subscription(base, quote)
        # Пробуем WS
        if self.ws_manager:
            data = self.ws_manager.get_data(pair)
            if data and data.get('ticker') and data['ticker'].get('last'):
                try:
                    return float(data['ticker']['last'])
                except Exception:
                    pass
        # REST fallback из основного API (публично)
        try:
            public_client = GateAPIClient(api_key=None, api_secret=None, network_mode='work')
            tick = public_client._request('GET', '/spot/tickers', params={'currency_pair': pair})
            if isinstance(tick, list) and tick:
                last = tick[0].get('last')
                if last is not None:
                    return float(last)
        except Exception as e:
            # Логируем ошибку получения цены (важно для диагностики)
            if not hasattr(self, '_price_error_logged'):
                self._price_error_logged = {}
            if pair not in self._price_error_logged:
                print(f"[AutoTrader][{base}] ⚠️ Ошибка получения цены через REST API: {e}")
                self._price_error_logged[pair] = True
        return None

    def _get_orderbook(self, base: str, quote: str) -> Optional[dict]:
        pair = f"{base}_{quote}".upper()
        if self.ws_manager:
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
        price_for_table = saved_start_price if saved_start_price > 0 else current_price
        
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
            'base_volume': 0.0
        })

    def _place_limit_order_all_or_nothing(self, side: str, base: str, quote: str, amount_base: float, limit_price: float):
        api_client = self.api_client_provider()
        currency_pair = f"{base}_{quote}".upper()
        if not api_client:
            # SIMULATION: считаем исполнено полностью
            print(f"[AutoTrader][{base}] ⚠️ СИМУЛЯЦИЯ: API клиент не доступен, ордер считается исполненным")
            return {'success': True, 'filled': amount_base, 'simulated': True}
        
        print(f"[AutoTrader][{base}] 📤 Отправка {side.upper()} ордера: {amount_base:.8f} {base} по цене {limit_price:.8f}")
        # FOK сначала
        try:
            result_fok = api_client.create_spot_order(
                currency_pair=currency_pair,
                side=side,
                amount=f"{amount_base:.8f}",
                price=f"{limit_price:.8f}",
                order_type='limit',
                time_in_force='fok'
            )
            # Проверяем результат (формат ответа может различаться; ищем executed "filled" или status)
            filled = self._parse_filled_amount(result_fok)
            if filled >= amount_base * 0.999:  # почти полный
                print(f"[AutoTrader][{base}] ✅ FOK ордер исполнен: {filled:.8f} {base}")
                return {'success': True, 'filled': filled, 'order': result_fok, 'tif': 'fok'}
            else:
                print(f"[AutoTrader][{base}] ⚠️ FOK частично: {filled:.8f}/{amount_base:.8f}, пробуем IOC")
        except Exception as e:
            print(f"[AutoTrader][{base}] ❌ FOK ошибка: {e}")
        # IOC как fallback
        try:
            result_ioc = api_client.create_spot_order(
                currency_pair=currency_pair,
                side=side,
                amount=f"{amount_base:.8f}",
                price=f"{limit_price:.8f}",
                order_type='limit',
                time_in_force='ioc'
            )
            filled = self._parse_filled_amount(result_ioc)
            if filled >= amount_base * 0.999:
                print(f"[AutoTrader][{base}] ✅ IOC ордер исполнен: {filled:.8f} {base}")
                return {'success': True, 'filled': filled, 'order': result_ioc, 'tif': 'ioc'}
            else:
                print(f"[AutoTrader][{base}] ❌ IOC частично исполнен: {filled:.8f}/{amount_base:.8f} (недостаточно)")
                return {'success': False, 'filled': filled, 'order': result_ioc, 'tif': 'ioc_partial'}
        except Exception as e:
            print(f"[AutoTrader][{base}] ❌ IOC ошибка: {e}")
            return {'success': False, 'filled': 0.0, 'error': str(e)}

    def _parse_filled_amount(self, order_result: dict) -> float:
        if not isinstance(order_result, dict):
            return 0.0
        # Gate.io возвращает поля: amount, left, filled_total, etc.
        try:
            amount = float(order_result.get('amount', 0))
            left = float(order_result.get('left', 0))
            filled = amount - left if amount > 0 else float(order_result.get('filled_total', 0))
            if filled < 0:
                filled = 0.0
            return filled
        except Exception:
            return 0.0

    def _get_pair_info(self, base: str, quote: str) -> dict:
        """Получить min_quote_amount/min_base_amount/precision (кешируется)."""
        pair = f"{base}_{quote}".upper()
        if pair in self._pair_info_cache:
            return self._pair_info_cache[pair]
        info = {"min_quote_amount": 0.0, "min_base_amount": 0.0}
        try:
            public = GateAPIClient(api_key=None, api_secret=None, network_mode='work')
            raw = public.get_currency_pair_details_exact(pair)
            if isinstance(raw, dict) and str(raw.get('id','')).upper() == pair:
                info["min_quote_amount"] = float(raw.get('min_quote_amount') or 0)
                info["min_base_amount"] = float(raw.get('min_base_amount') or 0)
            else:
                # fallback через список
                lst = public.get_currency_pair_details(pair)
                if isinstance(lst, list):
                    for it in lst:
                        if str(it.get('id','')).upper() == pair:
                            info["min_quote_amount"] = float(it.get('min_quote_amount') or 0)
                            info["min_base_amount"] = float(it.get('min_base_amount') or 0)
                            break
        except Exception:
            pass
        self._pair_info_cache[pair] = info
        return info

    # ------------------------ Логика цикла ------------------------
    def _try_start_cycle(self, base: str, quote: str, current_price: float):
        self._ensure_cycle_struct(base)
        cycle = self.cycles[base]
        
        # Проверка 1: Цикл уже активен?
        if cycle['active']:
            return
        
        # Проверка 2: Пересчёт таблицы
        self._recalc_table_if_needed(base, quote, current_price)
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
        base_balance_in_quote = base_balance * current_price
        
        # Если баланс BASE (в QUOTE) >= purchase_usd → цикл уже идёт или был прерван
        if base_balance_in_quote >= purchase_usd:
            # Логируем только раз в 10 минут
            if not hasattr(self, '_balance_check_logged'):
                self._balance_check_logged = {}
            last_log = self._balance_check_logged.get(base, 0)
            current_time = time.time()
            if current_time - last_log > 600:  # 10 минут
                print(f"[AutoTrader][{base}] ⏸️ Баланс BASE достаточен: {base_balance:.8f} {base} (~{base_balance_in_quote:.4f} {quote}) >= {purchase_usd:.4f} {quote}")
                print(f"  💡 Стартовая покупка не требуется. Продайте монеты или дождитесь условий для усреднения.")
                self._balance_check_logged[base] = current_time
            return
        
        # Проверка 4: Минимальные квоты пары
        pair_info = self._get_pair_info(base, quote)
        min_q = float(pair_info.get('min_quote_amount') or 0)
        min_b = float(pair_info.get('min_base_amount') or 0)
        
        print(f"[AutoTrader][{base}] 📊 Попытка стартовой закупки:")
        print(f"  • Текущая цена: {current_price:.8f} {quote}")
        print(f"  • Объём покупки: {purchase_usd:.4f} {quote}")
        print(f"  • Keep резерв: {keep:.4f} {quote}")
        print(f"  • Min quote: {min_q:.4f}, Min base: {min_b:.8f}")
        
        if purchase_usd < min_q:
            print(f"  ⚠️ Объём покупки ({purchase_usd:.4f}) < min_quote ({min_q:.4f}), увеличиваем")
            purchase_usd = min_q
        
        amount_base = purchase_usd / current_price if current_price > 0 else 0
        if amount_base < min_b:
            print(f"  ⚠️ Количество базы ({amount_base:.8f}) < min_base ({min_b:.8f}), увеличиваем")
            amount_base = min_b
            purchase_usd = amount_base * current_price
        
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
        
        # Получаем цену ask из orderbook для гарантированного исполнения
        orderbook = self._get_orderbook(base, quote)
        buy_price = current_price  # по умолчанию текущая цена
        
        if orderbook and orderbook.get('asks'):
            try:
                # Берём лучшую цену продавца (ask) для покупки
                asks = orderbook['asks']
                if asks and len(asks) > 0:
                    best_ask = float(asks[0][0])
                    buy_price = best_ask
                    print(f"  • Цена покупки (ask): {buy_price:.8f} {quote}")
            except Exception:
                pass
        
        # Пересчитываем количество для цены ask
        amount_base = purchase_usd / buy_price if buy_price > 0 else 0
        if amount_base < min_b:
            amount_base = min_b
            purchase_usd = amount_base * buy_price
        
        print(f"  • Финальная покупка: {amount_base:.8f} {base} по цене {buy_price:.8f}")
        print(f"[AutoTrader][{base}] 🔄 Отправка ордера на покупку...")
        order_res = self._place_limit_order_all_or_nothing('buy', base, quote, amount_base, buy_price)
        
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
                
                # Проверяем, что сохранилось
                verify_params = self.state_manager.get_breakeven_params(base)
                print(f"[AutoTrader][{base}] 🔍 DEBUG: start_price ПОСЛЕ сохранения: {verify_params.get('start_price', 'НЕТ')}")
                
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
            print(f"[AutoTrader][{base}] ❌ Старт цикла НЕ выполнен: {error_info}")

    def _try_rebuy(self, base: str, quote: str, current_price: float):
        cycle = self.cycles.get(base)
        if not cycle or not cycle.get('active'):
            return
        table = cycle.get('table') or []
        active_step = cycle['active_step']
        next_step = active_step + 1
        if next_step >= len(table):
            return
        last_buy = cycle['last_buy_price']
        params_row = table[next_step]
        decrease_step_pct = abs(params_row['decrease_step_pct'])  # положительное значение снижения
        if last_buy <= 0:
            return
        drop_pct = (last_buy - current_price) / last_buy * 100.0
        if drop_pct < decrease_step_pct:  # условие падения не достигнуто
            return
        # Проверяем ликвидность (упрощённо: наличие нужного объёма в bids/asks)
        orderbook = self._get_orderbook(base, quote)
        if not orderbook:
            return
        level = int(self.state_manager.get_breakeven_params(base).get('orderbook_level', 1))
        asks = orderbook.get('asks') or []
        if len(asks) < level:
            return
        level_price, level_amount = 0.0, 0.0
        try:
            # asks: [[price, amount], ...]
            level_price = float(asks[level - 1][0])
            level_amount = float(asks[level - 1][1])
        except Exception:
            return
        purchase_usd = float(params_row['purchase_usd'])
        # Учитываем минимальные квоты
        pair_info = self._get_pair_info(base, quote)
        min_q = float(pair_info.get('min_quote_amount') or 0)
        min_b = float(pair_info.get('min_base_amount') or 0)
        if purchase_usd < min_q:
            purchase_usd = min_q
        amount_needed = purchase_usd / current_price if current_price > 0 else 0
        if amount_needed < min_b:
            amount_needed = min_b
        # Ликвидность на уровне
        if level_amount < amount_needed * 0.95:
            return
        order_res = self._place_limit_order_all_or_nothing('buy', base, quote, amount_needed, level_price)
        if order_res.get('success'):
            filled = order_res['filled']
            invest = filled * level_price
            cycle['active_step'] = next_step
            cycle['last_buy_price'] = level_price
            cycle['total_invested_usd'] += invest
            cycle['base_volume'] += filled
            total_drop_pct = table[next_step]['cumulative_decrease_pct']
            self.logger.log_buy(base, filled, level_price, decrease_step_pct, total_drop_pct, cycle['total_invested_usd'])
            # Обновляем статистику
            self.stats['total_buy_orders'] += 1
            self.stats['last_update'] = time.time()
            # Сохраняем состояние
            self._save_cycles_state()
            print(f"[AutoTrader] Rebuy {base} step={next_step} price={level_price}")
        else:
            print(f"[AutoTrader] Rebuy пропущен {base}: partial/none fill")

    def _try_sell(self, base: str, quote: str, current_price: float):
        cycle = self.cycles.get(base)
        if not cycle or not cycle.get('active'):
            return
        table = cycle.get('table') or []
        active_step = cycle['active_step']
        if active_step >= len(table):
            return
        row = table[active_step]
        start_price = cycle['start_price']
        target_delta_pct = row['target_delta_pct']
        growth_pct = (current_price - start_price) / start_price * 100.0
        if growth_pct < target_delta_pct:
            return
        # Sell all base except keep reserve (keep в QUOTE, так что продаём весь BASE)
        base_volume = cycle['base_volume']
        if base_volume <= 0:
            return
        order_res = self._place_limit_order_all_or_nothing('sell', base, quote, base_volume, current_price)
        if order_res.get('success'):
            filled = order_res['filled']
            pnl = (current_price - (cycle['total_invested_usd'] / cycle['base_volume'])) * filled
            self.logger.log_sell(base, filled, current_price, growth_pct, pnl)
            # Обновляем статистику
            self.stats['total_sell_orders'] += 1
            self.stats['last_update'] = time.time()
            print(f"[AutoTrader] Sell {base} step={active_step} price={current_price} pnl={pnl:.4f}")
            print(f"[AutoTrader][{base}] 🔄 Цикл завершён! PnL: {pnl:.4f} USDT. Готов к новому циклу.")
            # Сброс цикла
            self.cycles[base] = {
                'active': False,
                'active_step': -1,
                'table': table,  # сохраняем последнюю таблицу для визуализации
                'last_buy_price': 0.0,
                'start_price': 0.0,
                'total_invested_usd': 0.0,
                'base_volume': 0.0
            }
            
            # КРИТИЧЕСКИ ВАЖНО: обнуляем start_price в state_manager для нового цикла
            try:
                current_params = self.state_manager.get_breakeven_params(base)
                current_params['start_price'] = 0.0
                self.state_manager.set_breakeven_params(base, current_params)
                print(f"[AutoTrader][{base}] 📊 start_price обнулён в state_manager, готов к новому циклу")
            except Exception as e:
                print(f"[AutoTrader][{base}] ⚠️ Ошибка обнуления start_price: {e}")
            
            # Сохраняем состояние (удаляем активный цикл)
            self._save_cycles_state()
        else:
            print(f"[AutoTrader] Sell попытка неуспешна {base}: partial/none fill")

    # ------------------------ Основной цикл ------------------------
    def _run(self):
        quote = self.state_manager.get_active_quote_currency()
        
        # Проверка API клиента при первом запуске
        if not hasattr(self, '_api_checked'):
            api_client = self.api_client_provider()
            if api_client:
                print(f"[AutoTrader] ✅ API клиент инициализирован (реальная торговля)")
            else:
                print(f"[AutoTrader] ⚠️ API клиент не доступен (режим симуляции)")
            self._api_checked = True
        
        while self.running:
            try:
                if not self.state_manager.get_auto_trade_enabled():
                    time.sleep(self._sleep_interval)
                    continue
                perms = self.state_manager.get_trading_permissions()
                if not isinstance(perms, dict) or len(perms) == 0:
                    # Нет явных разрешений — ничего не делаем, чтобы не торговать случайно
                    if not hasattr(self, '_no_perms_warned'):
                        print(f"[AutoTrader] ⚠️ Нет разрешений на торговлю валютами")
                        self._no_perms_warned = True
                    time.sleep(self._sleep_interval)
                    continue
                
                # Диагностика: показываем разрешения один раз при старте цикла
                if not hasattr(self, '_permissions_logged'):
                    enabled_list = [k for k, v in perms.items() if v]
                    disabled_list = [k for k, v in perms.items() if not v]
                    print(f"[AutoTrader] 🔄 Цикл запущен с разрешениями:")
                    print(f"  • Включено: {enabled_list}")
                    if disabled_list:
                        print(f"  • Выключено: {disabled_list}")
                    self._permissions_logged = True
                
                # Счетчик активных валют для диагностики
                enabled_count = sum(1 for enabled in perms.values() if enabled)
                processed_count = 0
                
                # Счётчик циклов (для периодического логирования)
                if not hasattr(self, '_cycle_count'):
                    self._cycle_count = 0
                self._cycle_count += 1
                log_details = (self._cycle_count % 10 == 1)  # Подробные логи раз в 10 циклов
                
                for base, enabled in perms.items():
                    if not enabled:
                        # Валюта отключена - пропускаем
                        continue
                    base = base.upper()
                    processed_count += 1
                    
                    if log_details:
                        print(f"[AutoTrader][{base}] Обработка: получение цены {base}_{quote}...")
                    
                    # гарантия подписки
                    self._ensure_ws_subscription(base, quote)
                    price = self._get_market_price(base, quote)
                    
                    if not price or price <= 0:
                        # Нет цены — пропуск итерации по этой валюте
                        if log_details:
                            print(f"[AutoTrader][{base}] ⚠️ Цена не получена, пропуск")
                        continue
                    
                    if log_details:
                        print(f"[AutoTrader][{base}] Цена получена: {price:.8f} {quote}")
                    
                    self._try_start_cycle(base, quote, price)
                    self._try_rebuy(base, quote, price)
                    self._try_sell(base, quote, price)
                
                # Итоговый отчёт (раз в 10 циклов)
                if log_details:
                    active_cycles = sum(1 for c in self.cycles.values() if c.get('active'))
                    # Обновляем статистику активных циклов
                    self.stats['active_cycles'] = active_cycles
                    self.stats['last_update'] = time.time()
                    print(f"[AutoTrader] 📈 Итого: обработано {processed_count} валют, активных циклов: {active_cycles}")
                
                time.sleep(self._sleep_interval)
            except Exception as e:
                print(f"[AutoTrader] Ошибка цикла: {e}")
                time.sleep(self._sleep_interval)

# Конец файла
