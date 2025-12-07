# Алгоритм создания стартовой покупки и стартового цикла

> **Версия:** 1.0  
> **Дата:** 6 декабря 2025  
> **Статус:** Готов к реализации  
> **Автотрейдер:** AutoTraderV2

---

## 🎯 Цель

Создать **ОДНУ** стартовую покупку (MARKET ордер) для валюты, если у неё ещё нет активного цикла, и запустить цикл докупок/продажи **БЕЗ ДУБЛЕЙ И ГОНОК**.

---

## 📋 Полный алгоритм (пошагово)

### **ШАГ 1: АТОМАРНАЯ ПРОВЕРКА УСЛОВИЙ (под Lock валюты)**

> ⚠️ **КРИТИЧНО:** Все проверки выполняются под `threading.Lock()` для конкретной валюты!

```
АТОМАРНАЯ ПРОВЕРКА (под Lock валюты):
│
├─ 1.1 Проверить, что валюта разрешена к торговле
│   └─ TRADING_PERMISSIONS[currency] == True
│   └─ Иначе → ВЫХОД (пропускаем валюту, ничего не делаем)
│
├─ 1.2 Проверить, что автотрейдер включен глобально
│   └─ AUTO_TRADE_GLOBAL_ENABLED == True
│   └─ Иначе → ВЫХОД (пропускаем валюту, ничего не делаем)
│
├─ 1.3 Проверить, что цикл в состоянии IDLE
│   └─ cycle['state'] == 'IDLE'
│   └─ cycle['active'] == False
│   └─ cycle.get('buying') == False  (флаг "в процессе покупки")
│   └─ Иначе → ВЫХОД (цикл уже активен или покупка в процессе)
│
├─ 1.4 Проверить, что нет активных BUY ордеров
│   └─ api_client.get_open_orders(currency_pair, side='buy') == []
│   └─ Иначе → ВЫХОД (ждём завершения активного ордера)
│
├─ 1.5 Проверить баланс базовой валюты (BTC, ETH и т.д.)
│   └─ balance_base = api_client.get_balance(base_currency)
│   └─ available_base = float(balance_base['available'])
│   └─ min_base_from_table = table[0]['buy_amount']  (шаг 0, колонка Покупка)
│   └─
│   └─ ЕСЛИ available_base >= min_base_from_table:
│   │   └─ У нас УЖЕ ЕСТЬ монеты! Не нужна стартовая покупка!
│   │   └─ Переходим в режим ПРОДАЖИ:
│   │       ├─ Устанавливаем cycle['state'] = 'ACTIVE'
│   │       ├─ Устанавливаем cycle['active'] = True
│   │       ├─ Устанавливаем cycle['base_volume'] = available_base
│   │       ├─ Рассчитываем cycle['start_price'] из истории или текущей цены
│   │       ├─ Рассчитываем cycle['last_buy_price'] = cycle['start_price']
│   │       ├─ Рассчитываем cycle['total_invested_usd'] = available_base * start_price
│   │       ├─ Устанавливаем cycle['active_step'] = 0
│   │       └─ ВЫХОД (цикл активирован в режиме продажи, без покупки)
│   │
│   └─ ИНАЧЕ → Продолжаем к шагу 1.6
│
├─ 1.6 Проверить баланс котируемой валюты (USDT)
│   └─ balance_usdt = api_client.get_balance('USDT')
│   └─ available_usdt = float(balance_usdt['available'])
│   └─ required_usdt = params['start_volume']  (из параметров торговли)
│   └─
│   └─ ЕСЛИ available_usdt < required_usdt:
│   │   └─ Недостаточно средств для стартовой покупки!
│   │   └─ print(f"[START_BUY][{currency}] ⚠️ Недостаточно USDT: {available_usdt} < {required_usdt}")
│   │   └─ ВЫХОД (ничего не делаем, ждём пополнения баланса)
│   │
│   └─ ИНАЧЕ → Продолжаем к шагу 2
│
└─ ЕСЛИ ВСЕ УСЛОВИЯ ВЫПОЛНЕНЫ → Переходим к ШАГУ 2
   ИНАЧЕ → ВЫХОД (не делаем стартовую покупку)
```

---

### **ШАГ 2: ПОЛУЧЕНИЕ ПАРАМЕТРОВ ТОРГОВЛИ**

