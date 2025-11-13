# Инструкция по очистке mTrade.py от дубликатов

**Дата**: 10 ноября 2025  
**Текущий размер**: ~1408 строк  
**Целевой размер**: ~850 строк  
**Уменьшение**: ~550 строк (39%)

## Проблема

Файл `mTrade.py` содержит дубликаты классов, которые уже вынесены в отдельные модули:
- `config.py` - класс Config
- `process_manager.py` - класс ProcessManager  
- `gate_api_client.py` - класс GateAPIClient

## Модули уже созданы и готовы ✅

1. **config.py** (~220 строк) - полностью готов
2. **process_manager.py** (~95 строк) - полностью готов
3. **gate_api_client.py** (~180 строк) - полностью готов

## Что нужно удалить из mTrade.py

### Строки для удаления:

#### 1. Удалить весь мусор после "# ИНИЦИАЛИЗАЦИЯ ГЛОБАЛЬНЫХ ПЕРЕМЕННЫХ" (строки ~73-257)
Удалить все строки с отступами и старым кодом Config до первого `class ProcessManager:`

#### 2. Первый ProcessManager (строки ~262-346)
Удалить весь класс `ProcessManager` (первый экземпляр)

#### 3. Удалить дубликат инициализации переменных (строки ~348-355)
```python
# Инициализация глобальных служебных переменных — выполняется здесь, после определения Config
server_start_time = time.time()
PAIR_INFO_CACHE = {}
PAIR_INFO_CACHE_TTL = 3600  # 1 час
CURRENT_NETWORK_MODE = Config.load_network_mode()
print(f"[NETWORK] Текущий режим сети: {CURRENT_NETWORK_MODE}")
```

#### 4. Функция `_reinit_network_mode` (строки ~357-402) - ОСТАВИТЬ!
Эту функцию НЕ удалять, она нужна для работы сервера.

#### 5. Второй ProcessManager (строки ~404-496)
Удалить весь класс `ProcessManager` (второй экземпляр - дубликат)

#### 6. Второй дубликат инициализации (строки ~498-505)
Удалить повторную инициализацию переменных

#### 7. Класс GateAPIClient (строки ~507-684)
Удалить весь класс `GateAPIClient`

#### 8. Удалить строку импорта TradingEngine (~686)
```python
from trading_engine import TradingEngine, AccountManager
```
Т.к. она уже есть в начале файла

## Что должно остаться

После очистки в начале файла должно быть:

```python
"""
Gate.io Multi-Trading Application
Поддержка обычного трейдинга и копитрейдинга
"""

import os
import sys
import json
import time
import random
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session
import requests
from threading import Thread
from typing import Dict, List, Optional

# Импорт модулей проекта
from config import Config
from process_manager import ProcessManager
from gate_api_client import GateAPIClient
from trading_engine import TradingEngine, AccountManager
from gateio_websocket import init_websocket_manager, get_websocket_manager

# Конфигурация Flask
app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['ETAG_DISABLED'] = True

@app.after_request
def add_header(response):
    # ...код...
    return response

@app.errorhandler(Exception)
def handle_error(error):
    # ...код...
    raise error

# =============================================================================
# ИНИЦИАЛИЗАЦИЯ ГЛОБАЛЬНЫХ ПЕРЕМЕННЫХ
# =============================================================================

server_start_time = time.time()
PAIR_INFO_CACHE = {}
PAIR_INFO_CACHE_TTL = 3600
CURRENT_NETWORK_MODE = Config.load_network_mode()
print(f"[NETWORK] Текущий режим сети: {CURRENT_NETWORK_MODE}")

# WebSocket lock
_ws_reinit_lock = None
try:
    from threading import Lock
    _ws_reinit_lock = Lock()
except Exception:
    pass

def _reinit_network_mode(new_mode: str) -> bool:
    """Переключение режима сети с переинициализацией WebSocket менеджера."""
    # ...код функции...
    return True

# =============================================================================
# FLASK ROUTES (WEB INTERFACE)
# =============================================================================

account_manager = AccountManager()
trading_engines = {}

@app.route('/')
def index():
    # ...и далее все роуты...
```

## Автоматическая очистка (скрипт PowerShell)

Создайте файл `clean_mtrade.ps1`:

```powershell
# Резервная копия
Copy-Item "mTrade.py" "mTrade.py.before_clean"

# Читаем весь файл
$content = Get-Content "mTrade.py" -Raw

# Удаляем дубликаты (примерные строки, нужно проверить)
# Этот скрипт требует ручной настройки номеров строк

Write-Host "Создана резервная копия: mTrade.py.before_clean"
Write-Host "Пожалуйста, выполните очистку вручную согласно инструкции"
```

## Ручная очистка (рекомендуется)

1. Открыть `mTrade.py` в VS Code
2. Найти строку с комментарием `# ИНИЦИАЛИЗАЦИЯ ГЛОБАЛЬНЫХ ПЕРЕМЕННЫХ`
3. Удалить все до первого `@app.route` кроме:
   - Импортов в начале файла
   - Flask app конфигурации
   - Декораторов `@app.after_request` и `@app.errorhandler`
   - Секции "ИНИЦИАЛИЗАЦИЯ ГЛОБАЛЬНЫХ ПЕРЕМЕННЫХ" (с чистыми переменными)
   - Функции `_reinit_network_mode`

4. Проверить, что остались только:
   - Импорты модулей
   - Flask конфигурация
   - Глобальные переменные (server_start_time, PAIR_INFO_CACHE, CURRENT_NETWORK_MODE)
   - Функция `_reinit_network_mode`
   - Все Flask роуты (@app.route)
   - Main entry point (if __name__ == '__main__')

## Проверка после очистки

```powershell
# Подсчет строк
Get-Content "mTrade.py" | Measure-Object -Line

# Должно быть примерно 850-900 строк

# Проверка синтаксиса
python -m py_compile mTrade.py

# Запуск сервера
python mTrade.py
```

## Ожидаемый результат

- **До**: 1408 строк
- **После**: ~850 строк
- **Удалено**: ~558 строк (39.6%)

### Структура после очистки:
```
1-25:    Импорты и docstring
26-50:   Flask конфигурация
51-70:   Декораторы (@app.after_request, @app.errorhandler)
71-85:   Глобальные переменные
86-125:  Функция _reinit_network_mode
126-800: Flask routes (все @app.route endpoints)
801-850: Main entry point и запуск сервера
```

## Если что-то пошло не так

Восстановить из резервной копии:
```powershell
Copy-Item "mTrade.py.backup" "mTrade.py" -Force
```

Или использовать чистую версию:
```powershell
Copy-Item "mTrade_clean.py" "mTrade.py" -Force
```
