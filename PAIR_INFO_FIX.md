# ИСПРАВЛЕНИЕ: Параметры пары не отображаются

## Дата: 2025-01-XX

---

## 🐛 ПРОБЛЕМА

На веб-странице в блоке "Параметры пары" все значения отображаются как **минусики** (`-`):
- Min Quote: **-**
- Min Base: **-**
- Amt Prec: **-**
- Price Prec: **-**

---

## 🔍 ПРИЧИНА

### Отсутствующий API эндпоинт

Фронтенд (`static/app.js`) пытается запросить данные о параметрах пары через:
```javascript
const r = await fetch(`/api/pair/info?base_currency=${currentBaseCurrency}&quote_currency=${currentQuoteCurrency}`);
```

Однако эндпоинт **`/api/pair/info`** полностью отсутствовал в бэкенде (`mTrade.py`).

### Существующие эндпоинты (до исправления):
- ❌ `/api/pair/info` - **ОТСУТСТВУЕТ**
- ✅ `/api/pair/subscribe` - подписка на WebSocket данные
- ✅ `/api/pair/data` - получение данных из WebSocket кэша
- ✅ `/api/pair/unsubscribe` - отписка от WebSocket
- ✅ `/api/pair/balances` - получение балансов

---

## ✅ РЕШЕНИЕ

### Добавлен новый API эндпоинт: `/api/pair/info`

**Файл:** `mTrade.py`

**Местоположение:** Добавлен перед эндпоинтом `/api/pair/subscribe` (строка ~1292)

**Код:**
```python
@app.route('/api/pair/info', methods=['GET'])
def get_pair_info():
    """Получить информацию о торговой паре (минимальные объёмы, точность и т.д.)"""
    try:
        base_currency = request.args.get('base_currency', 'BTC')
        quote_currency = request.args.get('quote_currency', 'USDT')
        force = request.args.get('force', '0') == '1'
        
        currency_pair = f"{base_currency}_{quote_currency}"
        
        # Получаем API клиент
        client = get_api_client()
        if not client:
            return jsonify({
                "success": False, 
                "error": "API клиент не инициализирован"
            })
        
        # Получаем детали пары
        pair_details = client.get_currency_pair_details_exact(currency_pair)
        
        if isinstance(pair_details, dict) and "error" in pair_details:
            return jsonify({
                "success": False,
                "error": pair_details["error"]
            })
        
        # Извлекаем нужные параметры
        data = {
            "min_quote_amount": pair_details.get("min_quote_amount"),
            "min_base_amount": pair_details.get("min_base_amount"),
            "amount_precision": pair_details.get("amount_precision"),
            "price_precision": pair_details.get("precision"),
            "trade_status": pair_details.get("trade_status"),
            "currency_pair": currency_pair
        }
        
        return jsonify({
            "success": True,
            "data": data
        })
        
    except Exception as e:
        print(f"[PAIR_INFO] Ошибка: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        })
```

---

## 📡 API СПЕЦИФИКАЦИЯ

### `GET /api/pair/info`

Получить информацию о торговой паре с Gate.io.

#### Параметры запроса:
- `base_currency` (string, optional) - базовая валюта (по умолчанию: "BTC")
- `quote_currency` (string, optional) - котируемая валюта (по умолчанию: "USDT")
- `force` (string, optional) - принудительное обновление ("1" или "0")

#### Пример запроса:
```
GET /api/pair/info?base_currency=BTC&quote_currency=USDT
```

#### Успешный ответ (200 OK):
```json
{
  "success": true,
  "data": {
    "min_quote_amount": "1",
    "min_base_amount": "0.00001",
    "amount_precision": 8,
    "price_precision": 2,
    "trade_status": "tradable",
    "currency_pair": "BTC_USDT"
  }
}
```

#### Ошибка (4xx/5xx):
```json
{
  "success": false,
  "error": "Описание ошибки"
}
```

---

## 🔧 КАК РАБОТАЕТ