```python
# Загружаем параметры из state_manager (per-currency)
params = state_manager.get_breakeven_params(base_currency)

# Получаем текущую цену из WebSocket
ws_manager = get_websocket_manager()
pair_data = ws_manager.get_data(f"{base_currency}_USDT")
current_price = float(pair_data['ticker']['last']) if pair_data else 0.0

# Нужны параметры:
# - start_volume: объём стартовой покупки в USD
# - current_price: текущая цена (из WebSocket тикера)
```

---

### **ШАГ 3: РАСЧЁТ ТАБЛИЦЫ БЕЗУБЫТОЧНОСТИ**

```python
from breakeven_calculator import calculate_breakeven_table

# Вызываем калькулятор с текущей ценой
table = calculate_breakeven_table(params, current_price=current_price)

# Таблица содержит все шаги:
# - buy_price: цены покупок для каждого шага
# - buy_amount: объёмы покупок в базовой валюте
# - sell_price: цена продажи для безубытка
# - cumulative_cost: накопленная стоимость в USDT
# - и другие поля...
```

---

### **ШАГ 4: УСТАНОВКА ФЛАГА "ПОКУПКА В ПРОЦЕССЕ"**

```python
# ⚠️ КРИТИЧНО: Устанавливаем флаг ДО создания ордера!
cycle['buying'] = True
cycle['last_action_at'] = time.time()

# Этот флаг предотвращает создание дубликата, если главный цикл
# успеет выполниться ещё раз до завершения покупки
```

---

### **ШАГ 5: СОЗДАНИЕ MARKET ОРДЕРА (стартовая покупка)**

```python
# 🔥 КРИТИЧНО: Это ЕДИНСТВЕННОЕ место, где создаётся стартовая покупка!
# Используем MARKET ордер для мгновенного исполнения

try:
    order = api_client.create_order(
        currency_pair=f"{base_currency}_USDT",
        side="buy",
        type="market",           # MARKET! Не limit!
        amount=params['start_volume'],  # Сумма в USDT для market ордера
        account="spot"
    )
    
    # Логируем создание ордера
    print(f"[START_BUY][{base_currency}] ✅ MARKET ордер создан: {order['id']}")
    print(f"[START_BUY][{base_currency}]   Сумма: {params['start_volume']} USDT")
    
    # Сохраняем ID ордера в цикле
    cycle['start_order_id'] = order['id']
    
except Exception as e:
    # Ошибка при создании ордера
    print(f"[START_BUY][{base_currency}] ❌ Ошибка создания ордера: {e}")
    cycle['buying'] = False  # Снимаем флаг!
    raise  # Пробрасываем исключение
```

---

### **ШАГ 6: ПРОВЕРКА ИСПОЛНЕНИЯ ОРДЕРА**

```python
# Ждём короткое время (0.5-1 сек), затем проверяем статус
time.sleep(0.5)

try:
    order_status = api_client.get_order(
        order_id=order['id'],
        currency_pair=f"{base_currency}_USDT"
    )
    
    if order_status['status'] != 'closed':
        # Ордер не исполнен полностью
        print(f"[START_BUY][{base_currency}] ⚠️ MARKET ордер не исполнен: {order_status['status']}")
        cycle['buying'] = False  # Снимаем флаг
        return  # ВЫХОД без активации цикла
    
    # ✅ Ордер исполнен! Получаем фактические параметры
    executed_price = float(order_status['fill_price'])      # Средняя цена исполнения
    executed_amount = float(order_status['filled_total'])   # Объём в базовой валюте
    executed_cost = float(order_status['filled_amount'])    # Фактическая стоимость в USDT
    
    print(f"[START_BUY][{base_currency}] ✅ Ордер исполнен!")
    print(f"[START_BUY][{base_currency}]   Цена: {executed_price}")
    print(f"[START_BUY][{base_currency}]   Объём: {executed_amount} {base_currency}")
    print(f"[START_BUY][{base_currency}]   Стоимость: {executed_cost} USDT")
    
except Exception as e:
    print(f"[START_BUY][{base_currency}] ❌ Ошибка проверки ордера: {e}")
    cycle['buying'] = False  # Снимаем флаг
    raise
```

---

