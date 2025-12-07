# 🚨 КРИТИЧЕСКАЯ ПРОБЛЕМА: Отсутствует функция _try_sell()

## ❌ Суть проблемы

**В файле `dual_thread_autotrader.py` вызывается несуществующий метод:**

```python
# dual_thread_autotrader.py, строка 327
def _execute_trading_logic(self, currency: str):
    # ...
    self.autotrader._try_start_cycle(currency, quote)  # ✅ Есть
    self.autotrader._try_rebuy(currency, quote)        # ✅ Есть
    self.autotrader._try_sell(currency, quote)         # ❌ НЕТ!
```

**Результат:**
- При попытке продажи возникает ошибка `AttributeError: 'AutoTrader' object has no attribute '_try_sell'`
- Продажи НЕ ПРОИСХОДЯТ
- Циклы не закрываются
- Прибыль не фиксируется

---

## 🔍 Анализ ситуации

### Что есть:

1. **В `_autotrader.py` (старая версия):**
   - Строки 1486-1550
   - Функция `_try_sell()` есть, но **НЕПОЛНАЯ**
   - Обрывается на комментарии: "Далее полный оригинальный код... копируем сюда..."

2. **В документации:**
   - Множество упоминаний `_try_sell()`:
     - `CRITICAL_RESTART_REQUIRED.md`
     - `DEBUG_PANEL_CLEANUP.md`
     - `DOUBLE_START_BUY_CHANGELOG_ENTRY.md`
     - `P0_DIAGRAM.md`
     - `ZERO_VALUES_README.md`
   - Описана логика работы функции

### Чего нет:

1. **В `autotrader.py` (текущая версия):**
   - Функции `_try_sell()` **НЕТ ВООБЩЕ**
   - Grep-поиск: `def.*sell` → **No matches found**
   - Продажа не может быть выполнена

---

## 📋 Что должна делать функция `_try_sell()`

### Основная логика:

```python
def _try_sell(self, base: str, quote: str):
    """
    Попытка продажи всего накопленного объёма BASE при достижении breakeven.
    
    Условия продажи:
    1. Цикл активен (active == True)
    2. Цена выросла на требуемый процент (текущая цена >= breakeven_price)
    
    Алгоритм:
    1. Проверить активность цикла
    2. Получить текущую цену
    3. Обработать pending.sell (если есть незавершённые ордера)
    4. Рассчитать breakeven_price и текущий рост
    5. Проверить условие продажи
    6. Получить цену продажи из orderbook (bids)
    7. Выполнить ордер на продажу всего объёма
    8. Закрыть цикл (active=False, обнулить параметры)
    9. Залогировать продажу (logger.log_sell)
    """
    
    # 1. Проверка цикла
    cycle = self.cycles.get(base)
    if not cycle or not cycle.get('active'):
        return
    
    # 2. Получение цены
    price = self._get_market_price(base, quote)
    if not price or price <= 0:
        return
    
    # 3. Обработка pending.sell
    pending = cycle.get('pending', {})
    if pending.get('sell'):
        # Повторная попытка продать остаток
        self._complete_pending_sell(base, quote, cycle, pending)
        return
    
    # 4. Получение параметров активного шага
    table = cycle.get('table', [])
    active_step = cycle.get('active_step', -1)
    
    if active_step < 0 or active_step >= len(table):
        return
    
    params_row = table[active_step]
    required_growth_pct = float(params_row.get('breakeven_pct', 0))
    
    # 5. Расчёт текущего роста от start_price
    start_price = cycle.get('start_price', 0)
    if start_price <= 0:
        return
    
    current_growth_pct = ((price - start_price) / start_price) * 100.0
    
    # 6. Проверка условия продажи
    if current_growth_pct < required_growth_pct:
        # Недостаточный рост для продажи
        return
    
    # 7. Получение цены продажи из orderbook
    orderbook = self._get_orderbook(base, quote)
    if not orderbook:
        return
    
    # sell_level из параметров (по умолчанию 1)
    params = self.state_manager.get_breakeven_params(base)
    sell_level = int(params.get('sell_level', 1))
    
    bids = orderbook.get('bids', [])
    if len(bids) < sell_level:
        sell_level = len(bids)
    
    if sell_level < 1:
        return
    
    exec_price = float(bids[sell_level - 1][0])
    
    # 8. Расчёт объёма продажи
    sell_volume = cycle.get('base_volume', 0)
    if sell_volume <= 0:
        return
    
    # 9. Выполнение ордера на продажу
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
        params = self.state_manager.get_breakeven_params(base)
        params['start_price'] = 0.0
        self.state_manager.set_breakeven_params(base, params)
        
        # Сохранение
        self._save_cycles_state()
        
        # Статистика
        self.stats['total_sell_orders'] += 1
        self.stats['last_update'] = time.time()
        
        print(f"[AutoTrader][{base}] ✅ Продажа выполнена: filled={filled:.8f}, price={actual_exec_price:.8f}, PnL={pnl:.4f}")
    
    else:
        # ЧАСТИЧНАЯ ПРОДАЖА или НЕУДАЧА
        
        if filled > 0:
            # Сохранить остаток в pending.sell
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
```