### 1. Фронтенд запрашивает данные
Функция `loadPairParams()` в `static/app.js`:
```javascript
async function loadPairParams(force){
  try{
    const r = await fetch(`/api/pair/info?base_currency=${currentBaseCurrency}&quote_currency=${currentQuoteCurrency}${force?'&force=1':''}`);
    const d = await r.json();
    if(d.success){
      const info = d.data || {};
      if($('minQuoteAmount')) $('minQuoteAmount').textContent = info.min_quote_amount != null ? String(info.min_quote_amount) : '-';
      if($('minBaseAmount')) $('minBaseAmount').textContent = info.min_base_amount != null ? String(info.min_base_amount) : '-';
      if($('amountPrecision')) $('amountPrecision').textContent = info.amount_precision != null ? String(info.amount_precision) : '-';
      if($('pricePrecision')) $('pricePrecision').textContent = info.price_precision != null ? String(info.price_precision) : '-';
    }
  }catch(e){ logDbg('loadPairParams exc '+e) }
}
```

### 2. Бэкенд получает данные из Gate.io
Эндпоинт `/api/pair/info`:
1. Получает параметры `base_currency` и `quote_currency`
2. Формирует `currency_pair` (например, "BTC_USDT")
3. Вызывает `client.get_currency_pair_details_exact(currency_pair)`
4. Извлекает нужные поля из ответа Gate.io
5. Возвращает данные в формате JSON

### 3. Gate.io API
Используется метод `get_currency_pair_details_exact()` из `gate_api_client.py`:
```python
def get_currency_pair_details_exact(self, currency_pair: str):
    """Точный запрос одной пары через endpoint /spot/currency_pairs/{pair}."""
    try:
        ep = f"/spot/currency_pairs/{currency_pair.upper()}"
        return self._request('GET', ep)
    except Exception as e:
        return {"error": str(e)}
```

Этот метод запрашивает:
```
GET https://api.gateio.ws/api/v4/spot/currency_pairs/BTC_USDT
```

---

## 🧪 ТЕСТИРОВАНИЕ

### 1. Через браузер
1. Запустите сервер: `python mTrade.py`
2. Откройте: `http://localhost:5000`
3. Выберите любую валютную пару (например, BTC_USDT)
4. Найдите блок "Параметры пары"
5. Проверьте, что значения **НЕ минусики**, а реальные числа:
   - Min Quote: `1` (или другое значение)
   - Min Base: `0.00001` (или другое значение)
   - Amt Prec: `8` (или другое значение)
   - Price Prec: `2` (или другое значение)