### **ШАГ 7: ИНИЦИАЛИЗАЦИЯ ЦИКЛА (переход в ACTIVE)**

```python
# АТОМАРНО (под Lock) устанавливаем состояние цикла
cycle['state'] = 'ACTIVE'           # Цикл активен
cycle['active'] = True
cycle['buying'] = False             # Снимаем флаг "покупка в процессе"
cycle['active_step'] = 0            # Стартовый шаг (0)
cycle['start_price'] = executed_price       # Цена стартовой покупки
cycle['last_buy_price'] = executed_price    # Последняя покупка = стартовая
cycle['base_volume'] = executed_amount      # Объём базовой валюты
cycle['total_invested_usd'] = executed_cost # Инвестировано USD (фактически)
cycle['last_action_at'] = time.time()      # Время последнего действия
cycle['table'] = table                      # Таблица безубыточности
cycle['start_order_id'] = order['id']       # ID стартового ордера

# Сохраняем в памяти (self.cycles[currency])
self.cycles[base_currency] = cycle

# ✅ Логируем успешный старт
print(f"[START_CYCLE][{base_currency}] ✅ Цикл запущен!")
print(f"[START_CYCLE][{base_currency}]   Стартовая цена: {executed_price}")
print(f"[START_CYCLE][{base_currency}]   Объём: {executed_amount} {base_currency}")
print(f"[START_CYCLE][{base_currency}]   Инвестировано: {executed_cost} USDT")
print(f"[START_CYCLE][{base_currency}]   Таблица: {len(table)} шагов")
```

---

## 🔒 Защита от дублей (ключевые моменты)

### **1. Lock на валюту**
```python
# Все операции проверки и создания покупки выполняются под Lock
with self._get_lock(base_currency):
    # Вся логика шагов 1-7 здесь
    pass
```

### **2. Атомарная проверка состояния**
```python
# Перед покупкой проверяем ВСЕ условия под Lock
if (cycle['state'] != 'IDLE' or 
    cycle['active'] or 
    cycle.get('buying')):
    return  # ВЫХОД, цикл уже активен или покупка в процессе
```

### **3. Флаг "в процессе покупки"**
```python
cycle['buying'] = True  # ДО создания ордера
try:
    order = api_client.create_order(...)
    # ... проверка исполнения ...
    cycle['buying'] = False  # ПОСЛЕ успешной покупки
except:
    cycle['buying'] = False  # При ошибке тоже снимаем
    raise
```

### **4. Одно место создания**
- Стартовая покупка создаётся **ТОЛЬКО** в методе `_start_buy_cycle()`
- Нигде больше в коде не должно быть создания MARKET BUY ордеров для автотрейдинга

### **5. Проверка существующих ордеров**
```python
# Перед созданием нового ордера проверяем, нет ли уже активных
open_orders = api_client.get_open_orders(currency_pair, side='buy')
if open_orders:
    return  # ВЫХОД, есть активный BUY ордер
```

### **6. Проверка баланса базовой валюты**
```python
# НОВАЯ ЗАЩИТА: если монеты уже есть, не создаём покупку!
balance_base = api_client.get_balance(base_currency)
if float(balance_base['available']) >= table[0]['buy_amount']:
    # Активируем цикл в режиме продажи (без покупки)
    cycle['state'] = 'ACTIVE'
    cycle['active'] = True
    # ... устанавливаем параметры цикла ...
    return  # ВЫХОД
```

---

## 🎭 Сценарии использования

### **Сценарий 1: Первый запуск автотрейдера**
```
1. Пользователь включает автотрейдер
2. Главный цикл проходит по всем разрешённым валютам
3. Для каждой валюты в IDLE → создаётся стартовая покупка
4. Цикл переходит в ACTIVE и начинает мониторинг докупок/продажи
```

### **Сценарий 2: После продажи**
```
1. Автотрейдер продал всю позицию (цикл завершён)
2. Цикл сбрасывается в IDLE
3. На следующей итерации главного цикла → создаётся новая стартовая покупка
4. Новый цикл стартует
```

### **Сценарий 3: Ручной сброс цикла**
```
1. Пользователь вызывает API /api/autotrader/reset_cycle
2. Цикл принудительно сбрасывается в IDLE
3. Автотрейдер автоматически создаст стартовую покупку на следующей итерации
```

