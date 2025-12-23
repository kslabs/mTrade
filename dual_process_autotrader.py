"""
Dual-Process AutoTrader Architecture
=====================================
Два параллельных процесса для максимально быстрой реакции на изменения цен:

1. Процесс-циклер (Cycler Process):
   - Последовательно перебирает валюты
   - Проверяет флаг обработки перед началом
   - Выполняет стандартную логику торговли
   - Устанавливает/сбрасывает флаги

2. Процесс-реактор (Reactor Process):
   - Реагирует на WebSocket обновления цен
   - Ставит задачи в очередь urgent-обработки
   - Применяет debounce для защиты от всплесков
"""

import time
import traceback
from multiprocessing import Process, Manager, Queue
from queue import Empty, Full
from typing import Optional, Dict, Any, Callable
from collections import defaultdict
from datetime import datetime
from autotrader import AutoTrader

class DualProcessAutoTrader:
    """
    Двухпроцессный автотрейдер с разделением на циклическую и реактивную обработку.
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
        """
        Инициализация двухпроцессного автотрейдера.
        
        Args:
            api_client_provider: Функция для получения API клиента
            ws_manager: WebSocket менеджер для получения данных
            state_manager: Менеджер состояния для сохранения данных
            currencies: Список валют для торговли
            debounce_seconds: Минимальный интервал между обработками одной валюты
            urgent_queue_max_size: Максимальный размер очереди срочных задач
            max_urgent_per_cycle: Максимум срочных задач за один цикл
        """
        self.api_client_provider = api_client_provider
        self.ws_manager = ws_manager
        self.state_manager = state_manager
        self.currencies = currencies
        self.debounce_seconds = debounce_seconds
        self.max_urgent_per_cycle = max_urgent_per_cycle
        
        # ВАЖНО: AutoTrader будет создаваться в каждом процессе отдельно,
        # а не передаваться через multiprocessing (он не сериализуем)
        # Сохраняем параметры для создания в процессах
        self._autotrader_params = {
            'api_client_provider': api_client_provider,
            'ws_manager': ws_manager,
            'state_manager': state_manager
        }
        
        # Multiprocessing Manager для разделяемых структур
        self.manager = Manager()
        
        # Флаги обработки (currency -> bool)
        # True = валюта сейчас обрабатывается, другие процессы должны пропустить
        self.processing_flags = self.manager.dict()
        
        # Последнее время обработки для debounce (currency -> timestamp)
        self.last_processed = self.manager.dict()
        
        # Очередь срочных задач (приоритетная)
        self.urgent_queue = Queue(maxsize=urgent_queue_max_size)
        
        # Статистика
        self.stats = self.manager.dict({
            'cycler_iterations': 0,
            'cycler_processed': 0,
            'cycler_skipped': 0,
            'reactor_updates': 0,
            'reactor_queued': 0,
            'reactor_debounced': 0,
            'urgent_processed': 0,
            'urgent_skipped': 0,
            'errors': 0
        })
        
        # Циклы автотрейдера (currency -> cycle_state)
        self.cycles = self.manager.dict()
        
        # Процессы
        self.cycler_process: Optional[Process] = None
        self.reactor_process: Optional[Process] = None
        
        # Флаги управления
        self.running = self.manager.Value('b', False)
        
        print("[DUAL-AT] Инициализация двухпроцессного автотрейдера")
        print(f"[DUAL-AT] Валюты: {len(currencies)}")
        print(f"[DUAL-AT] Debounce: {debounce_seconds}s")
        print(f"[DUAL-AT] Max urgent/cycle: {max_urgent_per_cycle}")
    
    def start(self):
        """Запустить оба процесса."""
        if self.running.value:
            print("[DUAL-AT] Автотрейдер уже запущен")
            return
        
        self.running.value = True
        
        # Загрузить состояние циклов
        self._load_cycles_state()
        
        # Запустить процесс-циклер
        self.cycler_process = Process(
            target=self._run_cycler,
            name="AutoTrader-Cycler",
            daemon=True
        )
        self.cycler_process.start()
        print(f"[DUAL-AT] ✅ Процесс-циклер запущен (PID: {self.cycler_process.pid})")
        
        # Запустить процесс-реактор
        self.reactor_process = Process(
            target=self._run_reactor,
            name="AutoTrader-Reactor",
            daemon=True
        )
        self.reactor_process.start()
        print(f"[DUAL-AT] ✅ Процесс-реактор запущен (PID: {self.reactor_process.pid})")
        
        print("[DUAL-AT] 🚀 Двухпроцессный автотрейдер активен")
    
    def stop(self):
        """Остановить оба процесса."""
        if not self.running.value:
            print("[DUAL-AT] Автотрейдер не запущен")
            return
        
        print("[DUAL-AT] Остановка автотрейдера...")
        self.running.value = False
        
        # Дать время процессам завершить текущие операции
        time.sleep(1)
        
        # Принудительно завершить процессы если они не остановились
        if self.cycler_process and self.cycler_process.is_alive():
            self.cycler_process.terminate()
            self.cycler_process.join(timeout=2)
            print("[DUAL-AT] Процесс-циклер остановлен")
        
        if self.reactor_process and self.reactor_process.is_alive():
            self.reactor_process.terminate()
            self.reactor_process.join(timeout=2)
            print("[DUAL-AT] Процесс-реактор остановлен")
        
        # Сохранить состояние
        self._save_cycles_state()
        
        print("[DUAL-AT] ⛔ Автотрейдер остановлен")
    
    def _run_cycler(self):
        """
        ПРОЦЕСС-ЦИКЛЕР
        Последовательно обрабатывает валюты по кругу.
        """
        print("[CYCLER] Процесс-циклер запущен")
        
        # Создать AutoTrader в этом процессе
        autotrader = AutoTrader(
            api_client_provider=self.api_client_provider,
            ws_manager=self.ws_manager,
            state_manager=self.state_manager
        )
        
        current_index = 0
        cycle_sleep = 0.5  # Пауза между валютами
        
        while self.running.value:
            try:
                self.stats['cycler_iterations'] = self.stats.get('cycler_iterations', 0) + 1
                
                # 1. Обработать срочные задачи из очереди (до лимита)
                urgent_processed = 0
                while urgent_processed < self.max_urgent_per_cycle:
                    try:
                        task = self.urgent_queue.get_nowait()
                        currency = task.get('currency')
                        reason = task.get('reason', 'unknown')
                        
                        if self._try_process_currency(autotrader, currency, f"urgent:{reason}"):
                            self.stats['urgent_processed'] = self.stats.get('urgent_processed', 0) + 1
                            urgent_processed += 1
                        else:
                            self.stats['urgent_skipped'] = self.stats.get('urgent_skipped', 0) + 1
                    
                    except Empty:
                        break  # Очередь пуста
                
                # 2. Обработать текущую валюту из цикла
                if not self.currencies:
                    time.sleep(1)
                    continue
                
                currency = self.currencies[current_index]
                
                if self._try_process_currency(autotrader, currency, "cycle"):
                    self.stats['cycler_processed'] = self.stats.get('cycler_processed', 0) + 1
                else:
                    self.stats['cycler_skipped'] = self.stats.get('cycler_skipped', 0) + 1
                
                # 3. Перейти к следующей валюте
                current_index = (current_index + 1) % len(self.currencies)
                
                # 4. Пауза между валютами
                time.sleep(cycle_sleep)
            
            except Exception as e:
                print(f"[CYCLER] ❌ Ошибка: {e}")
                print(traceback.format_exc())
                self.stats['errors'] = self.stats.get('errors', 0) + 1
                time.sleep(2)
        
        print("[CYCLER] Процесс-циклер завершён")
    
    def _run_reactor(self):
        """
        ПРОЦЕСС-РЕАКТОР
        Реагирует на WebSocket обновления и ставит задачи в очередь.
        """
        print("[REACTOR] Процесс-реактор запущен")
        
        # Отслеживание последних обновлений для debounce
        last_update_time = defaultdict(float)
        
        while self.running.value:
            try:
                # Получить обновления от WebSocket
                # TODO: Интегрировать с реальным WS
                # Пока используем polling с небольшой паузой
                time.sleep(0.05)  # 50ms polling
                
                # Проверить обновления для каждой валюты
                for currency in self.currencies:
                    try:
                        # Получить данные пары
                        pair = f"{currency}_USDT"
                        pair_data = self.ws_manager.get_data(pair) if self.ws_manager else None
                        
                        if not pair_data or not pair_data.get('ticker'):
                            continue
                        
                        self.stats['reactor_updates'] = self.stats.get('reactor_updates', 0) + 1
                        
                        # Проверить debounce
                        now = time.time()
                        last_time = last_update_time.get(currency, 0)
                        
                        if now - last_time < self.debounce_seconds:
                            self.stats['reactor_debounced'] = self.stats.get('reactor_debounced', 0) + 1
                            continue
                        
                        # Проверить флаг обработки
                        if self.processing_flags.get(currency, False):
                            # Валюта уже обрабатывается, пропускаем
                            continue
                        
                        # Поставить задачу в очередь (неблокирующе)
                        try:
                            self.urgent_queue.put_nowait({
                                'currency': currency,
                                'reason': 'price_update',
                                'timestamp': now
                            })
                            
                            last_update_time[currency] = now
                            self.stats['reactor_queued'] = self.stats.get('reactor_queued', 0) + 1
                            
                        except Full:
                            # Очередь переполнена, пропускаем
                            pass
                    
                    except Exception as e:
                        print(f"[REACTOR] Ошибка обработки {currency}: {e}")
                        continue
            
            except Exception as e:
                print(f"[REACTOR] ❌ Ошибка: {e}")
                print(traceback.format_exc())
                self.stats['errors'] = self.stats.get('errors', 0) + 1
                time.sleep(1)
        
        print("[REACTOR] Процесс-реактор завершён")
    
    def _try_process_currency(self, autotrader: AutoTrader, currency: str, reason: str) -> bool:
        """
        Попытаться обработать валюту с учётом флагов и debounce.
        
        Args:
            autotrader: Экземпляр AutoTrader для выполнения торговой логики
            currency: Код валюты
            reason: Причина обработки (для логирования)
        
        Returns:
            True если обработка выполнена, False если пропущена
        """
        try:
            # 1. Проверить флаг обработки
            if self.processing_flags.get(currency, False):
                print(f"[PROCESS] ⏭️  {currency} уже обрабатывается, пропуск ({reason})")
                return False
            
            # 2. Проверить debounce
            now = time.time()
            last_time = self.last_processed.get(currency, 0)
            
            if now - last_time < self.debounce_seconds:
                print(f"[PROCESS] 🕐 {currency} debounce active, пропуск ({reason})")
                return False
            
            # 3. Проверить разрешение торговли
            permissions = self.state_manager.get_trading_permissions()
            if not permissions.get(currency, False):
                print(f"[PROCESS] 🚫 {currency} торговля запрещена, пропуск ({reason})")
                return False
            
            # 4. Установить флаг обработки
            self.processing_flags[currency] = True
            
            try:
                # 5. ВЫПОЛНИТЬ ТОРГОВУЮ ЛОГИКУ
                print(f"[PROCESS] 🔄 {currency} начало обработки ({reason})")
                
                # Вызвать реальную логику автотрейдера
                self._execute_trading_logic(autotrader, currency)
                
                # 6. Обновить время последней обработки
                self.last_processed[currency] = time.time()
                
                print(f"[PROCESS] ✅ {currency} обработка завершена ({reason})")
                return True
            
            finally:
                # 7. Сбросить флаг обработки
                self.processing_flags[currency] = False
        
        except Exception as e:
            print(f"[PROCESS] ❌ {currency} ошибка обработки: {e}")
            print(traceback.format_exc())
            self.stats['errors'] = self.stats.get('errors', 0) + 1
            return False
    
    def _execute_trading_logic(self, autotrader: AutoTrader, currency: str):
        """
        ТОРГОВАЯ ЛОГИКА - интеграция с AutoTrader.
        
        Вызывает методы из autotrader.py:
        - _try_start_cycle: проверка и стартовая покупка
        - _try_rebuy: проверка и докупка
        - _try_sell: проверка и продажа
        
        Args:
            autotrader: Экземпляр AutoTrader
            currency: Код валюты для обработки
        """
        quote = "USDT"  # Котируемая валюта (можно сделать настраиваемой)
        
        try:
            # Убедиться что подписаны на WebSocket
            pair = f"{currency}_{quote}"
            
            # Получить данные цены
            pair_data = self.ws_manager.get_data(pair) if self.ws_manager else None
            
            if not pair_data or not pair_data.get('ticker'):
                print(f"[LOGIC] {currency} нет данных цены, пропуск")
                return
            
            try:
                current_price = float(pair_data['ticker'].get('last', 0))
                if current_price <= 0:
                    print(f"[LOGIC] {currency} некорректная цена: {current_price}")
                    return
            except (ValueError, TypeError) as e:
                print(f"[LOGIC] {currency} ошибка парсинга цены: {e}")
                return
            
            print(f"[LOGIC] {currency} текущая цена: {current_price:.8f} {quote}")
            
            # Вызвать методы автотрейдера последовательно
            # 1. Попытка стартовой покупки (если нет активного цикла)
            autotrader._try_start_cycle(currency, quote)
            
            # 2. Попытка докупки (если есть активный цикл и цена упала)
            autotrader._try_rebuy(currency, quote)
            
            # 3. Попытка продажи (если есть активный цикл и цена достигла цели)
            autotrader._try_sell(currency, quote)
            
        except Exception as e:
            print(f"[LOGIC] ❌ {currency} ошибка выполнения торговой логики: {e}")
            print(traceback.format_exc())
            self.stats['errors'] = self.stats.get('errors', 0) + 1
    
    def _load_cycles_state(self):
        """Загрузить состояние циклов из state_manager."""
        try:
            saved_cycles = self.state_manager.get('autotrader_cycles', {})
            if saved_cycles:
                self.cycles.update(saved_cycles)
                print(f"[DUAL-AT] Загружено {len(saved_cycles)} циклов")
        except Exception as e:
            print(f"[DUAL-AT] Ошибка загрузки циклов: {e}")
    
    def _save_cycles_state(self):
        """Сохранить состояние циклов в state_manager."""
        try:
            self.state_manager.set('autotrader_cycles', dict(self.cycles))
            print("[DUAL-AT] Состояние циклов сохранено")
        except Exception as e:
            print(f"[DUAL-AT] Ошибка сохранения циклов: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику работы."""
        return dict(self.stats)
    
    def get_cycle(self, currency: str) -> Optional[Dict[str, Any]]:
        """Получить цикл конкретной валюты."""
        return self.cycles.get(currency)
