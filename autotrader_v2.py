"""
AutoTrader V2 - Чистая реализация с правильной архитектурой

ПРИНЦИПЫ:
1. Простота > Сложность
2. Одна валюта = Одно состояние
3. Состояние хранится В ПАМЯТИ (не в файле!)
4. Файл используется только для восстановления после перезапуска

СОСТОЯНИЯ ЦИКЛА:
- IDLE: Нет цикла, можно начинать новый
- ACTIVE: Цикл активен, идёт торговля (ребай/продажа)

ВСЁ. Никаких промежуточных состояний!
"""

import time
import threading
import traceback
from typing import Dict, Optional
from dataclasses import dataclass, asdict
from enum import Enum

from breakeven_calculator import calculate_breakeven_table
from trade_logger import get_trade_logger
from gate_api_client import GateAPIClient


class CycleState(Enum):
    """Состояние торгового цикла"""
    IDLE = "idle"      # Нет цикла
    ACTIVE = "active"  # Цикл активен


@dataclass
class TradingCycle:
    """Состояние торгового цикла для одной валюты"""
    state: CycleState = CycleState.IDLE
    
    # Данные активного цикла
    cycle_id: int = 0  # Уникальный ID текущего цикла (инкрементируется при каждой активации)
    total_cycles_count: int = 0  # Общее количество завершённых циклов
    active_step: int = -1
    start_price: float = 0.0
    last_buy_price: float = 0.0
    total_invested_usd: float = 0.0
    base_volume: float = 0.0
    
    # Таблица breakeven
    table: list = None
    
    # Метки времени
    cycle_started_at: float = 0.0
    last_action_at: float = 0.0
    last_buy_attempt_at: float = 0.0  # НОВОЕ: Время последней попытки покупки (для защиты от дублирования)
    
    # Флаг ручной паузы (для блокировки автостарта после ручного сброса)
    manual_pause: bool = False
    
    def __post_init__(self):
        if self.table is None:
            self.table = []
    
    def is_active(self) -> bool:
        """Цикл активен?"""
        return self.state == CycleState.ACTIVE
    
    def reset(self, manual: bool = False):
        """Сброс цикла в IDLE
        
        Args:
            manual: True если сброс вручную (блокирует автостарт), False если автоматический
        """
        # Если цикл был активен - считаем его завершённым
        if self.state == CycleState.ACTIVE:
            self.total_cycles_count += 1
            print(f"[CYCLE] [OK] Цикл #{self.cycle_id} завершён! Всего циклов: {self.total_cycles_count}")
        
        self.state = CycleState.IDLE
        self.active_step = -1
        self.start_price = 0.0
        self.last_buy_price = 0.0
        self.total_invested_usd = 0.0
        self.base_volume = 0.0
        self.cycle_started_at = 0.0
        self.last_action_at = time.time()
        self.manual_pause = manual  # Устанавливаем флаг ручной паузы
    
    def activate(self, start_price: float, base_volume: float, invested_usd: float):
        """Активация цикла после стартовой покупки
        
        ВАЖНО: Каждая активация = НОВЫЙ цикл с НОВЫМ ID
        """
        # Инкрементируем ID цикла (каждая стартовая покупка = новый цикл!)
        self.cycle_id += 1
        
        self.state = CycleState.ACTIVE
        self.active_step = 0
        self.start_price = start_price
        self.last_buy_price = start_price
        self.total_invested_usd = invested_usd
        self.base_volume = base_volume
        self.cycle_started_at = time.time()
        self.last_action_at = time.time()
        self.manual_pause = False  # Снимаем флаг паузы при активации
        
        print(f"[CYCLE] [*] Новый цикл #{self.cycle_id} активирован!")