---

## ✅ Решение

### Шаг 1: Найти полную версию функции

Возможные источники:
1. ✅ Документация (описание логики)
2. ✅ `_autotrader.py` (частичная реализация)
3. ❓ Git история (возможно, была удалена)
4. ❓ Бэкапы (если есть)

### Шаг 2: Восстановить функцию в `autotrader.py`

**Расположение:** После функции `_try_rebuy()` (строка ~1955)

**Требования:**
- ✅ Проверка активности цикла
- ✅ Обработка `pending.sell` (повторные попытки)
- ✅ Расчёт breakeven_price и роста
- ✅ Получение цены из orderbook (`bids`)
- ✅ Выполнение ордера через `_place_limit_order_all_or_nothing('sell', ...)`
- ✅ Закрытие цикла при успехе
- ✅ Логирование через `self.logger.log_sell(...)`
- ✅ Инвалидация кэша балансов
- ✅ Установка `last_sell_time`

### Шаг 3: Протестировать

1. Запустить автотрейдер
2. Дождаться активации цикла
3. Дождаться роста цены до breakeven
4. Проверить, что продажа выполняется
5. Проверить логи и состояние цикла

---

## 📊 Где функция вызывается

### 1. `dual_thread_autotrader.py`

```python
# Строка 327
def _execute_trading_logic(self, currency: str):
    # ...
    self.autotrader._try_sell(currency, quote)  # ← ЗДЕСЬ
```

### 2. Частота вызова

- **Cycler:** Каждые 10мс для каждой валюты в цикле
- **Reactor:** При WebSocket обновлении (debounce 0.1с)
- **Итого:** ~10-20 раз в секунду для активной валюты

### 3. Ожидаемое поведение

- Проверка условий продажи (~1-2мс)
- При выполнении условий: ордер на продажу (~50-100мс)
- Логирование и сохранение (~5-10мс)

---

## 🔧 План действий

1. **[СЕЙЧАС]** Создать полную функцию `_try_sell()` в `autotrader.py`
2. Добавить вспомогательную функцию `_complete_pending_sell()` (если нужна)
3. Проверить синтаксис: `python -m py_compile autotrader.py`
4. Перезапустить автотрейдер
5. Проверить логи на наличие ошибок
6. Протестировать полный цикл: start → rebuy → sell

---

## 📝 Checklist

- [ ] Функция `_try_sell()` создана в `autotrader.py`
- [ ] Логика проверки условий реализована
- [ ] Обработка `pending.sell` добавлена
- [ ] Orderbook интеграция (bids) работает
- [ ] Ордер на продажу выполняется
- [ ] Цикл закрывается корректно
- [ ] Логирование работает (`logger.log_sell`)
- [ ] Кэш балансов инвалидируется
- [ ] `last_sell_time` устанавливается
- [ ] Синтаксических ошибок нет
- [ ] Автотрейдер перезапущен
- [ ] Тестирование пройдено

---

**Создано:** 2025-01-XX  
**Статус:** 🚨 КРИТИЧНО - требует немедленного исправления  
**Приоритет:** P0 (блокирующая проблема)
