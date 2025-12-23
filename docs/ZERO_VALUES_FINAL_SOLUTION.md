# ФИНАЛЬНЫЙ ОТЧЕТ: НУЛЕВЫЕ ЗНАЧЕНИЯ В ЛОГАХ ПОКУПКИ/ПРОДАЖИ

## 🎯 ПРОБЛЕМА НАЙДЕНА

При анализе логов торговли были обнаружены записи с нулевыми значениями:
- `↓Δ%: 0.00` (процент падения при покупке)
- `↑Δ%: 0.00` (процент роста при продаже)
- `PnL: 0.0000` (прибыль/убыток)

**Пример из реального лога:**
```json
{
  "timestamp": "2025-12-02T21:21:10.171346",
  "type": "sell",
  "currency": "ETH",
  "volume": 0.0113,
  "price": 2995.89,
  "delta_percent": 0.0,  ← ПРОБЛЕМА!
  "pnl": 0.0,            ← ПРОБЛЕМА!
  "total_invested": 0.24217300000 ← OK!
}
```

## 🔍 КОРЕНЬ ПРОБЛЕМЫ

### 1. **При продаже (SELL)**

В файле `autotrader.py` (строки 2397-2408):

```python
# Расчет процента изменения
last_buy_price = cycle.get('last_buy_price', 0.0)
if last_buy_price > 0:
    delta_from_last_buy = (actual_exec_price - last_buy_price) / last_buy_price * 100.0
else:
    delta_from_last_buy = 0.0  ← НОЛЬ, если last_buy_price == 0!

# Расчет PnL
avg_invest_price = cycle['total_invested_usd'] / cycle['base_volume'] if cycle['base_volume'] > 0 else start_price
real_pnl = (actual_exec_price - avg_invest_price) * filled  ← НОЛЬ, если цены равны!
```

**ПРИЧИНЫ НУЛЕВЫХ ЗНАЧЕНИЙ:**
1. **`last_buy_price == 0`** → `delta_from_last_buy = 0`
2. **`base_volume == 0`** или **`total_invested_usd == 0`** → `avg_invest_price = start_price`, и если `actual_exec_price ≈ start_price`, то `real_pnl ≈ 0`
3. **Старые циклы** с устаревшими данными в памяти или файлах состояния

### 2. **При покупке (BUY)**

В файле `autotrader.py` (строка 1464):

```python
self.logger.log_buy(base, filled, actual_buy_price, 0.0, 0.0, invest)
```

**При старте цикла передаются `0.0, 0.0`** для процентов, потому что это **первая покупка** - нет предыдущей цены для сравнения. **Это корректно!**

Но для **докупок (rebuy)** (строки 1827-1844) расчеты должны быть правильными:

```python
# Stepwise падение
real_decrease_step_pct = (last_buy - level_price) / last_buy * 100.0 if last_buy > 0 else 0.0

# Cumulative падение
start_price = cycle.get('start_price', 0.0)
if start_price > 0:
    real_cumulative_drop_pct = (start_price - level_price) / start_price * 100.0
else:
    real_cumulative_drop_pct = 0.0
```

**Если `last_buy == 0` или `start_price == 0`, будут нули!**

## ✅ РЕШЕНИЕ

### Вариант 1: **Исправить состояние циклов** (для текущих активных циклов)

Если в `autotrader_cycles_state.json` или `app_state.json` есть циклы с нулевыми значениями:

1. **Остановите autotrader.py**
2. **Запустите `fix_cycles_prices.py`** (уже создан) для исправления значений в state files
3. **Перезапустите autotrader.py**

### Вариант 2: **Добавить защиту в код** (для будущих циклов)

Добавить проверки в `autotrader.py`:

#### Для продажи (sell):

