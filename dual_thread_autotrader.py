# Двухпоточный автотрейдер (threading вместо multiprocessing)
# Более простая и стабильная реализация для Windows

import time
import traceback
from threading import Thread, Lock
from queue import Queue, Empty, Full
from typing import Optional, Dict, Any, Callable
from datetime import datetime
from autotrader import AutoTrader

class DualThreadAutoTrader:
    """
    Двухпоточный автотрейдер (использует threading вместо multiprocessing).
    Более стабильно работает на Windows.
    """
    
    def __init__(
        self,
        api_client_provider: Callable,
        ws_manager,
        state_manager,
        currencies: list,
        debounce_seconds: float = 0.1,
        urgent_queue_max_size: int = 100,
        max_urgent_per_cycle: int = 5
    ):
        self.api_client_provider = api_client_provider
        self.ws_manager = ws_manager
        self.state_manager = state_manager
        self.currencies = currencies
        self.debounce_seconds = debounce_seconds
        self.max_urgent_per_cycle = max_urgent_per_cycle
        
        # Создать экземпляр AutoTrader
        self.autotrader = AutoTrader(
            api_client_provider=api_client_provider,
            ws_manager=ws_manager,
            state_manager=state_manager
        )
        
        # Используем обычные dict с Lock вместо Manager
        self.lock = Lock()
        
        # Флаги обработки
        self.processing_flags: Dict[str, bool] = {}
        
        # Последнее время обработки
        self.last_processed: Dict[str, float] = {}
        
        # Очередь срочных задач
        self.urgent_queue = Queue(maxsize=urgent_queue_max_size)
        
        # Статистика
        self.stats: Dict[str, int] = {
            'cycler_iterations': 0,
            'cycler_processed': 0,
            'cycler_skipped': 0,
            'reactor_updates': 0,
            'reactor_queued': 0,
            'reactor_debounced': 0,
            'urgent_processed': 0,
            'urgent_skipped': 0,
            'errors': 0
        }
        
        # Циклы автотрейдера (используем из autotrader)
        self.cycles = self.autotrader.cycles
        
        # Потоки
        self.cycler_thread: Optional[Thread] = None
        self.reactor_thread: Optional[Thread] = None
        
        # Флаги управления
        self.running = False
        
        print("[DUAL-AT] Инициализация двухпоточного автотрейдера")
        print(f"[DUAL-AT] Валюты: {len(currencies)}")
        print(f"[DUAL-AT] Debounce: {debounce_seconds}s")
        print(f"[DUAL-AT] Max urgent/cycle: {max_urgent_per_cycle}")
    
    def start(self):
        """Запустить оба потока."""
        if self.running:
            print("[DUAL-AT] Автотрейдер уже запущен")
            return
        
        self.running = True
        
        # Загрузка циклов выполняется в mTrade.py ДО вызова start()
        # Здесь только запускаем потоки
        
        # Запустить поток-циклер
        self.cycler_thread = Thread(
            target=self._run_cycler,
            name="AutoTrader-Cycler",
            daemon=True
        )
        self.cycler_thread.start()
        print(f"[DUAL-AT] ✅ Поток-циклер запущен")
        
        # Запустить поток-реактор
        self.reactor_thread = Thread(
            target=self._run_reactor,
            name="AutoTrader-Reactor",
            daemon=True
        )
        self.reactor_thread.start()
        print(f"[DUAL-AT] ✅ Поток-реактор запущен")
        
        print("[DUAL-AT] 🚀 Двухпоточный автотрейдер активен")
    
    def stop(self):
        """Остановить оба потока."""
        if not self.running:
            print("[DUAL-AT] Автотрейдер не запущен")
            return
        
        print("[DUAL-AT] Остановка автотрейдера...")
        self.running = False
        
        # Дать время потокам завершить текущие операции
        time.sleep(1)
        
        # ИСПРАВЛЕНИЕ: Используем метод autotrader для сохранения циклов в файл
        self.autotrader._save_cycles_state()
        
        print("[DUAL-AT] ⛔ Автотрейдер остановлен")
    
    def _run_cycler(self):
        """
        ПОТОК-ЦИКЛЕР
        Последовательно обрабатывает валюты по кругу.
        """
        print("[CYCLER] Поток-циклер запущен")
        
        current_index = 0
        cycle_sleep = 0.01  # ОПТИМИЗАЦИЯ: 0.01 сек (10мс) — максимальная скорость
        
        while self.running:
            try:
                with self.lock:
                    self.stats['cycler_iterations'] += 1
                
                # 1. Обработать срочные задачи из очереди
                urgent_processed = 0
                while urgent_processed < self.max_urgent_per_cycle:
                    try:
                        task = self.urgent_queue.get_nowait()
                        currency = task.get('currency')
                        reason = task.get('reason', 'unknown')
                        
                        if self._try_process_currency(currency, f"urgent:{reason}"):
                            with self.lock:
                                self.stats['urgent_processed'] += 1
                            urgent_processed += 1
                        else:
                            with self.lock:
                                self.stats['urgent_skipped'] += 1
                    
                    except Empty:
                        break
                
                # 2. Обработать текущую валюту из цикла
                if not self.currencies:
                    time.sleep(1)
                    continue
                
                currency = self.currencies[current_index]
                
                if self._try_process_currency(currency, "cycle"):
                    with self.lock:
                        self.stats['cycler_processed'] += 1
                else:
                    with self.lock:
                        self.stats['cycler_skipped'] += 1
                
                # 3. Перейти к следующей валюте
                current_index = (current_index + 1) % len(self.currencies)
                
                # 4. Пауза
                time.sleep(cycle_sleep)
            
            except Exception as e:
                print(f"[CYCLER] ❌ Ошибка: {e}")
                print(traceback.format_exc())
                with self.lock:
                    self.stats['errors'] += 1
                time.sleep(2)
        
        print("[CYCLER] Поток-циклер завершён")
    
    def _run_reactor(self):
        """
        ПОТОК-РЕАКТОР
        Реагирует на WebSocket обновления.
        """
        print("[REACTOR] Поток-реактор запущен")
        
        last_update_time = {}
        
        while self.running:
            try:
                # Проверить WebSocket обновления для каждой валюты
                for currency in self.currencies:
                    try:
                        pair = f"{currency}_USDT"
                        pair_data = self.ws_manager.get_data(pair) if self.ws_manager else None
                        
                        if not pair_data or not pair_data.get('ticker'):
                            continue
                        
                        with self.lock:
                            self.stats['reactor_updates'] += 1
                        
                        # Проверить debounce
                        now = time.time()
                        last_time = last_update_time.get(currency, 0)
                        
                        if now - last_time < self.debounce_seconds:
                            with self.lock:
                                self.stats['reactor_debounced'] += 1
                            continue
                        
                        # Проверить флаг обработки
                        with self.lock:
                            if self.processing_flags.get(currency, False):
                                continue
                        
                        # Поставить задачу в очередь
                        try:
                            self.urgent_queue.put_nowait({
                                'currency': currency,
                                'reason': 'price_update',
                                'timestamp': now
                            })
                            
                            last_update_time[currency] = now
                            with self.lock:
                                self.stats['reactor_queued'] += 1
                        
                        except Full:
                            pass
                    
                    except Exception as e:
                        print(f"[REACTOR] Ошибка обработки {currency}: {e}")
                        continue
                
                time.sleep(0.05)  # ОПТИМИЗАЦИЯ: 0.05 сек (50мс) — быстрее реакция
            
            except Exception as e:
                print(f"[REACTOR] ❌ Ошибка: {e}")
                print(traceback.format_exc())
                with self.lock:
                    self.stats['errors'] += 1
                time.sleep(1)
        
        print("[REACTOR] Поток-реактор завершён")
    
    def _try_process_currency(self, currency: str, reason: str) -> bool:
        """Попытаться обработать валюту."""
        t_process_start = time.time()
        try:
            # Проверить флаг обработки
            with self.lock:
                if self.processing_flags.get(currency, False):
                    return False
                
                # Проверить debounce
                now = time.time()
                last_time = self.last_processed.get(currency, 0)
                
                if now - last_time < self.debounce_seconds:
                    return False
                
                # Проверить разрешение торговли
                permissions = self.state_manager.get_trading_permissions()
                if not permissions.get(currency, False):
                    return False
                
                # Установить флаг обработки
                self.processing_flags[currency] = True
            
            t_before_logic = time.time()
            try:
                # Выполнить торговую логику
                self._execute_trading_logic(currency)
                
                t_after_logic = time.time()
                logic_duration_ms = (t_after_logic - t_before_logic) * 1000
                total_duration_ms = (t_after_logic - t_process_start) * 1000
                
                # Логируем только если обработка заняла > 100ms (подозрительно долго)
                if total_duration_ms > 100:
                    print(f"[PROCESS] ⚠️ {currency} SLOW: logic={logic_duration_ms:.1f}ms, total={total_duration_ms:.1f}ms, reason={reason}")
                
                # Обновить время последней обработки
                with self.lock:
                    self.last_processed[currency] = time.time()
                
                return True
            
            finally:
                # Сбросить флаг обработки
                with self.lock:
                    self.processing_flags[currency] = False
        
        except Exception as e:
            print(f"[PROCESS] ❌ {currency} ошибка: {e}")
            with self.lock:
                self.stats['errors'] += 1
            return False
    
    def _execute_trading_logic(self, currency: str):
        """Выполнить торговую логику."""
        quote = "USDT"
        
        try:
            # Получить данные цены
            pair = f"{currency}_{quote}"
            pair_data = self.ws_manager.get_data(pair) if self.ws_manager else None
            
            if not pair_data or not pair_data.get('ticker'):
                return
            
            # Вызвать методы автотрейдера
            self.autotrader._try_start_cycle(currency, quote)
            self.autotrader._try_rebuy(currency, quote)
            self.autotrader._try_sell(currency, quote)
        
        except Exception as e:
            print(f"[LOGIC] ❌ {currency} ошибка: {e}")
            with self.lock:
                self.stats['errors'] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику работы."""
        with self.lock:
            return dict(self.stats)
    
    def get_cycle(self, currency: str) -> Optional[Dict[str, Any]]:
        """Получить цикл конкретной валюты."""
        return self.cycles.get(currency)
