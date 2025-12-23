# Окончательный диагноз: Нулевые значения в логах

## Проблема

Логи показывают нули для всех торговых параметров:
```
[20:51:53] [XRP5L] Buy{10.0001; Курс:0.0974; ↓Δ%:0.00; ↓%:0.00; Инвест:10.0001}
[20:51:49] [XRP5L] Sell{61.9678; Курс:0.0958; ↑Δ%:0.00; PnL:0.0000; Профит:0.0000}
```

## Root Cause (Корневая причина)

### 1. Несоответствие `start_price`

В `app_state.json` обнаружено **критическое несоответствие**:

**`breakeven_params.XRP5L`:**
```json
{
    "start_price": 0.0974  ← Цена из настроек
}
```

**`autotrader_cycles.XRP5L`:**
```json
{
    "last_buy_price": 0.0734,  ← Реальная цена покупки
    "start_price": 0.09740000000000001  ← Копия из breakeven_params
}
```

### 2. Причина несоответствия

1. **При старте цикла** (`_try_start_cycle_impl`):
   - `start_price` копируется из `breakeven_params` (0.0974)
   - Устанавливается в цикл: `cycle['start_price'] = buy_price`
   
2. **Но реальная покупка прошла по другой цене** (0.0734):
   - `last_buy_price` = 0.0734
   - `start_price` остался 0.0974 (из `breakeven_params`)

3. **Результат**:
   - Расчёты падения используют неправильный `start_price`
   - Все проценты некорректны или равны нулю

### 3. Почему это происходит?

**Сценарий**:
1. Пользователь устанавливает `start_price` = 0.0974 в настройках
2. Autotrader начинает цикл, ордер размещается по 0.0974
3. Но ордер **не исполняется** по этой цене (нет ликвидности, проскальзывание, etc.)
4. Ордер исполняется по **реальной рыночной цене** 0.0734
5. `last_buy_price` = 0.0734, но `start_price` остаётся 0.0974

## Решение

### Вариант 1: Исправить после покупки (РЕКОМЕНДУЕТСЯ)

В `_try_start_cycle_impl` после успешной покупки:

```python
if order_res.get('success'):
    filled = order_res['filled']
    invest = filled * buy_price
    
    # ⚠️ КРИТИЧЕСКИ ВАЖНО: используем РЕАЛЬНУЮ цену исполнения!
    actual_buy_price = float(order_res.get('avg_deal_price') or buy_price)
    
    cycle.update({
        'active': True,
        'active_step': 0,
        'last_buy_price': actual_buy_price,  ← РЕАЛЬНАЯ ЦЕНА
        'start_price': actual_buy_price,      ← РЕАЛЬНАЯ ЦЕНА
        'total_invested_usd': invest,
        'base_volume': filled
    })
    
    # Обновляем start_price в breakeven_params
    current_params['start_price'] = actual_buy_price
    self.state_manager.set_breakeven_params(base, current_params)
```

### Вариант 2: Очистить текущие циклы

Для уже активных циклов с неправильными ценами:

```powershell
# 1. Остановить autotrader
# 2. Исправить start_price в app_state.json:
#    - В autotrader_cycles: start_price = last_buy_price
#    - В breakeven_params: start_price = last_buy_price
# 3. Перезапустить autotrader
```

## Проверка

После исправления логи должны показывать корректные значения:

```
[HH:MM:SS] [XRP5L] Buy{102.63; Курс:0.0730; ↓Δ%:0.54; ↓%:0.54; Инвест:20.00}
[HH:MM:SS] [XRP5L] Sell{102.63; Курс:0.0737; ↑Δ%:0.96; PnL:0.7184; Профит:0.7184}
```

## Статус

- [x] Код расчётов исправлен ✅
- [x] Найдена корневая причина ✅
- [ ] Внедрить исправление в `_try_start_cycle_impl`
- [ ] Исправить текущие активные циклы
- [ ] Протестировать на живой торговле

## Файлы для изменения

1. `autotrader.py` - метод `_try_start_cycle_impl` (строка ~1380-1470)
2. `app_state.json` - вручную или скриптом исправить `start_price`

## Дополнительная информация

- Диагностика: `ZERO_VALUES_DIAGNOSIS.md`
- Скрипт исправления циклов: `fix_cycles_prices.py`
- Скрипт проверки состояния: `check_cycles_debug.py`
