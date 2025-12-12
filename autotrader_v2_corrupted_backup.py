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
import logging
from datetime import datetime

from breakeven_calculator import calculate_breakeven_table
from trade_logger import get_trade_logger
from gate_api_client import GateAPIClient


# ============================================================================
# НАСТРОЙКА ЛОГИРОВАНИЯ В ФАЙЛ
# ============================================================================
def setup_autotrader_logger():
    """Настройка логирования автотрейдера в файл"""
    logger = logging.getLogger('autotrader')
    logger.setLevel(logging.DEBUG)
    
    # Удаляем старые обработчики
    logger.handlers.clear()
    
    # Файловый обработчик
    fh = logging.FileHandler('autotrader_debug.log', encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    
    # Консольный обработчик
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    
    # Формат
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    
    logger.addHandler(fh)
    logger.addHandler(ch)
    
    return logger

# Создаём глобальный логгер
AT_LOGGER = setup_autotrader_logger()


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
            AT_LOGGER.info(f"[CYCLE] Цикл #{self.cycle_id} завершён! Всего циклов: {self.total_cycles_count}")
        
        self.state = CycleState.IDLE
        self.active_step = -1
        self.start_price = 0.0
        self.last_buy_price = 0.0
        self.total_invested_usd = 0.0
        self.base_volume = 0.0
        self.cycle_started_at = 0.0
        self.last_action_at = time.time()
        self.manual_pause = manual  # Устанавливаем флаг ручной паузы
        
        # ВАЖНО: Сбрасываем флаги операций
        if hasattr(self, '_buying_in_progress'):
            self._buying_in_progress = False
        if hasattr(self, '_selling_in_progress'):
            self._selling_in_progress = False
        
        AT_LOGGER.debug(f"[CYCLE] Сброс выполнен, manual_pause={manual}")
    
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
        
        AT_LOGGER.info(f"[CYCLE] Новый цикл #{self.cycle_id} активирован! Volume={base_volume}, Invested={invested_usd}")


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
            self._