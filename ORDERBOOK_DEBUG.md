# Диагностика проблемы отображения стакана

## Дата: 6 ноября 2025

## Проблема
Стаканы не отображаются на веб-странице при загрузке.

---

## Диагностика

### 1. Проверка API
✅ **API работает корректно:**
```powershell
Invoke-WebRequest -Uri "http://localhost:5000/api/pair/data?base_currency=WLD&quote_currency=USDT"
```

**Результат:**
```
success: True
pair: WLD_USDT
orderbook_asks: 20
orderbook_bids: 20
```

### 2. Проверка валют
✅ **Валюты загружаются:**
```powershell
Invoke-WebRequest -Uri "http://localhost:5000/api/currencies"
```

**Результат:**
```
success: True
count: 10
first: WLD
```

### 3. Тестовая страница
Создана упрощенная тестовая страница для проверки:
- URL: http://localhost:5000/test
- Показывает стакан напрямую из API

---

## Возможные причины

### 1. JavaScript не выполняется
**Симптомы:**
- Консоль браузера пустая
- Нет логов `console.log`
- Стакан показывает "Загрузка..."

**Решение:**
1. Откройте браузер (F12 → Console)
2. Проверьте наличие ошибок JavaScript
3. Перезагрузите страницу (Ctrl+F5)

### 2. WebSocket не подключается
**Симптомы:**
- Статус: "❌ Ошибка подключения"
- В консоли ошибки fetch/WebSocket

**Решение:**
1. Проверьте, что сервер запущен
2. Проверьте вручную: http://localhost:5000/api/pair/subscribe
3. Посмотрите логи сервера

### 3. Задержка загрузки
**Симптомы:**
- Данные приходят, но с задержкой
- После перезагрузки страницы стакан появляется

**Решение:**
1. Увеличьте задержку в `window.onload`:
```javascript
setTimeout(loadMarketData, 5000); // было: 2000
```

### 4. Кэш браузера
**Симптомы:**
- Старая версия страницы
- Изменения не применяются

**Решение:**
1. Очистите кэш: Ctrl+Shift+Delete
2. Или жесткая перезагрузка: Ctrl+F5

---

## Добавлены отладочные логи

### В index.html:

```javascript
function updateOrderBook(orderbook) {
    console.log('updateOrderBook вызвана:', orderbook);
    console.log('Asks:', orderbook.asks?.length, 'Bids:', orderbook.bids?.length);
    // ...
}

async function loadMarketData() {
    console.log(`Загрузка рыночных данных для ${currentBaseCurrency}_${currentQuoteCurrency}`);
    // ...
    console.log('Ответ API /api/pair/data:', result);
    // ...
}
```

### Что смотреть в консоли:

1. **При загрузке страницы:**
```
Загружено валют: 10, первая: WLD
Загрузка рыночных данных для WLD_USDT
Ответ API /api/pair/data: {success: true, pair: "WLD_USDT", data: {...}}
updateOrderBook вызвана: {asks: Array(20), bids: Array(20)}
Asks: 20 Bids: 20
```

2. **Если что-то не так:**
```
Error: Failed to fetch
или
Ответ API /api/pair/data: {success: false, error: "..."}
```

---

## Проверочный список

### Шаг 1: Проверить сервер
```powershell
python status.py
```
**Ожидаемый результат:** ✅ Сервер работает

### Шаг 2: Проверить API напрямую
```powershell
Invoke-WebRequest -Uri "http://localhost:5000/api/pair/data?base_currency=WLD&quote_currency=USDT"
```
**Ожидаемый результат:** success: True, 20 asks, 20 bids

### Шаг 3: Открыть тестовую страницу
```
http://localhost:5000/test
```
**Ожидаемый результат:** Стакан отображается

### Шаг 4: Проверить основную страницу
```
http://localhost:5000
```
**Откройте консоль (F12) и проверьте логи**

### Шаг 5: Проверить WebSocket статус
На странице должно быть: "✅ WebSocket подключен"

---

## Быстрые решения

### Решение 1: Жесткая перезагрузка
```
1. Ctrl+F5 в браузере
2. Очистка кэша
3. Перезагрузка страницы
```

### Решение 2: Перезапуск сервера
```powershell
python restart.py
```

### Решение 3: Увеличение задержки
В `index.html`, строка ~2167:
```javascript
// Было
setTimeout(loadMarketData, 2000);

// Стало
setTimeout(loadMarketData, 5000);
```

### Решение 4: Принудительная загрузка
Добавить в `window.onload`:
```javascript
// После subscribeToPairData
loadMarketData(); // Сразу
setTimeout(loadMarketData, 1000); // Через 1 сек
setTimeout(loadMarketData, 3000); // Через 3 сек
```

---

## Текущее состояние

### Добавлено:
1. ✅ Отладочные логи в `updateOrderBook`
2. ✅ Отладочные логи в `loadMarketData`
3. ✅ Тестовая страница `/test`
4. ✅ Документация по диагностике

### Для проверки:
1. Откройте http://localhost:5000
2. Откройте консоль браузера (F12)
3. Проверьте логи
4. Если стакан не появляется:
   - Посмотрите логи в консоли
   - Откройте тестовую страницу /test
   - Сообщите, какие ошибки видите

---

## Следующие шаги

### Если стакан все еще не показывается:

1. **Проверьте консоль браузера** - скриншот ошибок
2. **Откройте /test** - работает ли упрощенная версия?
3. **Проверьте Network** (F12 → Network):
   - Идут ли запросы к `/api/pair/data`?
   - Какой ответ приходит?
4. **Проверьте Elements** (F12 → Elements):
   - Есть ли элементы `#orderbookAsks` и `#orderbookBids`?
   - Какой HTML внутри них?

---

## Файлы изменены

1. **templates/index.html** - добавлены отладочные логи
2. **templates/test_orderbook.html** - создана тестовая страница
3. **mTrade.py** - добавлен роут `/test`
4. **ORDERBOOK_DEBUG.md** - этот файл

---

**Обновлено:** 6 ноября 2025, 23:45  
**Статус:** Диагностика в процессе  
**Тестовая страница:** http://localhost:5000/test
