# Руководство по сохранению состояния UI

## Описание

Система автоматического сохранения и восстановления всех настроек пользовательского интерфейса, включая:
- Включенные/выключенные валюты для торговли
- Состояние автотрейдинга (вкл/выкл)
- Сетевой режим (work/test)
- Активная валютная пара
- Настройки отображения (тема, видимость панелей)
- Глубина стакана ордеров

## Файл хранения

Все настройки сохраняются в файле: **`ui_state.json`**

### Структура файла

```json
{
  "enabled_currencies": {
    "BTC": true,
    "ETH": false,
    "SOL": true
  },
  "auto_trade_enabled": true,
  "network_mode": "work",
  "active_base_currency": "BTC",
  "active_quote_currency": "USDT",
  "theme": "dark",
  "show_indicators": true,
  "show_orderbook": true,
  "show_trades": true,
  "orderbook_depth": 20,
  "last_updated": 1699545600.123
}
```

## API Endpoints

### 1. Получить текущее состояние UI

**GET** `/api/ui/state`

**Ответ:**
```json
{
  "success": true,
  "state": {
    "enabled_currencies": {...},
    "auto_trade_enabled": true,
    "network_mode": "work",
    ...
  }
}
```

### 2. Сохранить полное состояние UI

**POST** `/api/ui/state`

**Тело запроса:**
```json
{
  "state": {
    "enabled_currencies": {...},
    "auto_trade_enabled": true,
    ...
  }
}
```

**Ответ:**
```json
{
  "success": true,
  "message": "Состояние UI сохранено"
}
```

### 3. Частичное обновление состояния

**POST** `/api/ui/state/partial`

**Тело запроса:**
```json
{
  "updates": {
    "theme": "light",
    "orderbook_depth": 50
  }
}
```

**Ответ:**
```json
{
  "success": true,
  "message": "Состояние UI обновлено",
  "state": {...}
}
```

### 4. Сбросить настройки к значениям по умолчанию

**POST** `/api/ui/state/reset`

**Ответ:**
```json
{
  "success": true,
  "message": "Состояние UI сброшено",
  "state": {...}
}
```

## Автоматическое сохранение

Система автоматически сохраняет настройки при следующих действиях:

1. **Включение/выключение автотрейдинга** (`/api/autotrade/start`, `/api/autotrade/stop`)
2. **Изменение разрешений торговли для валюты** (`/api/trade/permission`)
3. **Переключение сетевого режима** (`/api/network`)

## Восстановление при запуске

При запуске сервера автоматически:
1. Загружается файл `ui_state.json`
2. Восстанавливаются все сохраненные настройки
3. Применяются к глобальным переменным приложения

### Логи при запуске

```
[BOOT] Загружено сохраненное состояние UI
[BOOT] Восстановлены разрешения торговли: {'BTC': True, 'ETH': False, ...}
[BOOT] Автотрейдинг: True
[BOOT] Восстановлен сетевой режим: work
```

## Использование на клиенте (JavaScript)

### Загрузка состояния при инициализации страницы

```javascript
async function loadUIState() {
  try {
    const response = await fetch('/api/ui/state');
    const result = await response.json();
    
    if (result.success) {
      const state = result.state;
      
      // Применяем настройки к UI
      applyTheme(state.theme);
      setAutoTradeButton(state.auto_trade_enabled);
      restoreCurrencyToggles(state.enabled_currencies);
      selectCurrencyPair(state.active_base_currency, state.active_quote_currency);
      // и т.д.
    }
  } catch (error) {
    console.error('Ошибка загрузки состояния UI:', error);
  }
}

// Вызываем при загрузке страницы
document.addEventListener('DOMContentLoaded', loadUIState);
```

### Сохранение при изменении настроек

```javascript
async function saveUISetting(key, value) {
  try {
    const response = await fetch('/api/ui/state/partial', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        updates: { [key]: value }
      })
    });
    
    const result = await response.json();
    if (!result.success) {
      console.error('Ошибка сохранения:', result.error);
    }
  } catch (error) {
    console.error('Ошибка сохранения настройки:', error);
  }
}

// Примеры использования
toggleTheme.addEventListener('change', (e) => {
  const theme = e.target.checked ? 'light' : 'dark';
  saveUISetting('theme', theme);
});

currencySelector.addEventListener('change', (e) => {
  saveUISetting('active_base_currency', e.target.value);
});
```

### Автоматическое сохранение состояния валют

```javascript
function toggleCurrencyTrading(baseCurrency, enabled) {
  // Отправляем запрос (автоматически сохраняется на сервере)
  fetch('/api/trade/permission', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      base_currency: baseCurrency,
      enabled: enabled
    })
  })
  .then(response => response.json())
  .then(result => {
    if (result.success) {
      console.log(`Торговля ${baseCurrency}: ${enabled ? 'включена' : 'выключена'}`);
    }
  });
}
```

## Преимущества

1. ✅ **Персистентность**: Все настройки сохраняются между сеансами
2. ✅ **Автоматизация**: Не нужно вручную сохранять после каждого изменения
3. ✅ **Простота**: Понятная структура JSON для ручного редактирования при необходимости
4. ✅ **Отказоустойчивость**: При ошибке загрузки используются значения по умолчанию
5. ✅ **Производительность**: Частичное обновление без перезаписи всего файла

## Устранение проблем

### Настройки не сохраняются

1. Проверьте права на запись в директорию приложения
2. Убедитесь, что файл `ui_state.json` не защищен от записи
3. Проверьте логи сервера на наличие ошибок

### Настройки не восстанавливаются

1. Проверьте наличие файла `ui_state.json`
2. Проверьте корректность JSON в файле
3. Посмотрите логи при запуске сервера `[BOOT]`

### Сброс настроек

Если нужно вернуть все к дефолтным значениям:
- Удалите файл `ui_state.json` и перезапустите сервер
- Или используйте API: `POST /api/ui/state/reset`

## Безопасность

⚠️ **Важно**: Файл `ui_state.json` не содержит чувствительных данных (API ключи хранятся отдельно в `config/secrets.json`)

Хранятся только пользовательские настройки интерфейса.
