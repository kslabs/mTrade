/**
 * api-client.js - API клиент для взаимодействия с сервером mTrade
 * Простые функции для выполнения HTTP-запросов к API
 */

/**
 * Базовая функция для выполнения GET-запросов
 * @param {string} endpoint - Путь к API endpoint
 * @returns {Promise<any>} Ответ от сервера
 */
async function apiGet(endpoint) {
  const response = await fetch(endpoint);
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  return await response.json();
}

/**
 * Базовая функция для выполнения POST-запросов
 * @param {string} endpoint - Путь к API endpoint
 * @param {object} data - Данные для отправки
 * @returns {Promise<any>} Ответ от сервера
 */
async function apiPost(endpoint, data = {}) {
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  return await response.json();
}

// === Network Mode API ===

/**
 * Получить текущий режим сети (work/test)
 * @returns {Promise<{mode: string}>}
 */
export async function getNetworkMode() {
  return await apiGet('/api/network');
}

/**
 * Установить режим сети
 * @param {string} mode - Режим сети ('work' или 'test')
 * @returns {Promise<any>}
 */
export async function setNetworkMode(mode) {
  return await apiPost('/api/network', { mode });
}

// === Trading Mode API ===

/**
 * Получить текущий торговый режим (live/demo)
 * @returns {Promise<{mode: string}>}
 */
export async function getTradingMode() {
  return await apiGet('/api/mode');
}

/**
 * Установить торговый режим
 * @param {string} mode - Торговый режим ('live' или 'demo')
 * @returns {Promise<any>}
 */
export async function setTradingMode(mode) {
  return await apiPost('/api/mode', { mode });
}

// === Currencies API ===

/**
 * Получить список валют
 * @returns {Promise<{currencies: Array}>}
 */
export async function getCurrencies() {
  return await apiGet('/api/currencies');
}

/**
 * Сохранить список валют
 * @param {Array} currencies - Массив объектов валют {code, symbol}
 * @returns {Promise<any>}
 */
export async function saveCurrencies(currencies) {
  return await apiPost('/api/currencies', { currencies });
}

/**
 * Синхронизировать валюты с Gate.io
 * @param {string} quoteCurrency - Котируемая валюта (например, 'USDT')
 * @returns {Promise<any>}
 */
export async function syncCurrenciesFromGateIO(quoteCurrency) {
  return await apiPost('/api/currencies/sync', { quote_currency: quoteCurrency });
}

/**
 * Получить информацию о последней синхронизации
 * @returns {Promise<any>}
 */
export async function getSyncInfo() {
  return await apiGet('/api/currencies/sync-info');
}

// === Trading Permissions API ===

/**
 * Получить разрешения на торговлю для валют
 * @returns {Promise<any>}
 */
export async function getTradingPermissions() {
  return await apiGet('/api/trade/permissions');
}

/**
 * Переключить разрешение на торговлю для валюты
 * @param {string} code - Код валюты
 * @param {boolean} enabled - Включить или выключить
 * @returns {Promise<any>}
 */
export async function toggleTradingPermission(code, enabled) {
  return await apiPost('/api/trade/permission', { code, enabled });
}

// === Trade Parameters API ===

/**
 * Сохранить параметры торговли
 * @param {object} params - Параметры торговли
 * @returns {Promise<any>}
 */
export async function saveTradeParams(params) {
  return await apiPost('/api/trade/params', params);
}

// === Pair Subscription API ===

/**
 * Подписаться на данные торговой пары
 * @param {string} baseCurrency - Базовая валюта
 * @param {string} quoteCurrency - Котируемая валюта
 * @returns {Promise<any>}
 */
export async function subscribeToPair(baseCurrency, quoteCurrency) {
  return await apiPost('/api/pair/subscribe', {
    base_currency: baseCurrency,
    quote_currency: quoteCurrency
  });
}

// === UI State API ===

/**
 * Загрузить состояние UI
 * @returns {Promise<any>}
 */
export async function loadUIState() {
  return await apiGet('/api/ui/state');
}

/**
 * Загрузить частичное состояние UI
 * @param {Array<string>} keys - Список ключей для загрузки
 * @returns {Promise<any>}
 */
export async function loadPartialUIState(keys) {
  return await apiPost('/api/ui/state/partial', { keys });
}

// === Server Control API ===

/**
 * Перезапустить сервер
 * @returns {Promise<any>}
 */
export async function restartServer() {
  return await apiPost('/api/server/restart');
}

/**
 * Выключить сервер
 * @returns {Promise<any>}
 */
export async function shutdownServer() {
  return await apiPost('/api/server/shutdown');
}

/**
 * Получить статус сервера
 * @returns {Promise<any>}
 */
export async function getServerStatus() {
  return await apiGet('/api/server/status');
}

// === Trade Operations API ===

/**
 * Купить минимальный объём
 * @param {string} baseCurrency - Базовая валюта
 * @param {string} quoteCurrency - Котируемая валюта
 * @returns {Promise<any>}
 */
export async function buyMinOrder(baseCurrency, quoteCurrency) {
  return await apiPost('/api/trade/buy-min', {
    base_currency: baseCurrency,
    quote_currency: quoteCurrency
  });
}

/**
 * Продать всё
 * @param {string} baseCurrency - Базовая валюта
 * @param {string} quoteCurrency - Котируемая валюта
 * @returns {Promise<any>}
 */
export async function sellAll(baseCurrency, quoteCurrency) {
  return await apiPost('/api/trade/sell-all', {
    base_currency: baseCurrency,
    quote_currency: quoteCurrency
  });
}

// === Autotrader API ===

/**
 * Сбросить цикл автотрейдера
 * @param {string} baseCurrency - Базовая валюта
 * @param {string} quoteCurrency - Котируемая валюта
 * @returns {Promise<any>}
 */
export async function resetCycle(baseCurrency, quoteCurrency) {
  return await apiPost('/api/autotrader/reset_cycle', {
    base_currency: baseCurrency,
    quote_currency: quoteCurrency
  });
}

/**
 * Возобновить цикл автотрейдера
 * @param {string} baseCurrency - Базовая валюта
 * @param {string} quoteCurrency - Котируемая валюта
 * @returns {Promise<any>}
 */
export async function resumeCycle(baseCurrency, quoteCurrency) {
  return await apiPost('/api/autotrader/resume_cycle', {
    base_currency: baseCurrency,
    quote_currency: quoteCurrency
  });
}