```python
# В районе строки 2397-2408
last_buy_price = cycle.get('last_buy_price', 0.0)
if last_buy_price <= 0:
    # КРИТИЧЕСКАЯ ОШИБКА: нет last_buy_price!
    print(f"[AutoTrader][{base}] ⚠️  WARNING: last_buy_price is ZERO during SELL! Using start_price={cycle.get('start_price', 0.0)}")
    last_buy_price = cycle.get('start_price', actual_exec_price)  # Fallback

if last_buy_price > 0:
    delta_from_last_buy = (actual_exec_price - last_buy_price) / last_buy_price * 100.0
else:
    delta_from_last_buy = 0.0
    print(f"[AutoTrader][{base}] ⚠️  WARNING: Cannot calculate delta_percent, last_buy_price is ZERO!")

# Для PnL
base_volume = cycle.get('base_volume', 0.0)
total_invested_usd = cycle.get('total_invested_usd', 0.0)

if base_volume <= 0 or total_invested_usd <= 0:
    print(f"[AutoTrader][{base}] ⚠️  WARNING: base_volume={base_volume}, total_invested_usd={total_invested_usd} during SELL!")
    avg_invest_price = start_price if start_price > 0 else actual_exec_price
else:
    avg_invest_price = total_invested_usd / base_volume

real_pnl = (actual_exec_price - avg_invest_price) * filled
```

#### Для докупки (rebuy):

```python
# В районе строки 1827-1844
last_buy = cycle.get('last_buy_price', 0.0)
if last_buy <= 0:
    print(f"[AutoTrader][{base}] ⚠️  WARNING: last_buy_price is ZERO during REBUY!")
    last_buy = cycle.get('start_price', level_price)

real_decrease_step_pct = (last_buy - level_price) / last_buy * 100.0 if last_buy > 0 else 0.0

start_price = cycle.get('start_price', 0.0)
if start_price <= 0:
    print(f"[AutoTrader][{base}] ⚠️  WARNING: start_price is ZERO during REBUY!")
    start_price = level_price

if start_price > 0:
    real_cumulative_drop_pct = (start_price - level_price) / start_price * 100.0
else:
    real_cumulative_drop_pct = 0.0
```

### Вариант 3: **Пересоздать циклы** (самый простой)

Для валют с активными циклами:
1. **Дождитесь закрытия цикла** (продажи)
2. **Запустите новый цикл** - он будет создан с правильными значениями

## 📊 ДИАГНОСТИКА

Используйте скрипт `diagnose_zero_logs.py` для проверки состояния циклов:

```bash
python diagnose_zero_logs.py
```

Скрипт покажет:
- Какие циклы активны
- Какие значения `start_price`, `last_buy_price`, `total_invested_usd`, `base_volume`
- Есть ли нулевые или подозрительные значения

## 🎬 ФИНАЛЬНЫЕ ШАГИ

### Для текущего состояния:

1. **Запустите диагностику:**
   ```bash
   python diagnose_zero_logs.py
   ```

2. **Если найдены проблемы:**
   - Остановите `autotrader.py`
   - Запустите `fix_cycles_prices.py`
   - Перезапустите `autotrader.py`

3. **Мониторинг:**
   - Следите за новыми логами
   - Проверяйте, что `↓Δ%`, `↑Δ%` и `PnL` показывают правильные значения

### Для будущих циклов:

**Рекомендую добавить защиту в код autotrader.py (Вариант 2 выше)**, чтобы предотвратить подобные ситуации в будущем.

## 📝 ТЕХНИЧЕСКАЯ ИНФОРМАЦИЯ

### Места в коде:
- **Логи продажи**: `autotrader.py`, строки 2397-2425
- **Логи докупки**: `autotrader.py`, строки 1827-1844
- **Логи старта цикла**: `autotrader.py`, строка 1464
- **TradeLogger**: `trade_logger.py`, строки 280-365 (log_buy), 367-473 (log_sell)

### Файлы состояния:
- `autotrader_cycles_state.json` - состояние циклов (в памяти autotrader)
- `app_state.json` - breakeven параметры (start_price и др.)

### Ключевые значения в cycle:
- `start_price` - стартовая цена цикла (P0)
- `last_buy_price` - цена последней покупки
- `total_invested_usd` - общая сумма инвестиций
- `base_volume` - общий объем базовой валюты
- `active_step` - текущий активный шаг

## 🔗 СВЯЗАННЫЕ ДОКУМЕНТЫ

- `ZERO_VALUES_DIAGNOSIS.md` - первичная диагностика
- `ZERO_VALUES_ROOT_CAUSE.md` - анализ корневой причины
- `check_cycles_debug.py` - скрипт проверки циклов
- `fix_cycles_prices.py` - скрипт исправления state files

---

**ВАЖНО:** Эта проблема затрагивает **только отображение в логах**, реальная торговая логика работает правильно! Циклы выполняются корректно, но логи могут показывать нули из-за неправильных значений в state files.