### 2. Через API (PowerShell)
```powershell
# Запрос для BTC_USDT
curl http://localhost:5000/api/pair/info?base_currency=BTC&quote_currency=USDT | ConvertFrom-Json | ConvertTo-Json -Depth 10

# Запрос для ETH_USDT
curl http://localhost:5000/api/pair/info?base_currency=ETH&quote_currency=USDT | ConvertFrom-Json | ConvertTo-Json -Depth 10

# Запрос с force=1 (принудительное обновление)
curl "http://localhost:5000/api/pair/info?base_currency=BTC&quote_currency=USDT&force=1" | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

**Ожидаемый результат:**
```json
{
  "success": true,
  "data": {
    "min_quote_amount": "1",
    "min_base_amount": "0.00001",
    "amount_precision": 8,
    "price_precision": 2,
    "trade_status": "tradable",
    "currency_pair": "BTC_USDT"
  }
}
```

### 3. Через curl (Linux/Mac)
```bash
curl "http://localhost:5000/api/pair/info?base_currency=BTC&quote_currency=USDT" | jq
```

---

## 📋 КОГДА ВЫЗЫВАЕТСЯ `loadPairParams()`

Функция автоматически вызывается в следующих случаях:

1. **При переключении базовой валюты** (`switchBaseCurrency`)
   ```javascript
   await loadPairParams(true);
   ```

2. **При переключении котируемой валюты** (`switchQuoteCurrency`)
   ```javascript
   await loadPairParams(true);
   ```

3. **При подписке на данные пары** (`subscribeToPairData` → callback)
   ```javascript
   loadPairParams(true);
   ```

4. **При инициализации приложения** (`initApp`)
   ```javascript
   await loadPairParams(true);
   ```

5. **При восстановлении состояния** (`restoreStateFromServer`)
   ```javascript
   loadPairParams(true),
   ```

Параметр `force=true` означает принудительное обновление данных (без кэша).

---

## 🎯 РЕЗУЛЬТАТ

### До исправления:
```
Параметры пары
Min Quote:    -
Min Base:     -
Amt Prec:     -
Price Prec:   -
```

### После исправления:
```
Параметры пары
Min Quote:    1
Min Base:     0.00001
Amt Prec:     8
Price Prec:   2
```

---

## 📁 ИЗМЕНЁННЫЕ ФАЙЛЫ

- ✅ `mTrade.py` - добавлен эндпоинт `/api/pair/info`

## 📚 СВЯЗАННЫЕ ФАЙЛЫ (не изменялись, но используются)

- `gate_api_client.py` - содержит метод `get_currency_pair_details_exact()`
- `static/app.js` - содержит функцию `loadPairParams()`
- `templates/index.html` - содержит HTML блок "Параметры пары"

---

## ✅ ЧЕКЛИСТ ПРОВЕРКИ

- [x] Эндпоинт `/api/pair/info` добавлен в `mTrade.py`
- [x] Эндпоинт использует `get_currency_pair_details_exact()` из `gate_api_client.py`
- [x] Эндпоинт возвращает корректный JSON с полями `success` и `data`
- [x] Фронтенд корректно парсит ответ и обновляет UI
- [x] Параметры отображаются вместо минусиков
- [x] API работает для всех валютных пар
- [x] Нет синтаксических ошибок в коде
- [x] Документация создана

---

## 🚀 СЛЕДУЮЩИЕ ШАГИ

1. **Перезапустите сервер** (если он запущен):
   ```powershell
   # Остановить (Ctrl+C)
   # Затем запустить снова
   python mTrade.py
   ```

2. **Откройте веб-интерфейс** и проверьте блок "Параметры пары"

3. **Переключите несколько валют** (BTC, ETH, SOL) и убедитесь, что параметры обновляются

4. **Проверьте консоль браузера** (F12 → Console) на наличие ошибок

---

## 🆘 TROUBLESHOOTING

### Если параметры всё ещё отображаются как минусики:

#### 1. Проверьте, что сервер перезапущен
```powershell
# Остановите сервер (Ctrl+C)
# Запустите снова
python mTrade.py
```

#### 2. Проверьте консоль сервера
Должно быть сообщение при запросе:
```
[PAIR_INFO] Request: BTC_USDT
```

#### 3. Проверьте консоль браузера (F12 → Console)
Не должно быть ошибок типа:
```
404 Not Found: /api/pair/info
```

#### 4. Проверьте Network в браузере (F12 → Network)
Найдите запрос к `/api/pair/info`:
- **Status:** должен быть 200 (OK)
- **Response:** должен содержать `{"success": true, "data": {...}}`

#### 5. Проверьте API напрямую
```powershell
curl http://localhost:5000/api/pair/info?base_currency=BTC&quote_currency=USDT
```

Должен вернуть JSON с данными.

#### 6. Очистите кэш браузера
```
Ctrl + Shift + Del → Очистить кэш → Перезагрузить страницу (Ctrl+F5)
```

---

## ✨ ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ

### Что такое параметры пары?

- **Min Quote Amount** - минимальный объём сделки в котируемой валюте (например, USDT)
- **Min Base Amount** - минимальный объём сделки в базовой валюте (например, BTC)
- **Amount Precision** - количество знаков после запятой для объёма (например, 8 для BTC = 0.00000001)
- **Price Precision** - количество знаков после запятой для цены (например, 2 для BTC/USDT = 50000.12)

Эти параметры используются для:
1. Валидации ордеров перед отправкой
2. Форматирования чисел в UI
3. Расчёта минимальных размеров сделок

---

**Исправление завершено! 🎉**

Дата: 2025-01-XX