### **Сценарий 4: Монеты уже есть на балансе**
```
1. Автотрейдер проверяет баланс базовой валюты
2. Баланс >= min_base_from_table → монеты УЖЕ ЕСТЬ!
3. Активируем цикл в режиме продажи БЕЗ стартовой покупки
4. Рассчитываем start_price и ждём условий продажи
```

---

## ⚠️ Антипаттерны (что НЕ должно происходить)

| ❌ Антипаттерн | ✅ Правильно |
|----------------|--------------|
| Создание покупки без Lock | Все операции под Lock валюты |
| Проверка баланса без атомарности | Проверка баланса под Lock |
| Использование limit ордеров для стартовой покупки | Только MARKET ордера |
| Создание покупки в нескольких местах кода | Одно место: `_start_buy_cycle()` |
| Отсутствие проверки состояния цикла | Проверка `state`, `active`, `buying` |
| Игнорирование баланса базовой валюты | Проверка баланса → режим продажи |
| Отсутствие флага "покупка в процессе" | Флаг `buying = True` на время покупки |

---

## 📊 Схема алгоритма (визуально)

```
┌─────────────────────────────────────────────────┐
│  Главный цикл автотрейдера (каждые 1-2 сек)    │
└──────────────┬──────────────────────────────────┘
               │
               ▼
    ┌──────────────────────────┐
    │ Для каждой валюты:       │
    │ BTC, ETH, WLD, etc.      │
    └──────────┬───────────────┘
               │
               ▼
    ┌────────────────────────────────────┐
    │ Lock(currency).acquire() 🔒        │◄──── АТОМАРНОСТЬ!
    └──────────┬─────────────────────────┘
               │
               ▼
    ┌────────────────────────────────────┐
    │ ПРОВЕРКА 1: Валюта разрешена?      │
    │ TRADING_PERMISSIONS[currency]      │
    └──────────┬─────────────────────────┘
               │ ✅ ДА
               ▼
    ┌────────────────────────────────────┐
    │ ПРОВЕРКА 2: Автотрейдер включен?   │
    │ AUTO_TRADE_GLOBAL_ENABLED          │
    └──────────┬─────────────────────────┘
               │ ✅ ДА
               ▼
    ┌────────────────────────────────────┐
    │ ПРОВЕРКА 3: Цикл в IDLE?           │
    │ state=='IDLE' && !active && !buying│
    └──────────┬─────────────────────────┘
               │ ✅ ДА
               ▼
    ┌────────────────────────────────────┐
    │ ПРОВЕРКА 4: Нет активных BUY?      │
    │ get_open_orders(side='buy')==[]    │
    └──────────┬─────────────────────────┘
               │ ✅ ДА
               ▼
    ┌────────────────────────────────────┐
    │ ПРОВЕРКА 5: Баланс базовой валюты? │
    │ balance_base < min_base_from_table │
    └──────────┬─────────────────────────┘
               │
         ┌─────┴──────┐
         │ < MIN      │ >= MIN
         ▼            ▼
    ┌────────┐  ┌─────────────────────┐
    │        │  │ РЕЖИМ ПРОДАЖИ       │
    │        │  │ (без стартовой      │
    │        │  │  покупки!)          │
    │        │  │ - cycle['state']    │
    │        │  │   = 'ACTIVE'        │
    │        │  │ - cycle['active']   │
    │        │  │   = True            │
    │        │  │ - start_price       │
    │        │  │   = текущая/история │
    │        │  └─────────────────────┘
    │        │
    └────┬───┘
         │
         ▼
    ┌────────────────────────────────────┐
    │ ПРОВЕРКА 6: Баланс USDT?           │
    │ available_usdt >= start_volume     │
    └──────────┬─────────────────────────┘
               │ ✅ ДА
               ▼
    ┌────────────────────────────────────┐
    │ Получить параметры торговли        │
    │ params = get_breakeven_params()    │
    └──────────┬─────────────────────────┘
               │
               ▼
    ┌────────────────────────────────────┐
    │ Рассчитать таблицу безубыточности  │
    │ table = calculate_breakeven_table()│
    └──────────┬─────────────────────────┘
               │
               ▼
    ┌────────────────────────────────────┐
    │ ФЛАГ: cycle['buying'] = True 🚩    │
    └──────────┬─────────────────────────┘
               │
               ▼
    ┌────────────────────────────────────┐
    │ 🔥 MARKET BUY ОРДЕР 🔥             │◄──── ЕДИНСТВЕННОЕ МЕСТО!
    │ create_order(type='market')        │
    │ amount = start_volume (в USDT)     │
    └──────────┬─────────────────────────┘
               │
               ▼
    ┌────────────────────────────────────┐
    │ Проверка исполнения (sleep 0.5s)   │
    │ order_status = get_order()         │
    └──────────┬─────────────────────────┘
               │
         ┌─────┴──────┐
         │ closed?    │
         └─────┬──────┘
               │ ✅ ДА
               ▼
    ┌────────────────────────────────────┐
    │ Инициализация цикла:               │
    │ - state = 'ACTIVE'                 │
    │ - active = True                    │
    │ - buying = False                   │
    │ - active_step = 0                  │
    │ - start_price = executed_price     │
    │ - last_buy_price = executed_price  │
    │ - base_volume = executed_amount    │
    │ - total_invested_usd = exec_cost   │
    │ - table = <расчёт>                 │
    └──────────┬─────────────────────────┘
               │
               ▼
    ┌────────────────────────────────────┐
    │ Lock(currency).release() 🔓        │
    └──────────┬─────────────────────────┘
               │
               ▼
    ┌────────────────────────────────────┐
    │ ✅ ЦИКЛ ЗАПУЩЕН!                   │
    │ Переход к мониторингу              │
    │ докупок/продажи                    │
    └────────────────────────────────────┘
```

