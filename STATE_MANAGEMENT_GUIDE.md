# Управление состоянием приложения - Краткое руководство

**Дата:** 10 ноября 2025  
**Статус:** ✅ Реализовано

## Что сделано

### 1. ✅ Создан State Manager (`state_manager.py`)
Модуль для централизованного управления состоянием приложения с автоматическим сохранением в файл `app_state.json`.

### 2. ✅ Сохранение состояния всех кнопок и переключателей
- **Режим торговли (Trade/Copy)** - сохраняется и восстанавливается
- **Автоторговля (вкл/выкл)** - сохраняется
- **Разрешения торговли для каждой валюты** - сохраняются
- **Режим сети (work/test)** - сохраняется
- **Параметры безубыточности** - сохраняются отдельно для каждой валюты

### 3. ✅ Параметры торговли для каждой валюты
Каждая валюта имеет свои параметры таблицы безубыточности:
- steps (шаги)
- start_volume (стартовый объём)
- start_price (начальная цена)
- pprof (профит, %)
- kprof (коэффициент профита)
- target_r (цель безубыточности, %)
- geom_multiplier (множитель геометрии)
- rebuy_mode (режим докупок)

## API Endpoints

### Режим торговли (Trade/Copy)

**GET `/api/mode`** - Получить текущий режим
```json
{
  "success": true,
  "mode": "trade",
  "modes": {
    "trade": "Обычная торговля",
    "copy": "Копитрейдинг"
  }
}
```

**POST `/api/mode`** - Переключить режим
```json
{
  "mode": "copy"
}
```

### Автоторговля

**GET `/api/autotrade/status`** - Получить статус
```json
{
  "success": true,
  "enabled": true
}
```

**POST `/api/autotrade/start`** - Включить
**POST `/api/autotrade/stop`** - Выключить

### Разрешения торговли

**GET `/api/trade/permissions`** - Получить все разрешения
```json
{
  "success": true,
  "permissions": {
    "BTC": true,
    "ETH": false,
    "WLD": true
  }
}
```

**POST `/api/trade/permission`** - Установить разрешение для валюты
```json
{
  "base_currency": "BTC",
  "enabled": false
}
```

### Параметры торговли (для каждой валюты)

**GET `/api/trade/params?base_currency=BTC`** - Получить параметры для валюты
```json
{
  "success": true,
  "params": {
    "steps": 16,
    "start_volume": 3.0,
    "start_price": 0.0,
    "pprof": 0.6,
    "kprof": 0.02,
    "target_r": 3.65,
    "geom_multiplier": 2.0,
    "rebuy_mode": "geometric"
  },
  "currency": "BTC"
}
```

**POST `/api/trade/params`** - Сохранить параметры для валюты
```json
{
  "base_currency": "BTC",
  "steps": 20,
  "start_volume": 5.0,
  "pprof": 0.8
}
```

### Таблица безубыточности

**GET `/api/breakeven/table?base_currency=BTC`** - Получить таблицу для валюты
```json
{
  "success": true,
  "table": [...],
  "params": {...},
  "currency": "BTC"
}
```

### Состояние UI

**GET `/api/ui/state`** - Получить полное состояние UI
```json
{
  "success": true,
  "state": {
    "auto_trade_enabled": true,
    "enabled_currencies": {"BTC": true, "ETH": false},
    "network_mode": "test",
    "trading_mode": "trade"
  }
}
```

**POST `/api/ui/state`** - Сохранить состояние UI
```json
{
  "state": {
    "auto_trade_enabled": false,
    "enabled_currencies": {"BTC": false},
    "trading_mode": "copy"
  }
}
```

## Как это работает

### 1. Загрузка состояния при запуске
При запуске сервера:
```python
state_manager = get_state_manager()  # Автоматически загружает app_state.json
TRADING_MODE = state_manager.get_trading_mode()
AUTO_TRADE_GLOBAL_ENABLED = state_manager.get_auto_trade_enabled()
TRADING_PERMISSIONS = state_manager.get_trading_permissions()
```

### 2. Сохранение при изменении
Каждое изменение автоматически сохраняется в файл:
```python
state_manager.set_trading_mode("copy")  # Сохраняется в app_state.json
state_manager.set_auto_trade_enabled(False)  # Сохраняется
state_manager.set_trading_permission("BTC", False)  # Сохраняется
```

### 3. Восстановление при перезагрузке
- При обновлении страницы - фронтенд запрашивает `/api/ui/state` и восстанавливает UI
- При перезапуске сервера - состояние загружается из `app_state.json`

## Файл состояния

**Расположение:** `app_state.json` (в корне проекта)

**Пример содержимого:**
```json
{
  "trading_mode": "trade",
  "auto_trade_enabled": true,
  "trading_permissions": {
    "BTC": true,
    "ETH": false,
    "WLD": true,
    "SOL": true
  },
  "network_mode": "test",
  "breakeven_params": {
    "BTC": {
      "steps": 16,
      "start_volume": 3.0,
      "start_price": 0.0,
      "pprof": 0.6,
      "kprof": 0.02,
      "target_r": 3.65,
      "geom_multiplier": 2.0,
      "rebuy_mode": "geometric"
    },
    "ETH": {
      "steps": 20,
      "start_volume": 5.0,
      "start_price": 0.0,
      "pprof": 0.8,
      "kprof": 0.03,
      "target_r": 4.0,
      "geom_multiplier": 2.5,
      "rebuy_mode": "martingale"
    }
  }
}
```

## Тестирование

### 1. Проверить текущий режим торговли
```powershell
Invoke-RestMethod -Uri "http://localhost:5000/api/mode" -Method Get
```

### 2. Переключить на копитрейдинг
```powershell
Invoke-RestMethod -Uri "http://localhost:5000/api/mode" -Method Post -ContentType "application/json" -Body '{"mode":"copy"}'
```

### 3. Получить параметры для BTC
```powershell
Invoke-RestMethod -Uri "http://localhost:5000/api/trade/params?base_currency=BTC" -Method Get
```

### 4. Изменить параметры для ETH
```powershell
$body = @{
    base_currency = "ETH"
    steps = 20
    start_volume = 5.0
    pprof = 0.8
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:5000/api/mode" -Method Post -ContentType "application/json" -Body $body
```

### 5. Получить полное состояние
```powershell
Invoke-RestMethod -Uri "http://localhost:5000/api/ui/state" -Method Get
```

## Преимущества

✅ **Все состояние на сервере** - никаких localStorage/cookies в браузере  
✅ **Переживает перезагрузку** - и страницы, и сервера  
✅ **Отдельные параметры для каждой валюты** - гибкая настройка  
✅ **Централизованное управление** - один файл, один API  
✅ **Потокобезопасность** - используется Lock для синхронизации  
✅ **Автоматическое сохранение** - не нужно вручную вызывать save()

## Что дальше

1. **Перезапустите сервер** - чтобы State Manager инициализировался
2. **Откройте веб-интерфейс** - состояние восстановится автоматически
3. **Переключите режим Trade/Copy** - изменение сохранится
4. **Измените параметры для валюты** - каждая валюта имеет свои параметры
5. **Перезагрузите страницу** - все вернется как было
6. **Перезапустите сервер** - состояние восстановится из файла

**Файлы:**
- `state_manager.py` - новый модуль управления состоянием
- `mTrade.py` - обновлены все endpoints для работы с State Manager
- `app_state.json` - файл хранения состояния (создается автоматически)
