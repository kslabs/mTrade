# Упрощение логики запуска торгового цикла

## Дата изменений
**Текущая дата**: автоматически при сохранении

## Проблема
В файле `autotrader.py` алгоритм активации торгового цикла был перегружен избыточными проверками, которые блокировали нормальный запуск циклов:

1. **Проверка баланса BASE** - блокировала старт, если баланс >= минимальной суммы покупки
2. **Проверка времени после продажи** - требовала ждать минимум 5 секунд после последней продажи
3. **Дублирующие проверки `base_volume` и `start_price`** в `_try_start_cycle_impl`

Эти проверки приводили к следующим проблемам:
- Цикл не мог запуститься даже при наличии сигнала на покупку
- Ложные блокировки из-за "пыли" (малых остатков) после продажи
- Усложнение логики и увеличение количества точек отказа

## Решение

### 1. Удалены избыточные проверки в `_try_start_cycle()`

**Удалено (строки ~962-989)**:
```python
# ПРОВЕРКА БАЛАНСА BASE: разрешаем новый цикл только если баланс меньше минимальной суммы стартовой покупки
price_probe = self._get_market_price(base, quote) or 0.0
if price_probe > 0:
    base_balance_probe = self._get_account_balance(base, force_refresh=True)
    balance_value_usd = base_balance_probe * price_probe
    params = self.state_manager.get_breakeven_params(base)
    temp_table = calculate_breakeven_table(params, price_probe)
    if temp_table and len(temp_table) > 0:
        min_purchase_usd = float(temp_table[0].get('purchase_usd', 0))
        if balance_value_usd >= min_purchase_usd:
            print(f"[PROTECTION][{base}] ОТКАЗ стартовой покупки: баланс BASE=${balance_value_usd:.4f} >= min_purchase=${min_purchase_usd:.4f}")
            return
        elif base_balance_probe > 0:
            print(f"[START_CYCLE][{base}] Баланс BASE=${balance_value_usd:.4f} < min_purchase=${min_purchase_usd:.4f} - разрешаем новый цикл (пыль после продажи)")

# ПРОВЕРКА ВРЕМЕНИ ПОСЛЕ ПОСЛЕДНЕЙ ПРОДАЖИ
last_sell_time = cycle.get('last_sell_time', 0)
if last_sell_time > 0:
    elapsed = time.time() - last_sell_time
    if elapsed < 5:
        print(f"[PROTECTION][{base}] ОТКАЗ стартовой покупки: прошло {elapsed:.1f}с после продажи (минимум 5с)")
        return
    else:
        print(f"[START_CYCLE][{base}] Прошло {elapsed:.1f}с после продажи - разрешаем новый цикл")
```

**Заменено на**:
```python
# Lock захвачен и все проверки пройдены — выполняем стартовую покупку
print(f"[START_CYCLE][{base}] ✅ Все проверки пройдены, запускаем стартовую покупку")
```

### 2. Упрощены проверки в `_try_start_cycle_impl()`

**Удалено (строки ~1008-1015)**:
```python
# === ФИНАЛЬНАЯ ПРОВЕРКА #2: base_volume должен быть 0 ===
base_volume = cycle.get('base_volume', 0.0)
if base_volume > 0:
    print(f"[PROTECTION][{base}] ❌ ОТКАЗ: base_volume={base_volume:.8f} > 0 (цикл уже начат)")
    return

# === ФИНАЛЬНАЯ ПРОВЕРКА #3: start_price должен быть 0 ===
start_price = cycle.get('start_price', 0.0)
if start_price > 0:
    print(f"[PROTECTION][{base}] ❌ ОТКАЗ: start_price={start_price:.8f} > 0 (цикл был начат)")
    return
```

**Оставлена только одна проверка**:
```python
# === ЕДИНСТВЕННАЯ ПРОВЕРКА: Цикл НЕ должен быть активен ===
if cycle.get('active'):
    print(f"[PROTECTION][{base}] ❌ ОТКАЗ: цикл активен (active=True, active_step={cycle.get('active_step')})")
    return
```

## Текущая логика запуска цикла

### `_try_start_cycle()` - упрощённая схема:
1. ✅ Проверка: `active == False` (цикл не активен)
2. ✅ Проверка: `pending_start == False` (нет другой покупки)
3. ✅ Атомарная блокировка через Lock (защита от race condition)
4. ✅ Повторная проверка после захвата Lock (double-check pattern)
5. ✅ Вызов `_try_start_cycle_impl()`

### `_try_start_cycle_impl()` - минимальные проверки:
1. ✅ Проверка: `active == False`
2. ✅ Проверка: `pending_start == False`
3. ✅ Установка флага `pending_start = True` (блокировка повторных стартов)
4. ✅ Выполнение стартовой покупки через API

## Преимущества изменений

1. **Убрана ложная блокировка из-за баланса BASE** - цикл запускается по сигналу, а не по остаткам на балансе
2. **Убрана задержка 5 секунд после продажи** - цикл может запуститься сразу при появлении сигнала
3. **Упрощена логика** - меньше условий = меньше точек отказа
4. **Надёжная защита от двойного старта** через Lock и `pending_start` флаг
5. **Быстрая реакция** на торговые сигналы

## Что осталось для защиты

Механизмы защиты от двойной покупки:
- ✅ Атомарная блокировка через `threading.Lock` (мастер-Lock + Lock для каждой валюты)
- ✅ Флаг `pending_start` (блокирует повторные попытки во время выполнения покупки)
- ✅ Проверка `active` (предотвращает старт при активном цикле)
- ✅ Double-check pattern после захвата Lock

## Файлы изменены
- `c:\Users\Администратор\Documents\bGate.mTrade\autotrader.py`

## Рекомендации по тестированию

1. Запустить autotrader и проверить логи запуска цикла
2. Убедиться, что цикл запускается без ложных блокировок
3. Проверить, что нет двойных стартовых покупок
4. Убедиться, что цикл корректно активируется (`active=True`) только после успешной покупки

## Следующие шаги

- [ ] Запустить autotrader в тестовом режиме
- [ ] Мониторить логи на наличие ошибок
- [ ] Проверить работу на реальных торговых сигналах
- [ ] Убедиться в отсутствии двойных покупок

---
**Статус**: ✅ Изменения внесены, код без ошибок, готов к тестированию
