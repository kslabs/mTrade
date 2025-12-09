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
    last_sell_at: float = 0.0  # НОВОЕ: Время последней продажи (для задержки перед новым циклом)
    
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
        """
        import json
        import os
        from datetime import datetime
        
        STATE_FILE = "autotrader_cycles_state.json"
        
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
        
        while self.running:
            try:
                # Проверка: авто-торговля включена?
                auto_enabled = self.state_manager.get_auto_trade_enabled()
                if not auto_enabled:
                    time.sleep(self._sleep_interval)
                    continue
                
                # Получаем разрешения на торговлю
                perms = self.state_manager.get_trading_permissions()
                if not perms:
                    print("[AutoTraderV2] [WARN] Нет разрешений на торговлю (perms пуст)")
                    time.sleep(self._sleep_interval)
                    continue
                
                # Перебираем валюты
                enabled_count = sum(1 for v in perms.values() if v)
                if enabled_count > 0:
                    print(f"[AutoTraderV2] Обработка {enabled_count} валют...")
                
                for base in perms:
                    if not perms.get(base, False):
                        continue
                    
                    print(f"[{base}] Начало обработки...")
                    
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
                        print(f"[{base}] Цена: {price}")
                        
                        if not price or price <= 0:
                            print(f"[{base}] [WARN] Не удалось получить цену, пропуск")
                            continue
                        
                        # ШАГ 3: Принимаем решение и выполняем действия
                        if is_active:
                            print(f"[{base}] 🟢 Цикл АКТИВЕН (step={active_step}) → вызываем _try_sell")
                            
                            # Цикл АКТИВЕН → пытаемся продать
                            self._try_sell(base, quote, price)
                            print(f"[{base}] 🟢 _try_sell завершён")
                            
                            # TODO: После реализации ребая добавить:
                            # self._try_rebuy(base, quote, price)
                        else:
                            # Цикл НЕ АКТИВЕН
                            if is_paused:
                                print(f"[{base}] Цикл на РУЧНОЙ ПАУЗЕ → пропуск автостарта")
                            else:
                                print(f"[{base}] Цикл НЕ АКТИВЕН → попытка стартовой покупки")
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
    
    # ============================================================================
    # ТОРГОВАЯ ЛОГИКА - СТАРТОВАЯ ПОКУПКА
    # ============================================================================
    
    def _check_and_reset_if_empty(self, base: str, quote: str, price: float) -> bool:
        """
        Проверяет баланс базовой валюты и сбрасывает цикл, если монет недостаточно
        для минимального объёма первого шага
        
        Возвращает True, если цикл был сброшен
        """
        try:
            print(f"[{base}] [DEBUG] _check_and_reset_if_empty вызван")
            
            # ШАГ 1: Получаем баланс (БЕЗ lock - это API запрос)
            api_client = self.api_client_provider()
            if not api_client:
                return False
            
            all_balances = api_client.get_account_balance()
            balance_base = next((b for b in all_balances if b.get('currency') == base), None)
            
            if balance_base:
                available_base = float(balance_base.get('available', 0))
            else:
                available_base = 0.0
            
            # ШАГ 2: Получаем параметры и рассчитываем таблицу для определения минимального объёма
            params = self.state_manager.get_breakeven_params(base)
            if not params:
                return False
            
            table = calculate_breakeven_table(params, current_price=price)
            if not table or len(table) == 0:
                return False
            
            # Вычисляем минимальный объём базовой валюты для первого шага
            first_step = table[0]
            min_base = first_step['purchase_usd'] / first_step['rate'] if first_step['rate'] > 0 else 0
            
            print(f"[{base}] Проверка баланса: {available_base} {base} (минимум: {min_base})")
            
            # Если монет достаточно для первого шага - не сбрасываем
            if available_base >= min_base:
                return False
            
            # ШАГ 3: Если монет недостаточно - сбрасываем цикл (ПОД lock, быстро)
            print(f"[{base}] [INFO] Баланс недостаточен ({available_base} < {min_base}), сброс цикла в IDLE")
            
            lock = self._get_lock(base)
            with lock:
                self._ensure_cycle(base)
                cycle = self.cycles[base]
                cycle.reset()
                
                # Логируем сброс (просто выводим сообщение, т.к. специального метода нет)
                print(f"[{base}] [LOG] Цикл сброшен: недостаточно монет ({available_base} < {min_base})")
                
                # Сохраняем состояние
                self._save_state(base)
            
            return True
            
        except Exception as e:
            print(f"[{base}] [WARN] Ошибка проверки баланса для сброса: {e}")
            return False
    
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
                
                # НОВАЯ Проверка 2: Задержка после продажи (60 секунд)
                if hasattr(cycle, 'last_sell_at') and cycle.last_sell_at > 0:
                    time_since_sell = time.time() - cycle.last_sell_at
                    if time_since_sell < 60:
                        print(f"[{base}] [SKIP] Задержка после продажи ({time_since_sell:.1f}s < 60s)")
                        return
                
                # Проверка 3: Покупка уже в процессе?
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
    
    def _try_sell(self, base: str, quote: str, price: float):
        """
        Попытка продать все монеты, если цена достигла цели
        
        ПРАВИЛЬНАЯ АРХИТЕКТУРА:
        1. Все API запросы БЕЗ lock
        2. Только изменение состояния ПОД lock (быстро)
        
        ЛОГИКА:
        1. Проверяем, что цикл активен
        2. Получаем целевую цену продажи из таблицы
        3. Если текущая цена >= целевой → продаём
        4. После продажи сбрасываем цикл в IDLE
        """
        # 🔴 ЯВНАЯ МЕТКА — КОД ОБНОВЛЁН 08.12.2025 07:30
        print(f"[{base}] 🔴 _try_sell вызван | КОД ВЕРСИЯ: 2025-12-08_07:30 | Цена: {price}")
        
        try:
            # ШАГ 1: Проверяем состояние цикла (под lock, быстро)
            lock = self._get_lock(base)
            
            with lock:
                self._ensure_cycle(base)
                cycle = self.cycles[base]
                
                # Проверка 1: Цикл активен?
                if not cycle.is_active():
                    return
                
                # Проверка 2: Есть ли таблица и текущий шаг?
                if not cycle.table or cycle.active_step < 0 or cycle.active_step >= len(cycle.table):
                    print(f"[{base}] [WARN] Нет таблицы или некорректный шаг ({cycle.active_step})")
                    return
                
                # Проверка 3: Продажа уже в процессе?
                if not hasattr(cycle, '_selling_in_progress'):
                    cycle._selling_in_progress = False
                
                if cycle._selling_in_progress:
                    print(f"[{base}] [SKIP] Продажа уже в процессе (_selling_in_progress=True)")
                    return
                
                # Копируем нужные данные
                current_step = cycle.table[cycle.active_step]
                breakeven_price = current_step.get('breakeven_price', 0)
                rate = current_step.get('rate', 0)  # Расчетный курс на текущем шаге
                target_delta_pct = current_step.get('target_delta_pct', 0)
                base_volume = cycle.base_volume
                start_price = cycle.start_price
            
            # ШАГ 2: Вычисляем целевую цену продажи (БЕЗ lock)
            
            # 🔴 КРИТИЧЕСКОЕ ЛОГИРОВАНИЕ ДЛЯ ДИАГНОСТИКИ
            print(f"[{base}] 🔴 ========== ДИАГНОСТИКА ПЕРЕД ПРОДАЖЕЙ ==========")
            print(f"[{base}]   rate (из таблицы): {rate}")
            print(f"[{base}]   target_delta_pct (из таблицы): {target_delta_pct}")
            print(f"[{base}]   breakeven_price (из таблицы): {breakeven_price}")
            print(f"[{base}]   start_price (цена покупки): {start_price}")
            print(f"[{base}]   price (текущая цена): {price}")
            print(f"[{base}]   base_volume: {base_volume}")
            print(f"[{base}]   active_step: {cycle.active_step}")
            
            if not breakeven_price or breakeven_price <= 0:
                print(f"[{base}] [WARN] Некорректная цена безубыточности: {breakeven_price}")
                return
            
            if not rate or rate <= 0:
                print(f"[{base}] [WARN] Некорректный расчетный курс: {rate}")
                return
            
            # 🔴 КРИТИЧЕСКИ ВАЖНО: target_delta_pct рассчитывается для ПЕРВОГО шага (step=0)
            # и показывает минимальный процент роста для получения профита
            # 
            # ПРАВИЛЬНАЯ ФОРМУЛА:
            # target_sell_price = start_price * (1 + target_delta_pct / 100)
            #
            # ГДЕ:
            # - start_price = РЕАЛЬНАЯ цена покупки (из executed_price)
            # - target_delta_pct = минимальная дельта для профита (из таблицы)
            #
            # НЕПРАВИЛЬНО было использовать rate вместо start_price!
            target_sell_price = start_price * (1 + target_delta_pct / 100.0)
            
            # 🔴 КРИТИЧЕСКАЯ ПРОВЕРКА №1: target_sell_price ДОЛЖНА быть выше start_price!
            # Это проверка на ошибку в расчётах или таблице
            if target_sell_price <= start_price:
                print(f"[{base}] 🚨 КРИТИЧЕСКАЯ ОШИБКА: target_sell_price <= start_price!")
                print(f"[{base}]   target_sell_price: {target_sell_price:.8f}")
                print(f"[{base}]   start_price (цена покупки): {start_price:.8f}")
                print(f"[{base}]   target_delta_pct (из таблицы): {target_delta_pct:.2f}%")
                print(f"[{base}] 🚨 ПРОДАЖА ОТМЕНЕНА - целевая цена не выше цены покупки!")
                return  # БЛОКИРУЕМ продажу!
            
            # 🔴 КРИТИЧЕСКАЯ ПРОВЕРКА №2: target_sell_price ДОЛЖНА быть >= breakeven_price!
            # Если целевая цена ниже безубыточности - это ошибка таблицы!
            # НЕЛЬЗЯ заменять target_sell_price на breakeven_price, т.к. это нарушает логику целевой дельты
            if target_sell_price < breakeven_price:
                print(f"[{base}] 🚨 КРИТИЧЕСКАЯ ОШИБКА: target_sell_price < breakeven_price!")
                print(f"[{base}]   target_sell_price: {target_sell_price:.8f}")
                print(f"[{base}]   breakeven_price: {breakeven_price:.8f}")
                print(f"[{base}]   start_price: {start_price:.8f}")
                print(f"[{base}]   target_delta_pct: {target_delta_pct:.2f}%")
                print(f"[{base}] 🚨 ПРОДАЖА ОТМЕНЕНА - ошибка в таблице безубыточности!")
                print(f"[{base}] 🚨 Требуется пересчёт таблицы с правильными параметрами!")
                return  # БЛОКИРУЕМ продажу!
            
            print(f"[{base}]   target_sell_price (вычислено): {target_sell_price:.8f}")
            print(f"[{base}] 🔴 ===============================================")
            
            print(f"[{base}] 🟦 [SELL_CHECK_POINT_1] Проверка продажи:")
            print(f"  Текущая цена: {price:.8f}")
            print(f"  Расчетный курс шага (rate): {rate:.8f}")
            print(f"  Цена безубыточности: {breakeven_price:.8f}")
            print(f"  Целевая дельта (от start_price): +{target_delta_pct:.2f}%")
            print(f"  Целевая цена продажи: {target_sell_price:.8f}")
            print(f"  Объём для продажи: {base_volume} {base}")
            
            # 🔴🔴🔴 КРИТИЧЕСКАЯ ПРОВЕРКА УСЛОВИЯ ПРОДАЖИ 🔴🔴🔴
            print(f"[{base}] 🔴🔴🔴 ========== КРИТИЧЕСКАЯ ТОЧКА РЕШЕНИЯ ==========")
            print(f"[{base}] 🔴 price (текущая из параметра): {price:.10f}")
            print(f"[{base}] � target_sell_price (вычислено): {target_sell_price:.10f}")
            print(f"[{base}] 🔴 start_price (цена покупки):  {start_price:.10f}")
            print(f"[{base}] 🔴 Разница (price - target):    {(price - target_sell_price):.10f}")
            print(f"[{base}] 🔴 target_delta_pct из таблицы: {target_delta_pct:.4f}%")
            print(f"[{base}] �🟦 [SELL_CHECK_POINT_2] Проверка: {price:.10f} >= {target_sell_price:.10f} ?")
            
            if price < target_sell_price:
                print(f"[{base}] 🟦 [SELL_BLOCKED] Цена НЕ достигла цели ({price:.8f} < {target_sell_price:.8f})")
                print(f"[{base}] 🟦 [SELL_BLOCKED] Требуется рост ещё на {((target_sell_price - price) / price * 100):.2f}%")
                return
            
            print(f"[{base}] 🟢 [SELL_APPROVED] Условие выполнено! {price:.8f} >= {target_sell_price:.8f}")
            print(f"[{base}] 🟢 [SELL_APPROVED] Фактический рост: {((price - start_price) / start_price * 100):.2f}%")
            
            # ШАГ 3: АТОМАРНО устанавливаем флаг продажи (под lock, быстро)
            with lock:
                cycle = self.cycles[base]
                
                # Повторная проверка состояния (могло измениться)
                if not cycle.is_active():
                    return
                
                cycle._selling_in_progress = True
                print(f"[{base}] [LOCK] Флаг _selling_in_progress установлен, начинаем продажу...")
            
            # ШАГ 4: Все API запросы БЕЗ lock
            try:
                api_client = self.api_client_provider()
                if not api_client:
                    self._clear_selling_flag(base)
                    return
                
                currency_pair = f"{base}_{quote}".upper()
                
                # Проверяем открытые SELL ордера
                try:
                    open_orders = api_client.get_spot_orders(currency_pair, status="open")
                    sell_orders = [o for o in open_orders if o.get('side') == 'sell']
                    if sell_orders:
                        print(f"[{base}] [SKIP] Есть открытые SELL ордера ({len(sell_orders)})")
                        self._clear_selling_flag(base)
                        return
                except Exception as e:
                    print(f"[{base}] [WARN] Ошибка проверки открытых ордеров: {e}")
                    self._clear_selling_flag(base)
                    return
                
                # Получаем актуальный баланс
                all_balances = api_client.get_account_balance()
                balance_base = next((b for b in all_balances if b.get('currency') == base), None)
                available_base = float(balance_base.get('available', 0)) if balance_base else 0.0
                
                if available_base <= 0:
                    print(f"[{base}] [WARN] Недостаточно монет для продажи ({available_base})")
                    self._clear_selling_flag(base)
                    return
                
                # 🔴 КРИТИЧЕСКИ ВАЖНО: Повторная проверка цены перед продажей!
                # За время проверки ордеров и баланса цена могла уйти ниже целевой
                current_price_before_sell = self._get_market_price(base, quote)
                if not current_price_before_sell:
                    print(f"[{base}] [WARN] Не удалось получить цену перед продажей")
                    self._clear_selling_flag(base)
                    return
                
                print(f"[{base}] 🔴 ПОВТОРНАЯ ПРОВЕРКА ЦЕНЫ:")
                print(f"[{base}]   current_price_before_sell: {current_price_before_sell:.8f}")
                print(f"[{base}]   target_sell_price: {target_sell_price:.8f}")
                print(f"[{base}]   start_price (цена покупки): {start_price:.8f}")
                print(f"[{base}]   Минимальная дельта для продажи: {((target_sell_price - start_price) / start_price * 100.0):.2f}%")
                
                # Проверяем, что цена всё ещё выше целевой
                if current_price_before_sell < target_sell_price:
                    print(f"[{base}] [SKIP] ⚠️ Цена упала ниже целевой во время подготовки!")
                    print(f"[{base}]   Было: {price:.8f} >= {target_sell_price:.8f} ✅")
                    print(f"[{base}]   Сейчас: {current_price_before_sell:.8f} < {target_sell_price:.8f} ❌")
                    print(f"[{base}]   Продажа отменена для соответствия таблице безубыточности")
                    self._clear_selling_flag(base)
                    return
                
                # 🔴 ЛОГИРОВАНИЕ ПАРАМЕТРОВ ЗАПРОСА НА ПРОДАЖУ
                print(f"[{base}] 🔵 ========== ПАРАМЕТРЫ ЗАПРОСА НА ПРОДАЖУ ==========")
                print(f"[{base}] 🔵 [SELL_EXECUTION_FROM_TRY_SELL] ← Продажа из функции _try_sell")
                print(f"[{base}]   currency_pair: {currency_pair}")
                print(f"[{base}]   side: sell")
                print(f"[{base}]   order_type: LIMIT (гарантия минимальной цены!)")
                print(f"[{base}]   amount: {available_base} {base}")
                print(f"[{base}]   price (LIMIT): {target_sell_price:.8f} {quote}")
                print(f"[{base}]   ---")
                print(f"[{base}]   Текущая цена рынка: {current_price_before_sell:.8f}")
                print(f"[{base}]   Целевая цена продажи: {target_sell_price:.8f}")
                print(f"[{base}]   Цена покупки (start_price): {start_price:.8f}")
                print(f"[{base}]   Ожидаемая дельта: {((current_price_before_sell - start_price) / start_price * 100.0):.2f}%")
                print(f"[{base}]   Требуемая дельта (из таблицы): {target_delta_pct:.2f}%")
                print(f"[{base}]   Ожидаемая выручка: >={available_base * target_sell_price:.4f} {quote}")
                print(f"[{base}] 🔵 =====================================================")
                
                # 🔴 КРИТИЧЕСКИ ВАЖНО: Используем LIMIT-ордер с time_in_force='fok'
                # FOK (Fill-Or-Kill) = Всё или ничего:
                #   • Если ордер может быть исполнен ПОЛНОСТЬЮ и СРАЗУ → исполняется
                #   • Если НЕ может быть исполнен полностью → ОТМЕНЯЕТСЯ
                #   • Результат известен через 1-2 секунды
                # LIMIT гарантирует цену >= target_sell_price
                # FOK гарантирует, что ордер не зависнет в книге заявок
                print(f"[{base}] 🟢 Создаём LIMIT FOK-ордер с минимальной ценой {target_sell_price:.8f}")
                print(f"[{base}]    FOK = Fill-Or-Kill: продаст ВСЁ сразу или отменит ордер")
                order = api_client.create_spot_order(
                    currency_pair=currency_pair,
                    side='sell',
                    order_type='limit',
                    amount=str(available_base),
                    price=str(target_sell_price),
                    time_in_force='fok'  # 🔴 Fill-Or-Kill: всё или ничего!
                )
                
                order_id = order.get('id')
                print(f"[{base}] ✅ ========== РЕЗУЛЬТАТ СОЗДАНИЯ ОРДЕРА ==========")
                print(f"[{base}]   Order ID: {order_id}")
                print(f"[{base}] ✅ ==================================================")
                
                # 🔴 FOK-ордер исполняется или отменяется СРАЗУ (1-2 секунды)
                # Проверяем статус: должен быть 'closed' (исполнен) или 'cancelled' (отменён)
                max_attempts = 3  # Достаточно 3 попыток для FOK
                check_interval = 1.0  # Проверка каждую секунду
                order_real_status = 'unknown'
                
                print(f"[{base}] ⏳ Проверка FOK-ордера (максимум {max_attempts} секунды)...")
                
                for attempt in range(1, max_attempts + 1):
                    time.sleep(check_interval)
                    
                    try:
                        order_status = api_client.get_spot_order(order_id, currency_pair)
                        order_real_status = order_status.get('status', 'unknown')
                        
                        print(f"[{base}] 🔍 Попытка {attempt}/{max_attempts}: статус = {order_real_status}")
                        
                        if order_real_status in ['closed', 'cancelled']:
                            print(f"[{base}] ✅ FOK-ордер завершён после {attempt * check_interval:.0f} секунд (статус: {order_real_status})")
                            break
                            
                    except Exception as e:
                        print(f"[{base}] ⚠️ Ошибка проверки статуса (попытка {attempt}): {e}")
                        continue
                
                # Обработка результата FOK-ордера
                if order_real_status == 'closed':
                    # ✅ Ордер исполнен — продолжаем обработку ниже
                    print(f"[{base}] ✅ FOK-ордер ИСПОЛНЕН полностью")
                    
                elif order_real_status == 'cancelled':
                    # ❌ FOK-ордер отменён — не смог исполниться полностью по целевой цене
                    print(f"[{base}] ❌ FOK-ордер ОТМЕНЁН (не смог исполниться полностью)")
                    print(f"[{base}]   Причина: недостаточная ликвидность на уровне {target_sell_price:.8f}")
                    print(f"[{base}]   Требуется дождаться роста цены или увеличения ликвидности")
                    self._clear_selling_flag(base)
                    return
                    
                else:
                    # ⚠️ Неизвестный статус — проверяем баланс для уверенности
                    print(f"[{base}] ⚠️ FOK-ордер в неизвестном статусе: {order_real_status}")
                    print(f"[{base}]   Проверяем баланс для определения фактического состояния...")
                    
                    try:
                        new_balances = api_client.get_account_balance()
                        new_balance_base = next((b for b in new_balances if b.get('currency') == base), None)
                        new_available_base = float(new_balance_base.get('available', 0)) if new_balance_base else 0.0
                        
                        print(f"[{base}]   Баланс ДО продажи: {available_base:.8f} {base}")
                        print(f"[{base}]   Баланс СЕЙЧАС: {new_available_base:.8f} {base}")
                        print(f"[{base}]   Разница: {(available_base - new_available_base):.8f} {base}")
                        
                        # Если баланс уменьшился значительно (>90%) — ордер исполнился
                        if (available_base - new_available_base) >= (available_base * 0.9):
                            print(f"[{base}] ✅ Баланс уменьшился на {((available_base - new_available_base) / available_base * 100):.1f}%")
                            print(f"[{base}] ✅ Считаем ордер исполненным по факту изменения баланса")
                            order_real_status = 'closed'
                        else:
                            print(f"[{base}] ❌ Баланс не изменился значительно")
                            print(f"[{base}] ❌ Считаем ордер отменённым или не исполненным")
                            self._clear_selling_flag(base)
                            return
                            
                    except Exception as e:
                        print(f"[{base}] ❌ Ошибка проверки баланса: {e}")
                        self._clear_selling_flag(base)
                        return
                        print(f"[{base}]   Снимаем флаг, ордер будет проверен при следующей итерации")
                        self._clear_selling_flag(base)
                        return
                
                executed_price = float(order_status.get('avg_deal_price', price))
                executed_amount = float(order_status.get('filled_amount', available_base))
                executed_total = float(order_status.get('filled_total', 0))
                
                print(f"[{base}] ✅ ========== РЕЗУЛЬТАТ ИСПОЛНЕНИЯ ОРДЕРА ==========")
                print(f"[{base}]   Status: {order_status.get('status')}")
                print(f"[{base}]   Объём продано: {executed_amount} {base}")
                print(f"[{base}]   Цена исполнения: {executed_price:.8f}")
                print(f"[{base}]   Получено: {executed_total:.4f} {quote}")
                print(f"[{base}]   ---")
                print(f"[{base}]   Запрошено на продажу: {available_base} {base}")
                print(f"[{base}]   Цена перед ордером: {current_price_before_sell:.8f}")
                print(f"[{base}] ✅ ====================================================")
                
                # Вычисляем профит
                with lock:
                    cycle = self.cycles[base]
                    total_invested = cycle.total_invested_usd
                    profit = executed_total - total_invested
                    profit_pct = (profit / total_invested * 100.0) if total_invested > 0 else 0.0
                    
                    # Вычисляем рост от стартовой цены
                    growth_pct = ((executed_price - start_price) / start_price * 100.0) if start_price > 0 else 0.0
                
                print(f"[{base}] 💰 ========== ФИНАНСОВЫЕ ПОКАЗАТЕЛИ ==========")
                print(f"[{base}]   Инвестировано: {total_invested:.4f} {quote}")
                print(f"[{base}]   Получено: {executed_total:.4f} {quote}")
                print(f"[{base}]   Профит: {profit:.4f} {quote} ({profit_pct:+.2f}%)")
                print(f"[{base}]   ---")
                print(f"[{base}]   Цена покупки: {start_price:.8f}")
                print(f"[{base}]   Целевая цена (LIMIT): {target_sell_price:.8f}")
                print(f"[{base}]   Цена исполнения (факт): {executed_price:.8f}")
                print(f"[{base}]   Рост цены: {growth_pct:+.2f}%")
                print(f"[{base}]   Требуемый рост (из таблицы): {target_delta_pct:+.2f}%")
                print(f"[{base}]   ---")
                
                # 🔴 КРИТИЧЕСКАЯ ПРОВЕРКА: executed_price ДОЛЖНА быть >= target_sell_price!
                # Это гарантируется LIMIT-ордером
                if executed_price >= target_sell_price:
                    print(f"[{base}]   ✅ LIMIT-ордер сработал корректно: {executed_price:.8f} >= {target_sell_price:.8f}")
                else:
                    print(f"[{base}]   🚨 ОШИБКА! LIMIT-ордер исполнился ниже минимальной цены!")
                    print(f"[{base}]   🚨 executed_price: {executed_price:.8f} < target: {target_sell_price:.8f}")
                    print(f"[{base}]   🚨 Это НЕ должно происходить с LIMIT-ордерами!")
                
                if growth_pct >= target_delta_pct:
                    print(f"[{base}]   ✅ Рост достиг цели: {growth_pct:+.2f}% >= {target_delta_pct:+.2f}%")
                else:
                    print(f"[{base}]   🚨 ОШИБКА! Рост ниже требуемого: {growth_pct:+.2f}% < {target_delta_pct:+.2f}%")
                
                print(f"[{base}] 💰 ==============================================")
                
                # ШАГ 5: Сбрасываем цикл и сохраняем состояние (под lock, быстро!)
                with lock:
                    cycle = self.cycles[base]
                    cycle.reset()  # Сброс в IDLE (автоматически увеличит total_cycles_count)
                    cycle._selling_in_progress = False
                    cycle.last_sell_at = time.time()  # ВАЖНО: Устанавливаем метку времени продажи
                    
                    print(f"[{base}] 🎉 ЦИКЛ ЗАВЕРШЁН! Всего циклов: {cycle.total_cycles_count}, last_sell_at={cycle.last_sell_at}")
                    
                    # Сохраняем состояние
                    self._save_state(base)
                
                # ШАГ 6: Логируем продажу в файл (БЕЗ lock)
                try:
                    self.logger.log_sell(
                        currency=base,
                        volume=executed_amount,
                        price=executed_price,
                        delta_percent=growth_pct,
                        pnl=profit,
                        source="AUTO"  # Маркер автоматической продажи
                    )
                    print(f"[{base}] [OK] Продажа записана в лог")
                except Exception as log_error:
                    print(f"[{base}] [WARN] Ошибка записи в лог: {log_error}")
                    import traceback
                    traceback.print_exc()
                
            except Exception as e:
                print(f"[{base}] [ERROR] Ошибка выполнения продажи: {e}")
                import traceback
                traceback.print_exc()
                self._clear_selling_flag(base)
                
        except Exception as e:
            print(f"[{base}] [ERROR] Ошибка в _try_sell: {e}")
            import traceback
            traceback.print_exc()
    
    def _clear_selling_flag(self, base: str):
        """Снять флаг 'продажа в процессе'"""
        lock = self._get_lock(base)
        with lock:
            if base in self.cycles:
                self.cycles[base]._selling_in_progress = False
    
    # ============================================================================
    # API ДЛЯ ВЕБ-ИНТЕРФЕЙСА
    # ============================================================================
    
    def get_status(self) -> dict:
        """Получить статус автотрейдера"""
        return {
            'running': self.running,
            'stats': self.stats,
            'cycles_count': len(self.cycles),
            'active_cycles': sum(1 for c in self.cycles.values() if c.is_active())
        }
    
    def get_stats(self) -> dict:
        """Получить статистику автотрейдера (совместимость с API)"""
        return self.get_status()
    
    def get_cycle_info(self, base: str) -> Optional[dict]:
        """Получить информацию о цикле для валюты"""
        lock = self._get_lock(base)
        with lock:
            cycle = self.cycles.get(base)
            if not cycle:
                print(f"[DEBUG] get_cycle_info({base}): цикл не найден в self.cycles")
                return None
            
            result = {
                'state': cycle.state.value,
                'active': cycle.is_active(),
                'cycle_id': cycle.cycle_id,  # Текущий ID цикла
                'total_cycles_count': cycle.total_cycles_count,  # Количество завершённых циклов
                'active_step': cycle.active_step,
                'start_price': cycle.start_price,
                'last_buy_price': cycle.last_buy_price,
                'total_invested_usd': cycle.total_invested_usd,
                'base_volume': cycle.base_volume,
                'cycle_started_at': cycle.cycle_started_at,
                'last_action_at': cycle.last_action_at,
                'table_steps': len(cycle.table) if cycle.table else 0
            }
            print(f"[DEBUG] get_cycle_info({base}): state={result['state']}, active={result['active']}, cycle_id={result['cycle_id']}")
            return result
    
    def force_reset_cycle(self, base: str, reason: str = "manual_action"):
        """Принудительный сброс цикла при ручной продаже
        
        Используется когда продажа происходит через веб-интерфейс,
        чтобы корректно сбросить состояние цикла и предотвратить
        немедленные повторные покупки.
        """
        lock = self._get_lock(base)
        with lock:
            self._ensure_cycle(base)
            cycle = self.cycles[base]
            
            if cycle.is_active():
                print(f"[{base}] 🔴 ПРИНУДИТЕЛЬНЫЙ СБРОС ЦИКЛА (причина: {reason})")
                print(f"[{base}]   Цикл ID: {cycle.cycle_id}")
                print(f"[{base}]   Инвестировано: {cycle.total_invested_usd} USDT")
            
            # Сбрасываем цикл (manual=False чтобы НЕ блокировать автостарт)
            cycle.reset(manual=False)
            
            # КРИТИЧЕСКИ ВАЖНО: Устанавливаем метку времени продажи
            # Это предотвратит немедленную новую покупку
            cycle.last_sell_at = time.time()
            
            print(f"[{base}] ✅ Цикл сброшен, last_sell_at={cycle.last_sell_at}")
            
            # Сохраняем состояние
            self._save_state(base)