class AutoTraderV2:
    """
    Автотрейдер V2 - Чистая реализация
    
    АРХИТЕКТУРА:
    1. Один Lock на валюту (защита от race condition)
    2. Состояние В ПАМЯТИ (словарь cycles)
    3. Простая машина состояний (IDLE/ACTIVE)
    4. Веб-API для мониторинга
    """
    
    def __init__(self, api_client_provider, ws_manager, state_manager):
        self.api_client_provider = api_client_provider
        self.ws_manager = ws_manager
        self.state_manager = state_manager
        
        # Флаг работы
        self.running = False
        self._thread: Optional[threading.Thread] = None
        
        # Состояние циклов (В ПАМЯТИ!)
        self.cycles: Dict[str, TradingCycle] = {}
        self._locks: Dict[str, threading.Lock] = {}
        
        # НОВОЕ: Lock для сохранения файла состояния (предотвращает race condition)
        self._save_state_lock = threading.Lock()
        
        # Логгер
        self.logger = get_trade_logger()
        
        # Статистика для API
        self.stats = {
            'total_cycles': 0,
            'active_cycles': 0,
            'total_buy_orders': 0,
            'total_sell_orders': 0,
            'last_update': time.time()
        }
        
        # Интервал главного цикла
        self._sleep_interval = 1.0  # 1 секунда (не спешим!)
        
        # НОВОЕ: Загружаем и синхронизируем состояние при старте
        self._load_and_sync_state()
        
        print("[AutoTraderV2] Инициализация завершена")
    
    def _load_and_sync_state(self):
        """
        Загрузка состояния из файла и синхронизация с разрешениями
        
        ЛОГИКА:
        1. Загружаем autotrader_cycles_state.json (если существует)
        2. Получаем список разрешений из state_manager
        3. Синхронизируем: добавляем валюты с разрешениями, которых нет в файле
        4. Сохраняем обновлённое состояние
        """
        import json
        import os
        from datetime import datetime
        
        STATE_FILE = "autotrader_cycles_state.json"
        
        # 1. Загружаем существующее состояние
        loaded_cycles = {}
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    loaded_cycles = data if isinstance(data, dict) else {}
                print(f"[AutoTraderV2] Загружено {len(loaded_cycles)} циклов из файла")
            except Exception as e:
                print(f"[AutoTraderV2] [WARN] Ошибка загрузки состояния: {e}")
        
        # 2. Получаем разрешения
        perms = self.state_manager.get_trading_permissions()
        enabled_currencies = [curr for curr, enabled in perms.items() if enabled]
        print(f"[AutoTraderV2] Разрешений на торговлю: {len(enabled_currencies)}")
        
        # 3. Синхронизируем
        added_count = 0
        for curr in enabled_currencies:
            if curr not in loaded_cycles:
                # Создаём пустой цикл для новой валюты
                loaded_cycles[curr] = {
                    "active": False,
                    "active_step": -1,
                    "last_buy_price": 0.0,
                    "start_price": 0.0,
                    "total_invested_usd": 0.0,
                    "base_volume": 0.0,
                    "table": [],
                    "status": "idle",
                    "manual_pause": False,
                    "saved_at": datetime.now().timestamp()
                }
                added_count += 1
                print(f"[AutoTraderV2] Добавлена новая валюта: {curr}")
        
        # 4. Загружаем в память
        for base, cycle_data in loaded_cycles.items():
            cycle = TradingCycle()
            
            # Восстанавливаем счётчики
            cycle.cycle_id = cycle_data.get("cycle_id", 0)
            cycle.total_cycles_count = cycle_data.get("total_cycles_count", 0)
            
            # ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ ДЛЯ ОТЛАДКИ
            print(f"[LOAD_STATE][{base}] Загрузка из файла:")
            print(f"  - active (из файла): {cycle_data.get('active')}")
            print(f"  - cycle_id: {cycle_data.get('cycle_id', 0)}")
            print(f"  - base_volume: {cycle_data.get('base_volume', 0.0)}")
            print(f"  - total_invested_usd: {cycle_data.get('total_invested_usd', 0.0)}")
            
            # Восстанавливаем состояние из данных
            if cycle_data.get("active"):
                cycle.state = CycleState.ACTIVE
                cycle.active_step = cycle_data.get("active_step", -1)
                cycle.start_price = cycle_data.get("start_price", 0.0)
                cycle.last_buy_price = cycle_data.get("last_buy_price", 0.0)
                cycle.total_invested_usd = cycle_data.get("total_invested_usd", 0.0)
                cycle.base_volume = cycle_data.get("base_volume", 0.0)
                cycle.table = cycle_data.get("table", [])
                
                print(f"[LOAD_STATE][{base}] [+] Цикл АКТИВИРОВАН в памяти:")
                print(f"  - cycle.state = {cycle.state}")
                print(f"  - cycle.is_active() = {cycle.is_active()}")
                print(f"  - cycle.base_volume = {cycle.base_volume}")
                print(f"  - cycle.total_invested_usd = {cycle.total_invested_usd}")
            else:
                cycle.state = CycleState.IDLE
                print(f"[LOAD_STATE][{base}] Цикл IDLE (неактивен)")
            
            cycle.manual_pause = cycle_data.get("manual_pause", False)
            
            self.cycles[base] = cycle
        
        # 5. Сохраняем обновлённое состояние, если добавили новые валюты
        if added_count > 0:
            try:
                # Создаём backup перед сохранением
                if os.path.exists(STATE_FILE):
                    import shutil
                    backup_name = f"{STATE_FILE}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    shutil.copy2(STATE_FILE, backup_name)
                
                with open(STATE_FILE, "w", encoding="utf-8") as f:
                    json.dump(loaded_cycles, f, indent=2, ensure_ascii=False)
                
                print(f"[AutoTraderV2] Добавлено {added_count} новых валют, файл обновлён")
            except Exception as e:
                print(f"[AutoTraderV2] [WARN] Не удалось сохранить состояние: {e}")
        
        print(f"[AutoTraderV2] Итого загружено циклов: {len(self.cycles)}")
    
    def _save_state(self, base: str = None):
        """
        Сохранить состояние цикла(ов) в файл
        
        Args:
            base: Валюта для сохранения. Если None - сохраняются все валюты
        
        ВАЖНО: Использует Lock для предотвращения race condition при параллельном сохранении
        """
        import json
        import os
        from datetime import datetime
        
        STATE_FILE = "autotrader_cycles_state.json"
        
        # 🔴 КРИТИЧЕСКИ ВАЖНО: Lock для предотвращения race condition!
        with self._save_state_lock:
            try:
                # Загружаем текущий файл
                state_data = {}
                if os.path.exists(STATE_FILE):
                    with open(STATE_FILE, "r", encoding="utf-8") as f:
                        state_data = json.load(f)
                
                # Обновляем данные для указанной валюты или всех валют
                currencies_to_save = [base] if base else self.cycles.keys()
                
                for curr in currencies_to_save:
                    cycle = self.cycles.get(curr)
                    if not cycle:
                        continue
                    
                    # Конвертируем состояние в JSON-формат
                    state_data[curr] = {
                        "active": cycle.is_active(),
                        "cycle_id": cycle.cycle_id,
                        "total_cycles_count": cycle.total_cycles_count,
                        "active_step": cycle.active_step,
                        "start_price": cycle.start_price,
                        "last_buy_price": cycle.last_buy_price,
                        "total_invested_usd": cycle.total_invested_usd,
                        "base_volume": cycle.base_volume,
                        "table": cycle.table if cycle.table else [],
                        "status": cycle.state.value,
                        "manual_pause": cycle.manual_pause,
                        "saved_at": datetime.now().timestamp()
                    }
                
                # Сохраняем в файл
                with open(STATE_FILE, "w", encoding="utf-8") as f:
                    json.dump(state_data, f, indent=2, ensure_ascii=False)
                
            except Exception as e:
                print(f"[AutoTraderV2] [ERROR] Не удалось сохранить состояние: {e}")
    
    def start(self):
        """Запуск автотрейдера"""
        if self.running:
            return False
        
        self.running = True
        self._thread = threading.Thread(target=self._main_loop, daemon=True)
        self._thread.start()
        
        print("[AutoTraderV2] [OK] Запущен")
        return True
    
    def stop(self):
        """Остановка автотрейдера"""
        self.running = False
        print("[AutoTraderV2] ⏹️ Остановлен")
        return True
    
    def _get_lock(self, base: str) -> threading.Lock:
        """Получить Lock для валюты (создаётся автоматически)"""
        if base not in self._locks:
            self._locks[base] = threading.Lock()
        return self._locks[base]
    
    def _ensure_cycle(self, base: str):
        """Гарантировать наличие объекта цикла"""
        if base not in self.cycles:
            self.cycles[base] = TradingCycle()
    
    def _save_cycle_state(self, base: str):
        """
        Сохранить состояние цикла в файл
        
        Вызывается после изменения состояния (reset, activate, resume)
        """
        import json
        import os
        from datetime import datetime
        
        STATE_FILE = "autotrader_cycles_state.json"
        
        try:
            # Загружаем текущее состояние из файла
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = {}
            
            # Получаем цикл
            cycle = self.cycles.get(base)
            if not cycle:
                return
            
            # Обновляем данные для этой валюты
            data[base] = {
                "active": cycle.is_active(),
                "cycle_id": cycle.cycle_id,  # Сохраняем ID цикла
                "total_cycles_count": cycle.total_cycles_count,  # Сохраняем счётчик циклов
                "active_step": cycle.active_step,
                "start_price": cycle.start_price,
                "last_buy_price": cycle.last_buy_price,
                "total_invested_usd": cycle.total_invested_usd,
                "base_volume": cycle.base_volume,
                "table": cycle.table if cycle.table else [],
                "status": cycle.state.value,
                "manual_pause": cycle.manual_pause,
                "saved_at": datetime.now().timestamp()
            }
            
            # Сохраняем в файл
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"[{base}] Состояние сохранено в файл")
            
        except Exception as e:
            print(f"[{base}] [WARN] Не удалось сохранить состояние: {e}")
    
    def _main_loop(self):
        """
        ГЛАВНЫЙ ЦИКЛ
        
        Простая логика:
        1. Получить список валют
        2. Для каждой валюты:
           - Получить Lock
           - Проверить состояние
           - Выполнить действие (start/rebuy/sell)
        3. Спать 1 секунду
        """
        
        quote = self.state_manager.get_active_quote_currency()
        print(f"[AutoTraderV2] Главный цикл запущен, quote={quote}")
        
        # Счётчик итераций для периодического отчёта
        iteration = 0
        
        while self.running:
            iteration += 1
            try:
                # Проверка: авто-торговля включена?
                auto_enabled = self.state_manager.get_auto_trade_enabled()
                if not auto_enabled:
                    if iteration % 60 == 1:  # Каждые 60 секунд
                        print("[AutoTraderV2] ⏸️ Автоторговля выключена")
                    time.sleep(self._sleep_interval)
                    continue
                
                # Получаем разрешения на торговлю
                perms = self.state_manager.get_trading_permissions()
                if not perms:
                    if iteration % 60 == 1:
                        print("[AutoTraderV2] [WARN] Нет разрешений на торговлю (perms пуст)")
                    time.sleep(self._sleep_interval)
                    continue
                
                # Перебираем валюты (ЛОГИРУЕМ ТОЛЬКО ИЗМЕНЕНИЯ!)
                enabled_count = sum(1 for v in perms.values() if v)
                
                for base in perms:
                    if not perms.get(base, False):
                        continue
                    
                    # Убираем избыточное логирование "Начало обработки..."
                    
                    try:
                        # ШАГ 1: Читаем состояние (под lock, быстро)
                        lock = self._get_lock(base)
                        
                        with lock:
                            self._ensure_cycle(base)
                            cycle = self.cycles[base]
                            
                            # Копируем нужные данные
                            is_active = cycle.is_active()
                            is_paused = cycle.manual_pause
                            active_step = cycle.active_step
                        
                        # ШАГ 2: Получаем цену (БЕЗ lock! Это внешний API)
                        price = self._get_market_price(base, quote)
                        
                        if not price or price <= 0:
                            # Логируем только ошибки
                            if iteration % 60 == 1:  # Раз в минуту
                                print(f"[{base}] [WARN] Не удалось получить цену")
                            continue
                        
                        # ШАГ 3: Принимаем решение и выполняем действия
                        if is_active:
                            # Цикл АКТИВЕН - пытаемся продать/докупить
                            
                            # Получаем уровень стакана из текущей строки таблицы
                            with self._get_lock(base):
                                cycle = self.cycles[base]
                                if cycle.table and active_step >= 0 and active_step < len(cycle.table):
                                    table_orderbook_level = int(cycle.table[active_step].get('orderbook_level', 1))
                                    orderbook_level = max(0, table_orderbook_level - 1)
                                else:
                                    orderbook_level = 0
                            
                            # Для проверки условия используем ticker.last
                            # Для размещения ордера используем цену из стакана
                            market_price = price
                            
                            # Получаем цену из стакана на нужном уровне (bids для продажи)
                            orderbook_price = self._get_orderbook_price(base, quote, orderbook_level, 'bids')
                            if not orderbook_price:
                                orderbook_price = market_price
                            
                            # Цикл АКТИВЕН → пытаемся продать
                            self._try_sell(base, quote, market_price, orderbook_price)
                            
                            # Пытаемся докупить, если цена упала
                            self._try_rebuy(base, quote, market_price)
                        else:
                            # Цикл НЕ АКТИВЕН
                            if is_paused:
                                # Не логируем паузу каждую секунду
                                pass
                            else:
                                # ✅ ПРАВИЛЬНАЯ ЛОГИКА: Проверяем баланс
                                has_balance = self._check_balance_exists(base, quote, price)
                                
                                if has_balance:
                                    # ✅ Есть остатки монет → пытаемся продать
                                    # Получаем orderbook_level из параметров (для шага 0)
                                    params = self.state_manager.get_breakeven_params(base)
                                    if params:
                                        orderbook_level_raw = float(params.get('orderbook_level', 1.0))
                                        orderbook_level = max(0, int(orderbook_level_raw) - 1)
                                    else:
                                        orderbook_level = 0
                                    
                                    # Получаем цену из стакана
                                    orderbook_price = self._get_orderbook_price(base, quote, orderbook_level, 'bids')
                                    if not orderbook_price:
                                        orderbook_price = price
                                    
                                    # Пытаемся продать остатки (в специальном режиме)
                                    self._try_sell_idle_balance(base, quote, price, orderbook_price)
                                else:
                                    # ✅ Баланс чист → стартуем новый цикл
                                    self._try_start_cycle(base, quote, price)
                    
                    except Exception as e:
                        print(f"[{base}] Ошибка обработки: {e}")
            
            except Exception as e:
                print(f"[MainLoop] Ошибка: {e}")
            
            # Спим между итерациями
            time.sleep(self._sleep_interval)
    
    def _get_market_price(self, base: str, quote: str) -> Optional[float]:
        """Получить текущую рыночную цену"""
        try:
            # Сначала пробуем из WebSocket
            if self.ws_manager:
                pair = f"{base}_{quote}".upper()
                data = self.ws_manager.get_data(pair)
                if data and data.get('ticker'):
                    last = data['ticker'].get('last')
                    if last:
                        return float(last)
            
            # Fallback на REST API
            public = GateAPIClient(api_key=None, api_secret=None, network_mode='work')
            pair = f"{base}_{quote}".upper()
            tick = public._request('GET', '/spot/tickers', params={'currency_pair': pair})
            if isinstance(tick, list) and tick:
                return float(tick[0].get('last', 0))
        
        except Exception as e:
            print(f"[{base}] Ошибка получения цены: {e}")
        
        return None
    
    def _get_orderbook_price(self, base: str, quote: str, orderbook_level: int, side: str = 'bids') -> Optional[float]:
        """
        Получить цену из определённого уровня стакана
        
        Args:
            base: базовая валюта (например, ETH)
            quote: валюта котировки (например, USDT)
            orderbook_level: уровень стакана (0-based индекс)
            side: 'bids' для цен покупки или 'asks' для цен продажи
        
        Returns:
            Цена на указанном уровне стакана или None в случае ошибки
        """
        try:
            # Пробуем из WebSocket
            if self.ws_manager:
                pair = f"{base}_{quote}".upper()
                data = self.ws_manager.get_data(pair)
                if data and data.get('orderbook'):
                    orderbook = data['orderbook']
                    levels = orderbook.get(side, [])
                    if levels and orderbook_level < len(levels):
                        price = float(levels[orderbook_level][0])
                        print(f"[{base}] Цена из стакана (WS) {side}[{orderbook_level}] = {price:.8f}")
                        return price
            
            # Fallback на REST API
            public = GateAPIClient(api_key=None, api_secret=None, network_mode='work')
            pair = f"{base}_{quote}".upper()
            orderbook_data = public._request('GET', '/spot/order_book', params={'currency_pair': pair, 'limit': 50})
            
            if orderbook_data:
                levels = orderbook_data.get(side, [])
                if levels and orderbook_level < len(levels):
                    price = float(levels[orderbook_level][0])
                    print(f"[{base}] Цена из стакана (REST) {side}[{orderbook_level}] = {price:.8f}")
                    return price
                else:
                    print(f"[{base}] [WARN] Уровень стакана {orderbook_level} недоступен (доступно уровней: {len(levels)})")
        
        except Exception as e:
            print(f"[{base}] Ошибка получения цены из стакана: {e}")
        
        return None
    
    # ============================================================================
    # ТОРГОВАЯ ЛОГИКА - СТАРТОВАЯ ПОКУПКА
    # ============================================================================
    
    def _check_balance_exists(self, base: str, quote: str, price: float) -> bool:
        """
        Проверка наличия остатков базовой валюты на балансе.
        
        ✅ ВАЖНО: Эта функция ТОЛЬКО проверяет баланс, НЕ блокирует торговлю!
        
        ЛОГИКА:
        1. Получаем баланс базовой валюты
        2. Сравниваем с минимальным объёмом для шага 0
        3. Возвращаем True если есть остатки, False если баланс чист
        
        Возвращает:
            True - есть остатки монет (нужно продать)
            False - баланс чист (можно стартовать новый цикл)
        """
        try:
            # ШАГ 1: Получаем баланс (БЕЗ lock - это API запрос)
            api_client = self.api_client_provider()
            if not api_client:
                return False  # API недоступен → считаем баланс чистым
            
            all_balances = api_client.get_account_balance()
            balance_base = next((b for b in all_balances if b.get('currency') == base), None)
            
            if balance_base:
                available_base = float(balance_base.get('available', 0))
            else:
                available_base = 0.0
            
            # ШАГ 2: Получаем параметры и рассчитываем минимальный объём
            params = self.state_manager.get_breakeven_params(base)
            if not params:
                return False  # Параметры недоступны → считаем баланс чистым
            
            table = calculate_breakeven_table(params, current_price=price)
            if not table or len(table) == 0:
                return False  # Таблица пуста → считаем баланс чистым
            
            # Вычисляем минимальный объём базовой валюты для первого шага
            first_step = table[0]
            min_base = first_step['purchase_usd'] / first_step['rate'] if first_step['rate'] > 0 else 0
            
            # ШАГ 3: Сравниваем баланс с минимумом
            has_balance = available_base >= min_base
            
            if has_balance:
                print(f"[{base}] ⚠️ Обнаружены остатки: {available_base:.8f} {base} (мин: {min_base:.8f})")
            
            return has_balance
            
        except Exception as e:
            print(f"[{base}] [WARN] Ошибка проверки баланса: {e}")
            return False  # В случае ошибки считаем баланс чистым
    
    def _try_start_cycle(self, base: str, quote: str, price: float):
        """
        Попытка создать стартовую покупку и запустить цикл
        
        ПРАВИЛЬНАЯ АРХИТЕКТУРА:
        1. Все API запросы БЕЗ lock
        2. Только изменение состояния ПОД lock (быстро)
        
        ЗАЩИТА ОТ RACE CONDITION:
        Проверка и установка флага _buying_in_progress происходят АТОМАРНО под одним lock
        """
        try:
            # ШАГ 1: АТОМАРНАЯ проверка и установка флага (под lock, быстро)
            lock = self._get_lock(base)
            
            with lock:
                self._ensure_cycle(base)
                cycle = self.cycles[base]
                
                # Проверка 1: Цикл уже активен?
                if cycle.is_active():
                    print(f"[{base}] [SKIP] Цикл уже активен (state={cycle.state.value}, cycle_id={cycle.cycle_id})")
                    return
                
                # Проверка 2: Покупка уже в процессе?
                if not hasattr(cycle, '_buying_in_progress'):
                    cycle._buying_in_progress = False
                
                if cycle._buying_in_progress:
                    print(f"[{base}] [SKIP] Покупка уже в процессе (_buying_in_progress=True)")
                    return
                
                # ✅ АТОМАРНО устанавливаем флаг (блокируем другие потоки)
                cycle._buying_in_progress = True
                print(f"[{base}] [LOCK] Флаг _buying_in_progress установлен, начинаем покупку...")
            
            # ШАГ 2: Все API запросы БЕЗ lock
            try:
                api_client = self.api_client_provider()
                if not api_client:
                    self._clear_buying_flag(base)
                    return
                
                currency_pair = f"{base}_{quote}".upper()
                
                # Проверяем открытые BUY ордера
                try:
                    open_orders = api_client.get_spot_orders(currency_pair, status="open")
                    buy_orders = [o for o in open_orders if o.get('side') == 'buy']
                    if buy_orders:
                        self._clear_buying_flag(base)
                        return
                except:
                    self._clear_buying_flag(base)
                    return
                
                # Получаем параметры торговли
                print(f"[{base}] [DEBUG] Получаем параметры торговли...")
                params = self.state_manager.get_breakeven_params(base)
                if not params:
                    print(f"[{base}] [ERROR] Не удалось получить параметры торговли (get_breakeven_params вернул None или пустой объект)")
                    self._clear_buying_flag(base)
                    return
                
                print(f"[{base}] [DEBUG] Параметры получены: start_volume={params.get('start_volume')}")
                
                # Рассчитываем таблицу
                print(f"[{base}] [DEBUG] Рассчитываем таблицу breakeven...")
                table = calculate_breakeven_table(params, current_price=price)
                if not table or len(table) == 0:
                    print(f"[{base}] [ERROR] Не удалось рассчитать таблицу breakeven (таблица пуста)")
                    self._clear_buying_flag(base)
                    return
                
                print(f"[{base}] [DEBUG] Таблица рассчитана, шагов: {len(table)}")
                
                # Проверяем баланс USDT для стартовой покупки
                print(f"[{base}] [DEBUG] Проверяем баланс USDT...")
                all_balances = api_client.get_account_balance()
                balance_quote = next((b for b in all_balances if b.get('currency') == quote), None)
                available_usdt = float(balance_quote.get('available', 0)) if balance_quote else 0.0
                required_usdt = float(params.get('start_volume', 0))
                
                print(f"[{base}] [DEBUG] Баланс USDT: {available_usdt}, Требуется: {required_usdt}")
                
                if available_usdt < required_usdt:
                    print(f"[{base}] [ERROR] Недостаточно USDT для покупки ({available_usdt} < {required_usdt})")
                    self._clear_buying_flag(base)
                    return
                
                # Создаём MARKET ордер
                print(f"[{base}] Создание MARKET BUY: {required_usdt} {quote}")
                order = api_client.create_spot_order(
                    currency_pair=currency_pair,
                    side='buy',
                    order_type='market',
                    amount=str(required_usdt)
                )
                
                order_id = order.get('id')
                print(f"[{base}] [OK] MARKET ордер создан: {order_id}")
                
                # Проверяем исполнение
                time.sleep(0.5)
                order_status = api_client.get_spot_order(order_id, currency_pair)
                
                if order_status.get('status') != 'closed':
                    print(f"[{base}] [WARN] Ордер не исполнен")
                    self._clear_buying_flag(base)
                    return
                
                executed_price = float(order_status.get('avg_deal_price', price))
                executed_amount = float(order_status.get('filled_amount', 0))
                executed_cost = float(order_status.get('filled_total', required_usdt))
                
                print(f"[{base}] [OK] Ордер исполнен!")
                print(f"[{base}]   Объём: {executed_amount} {base}")
                print(f"[{base}]   Цена: {executed_price}")
                print(f"[{base}]   Стоимость: {executed_cost} {quote}")
                
                # КРИТИЧЕСКИ ВАЖНО: Пересчитываем таблицу с РЕАЛЬНОЙ ценой покупки!
                # Если цена изменилась между расчётом и покупкой, таблица будет неверной
                print(f"[{base}] [DEBUG] Пересчитываем таблицу с реальной ценой покупки {executed_price}...")
                table_with_real_price = calculate_breakeven_table(params, current_price=executed_price)
                print(f"[{base}] [DEBUG] Таблица пересчитана, target_delta_pct = {table_with_real_price[0].get('target_delta_pct')}%")
                
                # 🔴 КРИТИЧЕСКИ ВАЖНО: Обновляем start_price в параметрах!
                # Это гарантирует, что при следующем цикле таблица будет рассчитана с правильной ценой
                print(f"[{base}] [DEBUG] Обновляем start_price в параметрах: {executed_price}...")
                params['start_price'] = executed_price
                self.state_manager.set_breakeven_params(base, params)
                print(f"[{base}] [DEBUG] start_price обновлён и сохранён!")
                
                # ШАГ 3: Активируем цикл И сохраняем состояние (под lock, быстро!)
                print(f"[{base}] [DEBUG] Начинаем активацию цикла...")
                cycle_id = 0
                with lock:
                    print(f"[{base}] [DEBUG] Lock получен, активируем цикл...")
                    cycle = self.cycles[base]
                    
                    print(f"[{base}] [DEBUG] Состояние ДО активации: active={cycle.is_active()}, cycle_id={cycle.cycle_id}")
                    
                    cycle.activate(
                        start_price=executed_price,
                        base_volume=executed_amount,
                        invested_usd=executed_cost
                    )
                    cycle.table = table_with_real_price  # Используем пересчитанную таблицу!
                    cycle._buying_in_progress = False
                    cycle_id = cycle.cycle_id
                    
                    print(f"[{base}] [DEBUG] Состояние ПОСЛЕ активации: active={cycle.is_active()}, cycle_id={cycle.cycle_id}")
                    print(f"[{base}] [OK] ЦИКЛ ЗАПУЩЕН! (ID={cycle_id})")
                    
                    # ВАЖНО: Сохраняем состояние ПОД LOCK сразу после активации!
                    # Это предотвращает повторные покупки
                    print(f"[{base}] [DEBUG] Сохраняем состояние...")
                    self._save_state(base)
                    print(f"[{base}] [DEBUG] Состояние сохранено!")
                
                # ШАГ 4: Логируем покупку в файл (БЕЗ lock)
                try:
                    self.logger.log_buy(
                        currency=base,
                        volume=executed_amount,
                        price=executed_price,
                        delta_percent=0.0,  # Для стартовой покупки дельта = 0
                        total_drop_percent=0.0,  # Для стартовой покупки падение = 0
                        investment=executed_cost
                    )
                    print(f"[{base}] [OK] Покупка записана в лог")
                except Exception as log_error:
                    print(f"[{base}] [WARN] Ошибка записи в лог: {log_error}")
                
            except Exception as e:
                print(f"[{base}] [ERROR] Ошибка создания стартовой покупки: {e}")
                self._clear_buying_flag(base)
                
        except Exception as e:
            print(f"[{base}] [ERROR] Ошибка в _try_start_cycle: {e}")
    
    def _clear_buying_flag(self, base: str):
        """Снять флаг 'продажа в процессе'"""
        lock = self._get_lock(base)
        with lock:
            if base in self.cycles:
                self.cycles[base]._buying_in_progress = False
    
    # ============================================================================
    # ТОРГОВАЯ ЛОГИКА - ДОКУПКА (REBUY)
    # ============================================================================
    
    def _try_rebuy(self, base: str, quote: str, price: float):
        """
        Попытка докупки при падении цены
        
        АЛГОРИТМ:
        1. Проверяем условие: price < last_buy_price * (1 - rebuy_trigger_pct / 100)
        2. Определяем следующий шаг: active_step + 1
        3. Проверяем, есть ли следующий шаг в таблице
        4. Получаем объём покупки из таблицы
        5. Создаём MARKET ордер
        6. Обновляем состояние: active_step++, last_buy_price, total_invested_usd, base_volume
        7. Пересчитываем таблицу с новым средневзвешенным курсом
        
        ЗАЩИТА ОТ ДУБЛИРОВАНИЯ:
        - Флаг _rebuy_in_progress
        - Проверка открытых BUY ордеров
        - Задержка после последней докупки (5 секунд)
        
        Args:
            base: Базовая валюта (например, ETH)
            quote: Валюта котировки (например, USDT)
            price: Текущая рыночная цена
        """
        
        try:
            # ШАГ 1: Проверяем состояние цикла (под lock, быстро)
            lock = self._get_lock(base)
            
            with lock:
                self._ensure_cycle(base)
                cycle = self.cycles[base]
                
                # Проверка 1: Цикл активен?
                if not cycle.is_active():
                    return
                
                # Проверка 2: Есть ли таблица?
                if not cycle.table or len(cycle.table) == 0:
                    return
                
                # Проверка 3: Есть ли следующий шаг?
                next_step_index = cycle.active_step + 1
                if next_step_index >= len(cycle.table):
                    return
                
                # Проверка 4: Докупка уже в процессе?
                if not hasattr(cycle, '_rebuy_in_progress'):
                    cycle._rebuy_in_progress = False
                
                if cycle._rebuy_in_progress:
                    return
                
                # Проверка 5: Задержка после последней докупки (5 секунд)
                if hasattr(cycle, 'last_buy_attempt_at') and cycle.last_buy_attempt_at > 0:
                    time_since_last_buy = time.time() - cycle.last_buy_attempt_at
                    if time_since_last_buy < 5.0:
                        return
                
                # Копируем данные для проверки условия
                last_buy_price = cycle.last_buy_price
            
            # ШАГ 2: Получаем порог докупки из таблицы (БЕЗ lock)
            with lock:
                cycle = self.cycles[base]
                next_step_index = cycle.active_step + 1
                
                if next_step_index >= len(cycle.table):
                    return
                
                next_step = cycle.table[next_step_index]
                decrease_step_pct = abs(float(next_step.get('decrease_step_pct', 0)))
            
            if decrease_step_pct <= 0:
                return
            
            # ШАГ 3: Проверяем условие докупки
            rebuy_threshold = last_buy_price * (1.0 - decrease_step_pct / 100.0)
            
            if price >= rebuy_threshold:
                return
            
            # ШАГ 4: АТОМАРНО устанавливаем флаг докупки (под lock, быстро)
            with lock:
                cycle = self.cycles[base]
                
                # Повторная проверка состояния (могло измениться)
                if not cycle.is_active():
                    return
                
                cycle._rebuy_in_progress = True
                cycle.last_buy_attempt_at = time.time()
                print(f"[{base}] [LOCK] Флаг _rebuy_in_progress установлен, начинаем докупку...")
            
            # ШАГ 5: Все API запросы БЕЗ lock
            try:
                api_client = self.api_client_provider()
                if not api_client:
                    self._clear_rebuy_flag(base)
                    return
                
                currency_pair = f"{base}_{quote}".upper()
                
                # Проверяем открытые BUY ордера
                try:
                    open_orders = api_client.get_spot_orders(currency_pair, status="open")
                    buy_orders = [o for o in open_orders if o.get('side') == 'buy']
                    if buy_orders:
                        self._clear_rebuy_flag(base)
                        return
                except Exception as e:
                    self._clear_rebuy_flag(base)
                    return
                
                # Получаем данные следующего шага из таблицы
                with lock:
                    cycle = self.cycles[base]
                    next_step_index = cycle.active_step + 1
                    
                    if next_step_index >= len(cycle.table):
                        self._clear_rebuy_flag(base)
                        return
                    
                    next_step = cycle.table[next_step_index]
                    purchase_usd = float(next_step.get('purchase_usd', 0))
                    total_drop_pct = float(next_step.get('total_drop_pct', 0))
                
                # Получаем параметры для пересчёта таблицы
                params = self.state_manager.get_breakeven_params(base)
                if not params:
                    self._clear_rebuy_flag(base)
                    return
                
                if purchase_usd <= 0:
                    self._clear_rebuy_flag(base)
                    return
                
                # Проверяем баланс USDT
                all_balances = api_client.get_account_balance()
                balance_quote = next((b for b in all_balances if b.get('currency') == quote), None)
                available_usdt = float(balance_quote.get('available', 0)) if balance_quote else 0.0
                
                if available_usdt < purchase_usd:
                    print(f"[{base}] [ERROR] Недостаточно USDT для докупки ({available_usdt} < {purchase_usd})")
                    self._clear_rebuy_flag(base)
                    return
                
                # Создаём MARKET ордер на докупку
                print(f"[{base}] 📈 Создание MARKET BUY (докупка): {purchase_usd} {quote}")
                order = api_client.create_spot_order(
                    currency_pair=currency_pair,
                    side='buy',
                    order_type='market',
                    amount=str(purchase_usd)
                )
                
                order_id = order.get('id')
                print(f"[{base}] [OK] MARKET ордер на докупку создан: {order_id}")
                
                # Проверяем исполнение
                time.sleep(0.5)
                order_status = api_client.get_spot_order(order_id, currency_pair)
                
                if order_status.get('status') != 'closed':
                    print(f"[{base}] [WARN] Ордер на докупку не исполнен")
                    self._clear_rebuy_flag(base)
                    return
                
                executed_price = float(order_status.get('avg_deal_price', price))
                executed_amount = float(order_status.get('filled_amount', 0))
                executed_cost = float(order_status.get('filled_total', purchase_usd))
                
                print(f"[{base}] [OK] Ордер на докупку исполнен!")
                print(f"[{base}]   Объём: {executed_amount} {base}")
                print(f"[{base}]   Цена: {executed_price}")
                print(f"[{base}]   Стоимость: {executed_cost} {quote}")
                
                # ШАГ 6: Обновляем состояние цикла (под lock, быстро)
                with lock:
                    cycle = self.cycles[base]
                    
                    # Обновляем состояние
                    cycle.active_step = next_step_index
                    cycle.last_buy_price = executed_price
                    cycle.total_invested_usd += executed_cost
                    cycle.base_volume += executed_amount
                    cycle.last_action_at = time.time()
                    cycle._rebuy_in_progress = False
                    
                    # Рассчитываем новый средневзвешенный курс
                    if cycle.base_volume > 0:
                        weighted_avg_price = cycle.total_invested_usd / cycle.base_volume
                    else:
                        weighted_avg_price = executed_price
                    
                    # Пересчитываем таблицу с новым средневзвешенным курсом
                    new_table = calculate_breakeven_table(params, current_price=weighted_avg_price)
                    cycle.table = new_table
                    
                    # Сохраняем состояние
                    self._save_state(base)
                
                # ШАГ 7: Логируем докупку в файл (БЕЗ lock)
                try:
                    with lock:
                        cycle = self.cycles[base]
                        start_price = cycle.start_price
                        current_step = cycle.active_step
                        
                        if cycle.table and current_step >= 0 and current_step < len(cycle.table):
                            actual_total_drop_pct = abs(float(cycle.table[current_step].get('cumulative_decrease_pct', 0)))
                        else:
                            actual_total_drop_pct = 0.0
                    
                    if start_price > 0:
                        delta_percent = ((executed_price - start_price) / start_price) * 100.0
                    else:
                        delta_percent = 0.0
                    
                    self.logger.log_buy(
                        currency=base,
                        volume=executed_amount,
                        price=executed_price,
                        delta_percent=delta_percent,
                        total_drop_percent=actual_total_drop_pct,
                        investment=executed_cost
                    )
                    print(f"[{base}] ✅ Докупка записана в лог")
                except Exception as log_error:
                    print(f"[{base}] ⚠️ [WARN] Ошибка записи в лог: {log_error}")
                
            except Exception as api_error:
                print(f"[{base}] [ERROR] Ошибка при выполнении докупки через API: {api_error}")
                self._clear_rebuy_flag(base)
        
        except Exception as e:
            print(f"[{base}] [ERROR] Критическая ошибка в _try_rebuy: {e}")
            self._clear_rebuy_flag(base)
    
    def _clear_rebuy_flag(self, base: str):
        """Снять флаг 'докупка в процессе'"""
        lock = self._get_lock(base)
        with lock:
            if base in self.cycles:
                self.cycles[base]._rebuy_in_progress = False
    
    def _clear_selling_flag(self, base: str):
        """Снять флаг 'продажа в процессе'"""
        lock = self._get_lock(base)
        with lock:
            if base in self.cycles:
                self.cycles[base]._selling_in_progress = False
    
    def _try_sell_idle_balance(self, base: str, quote: str, market_price: float, orderbook_price: float):
        """
        🔥 КРИТИЧЕСКАЯ ФУНКЦИЯ: Продажа остатков монет когда цикл в IDLE состоянии.
        
        Вызывается когда бот обнаруживает остатки монет, но цикл НЕ АКТИВЕН.
        Это защита от "зависания" с монетами после проблем с балансом.
        
        Args:
            base: базовая валюта (например DOGE)
            quote: валюта котировки (например USDT)
            market_price: текущая рыночная цена
            orderbook_price: цена из стакана для продажи
        """
        print(f"\n[{base}] 🔄 === АВТОПРОДАЖА ОСТАТКОВ В IDLE СОСТОЯНИИ ===")
        print(f"[{base}] 🔄 [DEBUG] Параметры: market_price={market_price:.8f}, orderbook_price={orderbook_price:.8f}")
        
        try:
            # Получаем API клиент
            print(f"[{base}] 🔄 [DEBUG] Шаг 1: Получаем API клиент...")
            api_client = self.api_client_provider()
            if not api_client:
                print(f"[{base}] ❌ API клиент недоступен")
                return
            print(f"[{base}] 🔄 [DEBUG] ✅ API клиент получен")
            
            # Получаем реальный баланс монеты через get_account_balance
            print(f"[{base}] 🔄 [DEBUG] Шаг 2: Получаем баланс...")
            all_balances = api_client.get_account_balance()
            print(f"[{base}] 🔄 [DEBUG] Получено балансов: {len(all_balances)}")
            balance_info = next((b for b in all_balances if b.get('currency') == base), None)
            
            if not balance_info:
                print(f"[{base}] ❌ Не удалось получить баланс для {base}")
                print(f"[{base}] ❌ Доступные валюты в балансе: {[b.get('currency') for b in all_balances[:10]]}")
                return
            
            available_balance = float(balance_info.get('available', 0))
            print(f"[{base}] 🔄 [DEBUG] ✅ Баланс получен")
            print(f"[{base}] 💰 Доступный баланс для продажи: {available_balance:.8f}")
            
            if available_balance <= 0:
                print(f"[{base}] ✅ Баланс = 0, остатков нет")
                return
            
            # Получаем минимальный объем сделки для валютной пары
            print(f"[{base}] 🔄 [DEBUG] Шаг 3: Получаем информацию о паре...")
            pair = f"{base}_{quote}".upper()
            print(f"[{base}] 🔄 [DEBUG] Пара: {pair}")
            pair_info = api_client.get_currency_pair_details_exact(pair)
            if not pair_info:
                print(f"[{base}] ❌ Не удалось получить информацию о паре {pair}")
                return
            print(f"[{base}] 🔄 [DEBUG] ✅ Информация о паре получена")
            
            min_base_amount = float(pair_info.get('min_base_amount', 0))
            min_quote_amount = float(pair_info.get('min_quote_amount', 0))
            amount_precision = int(pair_info.get('amount_precision', 8))
            
            print(f"[{base}] 📊 Параметры пары: min_base={min_base_amount}, min_quote={min_quote_amount}, precision={amount_precision}")
            
            # Проверяем, достаточно ли объема для продажи
            print(f"[{base}] 🔄 [DEBUG] Шаг 4: Проверяем объемы...")
            sell_amount = available_balance
            sell_amount_rounded = round(sell_amount, amount_precision)
            total_value = sell_amount_rounded * orderbook_price
            print(f"[{base}] 🔄 [DEBUG] sell_amount={sell_amount}, rounded={sell_amount_rounded}, total_value={total_value}")
            
            if sell_amount_rounded < min_base_amount:
                print(f"[{base}] ⚠️ Объем {sell_amount_rounded} меньше минимального {min_base_amount}")
                print(f"[{base}] 🗑️ Сбрасываем цикл, остатки слишком малы для продажи")
                # Сбрасываем цикл напрямую через объект TradingCycle
                lock = self._get_lock(base)
                with lock:
                    if base in self.cycles:
                        self.cycles[base].reset(manual=False)
                        self._save_state(base)
                        print(f"[{base}] ✅ Цикл сброшен, остатки игнорируются")
                return
            
            if total_value < min_quote_amount:
                print(f"[{base}] ⚠️ Стоимость {total_value} USDT меньше минимальной {min_quote_amount}")
                print(f"[{base}] 🗑️ Сбрасываем цикл, остатки слишком малы для продажи")
                # Сбрасываем цикл напрямую через объект TradingCycle
                lock = self._get_lock(base)
                with lock:
                    if base in self.cycles:
                        self.cycles[base].reset(manual=False)
                        self._save_state(base)
                        print(f"[{base}] ✅ Цикл сброшен, остатки игнорируются")
                return
            
            # ✅ Создаем ордер на продажу по цене из стакана
            print(f"[{base}] � [DEBUG] Шаг 5: Создаем ордер...")
            print(f"[{base}] �🚀 Создаем ордер на продажу остатков:")
            print(f"[{base}] 🚀   Объем: {sell_amount_rounded} {base}")
            print(f"[{base}] 🚀   Цена: {orderbook_price:.8f} {quote}")
            print(f"[{base}] 🚀   Стоимость: {total_value:.2f} {quote}")
            print(f"[{base}] 🔄 [DEBUG] Вызов api_client.create_spot_order()...")
            
            result = api_client.create_spot_order(
                currency_pair=pair,
                side='sell',
                order_type='limit',
                amount=str(sell_amount_rounded),
                price=str(orderbook_price),
                time_in_force='ioc'  # Immediate-Or-Cancel (продаёт максимум, что может)
            )
            
            print(f"[{base}] 🔄 [DEBUG] ✅ create_spot_order() завершён")
            print(f"[{base}] 🔄 [DEBUG] result = {result}")
            
            if result and result.get('id'):
                order_id = result['id']
                print(f"[{base}] ✅ Ордер создан успешно: {order_id}")
                print(f"[{base}] 🔄 Сбрасываем цикл после продажи остатков")
                # Сбрасываем цикл напрямую через объект TradingCycle
                lock = self._get_lock(base)
                with lock:
                    if base in self.cycles:
                        self.cycles[base].reset(manual=False)
                        self._save_state(base)
                        print(f"[{base}] ✅ Цикл сброшен после продажи остатков")
            else:
                print(f"[{base}] ❌ Не удалось создать ордер на продажу остатков")
                print(f"[{base}] 🔄 Сбрасываем цикл из-за ошибки")
                # Сбрасываем цикл напрямую через объект TradingCycle
                lock = self._get_lock(base)
                with lock:
                    if base in self.cycles:
                        self.cycles[base].reset(manual=False)
                        self._save_state(base)
                        print(f"[{base}] ✅ Цикл сброшен из-за ошибки продажи")
        
        except Exception as e:
            print(f"[{base}] ❌ Ошибка при автопродаже остатков: {e}")
            print(f"[{base}] 🔄 Сбрасываем цикл из-за ошибки")
            traceback.print_exc()
            # Сбрасываем цикл напрямую через объект TradingCycle
            lock = self._get_lock(base)
            with lock:
                if base in self.cycles:
                    self.cycles[base].reset(manual=False)
                    self._save_state(base)
                    print(f"[{base}] ✅ Цикл сброшен из-за исключения")
        
        print(f"[{base}] 🔄 [DEBUG] === ВЫХОД ИЗ _try_sell_idle_balance ===\n")
    
    # ============================================================================
    # ТОРГОВАЯ ЛОГИКА - ПРОДАЖА
    # ============================================================================
    
    def _try_sell(self, base: str, quote: str, market_price: float, orderbook_price: float):
        """
        Попытка продажи при достижении целевого роста (target_delta_pct).
        
        АЛГОРИТМ:
        1. Проверяем условие: market_price >= breakeven_price * (1 + profit_pct / 100)
        2. Используем orderbook_price для создания лимитного FOK ордера
        3. Если ордер исполнен → закрываем цикл, логируем PnL
        4. Если ордер не исполнен → повторяем при следующей итерации
        
        ЗАЩИТА ОТ ДУБЛИРОВАНИЯ:
        - Флаг _selling_in_progress
        - Проверка открытых SELL ордеров
        
        Args:
            base: Базовая валюта (например, ETH)
            quote: Валюта котировки (например, USDT)
            market_price: Текущая рыночная цена (для проверки условия)
            orderbook_price: Цена из orderbook (для создания ордера)
        """
        
        try:
            # ШАГ 1: Проверяем состояние цикла (под lock, быстро)
            lock = self._get_lock(base)
            
            with lock:
                self._ensure_cycle(base)
                cycle = self.cycles[base]
                
                # Проверка 1: Цикл активен?
                if not cycle.is_active():
                    print(f"[{base}] [SKIP_SELL] Цикл неактивен (state={cycle.state.value})")
                    return
                
                # Проверка 2: Есть ли таблица?
                if not cycle.table or len(cycle.table) == 0:
                    print(f"[{base}] [SKIP_SELL] Таблица пустая! (table={cycle.table})")
                    return
                
                # Проверка 3: Продажа уже в процессе?
                if not hasattr(cycle, '_selling_in_progress'):
                    cycle._selling_in_progress = False
                
                if cycle._selling_in_progress:
                    print(f"[{base}] [SKIP_SELL] Продажа уже в процессе (_selling_in_progress=True)")
                    return
                
                # Копируем данные для проверки условия
                start_price = cycle.start_price
                active_step = cycle.active_step
                base_volume = cycle.base_volume
            
            # ШАГ 2: Получаем параметры продажи (БЕЗ lock)
            params = self.state_manager.get_breakeven_params(base)
            if not params:
                print(f"[{base}] [SKIP_SELL] Параметры не найдены (get_breakeven_params вернул None)")
                return
            
            # ШАГ 3: Проверяем условие продажи
            if start_price <= 0:
                print(f"[{base}] [SKIP_SELL] Некорректная стартовая цена (start_price={start_price})")
                return
            
            # Получаем данные из таблицы
            with lock:
                cycle = self.cycles[base]
                if active_step < 0 or active_step >= len(cycle.table):
                    print(f"[{base}] [SKIP_SELL] Некорректный шаг (active_step={active_step}, table_len={len(cycle.table)})")
                    return
                
                params_row = cycle.table[active_step]
                # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Используем breakeven_price из таблицы
                # target_delta_pct рассчитан от P0, но продавать нужно от безубытка!
                breakeven_price = float(params_row.get('breakeven_price', start_price))
                breakeven_pct = float(params_row.get('breakeven_pct', 0))
                target_delta_pct = float(params_row.get('target_delta_pct', 0))
            
            # ИСПРАВЛЕНИЕ: Рассчитываем рост от БЕЗУБЫТКА, а не от P0!
            # Цена продажи = BE × (1 + профит/100)
            # Профит = target_delta_pct - breakeven_pct
            profit_pct = target_delta_pct - breakeven_pct
            required_price = breakeven_price * (1 + profit_pct / 100.0)
            
            # Для логов показываем рост от безубытка
            if breakeven_price > 0:
                current_growth_from_be = ((market_price - breakeven_price) / breakeven_price) * 100.0
            else:
                current_growth_from_be = 0.0
            
            print(f"\n[{base}] 💰 ПРОВЕРКА ПРОДАЖИ:")
            print(f"[{base}] 💰   Start price (P0): {start_price:.8f}")
            print(f"[{base}] 💰   Breakeven price (BE): {breakeven_price:.8f}")
            print(f"[{base}] 💰   Market price: {market_price:.8f}")
            print(f"[{base}] 💰   Profit %: {profit_pct:.4f}%")
            print(f"[{base}] 💰   Required price: {required_price:.8f}")
            print(f"[{base}] 💰   Current growth from BE: {current_growth_from_be:.4f}%")
            print(f"[{base}] 💰   Условие: {market_price:.8f} >= {required_price:.8f} ?")
            
            if market_price < required_price:
                print(f"[{base}] ❌ Цена недостаточна для продажи\n")
                return
            
            print(f"[{base}] ✅✅✅ УСЛОВИЕ ВЫПОЛНЕНО! Начинаем продажу...")
            
            # ШАГ 4: АТОМАРНО устанавливаем флаг продажи (под lock, быстро)
            with lock:
                cycle = self.cycles[base]
                
                # Повторная проверка состояния (могло измениться)
                if not cycle.is_active():
                    print(f"[{base}] ❌ [SKIP] Цикл стал неактивым после проверки условия")
                    return
                
                if base_volume <= 0:
                    print(f"[{base}] ❌ [WARN] Нечего продавать: base_volume={base_volume}")
                    return
                
                cycle._selling_in_progress = True
                print(f"[{base}] ✅ [LOCK] Флаг _selling_in_progress установлен, начинаем продажу...")
            
            # ШАГ 5: Все API запросы БЕЗ lock
            print(f"[{base}] 💰 [DIAG] ШАГ 5: Начинаем API запросы...")
            try:
                print(f"[{base}] 💰 [DIAG] Получаем API клиент...")
                api_client = self.api_client_provider()
                if not api_client:
                    print(f"[{base}] ❌ [ERROR] Не удалось получить API клиент")
                    self._clear_selling_flag(base)
                    return
                print(f"[{base}] 💰 [DIAG] ✅ API клиент получен")
                
                currency_pair = f"{base}_{quote}".upper()
                print(f"[{base}] 💰 [DIAG] Currency pair: {currency_pair}")
                
                # Проверяем открытые SELL ордера
                print(f"[{base}] 💰 [DIAG] Проверяем открытые SELL ордера...")
                try:
                    open_orders = api_client.get_spot_orders(currency_pair, status="open")
                    sell_orders = [o for o in open_orders if o.get('side') == 'sell']
                    if sell_orders:
                        print(f"[{base}] ❌ [SKIP] Есть открытые SELL ордера ({len(sell_orders)})")
                        self._clear_selling_flag(base)
                        return
                    print(f"[{base}] 💰 [DIAG] ✅ Нет открытых SELL ордеров")
                except Exception as e:
                    print(f"[{base}] ❌ [WARN] Ошибка проверки открытых ордеров: {e}")
                    import traceback
                    traceback.print_exc()
                    self._clear_selling_flag(base)
                    return
                
                # 🔴 КРИТИЧЕСКАЯ ПРОВЕРКА: Достаточно ли баланса для продажи?
                print(f"[{base}] 💰 [DIAG] Проверяем реальный баланс {base}...")
                try:
                    all_balances = api_client.get_account_balance()
                    balance_base = next((b for b in all_balances if b.get('currency') == base), None)
                    available_base = float(balance_base.get('available', 0)) if balance_base else 0.0
                    
                    print(f"[{base}] 💰 [DIAG] Реальный баланс: {available_base:.8f} {base}")
                    print(f"[{base}] 💰 [DIAG] Требуется для продажи: {base_volume:.8f} {base}")
                    
                    # 🔴 УМНАЯ КОРРЕКЦИЯ: Если разница < 1%, используем реальный баланс
                    if available_base < base_volume:
                        diff_pct = ((base_volume - available_base) / base_volume) * 100.0
                        print(f"[{base}] ⚠️ Реальный баланс меньше на {diff_pct:.2f}%")
                        
                        if diff_pct < 1.0:  # Разница меньше 1% (погрешность округления/комиссии)
                            print(f"[{base}] 🔧 КОРРЕКЦИЯ: Используем реальный баланс {available_base:.8f} вместо {base_volume:.8f}")
                            base_volume = available_base  # Корректируем объём продажи
                        else:
                            # Разница больше 1% - критическая ошибка
                            print(f"\n[{base}] ❌❌❌ КРИТИЧЕСКАЯ ОШИБКА: НЕДОСТАТОЧНО БАЛАНСА!")
                            print(f"[{base}] ❌ Реальный баланс: {available_base:.8f} < Требуется: {base_volume:.8f}")
                            print(f"[{base}] ❌ Разница: {diff_pct:.2f}% (больше допустимого 1%)")
                            print(f"[{base}] ❌ Возможные причины:")
                            print(f"[{base}] ❌   1. Монеты заблокированы в открытом ордере")
                            print(f"[{base}] ❌   2. Часть монет была продана вручную")
                            print(f"[{base}] ❌   3. Баланс не синхронизирован с реальностью")
                            print(f"[{base}] 🔄 АВТОМАТИЧЕСКИЙ СБРОС ЦИКЛА для предотвращения зависания!")
                            
                            # Сбрасываем цикл
                            with lock:
                                cycle = self.cycles[base]
                                cycle._selling_in_progress = False
                                cycle.reset(manual=False)
                                self._save_state(base)
                            
                            print(f"[{base}] ✅ Цикл сброшен. Проверьте баланс вручную через веб-интерфейс!")
                            return
                    
                    print(f"[{base}] ✅ Баланс достаточен для продажи (объём: {base_volume:.8f})")
                    
                except Exception as balance_error:
                    print(f"[{base}] ⚠️ [WARN] Не удалось проверить баланс: {balance_error}")
                    # Продолжаем попытку продажи, но с предупреждением
                
                # Создаём лимитный FOK ордер на продажу
                print(f"\n[{base}] 💰💰💰 ===== СОЗДАНИЕ FOK ОРДЕРА ===== 💰💰💰")
                print(f"[{base}] 💰 Создание LIMIT FOK SELL: {base_volume:.8f} {base} @ {orderbook_price:.8f}")
                print(f"[{base}] 📊 Детали FOK ордера:")
                print(f"[{base}]    Пара: {currency_pair}")
                print(f"[{base}]    Объём: {base_volume:.8f} {base}")
                print(f"[{base}]    Цена: {orderbook_price:.8f} {quote}")
                print(f"[{base}]    Тип: LIMIT + FOK (Fill-Or-Kill)")
                print(f"[{base}]    Условие: Ордер будет исполнен ПОЛНОСТЬЮ или отменён")
                
                print(f"[{base}] 💰 [DIAG] Вызываем api_client.create_spot_order...")
                order = api_client.create_spot_order(
                    currency_pair=currency_pair,
                    side='sell',
                    order_type='limit',
                    amount=str(base_volume),
                    price=str(orderbook_price),
                    time_in_force='fok'  # Fill-Or-Kill
                )
                
                # 🔴 КРИТИЧЕСКАЯ ПРОВЕРКА: Ордер создан успешно?
                if not order or not order.get('id'):
                    print(f"\n[{base}] ❌❌❌ КРИТИЧЕСКАЯ ОШИБКА: ОРДЕР НЕ СОЗДАН!")
                    print(f"[{base}] ❌ Ответ API: {order}")
                    
                    # Проверяем, не ошибка ли баланса
                    if order and order.get('label') == 'BALANCE_NOT_ENOUGH':
                        print(f"[{base}] ❌ Причина: НЕДОСТАТОЧНО БАЛАНСА {base}")
                        print(f"[{base}] 🔄 АВТОМАТИЧЕСКИЙ СБРОС ЦИКЛА!")
                        
                        # Сбрасываем цикл
                        with lock:
                            cycle = self.cycles[base]
                            cycle._selling_in_progress = False
                            cycle.reset(manual=False)
                            self._save_state(base)
                        
                        print(f"[{base}] ✅ Цикл сброшен. Проверьте баланс вручную!")
                    else:
                        print(f"[{base}] ⚠️ Повторим попытку при следующей итерации")
                        self._clear_selling_flag(base)
                    
                    return
                
                order_id = order.get('id')
                print(f"[{base}] ✅ [OK] LIMIT FOK ордер на продажу создан: {order_id}")
                
                # Проверяем исполнение
                print(f"[{base}] 💰 [DIAG] Ожидание 0.5s перед проверкой статуса...")
                time.sleep(0.5)
                print(f"[{base}] 💰 [DIAG] Проверяем статус ордера...")
                order_status = api_client.get_spot_order(order_id, currency_pair)
                
                status = order_status.get('status')
                filled_amount = float(order_status.get('filled_amount', 0))
                
                print(f"[{base}] 💰 [DIAG] Статус ордера: {status}")
                print(f"[{base}] 💰 [DIAG] Исполнено: {filled_amount:.8f} / {base_volume:.8f}")
                
                if status == 'closed' and filled_amount >= base_volume * 0.999:
                    # ПОЛНАЯ ПРОДАЖА
                    print(f"\n[{base}] ✅✅✅ ===== ОРДЕР ИСПОЛНЕН ПОЛНОСТЬЮ! ===== ✅✅✅")
                    executed_price = float(order_status.get('avg_deal_price', orderbook_price))
                    executed_cost = float(order_status.get('filled_total', base_volume * orderbook_price))
                    
                    print(f"[{base}] ✅ Ордер на продажу исполнен ПОЛНОСТЬЮ!")
                    print(f"[{base}]   Объём: {filled_amount} {base}")
                    print(f"[{base}]   Цена: {executed_price}")
                    print(f"[{base}]   Сумма: {executed_cost} {quote}")
                    
                    # ШАГ 6: Обновляем состояние цикла (под lock, быстро)
                    with lock:
                        cycle = self.cycles[base]
                        
                        # Расчёт PnL
                        avg_invest_price = cycle.total_invested_usd / cycle.base_volume if cycle.base_volume > 0 else 0
                        pnl = (executed_price - avg_invest_price) * filled_amount
                        
                        print(f"[{base}] 🎉 Цикл завершён!")
                        print(f"[{base}]   Средняя цена покупки: {avg_invest_price:.8f}")
                        print(f"[{base}]   Цена продажи: {executed_price:.8f}")
                        print(f"[{base}]   PnL: {pnl:.4f} {quote}")
                        
                        # Закрываем цикл через reset() - это правильный способ!
                        cycle._selling_in_progress = False
                        cycle.reset(manual=False)  # Автоматический сброс после продажи
                        
                        # Сохраняем состояние
                        self._save_state(base)
                        print(f"[{base}] ✅ Состояние сохранено")
                    
                    # ШАГ 7: Логируем продажу в файл (БЕЗ lock)
                    try:
                        self.logger.log_sell(
                            currency=base,
                            volume=filled_amount,
                            price=executed_price,
                            delta_percent=current_growth_from_be,  # ✅ ИСПРАВЛЕНО: рост от безубытка
                            pnl=pnl,
                            source="AUTO"  # Маркер автоматической продажи
                        )
                        print(f"[{base}] ✅ Продажа записана в лог (рост от BE={current_growth_from_be:.2f}%, PnL={pnl:.4f} {quote})")
                    except Exception as log_error:
                        print(f"[{base}] ⚠️ [WARN] Ошибка записи в лог: {log_error}")
                        import traceback
                        traceback.print_exc()
                
                else:
                    # ПРОДАЖА НЕ УДАЛАСЬ (FOK отклонён)
                    print(f"\n[{base}] ❌❌❌ ===== ОРДЕР НЕ ИСПОЛНЕН! ===== ❌❌❌")
                    print(f"[{base}] ⚠️ Ордер на продажу НЕ исполнен (статус: {status}, filled: {filled_amount}/{base_volume})")
                    print(f"[{base}] ⚠️ FOK ордер отклонён - недостаточно ликвидности на уровне {orderbook_price:.8f}")
                    print(f"[{base}] ⚠️ Повторим попытку при следующей итерации цикла")
                    print(f"[{base}] 💰 [DIAG] Снимаем флаг _selling_in_progress...")
                    self._clear_selling_flag(base)
                    print(f"[{base}] ❌❌❌ ===== ВЫХОД ИЗ _TRY_SELL (FOK ОТКЛОНЁН) ===== ❌❌❌\n")
            
            except Exception as api_error:
                print(f"\n[{base}] ❌❌❌ ===== ОШИБКА API ЗАПРОСА! ===== ❌❌❌")
                print(f"[{base}] [ERROR] Ошибка при API запросе: {api_error}")
                import traceback
                traceback.print_exc()
                self._clear_selling_flag(base)
                print(f"[{base}] ❌❌❌ ===== ВЫХОД ИЗ _TRY_SELL (API ERROR) ===== ❌❌❌\n")
        
        except Exception as e:
            print(f"\n[{base}] ❌❌❌ ===== КРИТИЧЕСКАЯ ОШИБКА! ===== ❌❌❌")
            print(f"[{base}] [ERROR] Критическая ошибка в _try_sell: {e}")
            import traceback
            traceback.print_exc()
            self._clear_selling_flag(base)
            print(f"[{base}] ❌❌❌ ===== ВЫХОД ИЗ _TRY_SELL (CRITICAL ERROR) ===== ❌❌❌\n")
