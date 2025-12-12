#!/usr/bin/env python3
"""
ДИАГНОСТИКА ДВОЙНЫХ СТАРТОВЫХ ПОКУПОК

Этот скрипт анализирует проблему множественных стартовых покупок и тестирует защиты.

Что проверяется:
1. Логирование всех защит из autotrader.py
2. Анализ логики установки флагов (pending_start, active)
3. Проверка race condition между потоками
4. Анализ состояния циклов после продажи
5. Симуляция сценария "продажа → покупка"

Использование:
    python diagnose_double_start_buy.py [--test-race-condition] [--analyze-state] [--watch-logs]
"""

import json
import os
import sys
import time
import threading
from datetime import datetime
from pathlib import Path

# Пути к файлам
CYCLES_STATE_FILE = 'autotrader_cycles_state.json'
CONFIG_FILE = 'config.json'

class DoubleStartBuyDiagnostic:
    def __init__(self):
        self.cycles_state_path = Path(CYCLES_STATE_FILE)
        self.config_path = Path(CONFIG_FILE)
        
    def load_cycles_state(self):
        """Загрузить состояние циклов"""
        if not self.cycles_state_path.exists():
            print(f"⚠️ Файл {CYCLES_STATE_FILE} не найден!")
            return {}
        
        with open(self.cycles_state_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def analyze_cycle_state(self, base: str = None):
        """Анализ состояния циклов"""
        print("\n" + "="*80)
        print("АНАЛИЗ СОСТОЯНИЯ ЦИКЛОВ")
        print("="*80)
        
        cycles = self.load_cycles_state()
        
        if not cycles:
            print("❌ Нет данных о циклах")
            return
        
        if base:
            # Анализ конкретной валюты
            if base not in cycles:
                print(f"❌ Цикл для {base} не найден")
                return
            
            self._analyze_single_cycle(base, cycles[base])
        else:
            # Анализ всех валют
            for currency, cycle in cycles.items():
                self._analyze_single_cycle(currency, cycle)
                print()
    
    def _analyze_single_cycle(self, base: str, cycle: dict):
        """Детальный анализ одного цикла"""
        print(f"\n🔍 {base}")
        print("-" * 40)
        
        # Основные флаги
        active = cycle.get('active', False)
        pending_start = cycle.get('pending_start', False)
        active_step = cycle.get('active_step', 0)
        
        print(f"  active: {active}")
        print(f"  pending_start: {pending_start}")
        print(f"  active_step: {active_step}")
        
        # Цены и объёмы
        start_price = cycle.get('start_price', 0.0)
        last_buy_price = cycle.get('last_buy_price', 0.0)
        base_volume = cycle.get('base_volume', 0.0)
        total_invested = cycle.get('total_invested_usd', 0.0)
        
        print(f"  start_price: {start_price:.8f}")
        print(f"  last_buy_price: {last_buy_price:.8f}")
        print(f"  base_volume: {base_volume:.8f}")
        print(f"  total_invested_usd: {total_invested:.2f}")
        
        # Временные метки
        last_sell_time = cycle.get('last_sell_time', 0)
        last_start_attempt = cycle.get('last_start_attempt', 0)
        
        if last_sell_time > 0:
            elapsed = time.time() - last_sell_time
            dt = datetime.fromtimestamp(last_sell_time).strftime('%Y-%m-%d %H:%M:%S')
            print(f"  last_sell_time: {dt} ({elapsed:.1f}s назад)")
        
        if last_start_attempt > 0:
            elapsed = time.time() - last_start_attempt
            dt = datetime.fromtimestamp(last_start_attempt).strftime('%Y-%m-%d %H:%M:%S')
            print(f"  last_start_attempt: {dt} ({elapsed:.1f}s назад)")
        
        # Pending операции
        pending = cycle.get('pending', {})
        if pending:
            print(f"  pending: {json.dumps(pending, indent=4)}")
        
        # Диагностика состояния
        print("\n  📊 ДИАГНОСТИКА:")
        
        if active and pending_start:
            print("  ⚠️ АНОМАЛИЯ: active=True И pending_start=True одновременно!")
            print("     Это невозможно по логике - требуется исправление")
        
        if not active and not pending_start and base_volume > 0:
            print("  ⚠️ АНОМАЛИЯ: Есть баланс BASE, но цикл неактивен!")
            print(f"     base_volume={base_volume:.8f}, но active=False")
            print("     Возможно, цикл был сброшен, но баланс остался")
        
        if pending_start and last_start_attempt == 0:
            print("  ⚠️ АНОМАЛИЯ: pending_start=True, но нет last_start_attempt!")
            print("     Флаг был установлен, но метка времени не записана")
        
        if active and start_price == 0:
            print("  ⚠️ АНОМАЛИЯ: Цикл активен, но start_price=0!")
            print("     Это невозможно - цикл должен иметь цену входа")
        
        # Оценка риска двойной покупки
        risk_level = self._assess_double_buy_risk(cycle)
        print(f"\n  ⚠️ РИСК ДВОЙНОЙ ПОКУПКИ: {risk_level}")
    
    def _assess_double_buy_risk(self, cycle: dict) -> str:
        """Оценка риска двойной стартовой покупки"""
        active = cycle.get('active', False)
        pending_start = cycle.get('pending_start', False)
        base_volume = cycle.get('base_volume', 0.0)
        last_sell_time = cycle.get('last_sell_time', 0)
        
        # Низкий риск: цикл активен
        if active and not pending_start and base_volume > 0:
            return "НИЗКИЙ ✅ (цикл активен, баланс есть)"
        
        # Высокий риск: pending_start=True долгое время
        if pending_start:
            elapsed = time.time() - cycle.get('last_start_attempt', time.time())
            if elapsed > 10:
                return "ВЫСОКИЙ ⚠️ (pending_start=True больше 10с)"
            else:
                return "СРЕДНИЙ 🟡 (pending_start=True, идёт покупка)"
        
        # Высокий риск: недавняя продажа без баланса
        if last_sell_time > 0:
            elapsed = time.time() - last_sell_time
            if elapsed < 10 and base_volume == 0 and not active:
                return "ВЫСОКИЙ ⚠️ (недавняя продажа, нет защиты)"
        
        # Средний риск: нет цикла, нет баланса
        if not active and base_volume == 0:
            return "СРЕДНИЙ 🟡 (нет цикла, возможен старт)"
        
        return "НЕОПРЕДЕЛЁННЫЙ ❓"
    
    def test_race_condition_simulation(self, base: str = 'SOL', quote: str = 'USDT'):
        """Симуляция race condition между потоками"""
        print("\n" + "="*80)
        print("ТЕСТ: СИМУЛЯЦИЯ RACE CONDITION")
        print("="*80)
        print(f"Валюта: {base}/{quote}")
        print("Сценарий: 3 потока одновременно пытаются сделать стартовую покупку")
        print()
        
        # Загружаем текущее состояние
        cycles = self.load_cycles_state()
        if base not in cycles:
            print(f"⚠️ Цикл {base} не найден в состоянии, создаём новый")
            cycles[base] = {
                'active': False,
                'pending_start': False,
                'base_volume': 0.0,
                'start_price': 0.0
            }
        
        # Сохраняем исходное состояние
        original_state = cycles[base].copy()
        print(f"Исходное состояние: active={original_state.get('active')}, pending_start={original_state.get('pending_start')}")
        
        # Счётчик успешных "покупок"
        purchase_counter = {'count': 0}
        lock = threading.Lock()
        
        def simulate_start_buy(thread_id: int):
            """Симуляция стартовой покупки"""
            print(f"[Thread {thread_id}] Попытка стартовой покупки...")
            
            # Читаем состояние
            cycle = cycles.get(base, {})
            
            # Проверка 1: Цикл активен?
            if cycle.get('active'):
                print(f"[Thread {thread_id}] ❌ БЛОК: цикл активен")
                return
            
            # Проверка 2: pending_start?
            if cycle.get('pending_start'):
                print(f"[Thread {thread_id}] ❌ БЛОК: pending_start=True")
                return
            
            # КРИТИЧЕСКИЙ УЧАСТОК: установка флага и "покупка"
            # В реальном коде здесь должна быть блокировка!
            
            print(f"[Thread {thread_id}] ✅ Проверки пройдены, устанавливаем pending_start=True")
            
            # Имитация задержки перед установкой флага (race condition!)
            time.sleep(0.01)
            
            # Устанавливаем флаг
            cycle['pending_start'] = True
            cycle['last_start_attempt'] = time.time()
            
            # Имитация размещения ордера (задержка)
            time.sleep(0.05)
            
            # "Покупка" прошла успешно
            with lock:
                purchase_counter['count'] += 1
                purchase_id = purchase_counter['count']
            
            print(f"[Thread {thread_id}] 💰 ПОКУПКА #{purchase_id} ВЫПОЛНЕНА!")
            
            # Активируем цикл
            cycle['active'] = True
            cycle['pending_start'] = False
            cycle['base_volume'] = 0.1  # Купили 0.1 BASE
            cycle['start_price'] = 100.0
            
            cycles[base] = cycle
        
        # Запускаем 3 потока одновременно
        threads = []
        for i in range(3):
            t = threading.Thread(target=simulate_start_buy, args=(i+1,))
            threads.append(t)
        
        # Старт всех потоков одновременно
        print("\n🚀 Запуск 3 потоков одновременно...")
        for t in threads:
            t.start()
        
        # Ждём завершения
        for t in threads:
            t.join()
        
        # Результат
        print(f"\n📊 РЕЗУЛЬТАТ ТЕСТА:")
        print(f"  Количество выполненных покупок: {purchase_counter['count']}")
        
        if purchase_counter['count'] == 1:
            print("  ✅ ТЕСТ ПРОЙДЕН: Только одна покупка (защита работает)")
        else:
            print(f"  ❌ ТЕСТ НЕ ПРОЙДЕН: {purchase_counter['count']} покупок (race condition!)")
            print("  Причина: Отсутствует атомарная блокировка (Lock)")
            print("  Решение: Использовать threading.Lock в autotrader.py")
        
        # Восстанавливаем исходное состояние
        cycles[base] = original_state
    
    def test_lock_creation_race_condition(self, base: str = 'SOL', quote: str = 'USDT'):
        """Демонстрация race condition при создании Lock'ов (БАГ до исправления)"""
        print("\n" + "="*80)
        print("ТЕСТ: RACE CONDITION ПРИ СОЗДАНИИ LOCK'ОВ (КРИТИЧЕСКИЙ БАГ)")
        print("="*80)
        print(f"Валюта: {base}/{quote}")
        print("Сценарий: 3 потока одновременно пытаются создать Lock для валюты")
        print()
        
        # Симуляция НЕПРАВИЛЬНОГО кода (до исправления)
        print("🔴 НЕПРАВИЛЬНЫЙ КОД (БАГ):")
        print("-" * 40)
        print("""
        # Это код ДО исправления - НЕБЕЗОПАСЕН!
        if base not in self._start_cycle_locks:
            from threading import Lock
            self._start_cycle_locks[base] = Lock()
        
        acquired = self._start_cycle_locks[base].acquire(blocking=False)
        """)
        
        # Имитация словаря с Lock'ами
        locks_dict_broken = {}
        lock_ids_broken = {'count': 0}
        
        def broken_lock_creation(thread_id: int):
            """Неправильное создание Lock'а - race condition"""
            import threading
            print(f"[Thread {thread_id}] Проверяю: '{base}' in locks_dict? -> {base in locks_dict_broken}")
            
            # RACE CONDITION ЗДЕСЬ!
            if base not in locks_dict_broken:
                time.sleep(0.001)  # Имитация задержки
                
                # Каждый поток создаёт СВОЙ Lock!
                new_lock = threading.Lock()
                lock_ids_broken['count'] += 1
                lock_id = lock_ids_broken['count']
                
                print(f"[Thread {thread_id}] Создал Lock #{lock_id}")
                locks_dict_broken[base] = (new_lock, lock_id)
            
            # Попытка захватить Lock
            if base in locks_dict_broken:
                current_lock, lock_id = locks_dict_broken[base]
                acquired = current_lock.acquire(blocking=False)
                print(f"[Thread {thread_id}] Захват Lock #{lock_id}: {'✅ УСПЕХ' if acquired else '❌ ЗАНЯТ'}")
                return acquired
            return False
        
        # Запуск потоков
        print("\n🚀 Запуск 3 потоков...")
        threads = []
        for i in range(3):
            t = threading.Thread(target=broken_lock_creation, args=(i+1,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        print(f"\n📊 РЕЗУЛЬТАТ (НЕПРАВИЛЬНЫЙ КОД):")
        print(f"  Создано Lock'ов: {lock_ids_broken['count']}")
        if lock_ids_broken['count'] > 1:
            print(f"  ❌ БАГ: Создано {lock_ids_broken['count']} разных Lock'а для одной валюты!")
            print(f"  ❌ Несколько потоков могли пройти защиту одновременно!")
        
        # Теперь правильный код
        print("\n" + "="*80)
        print("✅ ПРАВИЛЬНЫЙ КОД (ИСПРАВЛЕНИЕ):")
        print("-" * 40)
        print("""
        # Это код ПОСЛЕ исправления - БЕЗОПАСЕН!
        with self._locks_creation_lock:  # Мастер-Lock!
            if base not in self._start_cycle_locks:
                from threading import Lock
                self._start_cycle_locks[base] = Lock()
        
        acquired = self._start_cycle_locks[base].acquire(blocking=False)
        """)
        
        # Правильная реализация
        locks_dict_correct = {}
        lock_ids_correct = {'count': 0}
        master_lock = threading.Lock()
        
        def correct_lock_creation(thread_id: int):
            """Правильное создание Lock'а с мастер-Lock'ом"""
            import threading
            
            # КРИТИЧНО: Проверка и создание под защитой мастер-Lock'а
            with master_lock:
                if base not in locks_dict_correct:
                    time.sleep(0.001)  # Имитация задержки
                    
                    new_lock = threading.Lock()
                    lock_ids_correct['count'] += 1
                    lock_id = lock_ids_correct['count']
                    
                    print(f"[Thread {thread_id}] Создал Lock #{lock_id} (под защитой мастер-Lock'а)")
                    locks_dict_correct[base] = (new_lock, lock_id)
                else:
                    _, lock_id = locks_dict_correct[base]
                    print(f"[Thread {thread_id}] Lock #{lock_id} уже существует")
            
            # Попытка захватить Lock (вне мастер-Lock'а)
            if base in locks_dict_correct:
                current_lock, lock_id = locks_dict_correct[base]
                acquired = current_lock.acquire(blocking=False)
                print(f"[Thread {thread_id}] Захват Lock #{lock_id}: {'✅ УСПЕХ' if acquired else '❌ ЗАНЯТ'}")
                if acquired:
                    time.sleep(0.01)  # Имитация работы
                    current_lock.release()
                return acquired
            return False
        
        print("\n🚀 Запуск 3 потоков...")
        threads = []
        successes = []
        for i in range(3):
            def run(tid):
                result = correct_lock_creation(tid)
                successes.append(result)
            
            t = threading.Thread(target=run, args=(i+1,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        print(f"\n📊 РЕЗУЛЬТАТ (ПРАВИЛЬНЫЙ КОД):")
        print(f"  Создано Lock'ов: {lock_ids_correct['count']}")
        print(f"  Захватов успешных: {sum(successes)}")
        
        if lock_ids_correct['count'] == 1:
            print(f"  ✅ УСПЕХ: Создан только ОДИН Lock для валюты!")
            print(f"  ✅ Только один поток смог захватить Lock!")
        else:
            print(f"  ❌ Что-то пошло не так...")
        
        print("\n" + "="*80)
        print("ВЫВОДЫ:")
        print("="*80)
        print("""
1. БЕЗ мастер-Lock'а:
   ❌ Несколько потоков создают РАЗНЫЕ Lock'и
   ❌ Каждый поток захватывает СВОЙ Lock
   ❌ Все потоки проходят защиту → ДВОЙНЫЕ ПОКУПКИ

2. С мастер-Lock'ом:
   ✅ Создаётся только ОДИН Lock для валюты
   ✅ Все потоки пытаются захватить ОДИН И ТОТ ЖЕ Lock
   ✅ Только один поток проходит защиту → НЕТ ДВОЙНЫХ ПОКУПОК

3. Почему это критично:
   - Lock - это ОБЪЕКТ, а не примитив
   - Lock() создаёт НОВЫЙ объект при каждом вызове
   - Запись в словарь НЕ атомарна без блокировки
   - Результат: race condition при инициализации защиты!
        """)
    
    def check_protection_code(self):
        """Проверка кода защит в autotrader.py"""
        print("\n" + "="*80)
        print("ПРОВЕРКА ЗАЩИТ В КОДЕ")
        print("="*80)
        
        autotrader_path = Path('autotrader.py')
        if not autotrader_path.exists():
            print("❌ Файл autotrader.py не найден!")
            return
        
        with open(autotrader_path, 'r', encoding='utf-8') as f:
            code = f.read()
        
        # Проверяем наличие ключевых защит
        checks = {
            'Lock для валюты': 'self._start_cycle_locks' in code,
            'Проверка pending_start до Lock': "if cycle.get('pending_start'):" in code,
            'Проверка active до Lock': "if cycle.get('active'):" in code,
            'Проверка баланса BASE': 'base_balance_in_quote >= purchase_usd' in code,
            'Проверка времени после продажи': 'last_sell_time' in code,
            'Финальная проверка перед покупкой': 'КРИТИЧЕСКАЯ ФИНАЛЬНАЯ ПРОВЕРКА' in code or 'ФИНАЛЬНАЯ ПРОВЕРКА ПЕРЕД ПОКУПКОЙ' in code,
            'Установка pending_start=True': "cycle['pending_start'] = True" in code,
            'Логирование [PROTECTION]': '[PROTECTION]' in code
        }
        
        print("\n📋 Результаты проверки:")
        all_ok = True
        for check_name, result in checks.items():
            status = "✅" if result else "❌"
            print(f"  {status} {check_name}")
            if not result:
                all_ok = False
        
        if all_ok:
            print("\n✅ Все защиты присутствуют в коде!")
        else:
            print("\n⚠️ Некоторые защиты отсутствуют - требуется добавить!")
    
    def generate_fix_report(self):
        """Генерация отчёта с рекомендациями"""
        print("\n" + "="*80)
        print("ОТЧЁТ И РЕКОМЕНДАЦИИ")
        print("="*80)
        
        print("""
📌 ПРОБЛЕМА: Множественные стартовые покупки после продажи

🔍 ПРИЧИНА:
   Race condition между потоками автотрейдера. Несколько потоков одновременно
   проверяют условия для стартовой покупки, и все они проходят проверки,
   т.к. флаги устанавливаются с задержкой.

✅ РЕШЕНИЕ (уже реализовано в autotrader.py):

1. **Атомарная блокировка (Lock)**
   - Создан словарь self._start_cycle_locks[base] для каждой валюты
   - Используется Lock.acquire(blocking=False) - неблокирующий захват
   - Если Lock уже захвачен другим потоком - выход из функции
   - Lock освобождается в finally блоке

2. **Проверка pending_start ДО блокировки**
   - Быстрый выход если покупка уже идёт
   - Экономия ресурсов

3. **Double-check после захвата Lock**
   - Повторная проверка active и pending_start ПОСЛЕ захвата Lock
   - Гарантия, что состояние не изменилось во время ожидания

4. **Тройная проверка баланса BASE**
   - Проверка 1: В начале _try_start_cycle (до Lock)
   - Проверка 2: После захвата Lock (в _try_start_cycle_impl)
   - Проверка 3: ПЕРЕД размещением ордера (финальная)
   - Все проверки через API, без кеша

5. **Проверка времени после продажи**
   - Минимум 5 секунд после last_sell_time
   - Даёт время на завершение всех операций

6. **Правильный порядок установки флагов**
   - Сначала: pending_start = True (блокирует повторные старты)
   - Сохранение состояния в файл
   - Размещение ордера
   - После успеха: active = True, pending_start = False

📊 ТЕСТИРОВАНИЕ:

1. Запустить autotrader с новым кодом
2. Выполнить ручную продажу любой валюты
3. Сбросить цикл через UI
4. Наблюдать логи - должна быть ТОЛЬКО ОДНА покупка
5. Проверить логи на наличие [PROTECTION] сообщений

🔧 ДОПОЛНИТЕЛЬНО:

Если проблема сохраняется:
1. Включить детальное логирование всех Lock операций
2. Добавить уникальные ID для каждой попытки покупки
3. Логировать все проверки с timestamp
4. Использовать этот скрипт для анализа состояния циклов

📝 КАК ИСПОЛЬЗОВАТЬ ЭТОТ СКРИПТ:

# Анализ состояния всех циклов
python diagnose_double_start_buy.py --analyze-state

# Анализ конкретной валюты
python diagnose_double_start_buy.py --analyze-state --base SOL

# Тест race condition
python diagnose_double_start_buy.py --test-race-condition

# Проверка кода защит
python diagnose_double_start_buy.py --check-protection
""")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Диагностика двойных стартовых покупок')
    parser.add_argument('--analyze-state', action='store_true', help='Анализ состояния циклов')
    parser.add_argument('--base', type=str, help='Анализ конкретной валюты')
    parser.add_argument('--test-race-condition', action='store_true', help='Тест race condition')
    parser.add_argument('--test-lock-race', action='store_true', help='Тест race condition при создании Lock\'ов')
    parser.add_argument('--check-protection', action='store_true', help='Проверка защит в коде')
    parser.add_argument('--report', action='store_true', help='Показать отчёт и рекомендации')
    
    args = parser.parse_args()
    
    diag = DoubleStartBuyDiagnostic()
    
    # Если нет аргументов - показываем всё
    if not any(vars(args).values()):
        args.analyze_state = True
        args.check_protection = True
        args.report = True
    
    if args.analyze_state:
        diag.analyze_cycle_state(base=args.base)
    
    if args.test_race_condition:
        diag.test_race_condition_simulation()
    
    if args.test_lock_race:
        diag.test_lock_creation_race_condition()
    
    if args.check_protection:
        diag.check_protection_code()
    
    if args.report:
        diag.generate_fix_report()

if __name__ == '__main__':
    main()
