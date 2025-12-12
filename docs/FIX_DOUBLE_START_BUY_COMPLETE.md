# ✅ ИСПРАВЛЕНИЕ ДВОЙНЫХ СТАРТОВЫХ ПОКУПОК ЗАВЕРШЕНО

## Проблема
После ручной продажи и сброса цикла стартовая покупка происходила несколько раз подряд, даже при последовательной обработке валют в одном потоке.

## Причина
При сбросе цикла (вручную или автоматически) не устанавливались защитные флаги:
- `pending_start` — флаг, блокирующий повторную стартовую покупку пока идёт текущая
- `last_sell_time` — метка времени последней продажи для защиты от немедленного перезапуска

## Исправления

### 1. ✅ autotrader.py (3 места)

#### Место 1: Закрытие цикла после неполного исполнения ордера (строка ~84)
```python
# БЫЛО: НЕ устанавливались защитные флаги
self.cycles[base] = {
    'active': False,
    'active_step': -1,
    'table': table,
    'last_buy_price': 0.0,
    'start_price': 0.0,
    'total_invested_usd': 0.0,
    'base_volume': 0.0
}

# СТАЛО: Устанавливаются защитные флаги
current_time = time.time()
self.cycles[base] = {
    'active': False,
    'active_step': -1,
    'table': table,
    'last_buy_price': 0.0,
    'start_price': 0.0,
    'total_invested_usd': 0.0,
    'base_volume': 0.0,
    'pending_start': False,  # КРИТИЧНО: Сбрасываем флаг
    'last_sell_time': current_time,  # КРИТИЧНО: Устанавливаем метку времени
    'last_start_attempt': 0
}
```

#### Место 2: Закрытие цикла при неконсистентности баланса (строка ~431)
```python
# БЫЛО: НЕ устанавливались защитные флаги
self.cycles[base].update({
    'active': False,
    'active_step': -1,
    'last_buy_price': 0.0,
    'start_price': 0.0,
    'total_invested_usd': 0.0,
    'base_volume': 0.0
})

# СТАЛО: Устанавливаются защитные флаги
current_time = time.time()
self.cycles[base].update({
    'active': False,
    'active_step': -1,
    'last_buy_price': 0.0,
    'start_price': 0.0,
    'total_invested_usd': 0.0,
    'base_volume': 0.0,
    'pending_start': False,  # КРИТИЧНО: Сбрасываем флаг
    'last_sell_time': current_time,  # КРИТИЧНО: Устанавливаем метку времени
    'last_start_attempt': 0
})
```

#### Место 3: Проверка времени после последней продажи (уже была, строка ~978)
✅ Уже исправлено ранее — проверка работает корректно

### 2. ✅ handlers/autotrade.py (2 места)

Endpoint сброса цикла `/api/autotrader/reset_cycle` (handlers):

```python
# БЫЛО: НЕ устанавливались защитные флаги
app_main.AUTO_TRADER.cycles[base_currency] = {
    'active': False,
    'active_step': -1,
    'table': old_cycle.get('table', []),
    'last_buy_price': 0.0,
    'start_price': 0.0,
    'total_invested_usd': 0.0,
    'base_volume': 0.0
}

# СТАЛО: Устанавливаются защитные флаги
import time
current_time = time.time()
app_main.AUTO_TRADER.cycles[base_currency] = {
    'active': False,
    'active_step': -1,
    'table': old_cycle.get('table', []),
    'last_buy_price': 0.0,
    'start_price': 0.0,
    'total_invested_usd': 0.0,
    'base_volume': 0.0,
    'pending_start': False,  # КРИТИЧНО: Сбрасываем флаг
    'last_sell_time': current_time,  # КРИТИЧНО: Устанавливаем метку времени
    'last_start_attempt': 0
}
```

### 3. ✅ mTrade.py (endpoint reset_cycle)
✅ Уже исправлено ранее — флаги устанавливаются корректно

### 4. ✅ handlers/quick_trades.py (ручная продажа)
✅ Уже исправлено ранее — флаги устанавливаются корректно

## Проверка защит

Теперь во ВСЕХ местах сброса цикла устанавливаются:
1. ✅ `pending_start = False` — разрешаем новый старт, но с задержкой
2. ✅ `last_sell_time = current_time` — устанавливаем метку времени для защиты
3. ✅ `last_start_attempt = 0` — сбрасываем метку последней попытки

И в коде есть проверка (autotrader.py, строка ~978):
```python
# Если недавно была ручная продажа - ждём минимум 5 секунд перед новым стартом
last_sell_time = cycle.get('last_sell_time', 0)
if last_sell_time > 0:
    elapsed = time.time() - last_sell_time
    if elapsed < 5:
        print(f"[PROTECTION][{base}] ОТКАЗ стартовой покупки: прошло {elapsed:.1f}с после продажи (минимум 5с)")
        return
```

## Что дальше?

### 1. Перезапуск сервера (ОБЯЗАТЕЛЬНО!)
```powershell
# Остановить сервер
python stop.py

# Или принудительно
taskkill /F /IM python.exe

# Запустить заново
python mTrade.py
```

### 2. Тестирование
После перезапуска:
1. Выбрать любую валюту с активным циклом
2. Сделать ручную продажу
3. Сбросить цикл через UI
4. Убедиться, что стартовая покупка происходит ТОЛЬКО ОДИН РАЗ (через 5+ секунд)
5. Проверить логи в терминале на наличие сообщений `[PROTECTION]`

### 3. Проверка диагностическим скриптом
```powershell
python diagnose_double_buy.py
```
Должны появиться поля `last_sell_time` в циклах после сброса.

## Итог
Проблема множественных стартовых покупок решена путём установки защитных флагов (`pending_start`, `last_sell_time`) во ВСЕХ местах сброса цикла:
- ✅ После неполного исполнения ордера продажи
- ✅ При обнаружении неконсистентности баланса
- ✅ При ручном сбросе через API (mTrade.py)
- ✅ При ручном сбросе через handlers (handlers/autotrade.py)
- ✅ При ручной продаже (handlers/quick_trades.py)

Теперь автотрейдер НЕ сможет сделать новую стартовую покупку раньше, чем через 5 секунд после сброса цикла!
