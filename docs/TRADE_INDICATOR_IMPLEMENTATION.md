# TRADE_INDICATOR_IMPLEMENTATION.md

## Описание задачи
Добавить простой надежный индикатор состояния торговли с таймером в веб-интерфейс bGate.mTrade.

## Что уже сделано
1. В `templates/index.html` добавлена новая строка "Торговля" в блоке статистики торгового цикла (элемент с id `tradeIndicator`)
2. В `static/app.js` есть код для определения состояния торговли на основе пересечения ценовых порогов

## Что нужно доделать

### 1. Добавить функцию для выполнения торговых операций

Добавить после строки 493 (`}`) в файле `static/app.js`:

```javascript
// Функция для автоматического выполнения торговых операций
async function executeTrade(side, currency){
  if(!currency || !currentQuoteCurrency){
    if(typeof window.uiDebugLog === 'function'){
      window.uiDebugLog(`❌ Не выбрана валютная пара для ${side}`, 'error');
    }
    return;
  }
  
  // Определяем endpoint и сообщения в зависимости от типа операции
  const endpoint = side === 'buy' ? '/api/trade/buy-min' : '/api/trade/sell-all';
  const actionName = side === 'buy' ? 'покупка' : 'продажа';
  const actionEmoji = side === 'buy' ? '🔴' : '🟢';
  
  try {
    // Логируем начало операции
    if(typeof window.uiDebugLog === 'function'){
      window.uiDebugLog(`${actionEmoji} ${currency}: Отправка команды на ${actionName}...`, 'trade');
    }
    
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        base_currency: currency,
        quote_currency: currentQuoteCurrency
      })
    });
    
    const data = await response.json();
    
    if(data.success){
      // Логируем успешное выполнение
      const details = data.details || {};
      const price = data.execution_price || data.price || 'N/A';
      const amount = data.amount || 'N/A';
      const total = data.total || 'N/A';
      
      if(typeof window.uiDebugLog === 'function'){
        window.uiDebugLog(
          `✅ ${currency}: ${actionName.toUpperCase()} выполнена! ` +
          `Цена: ${price}, Количество: ${amount}, Сумма: ${total} ${currentQuoteCurrency}`,
          'success'
        );
      }
      
      // Обновляем данные после сделки
      await loadPairBalances();
      await loadMarketData(true);
    } else {
      // Логируем ошибку
      if(typeof window.uiDebugLog === 'function'){
        window.uiDebugLog(
          `❌ ${currency}: Ошибка ${actionName} - ${data.error || 'Неизвестная ошибка'}`,
          'error'
        );
      }
    }
  } catch(error) {
    // Логируем исключение
    if(typeof window.uiDebugLog === 'function'){
      window.uiDebugLog(
        `❌ ${currency}: Критическая ошибка ${actionName} - ${error.message || String(error)}`,
        'error'
      );
    }
  }
}
```

### 2. Модифицировать updateAutoTradeLevels

Найти строку, где обновляется индикатор торговли (примерно строка 580-660). Заменить весь блок обновления индикатора на следующий код:

