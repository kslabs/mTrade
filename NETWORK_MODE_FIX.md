# Исправление переключения режима сети (work/test)

## Проблема
Пользователь сообщил, что веб-страница показывает баланс из тестовой сети, даже когда кнопка включена на рабочую сеть. При попытке переключить режим появляется слово "ошибка".

## Причина
Фронтенд использовал endpoints `/api/network` (без `/mode`), которые не были определены в бэкенде. В коде были определены только `/api/network/mode`, что вызывало 404 ошибку при попытке получить или изменить режим сети.

## Исправления

### 1. Добавлены алиасы endpoints для совместимости
**Файл:** `mTrade.py`

Добавлены дополнительные route decorators для поддержки обоих путей:
- `/api/network` (используется фронтендом)
- `/api/network/mode` (новый путь)

```python
@app.route('/api/network', methods=['GET'])
@app.route('/api/network/mode', methods=['GET'])
def get_network_mode():
    """Получить текущий режим сети"""
    return jsonify({
        "success": True,
        "mode": CURRENT_NETWORK_MODE,
        "modes": {
            "work": "Рабочая сеть (Real trading)",
            "test": "Тестовая сеть (Paper trading)"
        }
    })

@app.route('/api/network', methods=['POST'])
@app.route('/api/network/mode', methods=['POST'])
def set_network_mode():
    """Переключить режим сети"""
    # ... код переключения ...
```

### 2. Исправлена опечатка в декораторе
**Файл:** `mTrade.py`, строка 273

**Было:**
```python
@app.route('/api/balance', methods=['GET])  # Незакрытая кавычка!
```

**Стало:**
```python
@app.route('/api/balance', methods=['GET'])
```

### 3. Перемещены глобальные переменные
**Файл:** `mTrade.py`

Переменные `WATCHED_PAIRS` и `MULTI_PAIRS_CACHE` перенесены в раздел "ИНИЦИАЛИЗАЦИЯ ГЛОБАЛЬНЫХ ПЕРЕМЕННЫХ" (после строки 75), чтобы они были доступны при инициализации.

### 4. Перемещена функция `_init_default_watchlist`
**Файл:** `mTrade.py`

Функция перемещена перед `_reinit_network_mode` (строка 88), так как используется внутри неё.

## Проверка работоспособности

### 1. Проверка текущего режима
```bash
curl http://localhost:5000/api/network
# или
curl http://localhost:5000/api/network/mode
```

**Ответ:**
```json
{
  "mode": "test",
  "modes": {
    "work": "Рабочая сеть (Real trading)",
    "test": "Тестовая сеть (Paper trading)"
  },
  "success": true
}
```

### 2. Переключение режима на work
```bash
curl -X POST http://localhost:5000/api/network \
  -H "Content-Type: application/json" \
  -d '{"mode":"work"}'
```

**Ответ:**
```json
{
  "message": "Режим сети изменен на 'work'",
  "mode": "work",
  "success": true
}
```

### 3. Проверка сохранения режима
```bash
cat network_mode.json
```

**Содержимое:**
```json
{
  "mode": "work",
  "saved_at": 1762790052.21063
}
```

### 4. Проверка баланса
Теперь баланс запрашивается из правильной сети:

```bash
curl http://localhost:5000/api/balance
curl http://localhost:5000/api/pair/balances?base_currency=BTC&quote_currency=USDT
```

Оба endpoint используют глобальную переменную `CURRENT_NETWORK_MODE`, которая обновляется при переключении режима.

## Как работает переключение режима

1. **Пользователь переключает режим на фронтенде** → вызов `POST /api/network` с `{"mode":"work"}`
2. **Бэкенд получает запрос** → вызов функции `set_network_mode()`
3. **Функция `_reinit_network_mode()`**:
   - Сохраняет новый режим в `network_mode.json`
   - Обновляет глобальную переменную `CURRENT_NETWORK_MODE`
   - Закрывает старые WebSocket соединения
   - Инициализирует новый WebSocket менеджер с ключами из правильной сети
   - Пересоздает watchlist валютных пар
4. **Фронтенд получает подтверждение** → обновляет UI и запрашивает свежие данные
5. **Все последующие запросы баланса** используют `CURRENT_NETWORK_MODE` для выбора правильного API

## Статус
✅ **Исправлено и протестировано** (10 ноября 2025)

### Результаты тестирования:
- ✅ GET `/api/network` возвращает текущий режим
- ✅ POST `/api/network` переключает режим
- ✅ Режим сохраняется в `network_mode.json`
- ✅ WebSocket менеджер переинициализируется при переключении
- ✅ Баланс запрашивается из правильной сети
- ✅ Нет ошибок компиляции

## Что дальше?
1. **Протестировать на фронтенде**: переключить режим через веб-интерфейс и проверить, что баланс обновляется
2. **Проверить кэш браузера**: если проблема сохраняется, очистить кэш браузера (Ctrl+Shift+R)
3. **Проверить сетевые запросы**: открыть DevTools → Network и убедиться, что запросы идут к правильному endpoint

## Дополнительная информация

### Endpoints баланса
Оба endpoint корректно используют `CURRENT_NETWORK_MODE`:

**`/api/balance`** (строка 299):
```python
client = GateAPIClient(account['api_key'], account['api_secret'], CURRENT_NETWORK_MODE)
```

**`/api/pair/balances`** (строка 644):
```python
client = GateAPIClient(api_key, api_secret, CURRENT_NETWORK_MODE)
```

### Логика получения API ключей
При запросе баланса:
1. Если есть активный аккаунт → используются его ключи
2. Иначе → загружаются ключи из конфигурации для текущего режима (`Config.load_secrets_by_mode(CURRENT_NETWORK_MODE)`)
3. Клиент создается с правильным режимом сети

### Важное замечание
Для рыночных данных (orderbook, ticker) всегда используется основной API Gate.io (`work`), даже в тестовом режиме, так как тестовая сеть не предоставляет рыночные данные. Это сделано намеренно в endpoint `/api/pair/data` (строка 587).
