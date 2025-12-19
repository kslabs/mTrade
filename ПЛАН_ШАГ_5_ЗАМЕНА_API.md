# 🚀 Рефакторинг app.js — Шаг 5: План действий

## 📊 Текущее состояние

- **app.js**: 2597 строк (было 2676)
- **Прогресс**: −79 строк (13% от цели)
- **Цель**: 2000 строк
- **Осталось**: ~597 строк

---

## 🎯 Шаг 5: Замена оставшихся fetch-вызовов

**Цель**: −50 строк  
**Оценка времени**: 15-20 минут

### Функции для замены (14 штук)

#### 1. `subscribeToPairData(base, quote)`
```javascript
// Было:
const resp = await fetch('/api/pair/subscribe', {...});

// Будет:
const resp = await api.subscribeToPair(base, quote);
```

#### 2. `saveTradeParams()`
```javascript
// Было:
const r = await fetch('/api/trade/params', {...});

// Будет:
const r = await api.saveTradeParams(params);
```

#### 3. `loadUIState()`
```javascript
// Было:
const response = await fetch('/api/ui/state');

// Будет:
const response = await api.loadUIState();
```

#### 4. `UIStateManager.loadPartial()`
```javascript
// Было:
const response = await fetch('/api/ui/state/partial', {...});

// Будет:
const response = await api.loadPartialUIState(keys);
```

#### 5. `saveCurrenciesList()`
```javascript
// Было:
fetch('/api/currencies', {...}).then(...)

// Будет:
const d = await api.saveCurrencies(items);
```

#### 6. `syncCurrenciesFromGateIO()`
```javascript
// Было:
const response = await fetch('/api/currencies/sync', {...});

// Будет:
const result = await api.syncCurrenciesFromGateIO(currentQuoteCurrency);
```

#### 7. `updateSyncInfo()`
```javascript
// Было:
const response = await fetch('/api/currencies/sync-info');

// Будет:
const response = await api.getSyncInfo();
```

#### 8. `handleServerRestart()`
```javascript
// Было:
const resp = await fetch('/api/server/restart', {...});

// Будет:
const resp = await api.restartServer();
```

#### 9. `handleServerShutdown()`
```javascript
// Было:
const resp = await fetch('/api/server/shutdown', {...});

// Будет:
const resp = await api.shutdownServer();
```

#### 10. `fetchServerStatusOnce()`
```javascript
// Было:
const resp = await fetch('/api/server/status');

// Будет:
const resp = await api.getServerStatus();
```

#### 11. `handleBuyMinOrder()`
```javascript
// Было:
const resp = await fetch('/api/trade/buy-min', {...});

// Будет:
const resp = await api.buyMinOrder(currentBaseCurrency, currentQuoteCurrency);
```

#### 12. `handleSellAll()`
```javascript
// Было:
const resp = await fetch('/api/trade/sell-all', {...});

// Будет:
const resp = await api.sellAll(currentBaseCurrency, currentQuoteCurrency);
```

#### 13. `handleResetCycle()`
```javascript
// Было:
const response = await fetch('/api/autotrader/reset_cycle', {...});

// Будет:
const response = await api.resetCycle(currentBaseCurrency, currentQuoteCurrency);
```

#### 14. `handleResumeCycle()`
```javascript
// Было:
const response = await fetch('/api/autotrader/resume_cycle', {...});

// Будет:
const response = await api.resumeCycle(currentBaseCurrency, currentQuoteCurrency);
```

---

## 📋 Порядок действий

### 1. Подготовка
```powershell
# Проверить текущее состояние
Get-Content "static\app.js" | Measure-Object -Line
```

### 2. Поиск и замена
Для каждой функции:
1. Найти функцию с помощью `grep_search`
2. Прочитать контекст с помощью `read_file`
3. Заменить fetch на api-client с помощью `replace_string_in_file`
4. Проверить на ошибки с помощью `get_errors`

### 3. Проверка
```powershell
# Подсчёт строк
Get-Content "static\app.js" | Measure-Object -Line

# Запуск приложения
python app.py
```

### 4. Тестирование
- Открыть браузер: http://127.0.0.1:5000
- Проверить консоль (F12) на ошибки
- Проверить функциональность

---

## ⚠️ Важно

1. **Заменять по одной функции**
   - Не заменять все сразу
   - После каждой замены проверять на ошибки

2. **Сохранять логику**
   - Не менять обработку ошибок
   - Не менять параметры

3. **Проверять зависимости**
   - Некоторые функции могут использовать глобальные переменные
   - Убедиться, что API-клиент получает нужные параметры

---

## 🎯 Ожидаемый результат

- **app.js**: ~2547 строк (−50 строк)
- **Прогресс**: −129 строк (19% от цели)
- **Все fetch-вызовы заменены на api-client**

---

## 🔜 После Шага 5

### Шаг 6: Вынос обработчиков событий
**Кандидаты**:
- `openCurrencyManager()`, `closeCurrencyManager()`
- `showEmojiPicker()`, `closeEmojiPicker()`
- Обработчики кликов на кнопках

### Шаг 7: Вынос WebSocket логики
**Кандидаты**:
- Логика подключения/переподключения
- Обработчики сообщений

### Шаг 8: Вынос UI-рендеринга
**Кандидаты**:
- `renderCurrencyTabs()`, `renderBreakEvenTable()`
- `updateOrderBook()`, `updateTradeIndicators()`

---

**Статус**: Готово к Шагу 5 ✅  
**Инструменты готовы**: api-client.js (21 функция)  
**Время выполнения**: ~15-20 минут