```javascript
  // Обновляем индикатор торговли (новая строка в статистике)
  const tradeIndicatorEl = $('tradeIndicator');
  if(tradeIndicatorEl){
    const currentPrice = parseFloat(levels.current_price);
    const sellPrice = levels.sell_price !== null && levels.sell_price !== undefined ? parseFloat(levels.sell_price) : null;
    const buyPrice = levels.next_buy_price !== null && levels.next_buy_price !== undefined ? parseFloat(levels.next_buy_price) : null;
    
    let newState = 'waiting';
    if(!isNaN(currentPrice) && sellPrice !== null && !isNaN(sellPrice) && currentPrice >= sellPrice){
      newState = 'sell';
    } else if(!isNaN(currentPrice) && buyPrice !== null && !isNaN(buyPrice) && currentPrice <= buyPrice){
      newState = 'buy';
    } else if(levels.active_cycle){
      newState = 'waiting';
    }
    
    // Инициализация глобального состояния таймера
    if(!window.__tradeStateTimer){
      window.__tradeStateTimer = {
        state: 'waiting',
        startTime: Date.now(),
        intervalId: null,
        tradeExecuted: false
      };
    }
    
    // Проверяем изменение состояния
    if(window.__tradeStateTimer.state !== newState){
      const oldState = window.__tradeStateTimer.state;
      window.__tradeStateTimer.state = newState;
      window.__tradeStateTimer.startTime = Date.now();
      window.__tradeStateTimer.tradeExecuted = false; // Сбрасываем флаг при смене состояния
      
      // Логируем изменение состояния в отладочную панель
      const stateNames = {
        'sell': '🟢 ПРОДАЖА',
        'buy': '🔴 ПОКУПКА',
        'waiting': '⏸️ ОЖИДАНИЕ'
      };
      
      const currency = currentBaseCurrency || 'N/A';
      const priceText = !isNaN(currentPrice) ? currentPrice.toFixed(8) : 'N/A';
      
      if(newState === 'sell'){
        if(typeof window.uiDebugLog === 'function'){
          window.uiDebugLog(`${currency}: Состояние → ${stateNames[newState]} (цена ${priceText} >= ${sellPrice?.toFixed(8)})`, 'trade');
        }
        // Отправляем команду на продажу (только один раз при смене состояния)
        if(!window.__tradeStateTimer.tradeExecuted && autoTradeEnabled){
          executeTrade('sell', currency);
          window.__tradeStateTimer.tradeExecuted = true;
        }
      } else if(newState === 'buy'){
        if(typeof window.uiDebugLog === 'function'){
          window.uiDebugLog(`${currency}: Состояние → ${stateNames[newState]} (цена ${priceText} <= ${buyPrice?.toFixed(8)})`, 'trade');
        }
        // Отправляем команду на покупку (только один раз при смене состояния)
        if(!window.__tradeStateTimer.tradeExecuted && autoTradeEnabled){
          executeTrade('buy', currency);
          window.__tradeStateTimer.tradeExecuted = true;
        }
      } else if(oldState !== 'waiting'){
        // Возврат в ожидание только если был в другом состоянии
        if(typeof window.uiDebugLog === 'function'){
          window.uiDebugLog(`${currency}: Состояние → ${stateNames[newState]}`, 'info');
        }
      }
    }
    
    // Функция форматирования времени
    const formatDuration = (ms) => {
      const seconds = Math.floor(ms / 1000);
      const minutes = Math.floor(seconds / 60);
      const hours = Math.floor(minutes / 60);
      
      if(hours > 0){
        return `${hours}ч ${minutes % 60}м`;
      } else if(minutes > 0){
        return `${minutes}м ${seconds % 60}с`;
      } else {
        return `${seconds}с`;
      }
    };
    
    // Функция обновления таймера
    const updateTimer = () => {
      const duration = Date.now() - window.__tradeStateTimer.startTime;
      const durationText = formatDuration(duration);
      
      const state = window.__tradeStateTimer.state;
      if(state === 'sell'){
        tradeIndicatorEl.innerHTML = `🟢 Продажа (${durationText})`;
        tradeIndicatorEl.style.color = '#28a745';
      } else if(state === 'buy'){
        tradeIndicatorEl.innerHTML = `🔴 Покупка (${durationText})`;
        tradeIndicatorEl.style.color = '#dc3545';
      } else {
        tradeIndicatorEl.innerHTML = `⏸️ Ожидание (${durationText})`;
        tradeIndicatorEl.style.color = '#6c757d';
      }
    };
    
    // Запускаем интервал для обновления таймера (если еще не запущен)
    if(!window.__tradeStateTimer.intervalId){
      window.__tradeStateTimer.intervalId = setInterval(updateTimer, 1000);
    }
    
    // Обновляем текст и цвет сразу
    updateTimer();
  }
```

## Ключевые особенности реализации

1. **Таймер обновляется каждую секунду** - setInterval вызывает updateTimer() каждую секунду
2. **Торговая команда отправляется только один раз** - флаг `tradeExecuted` предотвращает повторную отправку
3. **Логи в debug panel** - все события логируются через `window.uiDebugLog`
4. **Автоматическая торговля** - при изменении состояния на "sell" или "buy" автоматически вызывается `executeTrade()`
5. **Проверка autoTradeEnabled** - торговля выполняется только если автоторговля включена

## Тестирование

После внесения изменений:

1. Перезапустить сервер
2. Открыть веб-интерфейс
3. Выбрать валютную пару
4. Наблюдать за индикатором "Торговля" в статистике
5. Проверить debug panel (должны появляться сообщения о смене состояний)
6. При пересечении порогов должны автоматически выполняться сделки (если автоторговля включена)

## Примечание

Код проверяет `autoTradeEnabled` перед выполнением сделок. Если вы хотите тестировать без реальных сделок, можно временно закомментировать вызовы `executeTrade()`.
