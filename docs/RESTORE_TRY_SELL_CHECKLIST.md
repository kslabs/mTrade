# ✅ ЧЕК-ЛИСТ: Восстановление функции _try_sell()

## 🎯 Цель
Восстановить отсутствующую функцию `_try_sell()` в файле `autotrader.py`, чтобы автотрейдер мог выполнять продажи и закрывать торговые циклы с фиксацией прибыли.

---

## 📋 Что нужно сделать

### Этап 1: Подготовка ✅ ВЫПОЛНЕНО

- [x] Проанализирована структура сервера
- [x] Найден цикл обработки валют
- [x] Описаны этапы buy/sell
- [x] Выявлена проблема отсутствия `_try_sell()`
- [x] Создана документация:
  - [x] AUTOTRADER_COMPLETE_ARCHITECTURE.md
  - [x] MISSING_TRY_SELL_PROBLEM.md
  - [x] CURRENCY_CYCLE_QUICK_SCHEME.md
  - [x] FINAL_ANALYSIS_SUMMARY.md
  - [x] DOCS_INDEX_AUTOTRADER_FIX.md (обновлён)

### Этап 2: Восстановление функции ✅ ВЫПОЛНЕНО

- [x] **Создать функцию `_try_sell()` в `autotrader.py`**
  - Расположение: После `_try_rebuy()` (строка ~1955)
  - Основа: Описание из MISSING_TRY_SELL_PROBLEM.md
  - Требования:
    - [x] Проверка активности цикла
    - [x] Получение текущей цены
    - [x] Обработка `pending.sell` (повторные попытки)
    - [x] Получение параметров breakeven из таблицы
    - [x] Расчёт роста цены от start_price
    - [x] Проверка условия продажи
    - [x] Получение цены из orderbook (bids)
    - [x] Выполнение ордера через `_place_limit_order_all_or_nothing('sell', ...)`
    - [x] Расчёт PnL (прибыль/убыток)
    - [x] Закрытие цикла (active=False, обнуление параметров)
    - [x] Установка `last_sell_time`
    - [x] Обнуление `start_price` в state_manager
    - [x] Инвалидация кэша балансов
    - [x] Логирование через `logger.log_sell()`
    - [x] Обновление статистики

### Этап 3: Проверка синтаксиса ✅ ВЫПОЛНЕНО

- [x] **Проверить синтаксис Python:**
  ```powershell
  python -m py_compile autotrader.py
  ```
  Результат: ✅ Нет ошибок

- [x] **Проверить импорты:**
  - [x] `time`
  - [x] `json`
  - [x] `os`
  - [x] `threading`
  - [x] `datetime`
  - [x] `math`
  - [x] `traceback`
  - Все импорты присутствуют в начале файла

### Этап 3.5: Интеграция в основной цикл ✅ ВЫПОЛНЕНО

- [x] **Добавить вызов `_try_sell()` в основной цикл:**
  - Расположение: В блоке обработки активного цикла (строка ~2304)
  - Вызов добавлен перед `_try_rebuy()`
  - Синтаксис проверен: ✅ Нет ошибок
  - Документ создан: [SELL_FUNCTION_INTEGRATED.md](SELL_FUNCTION_INTEGRATED.md)

### Этап 4: Тестирование ⏳ ТРЕБУЕТСЯ

- [ ] **Перезапустить автотрейдер:**
  ```powershell
  # Остановить текущий процесс (Ctrl+C)
  # Запустить заново
  python mTrade.py
  ```

- [ ] **Проверить логи на наличие ошибок:**
  - [ ] Нет `AttributeError: 'AutoTrader' object has no attribute '_try_sell'`
  - [ ] Нет других ошибок при вызове `_try_sell()`

- [ ] **Проверить работу через API:**
  ```powershell
  # Получить статистику
  curl http://localhost:5000/api/autotrade/stats
  
  # Проверить, что total_sell_orders увеличивается
  ```

- [ ] **Проверить полный цикл:**
  - [ ] Запустить автотрейдер
  - [ ] Дождаться активации цикла (start)
  - [ ] Дождаться докупки (rebuy) - если цена упадёт
  - [ ] Дождаться роста цены до breakeven
  - [ ] Проверить, что продажа выполнилась
  - [ ] Проверить, что цикл закрылся (active=False)
  - [ ] Проверить логи: должна быть запись `log_sell`

### Этап 5: Валидация ⏳ ТРЕБУЕТСЯ

- [ ] **Проверить состояние циклов:**
  ```powershell
  curl http://localhost:5000/api/autotrade/cycles
  ```
  - [ ] После продажи: `active = false`
  - [ ] После продажи: `base_volume = 0.0`
  - [ ] После продажи: `start_price = 0.0`
  - [ ] После продажи: `last_sell_time` установлен

- [ ] **Проверить логи сделок:**
  - [ ] В логах есть записи sell
  - [ ] PnL рассчитан корректно
  - [ ] Цена продажи корректна

- [ ] **Проверить баланс:**
  - [ ] После продажи баланс USDT увеличился
  - [ ] После продажи баланс BASE уменьшился (продано)

### Этап 6: Документация ⏳ ТРЕБУЕТСЯ