---

## 🔧 Реализация в коде (псевдокод)

```python
class AutoTraderV2:
    def _start_buy_cycle(self, base_currency: str):
        """Создать стартовую покупку и запустить цикл для валюты."""
        
        # ШАГ 1: АТОМАРНАЯ ПРОВЕРКА под Lock
        lock = self._get_lock(base_currency)
        with lock:
            # 1.1 Проверка: валюта разрешена?
            if not self.state_manager.get_trading_permission(base_currency):
                return  # ВЫХОД
            
            # 1.2 Проверка: автотрейдер включен?
            if not self.state_manager.get_auto_trade_enabled():
                return  # ВЫХОД
            
            # 1.3 Проверка: цикл в IDLE?
            cycle = self.cycles.get(base_currency, {})
            if (cycle.get('state') != 'IDLE' or 
                cycle.get('active') or 
                cycle.get('buying')):
                return  # ВЫХОД
            
            # 1.4 Проверка: нет активных BUY ордеров?
            api_client = self.api_client_provider()
            if not api_client:
                return  # ВЫХОД
            
            currency_pair = f"{base_currency}_USDT"
            open_orders = api_client.get_open_orders(currency_pair, side='buy')
            if open_orders:
                return  # ВЫХОД
            
            # ШАГ 2: Получение параметров
            params = self.state_manager.get_breakeven_params(base_currency)
            current_price = self._get_current_price(base_currency)
            if not current_price:
                return  # ВЫХОД
            
            # ШАГ 3: Расчёт таблицы
            table = calculate_breakeven_table(params, current_price)
            if not table:
                return  # ВЫХОД
            
            # 1.5 Проверка: баланс базовой валюты
            balance_base = api_client.get_balance(base_currency)
            available_base = float(balance_base.get('available', 0))
            min_base = float(table[0]['buy_amount'])
            
            if available_base >= min_base:
                # Монеты УЖЕ ЕСТЬ! Активируем цикл в режиме продажи
                cycle['state'] = 'ACTIVE'
                cycle['active'] = True
                cycle['base_volume'] = available_base
                cycle['start_price'] = current_price  # или из истории
                cycle['last_buy_price'] = cycle['start_price']
                cycle['total_invested_usd'] = available_base * cycle['start_price']
                cycle['active_step'] = 0
                cycle['table'] = table
                cycle['last_action_at'] = time.time()
                self.cycles[base_currency] = cycle
                print(f"[START_CYCLE][{base_currency}] ✅ Цикл активирован (режим продажи, без покупки)")
                return  # ВЫХОД
            
            # 1.6 Проверка: баланс USDT
            balance_usdt = api_client.get_balance('USDT')
            available_usdt = float(balance_usdt.get('available', 0))
            required_usdt = float(params['start_volume'])
            
            if available_usdt < required_usdt:
                print(f"[START_BUY][{base_currency}] ⚠️ Недостаточно USDT: {available_usdt} < {required_usdt}")
                return  # ВЫХОД
            
            # ШАГ 4: Установка флага "покупка в процессе"
            cycle['buying'] = True
            cycle['last_action_at'] = time.time()
            self.cycles[base_currency] = cycle
            
            # ШАГ 5: Создание MARKET ордера
            try:
                order = api_client.create_order(
                    currency_pair=currency_pair,
                    side='buy',
                    type='market',
                    amount=required_usdt,
                    account='spot'
                )
                print(f"[START_BUY][{base_currency}] ✅ MARKET ордер создан: {order['id']}")
                cycle['start_order_id'] = order['id']
            except Exception as e:
                print(f"[START_BUY][{base_currency}] ❌ Ошибка создания ордера: {e}")
                cycle['buying'] = False
                raise
            
            # ШАГ 6: Проверка исполнения
            time.sleep(0.5)
            try:
                order_status = api_client.get_order(order['id'], currency_pair)
                
                if order_status['status'] != 'closed':
                    print(f"[START_BUY][{base_currency}] ⚠️ Ордер не исполнен: {order_status['status']}")
                    cycle['buying'] = False
                    return  # ВЫХОД
                
                executed_price = float(order_status['fill_price'])
                executed_amount = float(order_status['filled_total'])
                executed_cost = float(order_status['filled_amount'])
                
                print(f"[START_BUY][{base_currency}] ✅ Ордер исполнен!")
                print(f"  Цена: {executed_price}, Объём: {executed_amount}, Стоимость: {executed_cost}")
                
            except Exception as e:
                print(f"[START_BUY][{base_currency}] ❌ Ошибка проверки ордера: {e}")
                cycle['buying'] = False
                raise
            
            # ШАГ 7: Инициализация цикла (ACTIVE)
            cycle['state'] = 'ACTIVE'
            cycle['active'] = True
            cycle['buying'] = False
            cycle['active_step'] = 0
            cycle['start_price'] = executed_price
            cycle['last_buy_price'] = executed_price
            cycle['base_volume'] = executed_amount
            cycle['total_invested_usd'] = executed_cost
            cycle['table'] = table
            cycle['last_action_at'] = time.time()
            
            self.cycles[base_currency] = cycle
            
            print(f"[START_CYCLE][{base_currency}] ✅ Цикл запущен!")
            print(f"  Стартовая цена: {executed_price}")
            print(f"  Объём: {executed_amount} {base_currency}")
            print(f"  Инвестировано: {executed_cost} USDT")
```

