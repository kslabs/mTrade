# Тестирование исправлений - Trade/Copy и таблица безубыточности

## Дата: 10 ноября 2025

## Запуск сервера:
```powershell
cd "c:\Users\Администратор\Documents\bGate.mTrade"
python mTrade.py
```

## 1. Тест переключателя Trade/Copy

### Получить текущий режим:
```powershell
# PowerShell
Invoke-RestMethod -Uri "http://localhost:5000/api/mode" -Method GET

# Expected result:
# {
#   "mode": "trade",  # или "copy"
#   "internal_mode": "normal",  # или "copy"
#   "success": true
# }
```

### Переключить на Copy:
```powershell
# PowerShell
$body = @{mode="copy"} | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:5000/api/mode" -Method POST -Body $body -ContentType "application/json"

# Expected result:
# {
#   "mode": "copy",
#   "internal_mode": "copy",
#   "success": true
# }
```

### Переключить на Trade:
```powershell
# PowerShell
$body = @{mode="trade"} | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:5000/api/mode" -Method POST -Body $body -ContentType "application/json"

# Expected result:
# {
#   "mode": "trade",
#   "internal_mode": "normal",
#   "success": true
# }
```

## 2. Тест таблицы безубыточности

### Legacy режим (без указания валюты):
```powershell
# PowerShell
Invoke-RestMethod -Uri "http://localhost:5000/api/breakeven/table" -Method GET

# Expected result:
# {
#   "success": true,
#   "table": [...],  # массив строк таблицы
#   "params": {...},  # TRADE_PARAMS (legacy)
#   "currency": "LEGACY",
#   "legacy": true,
#   "current_price": 0 или текущая цена BTC
# }
```

### Per-currency режим (для BTC):
```powershell
# PowerShell
Invoke-RestMethod -Uri "http://localhost:5000/api/breakeven/table?base_currency=BTC" -Method GET

# Expected result:
# {
#   "success": true,
#   "table": [...],
#   "params": {...},  # параметры для BTC
#   "currency": "BTC",
#   "legacy": false,
#   "current_price": текущая цена BTC (если доступна)
# }
```

### Per-currency режим (для ETH):
```powershell
# PowerShell
Invoke-RestMethod -Uri "http://localhost:5000/api/breakeven/table?base_currency=ETH" -Method GET

# Expected result:
# {
#   "success": true,
#   "table": [...],
#   "params": {...},  # параметры для ETH
#   "currency": "ETH",
#   "legacy": false,
#   "current_price": текущая цена ETH (если доступна)
# }
```

## 3. Тест параметров торговли

### Legacy параметры GET:
```powershell
# PowerShell
Invoke-RestMethod -Uri "http://localhost:5000/api/trade/params/legacy" -Method GET

# Expected result:
# {
#   "success": true,
#   "params": {
#     "steps": 16,
#     "start_volume": 3.0,
#     "start_price": 0.0,
#     "pprof": 0.6,
#     "kprof": 0.02,
#     "target_r": 3.65,
#     "geom_multiplier": 2.0,
#     "rebuy_mode": "geometric"
#   },
#   "legacy": true
# }
```

### Legacy параметры POST (изменить steps):
```powershell
# PowerShell
$body = @{steps=20; start_volume=5.0} | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:5000/api/trade/params/legacy" -Method POST -Body $body -ContentType "application/json"

# Expected result:
# {
#   "success": true,
#   "params": {...},  # обновленные параметры
#   "legacy": true
# }
```

### Per-currency параметры GET (для BTC):
```powershell
# PowerShell
Invoke-RestMethod -Uri "http://localhost:5000/api/trade/params?base_currency=BTC" -Method GET

# Expected result:
# {
#   "success": true,
#   "params": {...},  # параметры BTC
#   "currency": "BTC"
# }
```