- [ ] **Обновить документацию после успешного тестирования:**
  - [ ] Отметить в MISSING_TRY_SELL_PROBLEM.md, что проблема решена
  - [ ] Добавить в FINAL_ANALYSIS_SUMMARY.md результаты тестирования
  - [ ] Создать файл SELL_FUNCTION_RESTORED.md с описанием решения

---

## 📝 Шаблон функции `_try_sell()`

### Минимальная реализация (для начала):

```python
def _try_sell(self, base: str, quote: str):
    """
    Попытка продажи при достижении breakeven.
    
    Условия:
    - Цикл активен (active == True)
    - Цена выросла на требуемый процент (>= breakeven_pct)
    
    Действия:
    - Получить цену из orderbook (bids)
    - Продать весь объём base_volume
    - Закрыть цикл (active=False)
    - Залогировать продажу
    """
    
    # 1. Проверка цикла
    cycle = self.cycles.get(base)
    if not cycle or not cycle.get('active'):
        return
    
    # 2. Получение цены
    price = self._get_market_price(base, quote)
    if not price or price <= 0:
        return
    
    # 3. Обработка pending.sell (если есть)
    pending = cycle.get('pending', {})
    if pending.get('sell'):
        # TODO: Реализовать обработку незавершённых ордеров
        return
    
    # 4. Получение параметров
    table = cycle.get('table', [])
    active_step = cycle.get('active_step', -1)
    
    if active_step < 0 or active_step >= len(table):
        return
    
    params_row = table[active_step]
    required_growth_pct = float(params_row.get('breakeven_pct', 0))
    
    # 5. Расчёт роста
    start_price = cycle.get('start_price', 0)
    if start_price <= 0:
        return
    
    current_growth_pct = ((price - start_price) / start_price) * 100.0
    
    # 6. Проверка условия
    if current_growth_pct < required_growth_pct:
        return  # Недостаточный рост
    
    # 7. Получение цены продажи из orderbook
    orderbook = self._get_orderbook(base, quote)
    if not orderbook:
        return
    
    params = self.state_manager.get_breakeven_params(base)
    sell_level = int(params.get('sell_level', 1))
    
    bids = orderbook.get('bids', [])
    if len(bids) < sell_level:
        sell_level = len(bids)
    
    if sell_level < 1:
        return
    
    exec_price = float(bids[sell_level - 1][0])
    
    # 8. Расчёт объёма
    sell_volume = cycle.get('base_volume', 0)
    if sell_volume <= 0:
        return
    
    # 9. Выполнение ордера
    order_res = self._place_limit_order_all_or_nothing('sell', base, quote, sell_volume, exec_price)
    
    filled = float(order_res.get('filled', 0))
    
    if order_res.get('success') and filled >= sell_volume * 0.999:
        # ПОЛНАЯ ПРОДАЖА
        
        # Инвалидация кэша
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
        
        # Обнуление в state_manager
        params = self.state_manager.get_breakeven_params(base)
        params['start_price'] = 0.0
        self.state_manager.set_breakeven_params(base, params)
        
        # Сохранение
        self._save_cycles_state()
        
        # Статистика
        self.stats['total_sell_orders'] += 1
        self.stats['last_update'] = time.time()
        
        print(f"[AutoTrader][{base}] ✅ Продажа: filled={filled:.8f}, price={actual_exec_price:.8f}, PnL={pnl:.4f}")
    
    else:
        # ЧАСТИЧНАЯ ПРОДАЖА
        if filled > 0:
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
```

---

## 🚀 Быстрый старт

### 1. Создать функцию:
```powershell
# Открыть файл
code autotrader.py

# Найти строку после _try_rebuy() (примерно строка 1955)
# Вставить код функции _try_sell() (см. шаблон выше)
```

### 2. Проверить синтаксис:
```powershell
python -m py_compile autotrader.py
```

### 3. Перезапустить:
```powershell
# Ctrl+C (остановить)
python mTrade.py
```

### 4. Проверить логи:
```powershell
# Ищем ошибки
grep -i "error" mTrade.log
grep -i "_try_sell" mTrade.log
```

---

## 📊 Ожидаемый результат

После успешного восстановления функции:

✅ Автотрейдер запускается без ошибок  
✅ При вызове `_try_sell()` нет `AttributeError`  
✅ При достижении breakeven происходит продажа  
✅ Цикл закрывается корректно  
✅ Прибыль фиксируется в логах  
✅ Баланс обновляется  

---

## 📚 Документация

- [MISSING_TRY_SELL_PROBLEM.md](MISSING_TRY_SELL_PROBLEM.md) - Описание проблемы
- [AUTOTRADER_COMPLETE_ARCHITECTURE.md](AUTOTRADER_COMPLETE_ARCHITECTURE.md) - Полная архитектура
- [FINAL_ANALYSIS_SUMMARY.md](FINAL_ANALYSIS_SUMMARY.md) - Итоговое резюме
- [DOCS_INDEX_AUTOTRADER_FIX.md](DOCS_INDEX_AUTOTRADER_FIX.md) - Индекс документации

---

**Создано:** 2025-01-XX  
**Статус:** ⏳ В ожидании реализации  
**Приоритет:** 🚨 КРИТИЧНО