---

## 📝 Чеклист перед реализацией

- [ ] Убедиться, что `AutoTraderV2` имеет методы `_get_lock()` и `_ensure_cycle()`
- [ ] Реализовать метод `_get_current_price(base_currency)` для получения цены из WebSocket
- [ ] Убедиться, что `api_client` имеет методы:
  - [ ] `get_balance(currency)`
  - [ ] `get_open_orders(currency_pair, side)`
  - [ ] `create_order(...)`
  - [ ] `get_order(order_id, currency_pair)`
- [ ] Протестировать на **тестовой сети** (test mode)
- [ ] Добавить логирование **всех** шагов для диагностики
- [ ] Убедиться, что `breakeven_calculator.py` работает корректно
- [ ] Проверить, что `state_manager` возвращает корректные параметры
- [ ] Добавить обработку исключений на каждом шаге
- [ ] Добавить мониторинг через `/api/autotrader/stats`

---

## 🎉 Итог

Этот алгоритм гарантирует:

1. ✅ **Отсутствие дублей** (Lock + атомарные проверки)
2. ✅ **Отсутствие гонок** (флаг `buying`, проверка активных ордеров)
3. ✅ **Корректная работа с балансом** (проверка базовой и котируемой валют)
4. ✅ **Режим продажи без покупки** (если монеты уже есть)
5. ✅ **Единая точка создания** (метод `_start_buy_cycle()`)
6. ✅ **Полная диагностика** (логи на каждом шаге)

---

**Статус:** ✅ Готов к реализации  
**Следующий шаг:** Реализовать в `autotrader_v2.py`