### Per-currency параметры POST (для BTC):
```powershell
# PowerShell
$body = @{base_currency="BTC"; steps=18; start_volume=4.0} | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:5000/api/trade/params" -Method POST -Body $body -ContentType "application/json"

# Expected result:
# {
#   "success": true,
#   "message": "Параметры для BTC сохранены",
#   "params": {...},  # обновленные параметры BTC
#   "currency": "BTC"
# }
```

## 4. Проверка в браузере

### Откройте в браузере:
```
http://localhost:5000
```

### В консоли браузера (F12):
```javascript
// Получить текущий режим
fetch('/api/mode').then(r => r.json()).then(console.log)

// Переключить на copy
fetch('/api/mode', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({mode: 'copy'})
}).then(r => r.json()).then(console.log)

// Переключить на trade
fetch('/api/mode', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({mode: 'trade'})
}).then(r => r.json()).then(console.log)

// Получить таблицу безубыточности (legacy)
fetch('/api/breakeven/table').then(r => r.json()).then(console.log)

// Получить таблицу безубыточности (BTC)
fetch('/api/breakeven/table?base_currency=BTC').then(r => r.json()).then(console.log)
```

## Что исправлено:

### 1. Инициализация глобальных переменных
**Проблема:** Переменные `TRADING_MODE`, `TRADING_PERMISSIONS`, `AUTO_TRADE_GLOBAL_ENABLED`, `TRADE_PARAMS` инициализировались **ПОСЛЕ** определения эндпойнтов Flask, что вызывало ошибки `NameError`.

**Решение:** Переместил инициализацию этих переменных **ДО** определения эндпойнтов (строка ~178):
```python
# Глобальные переменные для торговли (загружаются из state_manager)
TRADING_MODE = state_manager.get_trading_mode()
TRADING_PERMISSIONS = state_manager.get_trading_permissions()
AUTO_TRADE_GLOBAL_ENABLED = state_manager.get_auto_trade_enabled()
TRADE_PARAMS = state_manager.get("legacy_trade_params", DEFAULT_TRADE_PARAMS.copy())
```

### 2. Порядок инициализации
```
1. Импорты
2. Flask app setup
3. Глобальные константы (PAIR_INFO_CACHE, etc)
4. State Manager
5. AUTO_TRADER = None
6. ТОРГОВЫЕ ПЕРЕМЕННЫЕ (НОВОЕ - ЗДЕСЬ!)
7. Flask routes/endpoints
8. Инициализация валют/permissions
9. MAIN ENTRY POINT
```

## Ожидаемое поведение:

✅ **Trade/Copy переключатель:**
- GET `/api/mode` возвращает текущий режим
- POST `/api/mode` переключает режим
- Режим применяется ко всем активным движкам
- Режим сохраняется в state_manager

✅ **Таблица безубыточности:**
- Legacy режим (без `base_currency`) использует `TRADE_PARAMS`
- Per-currency режим (с `base_currency`) использует параметры конкретной валюты
- Текущая цена загружается из WebSocket
- Fallback на дефолтное значение если цена недоступна

✅ **Параметры торговли:**
- Legacy эндпоинты: `/api/trade/params/legacy`
- Per-currency эндпоинты: `/api/trade/params`
- Параметры сохраняются отдельно для каждой валюты
- Legacy параметры не влияют на per-currency

## Если всё равно не работает:

### 1. Проверьте логи при запуске:
```powershell
python mTrade.py 2>&1 | Select-String "ERROR|TRADING|MODE"
```

### 2. Проверьте app_state.json:
```powershell
Get-Content app_state.json | ConvertFrom-Json
```

### 3. Перезапустите с чистым состоянием:
```powershell
# Сделайте backup
Copy-Item app_state.json app_state.json.backup

# Удалите (будет создан новый с дефолтами)
Remove-Item app_state.json

# Запустите сервер
python mTrade.py
```

### 4. Проверьте ответы API:
```powershell
# Если ошибка 500, проверьте логи в консоли сервера
# Если ошибка 400, проверьте формат запроса
# Если success: false, проверьте поле "error" в ответе
```
