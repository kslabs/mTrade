// === Импорты модулей ===
import { logDbg, formatPrice, $, formatUptime } from './js/utils.js';
import { showMessageModal, closeMessageModal, copyMessageModalContent } from './js/ui-helpers.js';
import * as api from './js/api-client.js';
import { updateOrderBook, setGlobalBuyPrice, setGlobalSellPrice } from './js/orderbook.js';

// Инициализация для обратной совместимости
window.__diagLogs = [];

// Экспортируем функции в глобальную область для использования в HTML
window.showMessageModal = showMessageModal;
window.closeMessageModal = closeMessageModal;
window.copyMessageModalContent = copyMessageModalContent;

// 🔍 Диагностика: проверка импорта
console.log('[INIT] Импортированные функции:', {
  logDbg: typeof logDbg,
  formatPrice: typeof formatPrice,
  $: typeof $
});

let globalActiveStep = null; // Текущий активный шаг в таблице безубыточности


// === UI функции импортированы из ui-helpers.js ===
// showMessageModal, closeMessageModal, copyMessageModalContent доступны через window

// $ импортируется из utils.js
let currentNetworkMode='work';
let currentBaseCurrency=null; // Будет установлено после загрузки currencies
try{ window.currentBaseCurrency = currentBaseCurrency; }catch(_){/* noop */}
let currentQuoteCurrency='USDT';
try{ window.currentQuoteCurrency = currentQuoteCurrency; }catch(_){/* noop */}
let currencySetByUser = false; // Флаг, что валюта была установлена пользователем
let currenciesList=[];
let currentPairPricePrecision=8; // Точность цены для текущей пары (по умолчанию 8)
let autoTradeActive=false;
let autoTradeEnabled = true; // По умолчанию включено (ON), будет загружено из state
let tradingPermissions = {}; // статус разрешений торговли

// Флаг для предотвращения множественных одновременных переключений валюты
let isSwitchingCurrency = false;
let pendingSwitchCurrency = null; // Последняя запрошенная валюта во время блокировки

// Объекты для хранения шагов и диагностических решений по валютам
let activeSteps = {};
let diagnosticDecisions = {};
let sellPrices = {};
let buyPrices = {};
let currentPrices = {};
let activeCycles = {}; // Статус цикла для каждой валюты (true = активен, false = неактивен)

// --- On-page debug panel --------------------------------------------------
// Creates a collapsible debug panel with a side tab
// Use window.uiDebugLog(message, level) from any script to append messages
window.uiDebugLog = function(msg, level='DEBUG'){
  try{
    if(!window.__uiDebugPanel){
      // Create main panel container
      const panel = document.createElement('div');
      panel.id = 'uiDebugPanel';
      panel.style.position = 'fixed';
      panel.style.right = '0';
      panel.style.bottom = '12px';
      panel.style.width = '420px';
      panel.style.maxHeight = '40vh';
      panel.style.background = 'rgba(18,18,18,0.95)';
      panel.style.color = '#ddd';
      panel.style.border = '1px solid rgba(255,255,255,0.08)';
      panel.style.borderRight = 'none';
      panel.style.borderRadius = '8px 0 0 8px';
      panel.style.fontSize = '12px';
      panel.style.zIndex = 99999;
      panel.style.padding = '8px';
      panel.style.boxShadow = '-4px 4px 20px rgba(0,0,0,0.7)';
      panel.style.transition = 'transform 0.3s ease';
      panel.style.transform = 'translateX(100%)'; // Initially hidden
      
      // Create toggle tab
      const tab = document.createElement('div');
      tab.id = 'uiDebugTab';
      tab.innerHTML = '◀<br>D<br>E<br>B<br>U<br>G';
      tab.style.position = 'fixed';
      tab.style.right = '0';
      tab.style.bottom = '50%';
      tab.style.transform = 'translateY(50%)';
      tab.style.width = '28px';
      tab.style.padding = '8px 4px';
      tab.style.background = 'rgba(18,18,18,0.95)';
      tab.style.color = '#4a9eff';
      tab.style.border = '1px solid rgba(255,255,255,0.08)';
      tab.style.borderRight = 'none';
      tab.style.borderRadius = '8px 0 0 8px';
      tab.style.fontSize = '11px';
      tab.style.fontWeight = '700';
      tab.style.letterSpacing = '1px';
      tab.style.textAlign = 'center';
      tab.style.lineHeight = '1.2';
      tab.style.cursor = 'pointer';
      tab.style.zIndex = 99998;
      tab.style.userSelect = 'none';
      tab.style.boxShadow = '-2px 2px 8px rgba(0,0,0,0.5)';
      tab.style.transition = 'background 0.2s';
      
      tab.onmouseenter = () => { tab.style.background = 'rgba(74,158,255,0.2)'; };
      tab.onmouseleave = () => { tab.style.background = 'rgba(18,18,18,0.95)'; };
      
      // Toggle panel visibility
      let isOpen = false;
      tab.onclick = () => {
        isOpen = !isOpen;
        if(isOpen){
          panel.style.transform = 'translateX(0)';
          tab.innerHTML = '▶<br>D<br>E<br>B<br>U<br>G';
        } else {
          panel.style.transform = 'translateX(100%)';
          tab.innerHTML = '◀<br>D<br>E<br>B<br>U<br>G';
        }
      };

      const header = document.createElement('div');
      header.style.display = 'flex';
      header.style.justifyContent = 'space-between';
      header.style.alignItems = 'center';
      header.style.marginBottom = '6px';

      const title = document.createElement('div');
      title.textContent = 'DEBUG PANEL';
      title.style.fontWeight = '700';
      title.style.color = '#fff';
      title.style.letterSpacing = '0.6px';
      header.appendChild(title);

      const controls = document.createElement('div');
      controls.style.display = 'flex';
      controls.style.gap = '6px';

      const clearBtn = document.createElement('button');
      clearBtn.textContent = 'Clear';
      clearBtn.style.background = '#333';
      clearBtn.style.color = '#fff';
      clearBtn.style.border = 'none';
      clearBtn.style.padding = '4px 8px';
      clearBtn.style.borderRadius = '4px';
      clearBtn.style.cursor = 'pointer';
      clearBtn.onclick = () => { panel.querySelector('.dbg-body').innerHTML = ''; };

      const copyBtn = document.createElement('button');
      copyBtn.textContent = 'Copy';
      copyBtn.style.background = '#1f6feb';
      copyBtn.style.color = '#fff';
      copyBtn.style.border = 'none';
      copyBtn.style.padding = '4px 8px';
      copyBtn.style.borderRadius = '4px';
      copyBtn.style.cursor = 'pointer';
      copyBtn.onclick = () => {
        const text = [...panel.querySelectorAll('.dbg-row')].map(n=>n.textContent).join('\n');
        navigator.clipboard?.writeText(text).then(()=>{ copyBtn.textContent = 'Copied!'; setTimeout(()=>copyBtn.textContent='Copy',800) });
      };
      
      const closeBtn = document.createElement('button');
      closeBtn.textContent = '✕';
      closeBtn.style.background = '#dc3545';
      closeBtn.style.color = '#fff';
      closeBtn.style.border = 'none';
      closeBtn.style.padding = '4px 10px';
      closeBtn.style.borderRadius = '4px';
      closeBtn.style.cursor = 'pointer';
      closeBtn.style.fontWeight = 'bold';
      closeBtn.onclick = () => { 
        isOpen = false;
        panel.style.transform = 'translateX(100%)';
        tab.innerHTML = '◀<br>D<br>E<br>B<br>U<br>G';
      };

      controls.appendChild(clearBtn);
      controls.appendChild(copyBtn);
      controls.appendChild(closeBtn);
      header.appendChild(controls);

      const body = document.createElement('div');
      body.className = 'dbg-body';
      body.style.maxHeight = 'calc(40vh - 36px)';
      body.style.overflow = 'auto';
      body.style.padding = '4px';

      panel.appendChild(header);
      panel.appendChild(body);
      document.body.appendChild(panel);
      document.body.appendChild(tab);

      window.__uiDebugPanel = panel;
      window.__uiDebugTab = tab;
      window.__uiDebugBuffer = [];
    }

    const timestamp = new Date().toLocaleTimeString();
    const row = document.createElement('div');
    row.className = 'dbg-row';
    row.style.padding = '4px 6px';
    row.style.borderBottom = '1px dashed rgba(255,255,255,0.03)';
    row.style.fontFamily = 'monospace';
    row.style.fontSize = '12px';
    row.textContent = `[${timestamp}] ${level}: ${msg}`;

    // cap buffer size
    const body = window.__uiDebugPanel.querySelector('.dbg-body');
    body.insertBefore(row, body.firstChild);
    window.__uiDebugBuffer.unshift(row.textContent);
    if(window.__uiDebugBuffer.length > 400){
      window.__uiDebugBuffer.pop();
      const nodes = body.querySelectorAll('.dbg-row');
      if(nodes.length>400) nodes[nodes.length-1].remove();
    }
    return true;
  }catch(e){ console.error('uiDebugLog err', e); return false; }
};

// ------------------ Watcher для currentBaseCurrency ---------------------
// Если значение меняется в рантайме — пишем в debug панель (с небольшой подписью стека)
try{
  window.__lastObservedBaseCurrency = currentBaseCurrency;
  setInterval(()=>{
    try{
      if(window.__lastObservedBaseCurrency !== currentBaseCurrency){
        const from = window.__lastObservedBaseCurrency;
        const to = currentBaseCurrency;
        window.__lastObservedBaseCurrency = currentBaseCurrency;
        const stack = (new Error()).stack || '';
        const shortStack = stack.split('\n').slice(2,7).map(s=>s.trim()).join(' | ');
        if(window.uiDebugLog) window.uiDebugLog(`currentBaseCurrency changed ${from} -> ${to}  stack: ${shortStack}`,'CHANGE');
        else console.debug('currentBaseCurrency changed', from, '->', to);
      }
    }catch(e){/* nop */}
  }, 400);
}catch(e){ console.warn('currency watcher not started', e); }

// UI State Manager - простой менеджер для сохранения состояния UI
const UIStateManager = {
  async savePartial(updates) {
    try {
      // Преобразуем ключи в формат, ожидаемый сервером
      const stateUpdates = {};
      if (updates.baseCurrency) stateUpdates.active_base_currency = updates.baseCurrency;
      if (updates.quoteCurrency) stateUpdates.active_quote_currency = updates.quoteCurrency;
      if (updates.autoTradeEnabled !== undefined) stateUpdates.auto_trade_enabled = updates.autoTradeEnabled;
      if (updates.networkMode) stateUpdates.network_mode = updates.networkMode;
      if (updates.tradingMode) stateUpdates.trading_mode = updates.tradingMode;
      if (updates.breakeven_params) stateUpdates.breakeven_params = updates.breakeven_params;
      
      const result = await api.loadPartialUIState([stateUpdates]);
      if (result.success) {
        logDbg('UI State: частичное сохранение успешно - ' + JSON.stringify(stateUpdates));
      } else {
        logDbg('UI State: ошибка частичного сохранения - ' + (result.error || 'unknown'));
      }
      return result;
    } catch (error) {
      logDbg('UI State: исключение при сохранении - ' + error);
      return {success: false, error: String(error)};
    }
  }
};

// Глобальная переменная для хранения точности текущей пары
let currentPricePrecision = 5;
function updateTradeIndicators(d){
  d=d||{};
  const priceEl=$('indPrice');
  if(priceEl&&d.price) priceEl.textContent=formatPrice(d.price, currentPricePrecision);
  
  // Поддерживаем старый формат: autotrade_levels внутри d
  const levels = d.autotrade_levels || {};

  // Если в WS-пакете указана валюта — используем её как целевую вкладку.
  // Фолбэк — currentBaseCurrency.
  const targetCurrency = (levels.base_currency || d.base_currency || d.currency || currentBaseCurrency || '').toString().toUpperCase();

  // Обновляем значения в футере индикатора с единой точностью
  const updates = {
    'sell': levels.sell_price,
    'be': levels.breakeven_price,
    'last': levels.current_price,
    'start': levels.start_price,
    'buy': levels.next_buy_price
  };
  
  for(const [key, value] of Object.entries(updates)){
    const elementId = key === 'be' ? 'indBE' : 'ind' + key.charAt(0).toUpperCase() + key.slice(1);
    const el = $(elementId);
    if(el){
      if(value === null || value === undefined || value === 0){
        el.textContent = '-';
      } else {
        el.textContent = formatPrice(value, currentPricePrecision);
      }
    }
  }
  
  // Обновляем autotrade_levels если есть
  if(d.autotrade_levels){
    updateAutoTradeLevels(d.autotrade_levels);
  }

  // APPLY per-currency tab border coloring based on incoming levels
  try {
    const diag = levels.diagnostic_decision;

    const currentPrice = levels.current_price != null ? parseFloat(levels.current_price) : NaN;
    const sellPrice = levels.sell_price != null ? parseFloat(levels.sell_price) : null;
    const buyPrice = levels.next_buy_price != null ? parseFloat(levels.next_buy_price) : null;

    // 1) Обновляем общий контейнер (как раньше) — оставляем для визуального индикатора
    const container = document.querySelector('.indicator-card');
    if (container) {
      container.style.transition = 'box-shadow 160ms ease, border-color 160ms ease';

      let applied = false;

      if (!isNaN(currentPrice) && sellPrice !== null && !isNaN(sellPrice) && currentPrice >= sellPrice) {
        container.style.border = '3px solid #28a745';
        container.style.boxShadow = '0 6px 18px rgba(40,167,69,0.12)';
        applied = true;
      } else if (!isNaN(currentPrice) && buyPrice !== null && !isNaN(buyPrice) && currentPrice <= buyPrice) {
        container.style.border = '3px solid #dc3545';
        container.style.boxShadow = '0 6px 18px rgba(220,53,69,0.12)';
        applied = true;
      } else if (!isNaN(currentPrice) && (sellPrice !== null || buyPrice !== null)) {
        container.style.border = '';
        container.style.boxShadow = '';
        applied = true;
      }

      if (!applied) {
        if (diag && diag.decision === 'sell') {
          container.style.border = '3px solid #28a745';
          container.style.boxShadow = '0 6px 18px rgba(40,167,69,0.12)';
        } else if (diag && diag.decision === 'buy') {
          container.style.border = '3px solid #dc3545';
          container.style.boxShadow = '0 6px 18px rgba(220,53,69,0.12)';
        } else if (diag && diag.decision === 'sell_attempt_failed') {
          container.style.border = '3px solid #ff8c00';
          container.style.boxShadow = '0 6px 18px rgba(255,140,0,0.12)';
        } else {
          const shouldSell = (levels.last_detected && levels.last_detected.sell) || (levels.should_sell === true);
          const shouldBuy = (levels.last_detected && levels.last_detected.buy) || (levels.should_buy === true);
          if (shouldSell) {
            container.style.border = '3px solid #28a745';
            container.style.boxShadow = '0 6px 18px rgba(40,167,69,0.12)';
          } else if (shouldBuy) {
            container.style.border = '3px solid #dc3545';
            container.style.boxShadow = '0 6px 18px rgba(220,53,69,0.12)';
          } else {
            container.style.border = '';
            container.style.boxShadow = '';
          }
        }
      }
    }

    // 2) Теперь ОБЯЗАТЕЛЬНО обновляем бордюр и классы соответствующей вкладки валюты
    if(targetCurrency){
      const tab = document.querySelector(`.tab-item[data-code="${targetCurrency}"]`);
      if(tab){
        // Убираем старые классы бордюра
        tab.classList.remove('ready-to-sell','ready-to-buy','price-normal','ws-disconnected');

        // 🔥 КРИТИЧЕСКИ ВАЖНАЯ ПРОВЕРКА: Если цена отсутствует или равна 0 → WS отключён (светло-синий бордюр)
        const hasValidPrice = currentPrice !== undefined && !isNaN(currentPrice) && currentPrice > 0;
        const hasSellPrice = sellPrice !== null && !isNaN(sellPrice) && sellPrice > 0;
        const hasBuyPrice = buyPrice !== null && !isNaN(buyPrice) && buyPrice > 0;
        
        if (!hasValidPrice || !hasSellPrice || !hasBuyPrice) {
          // 🔵 Нет цены или она равна 0 → считаем, что WS отключён (светло-синий)
          tab.classList.add('ws-disconnected');
          console.log(`[BORDER_WS] ${targetCurrency}: ws-disconnected (currentPrice=${currentPrice}, sell=${sellPrice}, buy=${buyPrice})`);
        } else if(currentPrice >= sellPrice){
          // 🟡 Цена есть и выше порога продажи → жёлтый бордюр
          tab.classList.add('ready-to-sell');
          console.log(`[BORDER_WS] ${targetCurrency}: ready-to-sell (YELLOW) (current=${currentPrice} >= sell=${sellPrice})`);
        } else if(currentPrice <= buyPrice){
          // 🔴 Цена есть и ниже порога покупки → красный бордюр
          tab.classList.add('ready-to-buy');
          console.log(`[BORDER_WS] ${targetCurrency}: ready-to-buy (RED) (current=${currentPrice} <= buy=${buyPrice})`);
        } else {
          // 🟢 Цена есть и между порогами → зелёный бордюр
          tab.classList.add('price-normal');
          console.log(`[BORDER_WS] ${targetCurrency}: price-normal (GREEN) (buy=${buyPrice} < current=${currentPrice} < sell=${sellPrice})`);
        }
      } else {
        console.warn('[BORDER_WS] Вкладка для валюты не найдена:', targetCurrency);
      }
    }

  } catch (e) { console.error('apply diag color failed', e); }
}

function updateAutoTradeLevels(levels){
  if(!levels) return;
  
  // Сохраняем уровни покупки/продажи для подсветки в стакане
  setGlobalBuyPrice(levels.next_buy_price);
  setGlobalSellPrice(levels.sell_price);
  
  // Сохраняем активный шаг для подсветки в таблице безубыточности
  globalActiveStep = levels.active_step;
  
  // Сохраняем шаги и диагностические решения для всех валют
  activeSteps[currentBaseCurrency] = levels.active_step;
  diagnosticDecisions[currentBaseCurrency] = levels.diagnostic_decision;
  sellPrices[currentBaseCurrency] = levels.sell_price;
  buyPrices[currentBaseCurrency] = levels.next_buy_price;
  currentPrices[currentBaseCurrency] = levels.current_price;
  activeCycles[currentBaseCurrency] = levels.active_cycle; // 🔥 СОХРАНЯЕМ СТАТУС ЦИКЛА
  
  // Обновляем UI разрешений для отображения активного шага
  updateTabsPermissionsUI();
  
  // Обновляем индикаторы текущего цикла
  const activeEl = $('autotradeCycleActive');
  if(activeEl){
    activeEl.textContent = levels.active_cycle ? 'Активен' : 'Неактивен';
    activeEl.className = 'value ' + (levels.active_cycle ? 'active' : 'inactive');
  }
  
  // Обновляем текущий шаг
  const stepEl = $('autotradeCurrentStep');
  if(stepEl){
    if(levels.active_step !== null && levels.total_steps !== null){
      stepEl.textContent = `${levels.active_step} / ${levels.total_steps}`;
    } else {
      stepEl.textContent = '-';
    }
  }
  
  // Обновляем все уровни цен
  const priceFields = {
    'autotradePriceCurrent': levels.current_price,
    'autotradePriceStart': levels.start_price,
    'autotradePriceBreakeven': levels.breakeven_price,
    'autotradePriceLastBuy': levels.last_buy_price,
    'autotradePriceSell': levels.sell_price,
    'autotradePriceNextBuy': levels.next_buy_price
  };
  
  for(const [id, value] of Object.entries(priceFields)){
    const el = $(id);
    if(el){
      el.textContent = (value === null || value === undefined) ? '-' : formatPrice(value);
    }
  }
  
  // Обновляем уровень стакана
  const orderbookLevelEl = $('autotradeOrderbookLevel');
  if(orderbookLevelEl){
    orderbookLevelEl.textContent = (levels.orderbook_level !== null && levels.orderbook_level !== undefined) ? levels.orderbook_level : '-';
  }
  
  // Обновляем процент роста от P0
  const growthEl = $('autotradeGrowthPct');
  if(growthEl){
    if(levels.current_growth_pct !== null && levels.current_growth_pct !== undefined){
      const pct = levels.current_growth_pct;
      growthEl.textContent = pct.toFixed(2) + '%';
      growthEl.className = 'value ' + (pct >= 0 ? 'positive' : 'negative');
    } else {
      growthEl.textContent = '-';
      growthEl.className = 'value';
    }
  }
  
  // Обновляем процент роста от последней покупки
  const growthFromLastBuyEl = $('autotradeGrowthFromLastBuy');
  if(growthFromLastBuyEl){
    if(levels.growth_from_last_buy_pct !== null && levels.growth_from_last_buy_pct !== undefined){
      const pct = levels.growth_from_last_buy_pct;
      growthFromLastBuyEl.textContent = pct.toFixed(2) + '%';
      growthFromLastBuyEl.className = 'value ' + (pct >= 0 ? 'positive' : 'negative');
    } else {
      growthFromLastBuyEl.textContent = '-';
      growthFromLastBuyEl.className = 'value';
    }
  }
  
  // Обновляем инвестировано
  const investedEl = $('autotradeInvested');
  if(investedEl){
    investedEl.textContent = levels.invested_usd !== null ? levels.invested_usd.toFixed(2) + ' USDT' : '-';
  }
  
  // Обновляем объём базовой валюты
  const volumeEl = $('autotradeBaseVolume');
  let totalBaseVolume = null;
  if(volumeEl){
    // Показываем реальный баланс (если есть) или base_volume из цикла
    if (levels.real_balance && levels.real_balance.total !== undefined) {
      const total = levels.real_balance.total;
      const available = levels.real_balance.available;
      const locked = levels.real_balance.locked;
      totalBaseVolume = total; // сохраняем для расчёта эквивалента
      
      if (locked > 0) {
        volumeEl.innerHTML = `${total.toFixed(8)}<br><small style="color: #999;">(${available.toFixed(8)} + <span style="color: #ff9800;">${locked.toFixed(8)} 🔒</span>)</small>`;
      } else {
        volumeEl.textContent = total.toFixed(8);
      }
    } else if (levels.base_volume !== null) {
      totalBaseVolume = levels.base_volume;
      volumeEl.textContent = levels.base_volume.toFixed(8);
    } else {
      volumeEl.textContent = '-';
    }
  }
  
  // Обновляем эквивалент объёма базы в котируемой валюте (USDT)
  const volumeUSDTEl = $('autotradeBaseVolumeUSDT');
  if(volumeUSDTEl){
    const currentPrice = levels.current_price;
    if (totalBaseVolume !== null && totalBaseVolume > 0 && currentPrice !== null && currentPrice !== undefined && currentPrice > 0) {
      const equivalent = totalBaseVolume * parseFloat(currentPrice);
      volumeUSDTEl.textContent = equivalent.toFixed(2) + ' USDT';
    } else {
      volumeUSDTEl.textContent = '-';
    }
  }
  
  // Обновляем визуальную шкалу с маркерами
  updateVisualIndicatorScale(levels);

  // Apply diagnostic decision coloring: green border for sell, red for buy
  try {
    const diag = levels.diagnostic_decision;
    const container = document.querySelector('.indicator-card');
    if (container) {
      container.style.transition = 'box-shadow 160ms ease, border-color 160ms ease';

      // Preferred: use numeric price bands when available.
      //  - if current_price >= sell_price -> GREEN
      //  - else if current_price <= next_buy_price -> RED
      //  - else -> GREY (neutral)
      // If either price is missing, fall back to detection/diagnostic state so clients still get a signal.

      const currentPrice = parseFloat(levels.current_price);
      const sellPrice = levels.sell_price !== null && levels.sell_price !== undefined ? parseFloat(levels.sell_price) : null;
      const buyPrice = levels.next_buy_price !== null && levels.next_buy_price !== undefined ? parseFloat(levels.next_buy_price) : null;

      let applied = false;

      if (!isNaN(currentPrice) && sellPrice !== null && !isNaN(sellPrice) && currentPrice >= sellPrice) {
        // price above or equal sell price -> green
        container.style.border = '3px solid #28a745';
        container.style.boxShadow = '0 6px 18px rgba(40,167,69,0.12)';
        applied = true;
      } else if (!isNaN(currentPrice) && buyPrice !== null && !isNaN(buyPrice) && currentPrice <= buyPrice) {
        // price at or below next buy price -> red
        container.style.border = '3px solid #dc3545';
        container.style.boxShadow = '0 6px 18px rgba(220,53,69,0.12)';
        applied = true;
      } else if (!isNaN(currentPrice) && (sellPrice !== null || buyPrice !== null)) {
        // price is between buy and sell (or one side missing) -> neutral
        container.style.border = '';
        container.style.boxShadow = '';
        applied = true;
      }

      if (!applied) {
        // No numeric band applied — fallback to diagnostic decision/last_detected
        if (diag && diag.decision === 'sell') {
          container.style.border = '3px solid #28a745'; // green
          container.style.boxShadow = '0 6px 18px rgba(40,167,69,0.12)';
        } else if (diag && diag.decision === 'buy') {
          container.style.border = '3px solid #dc3545'; // red
          container.style.boxShadow = '0 6px 18px rgba(220,53,69,0.12)';
        } else if (diag && diag.decision === 'sell_attempt_failed') {
          container.style.border = '3px solid #ff8c00';
          container.style.boxShadow = '0 6px 18px rgba(255,140,0,0.12)';
        } else {
          // fallback: use derived sentiment flags should_sell / should_buy OR last_detected events
          const shouldSell = (levels.last_detected && levels.last_detected.sell) || (levels.should_sell === true);
          const shouldBuy = (levels.last_detected && levels.last_detected.buy) || (levels.should_buy === true);
          if (shouldSell) {
            container.style.border = '3px solid #28a745';
            container.style.boxShadow = '0 6px 18px rgba(40,167,69,0.12)';
          } else if (shouldBuy) {
            container.style.border = '3px solid #dc3545';
            container.style.boxShadow = '0 6px 18px rgba(220,53,69,0.12)';
          } else {
            container.style.border = '';
            container.style.boxShadow = '';
          }
        }
      }

      // Sync border color with active currency tab
      // const activeTab = document.querySelector('.tab-item.active');
      // if (activeTab) {
      //   activeTab.style.transition = 'border-color 160ms ease';
      //   activeTab.style.border = container.style.border;
      // }
    }
  } catch (e) { console.error('apply diag color failed', e); }
}

function updateVisualIndicatorScale(levels){
  console.log('[SCALE] updateVisualIndicatorScale вызван с levels:', levels);
  if(!levels) {
    console.warn('[SCALE] levels не переданы!');
    return;
  }
  
  // Получаем все маркеры
  const markers = {
    sell: $('markerSell'),
    be: $('markerBE'),
    price: $('markerPrice'),
    last: $('markerLast'),
    start: $('markerStart'),
    buy: $('markerBuy')
  };
  
  console.log('[SCALE] Маркеры:', {
    sell: markers.sell ? 'найден' : 'НЕ НАЙДЕН',
    be: markers.be ? 'найден' : 'НЕ НАЙДЕН',
    price: markers.price ? 'найден' : 'НЕ НАЙДЕН',
    last: markers.last ? 'найден' : 'НЕ НАЙДЕН',
    start: markers.start ? 'найден' : 'НЕ НАЙДЕН',
    buy: markers.buy ? 'найден' : 'НЕ НАЙДЕН'
  });
  
  // Проверяем, что все маркеры существуют
  const allMarkersExist = Object.values(markers).every(m => m !== null);
  if(!allMarkersExist) {
    console.error('[SCALE] Не все маркеры найдены в DOM!');
    return;
  }
  
  // Собираем все цены для определения диапазона
  const prices = {
    current: levels.current_price,
    sell: levels.sell_price,
    be: levels.breakeven_price,
    last: levels.last_buy_price,
    start: levels.start_price,
    buy: levels.next_buy_price
  };
  
  console.log('[SCALE] Цены для индикатора:', prices);
  
  // Фильтруем валидные цены
  const validPrices = Object.values(prices).filter(p => p !== null && p !== undefined && !isNaN(p) && p > 0);
  
  if(validPrices.length === 0){
    // Нет валидных цен - скрываем все маркеры
    Object.values(markers).forEach(marker => {
      marker.style.bottom = '50%';
      marker.style.opacity = '0.3';
    });
    return;
  }
  
  // Определяем диапазон цен с небольшим запасом (±5%)
  const minPrice = Math.min(...validPrices);
  const maxPrice = Math.max(...validPrices);
  const range = maxPrice - minPrice;
  const padding = range * 0.1; // 10% padding сверху и снизу
  const displayMin = minPrice - padding;
  const displayMax = maxPrice + padding;
  const displayRange = displayMax - displayMin;
  
  // Функция для вычисления позиции маркера (0-100%)
  function calculatePosition(price){
    if(!price || price <= 0) return null;
    const normalized = (price - displayMin) / displayRange;
    return Math.max(0, Math.min(100, normalized * 100)); // Ограничиваем 0-100%
  }
  
  // Обновляем позиции маркеров
  const positions = {
    sell: calculatePosition(prices.sell),
    be: calculatePosition(prices.be),
    price: calculatePosition(prices.current),
    last: calculatePosition(prices.last),
    start: calculatePosition(prices.start),
    buy: calculatePosition(prices.buy)
  };
  
  // Применяем позиции и обновляем тултипы
  for(const [key, marker] of Object.entries(markers)){
    const pos = positions[key];
    const price = prices[key === 'price' ? 'current' : key];
    
    if(pos !== null && price){
      marker.style.bottom = pos + '%';
      marker.style.opacity = '1';
      
      // Обновляем тултип
      const tooltip = marker.querySelector('.marker-tooltip');
      if(tooltip){
        const label = key.charAt(0).toUpperCase() + key.slice(1);
        tooltip.textContent = `${label}: ${formatPrice(price)}`;
      }
    } else {
      marker.style.bottom = '50%';
      marker.style.opacity = '0.3';
      
      const tooltip = marker.querySelector('.marker-tooltip');
      if(tooltip){
        tooltip.textContent = `${key}: -`;
      }
    }
  }
  
  // Добавляем анимацию при обновлении
  Object.values(markers).forEach(marker => {
    marker.style.transition = 'bottom 0.3s ease-out, opacity 0.3s ease-out';
  });
}
function updateNetworkUI(){
  const sw=$('networkSwitcher');
  if(!sw) return;
  sw.classList.remove('work','test');
  sw.classList.add(currentNetworkMode==='test'?'test':'work');
  
  // Обновляем активность кнопок
  const workBtn = sw.querySelector('[data-mode="work"]');
  const testBtn = sw.querySelector('[data-mode="test"]');
  if(workBtn && testBtn){
    workBtn.classList.toggle('active', currentNetworkMode==='work');
    testBtn.classList.toggle('active', currentNetworkMode==='test');
  }
}
function setNetworkConnectionState(st){
  const sw=$('networkSwitcher');
  const cs=$('networkConnStatus');
  if(!sw) return;
  sw.classList.remove('pending','error');
  if(st==='pending'){
    sw.classList.add('pending');
    if(cs) cs.textContent='подключение...';
  }else if(st==='error'){
    sw.classList.add('error');
    if(cs) cs.textContent='ошибка';
  }else{
    if(cs) cs.textContent='';
  }
}
async function loadNetworkMode(){
  try{
    const d = await api.getNetworkMode();
    if(d.success){
      currentNetworkMode=d.mode;
      updateNetworkUI();
      
      // Выводим информацию о текущем режиме и подключении
      console.log('========================================');
      console.log('[NETWORK] Текущий режим:', d.mode);
      if(d.api_host) console.log('[NETWORK] API Host:', d.api_host);
      if(d.api_key) console.log('[NETWORK] API Key:', d.api_key);
      if(d.keys_loaded !== undefined) {
        console.log('[NETWORK] Ключи загружены:', d.keys_loaded ? 'ДА' : 'НЕТ');
      }
      console.log('========================================');
      
      logDbg('network mode='+currentNetworkMode);
    }
  }catch(e){ 
    console.error('[NETWORK] Ошибка загрузки режима:', e);
    logDbg('loadNetworkMode err '+e);
  }
}
async function loadCurrenciesFromServer(){
  console.log('[CURRENCIES] 🌐 loadCurrenciesFromServer вызвана');
  try{
    console.log('[CURRENCIES] 📡 Отправка запроса /api/currencies...');
    const d = await api.getCurrencies();
    console.log('[CURRENCIES] 📦 Данные получены:', d);
    if(d.success&&Array.isArray(d.currencies)){
      console.log('[CURRENCIES] ✅ Валюты получены, количество:', d.currencies.length);
      console.log('[CURRENCIES] 📋 Список валют:', d.currencies);
      currenciesList=d.currencies;
      renderCurrencyTabs(currenciesList);
    } else {
      console.error('[CURRENCIES] ❌ Ошибка: success=', d.success, 'currencies=', d.currencies);
      logDbg('loadCurrencies fail');
    }
  }catch(e){ 
    console.error('[CURRENCIES] ❌ Исключение:', e);
    logDbg('loadCurrencies exc '+e);
  }
}

// 🔥 ПРИНУДИТЕЛЬНАЯ функция для окрашивания валют с неактивным циклом в синий цвет
function forceApplyInactiveColors(){
  console.log('[FORCE_COLOR] Принудительное применение синего цвета для валют с неактивным циклом');
  const cont = document.getElementById('currencyTabsContainer');
  if(!cont) {
    console.warn('[FORCE_COLOR] currencyTabsContainer не найден');
    return;
  }
  
  const tabs = cont.querySelectorAll('.tab-item');
  let processedCount = 0;
  
  tabs.forEach(tab => {
    const code = tab.dataset.code;
    if(!code) return;
    
    const cycleActive = activeCycles[code]; // Используем статус цикла
    const isCycleInactive = (cycleActive === false); // Синий ТОЛЬКО если явно false
    
    console.log(`[FORCE_COLOR] ${code}: cycleActive=${cycleActive}, isCycleInactive=${isCycleInactive}`);
    
    if(isCycleInactive){
      const codeLabel = tab.querySelector('.code-label');
      if(codeLabel){
        const isActive = tab.classList.contains('active');
        const blueColor = isActive ? '#64B5F6' : '#2196F3'; // Светло-синий для активной, ярко-синий для неактивной
        const shadow = isActive ? '0 0 3px rgba(66,165,245,0.6)' : '0 0 2px rgba(33,150,243,0.5)';
        
        // Применяем синий цвет максимально агрессивно
        const styleText = `color: ${blueColor} !important; text-shadow: ${shadow} !important;`;
        codeLabel.style.cssText = styleText;
        codeLabel.setAttribute('style', styleText);
        
        // Также добавляем класс для CSS
        tab.classList.add('inactive-currency');
        
        // Проверяем результат
        const finalColor = window.getComputedStyle(codeLabel).color;
        console.log(`[FORCE_COLOR] ${code}: установлен синий цвет ${blueColor}, computed="${finalColor}"`);
        processedCount++;
      } else {
        console.warn(`[FORCE_COLOR] ${code}: .code-label не найден!`);
      }
    } else {
      // Для валют с активным циклом убираем класс и inline-стили
      tab.classList.remove('inactive-currency');
      const codeLabel = tab.querySelector('.code-label');
      if(codeLabel && codeLabel.hasAttribute('style')){
        // Сохраняем только те стили, которые не относятся к цвету
        const style = codeLabel.getAttribute('style');
        if(style && (style.includes('color') || style.includes('text-shadow'))){
          codeLabel.removeAttribute('style');
          console.log(`[FORCE_COLOR] ${code}: убран inline-стиль (цикл активен)`);
        }
      }
    }
  });
  
  console.log(`[FORCE_COLOR] Обработано валют с неактивным циклом: ${processedCount}`);
}

async function loadTradingPermissions(){
  console.log('[DEBUG] loadTradingPermissions called');
  try{
    const d = await api.getTradingPermissions();
    console.log('[DEBUG] loadTradingPermissions response:', d);
    if(d.success && d.permissions){
      // Обновляем глобальный объект разрешений (если нужно)
      window.tradingPermissions = d.permissions;
      // Обновляем UI (индикаторы на вкладках)
      updateTabsPermissionsUI();
      // 🔥 ПРИНУДИТЕЛЬНО применяем синий цвет
      setTimeout(() => forceApplyInactiveColors(), 50);
    } else {
      console.warn('[WARN] loadTradingPermissions failed:', d.error || 'unknown');
    }
  }catch(e){ 
    console.error('[ERROR] loadTradingPermissions exception:', e);
  }
}

async function toggleTradingPermission(code, event){
  if(event) event.stopPropagation(); // Предотвращаем переключение вкладки
  if(!code) return;
  
  // ВАЖНО: undefined трактуется как false (торговля запрещена)
  const currentState = (window.tradingPermissions && window.tradingPermissions[code]) === true;
  const newState = !currentState;
  
  console.log(`[DEBUG] toggleTradingPermission: ${code} ${currentState} -> ${newState}`);
  
  try{
    const d = await api.toggleTradingPermission(code, newState);
    
    if(d.success){
      // Обновляем локальное состояние
      if(!window.tradingPermissions) window.tradingPermissions = {};
      window.tradingPermissions[code] = newState;
      console.log(`[SUCCESS] Торговля для ${code}: ${newState ? 'разрешена' : 'запрещена'}`);
      // Обновляем UI
      updateTabsPermissionsUI();
      // 🔥 ПРИНУДИТЕЛЬНО применяем синий цвет
      setTimeout(() => forceApplyInactiveColors(), 50);
    } else {
      console.error('[ERROR] toggleTradingPermission failed:', d.error);
      alert('Ошибка: ' + (d.error || 'Не удалось изменить разрешение'));
    }
  }catch(e){
    console.error('[ERROR] toggleTradingPermission exception:', e);
    alert('Ошибка при изменении разрешения: ' + e);
  }
}

function renderCurrencyTabs(list){
  console.log('[RENDER_TABS] 🎯 renderCurrencyTabs вызвана, list:', list);
  const cont=$('currencyTabsContainer');
  if(!cont) {
    console.error('[RENDER_TABS] ❌ Элемент currencyTabsContainer НЕ НАЙДЕН!');
    return;
  }
  console.log('[RENDER_TABS] ✅ Контейнер найден:', cont);
  cont.innerHTML='';
  const arr=Array.isArray(list)?list:[];
  console.log('[RENDER_TABS] 📊 Массив валют, длина:', arr.length, 'данные:', arr);
  logDbg('renderCurrencyTabs raw len='+(arr.length));
  let norm=arr.map(c=>{if(typeof c==='string')return {code:c.toUpperCase(),symbol:''};return {code:(c.code||'').toUpperCase(),symbol:(c.symbol||'').trim()};}).filter(o=>o.code);
  console.log('[RENDER_TABS] 📋 Нормализованные валюты:', norm);
  // Если список пуст – загрузить дефолтные
  if(!norm.length){
    console.warn('[RENDER_TABS] ⚠️ Список пуст, загружаем дефолтные валюты');
    logDbg('список пуст – добавляю дефолтные');
    norm=['BTC','ETH','SOL','BNB','XRP','ADA','AVAX','DOT','MATIC','LINK'].map(c=>({code:c,symbol:''}));
    console.log('[RENDER_TABS] 📋 Дефолтные валюты загружены:', norm);
  }
  // Установить активную валюту: если текущая есть в списке - оставляем, иначе - первая из списка
  const codes=new Set(norm.map(o=>o.code));
  console.log('[DEBUG] renderCurrencyTabs: currentBaseCurrency:', currentBaseCurrency, 'currencySetByUser:', currencySetByUser, 'codes:', Array.from(codes));
  if((!currentBaseCurrency || !codes.has(currentBaseCurrency)) && !currencySetByUser){
    const oldCurrency = currentBaseCurrency;
    currentBaseCurrency=norm[0].code;
    try{ window.currentBaseCurrency = currentBaseCurrency; }catch(_){/* noop */}
    console.log('[DEBUG] renderCurrencyTabs: changed currentBaseCurrency from', oldCurrency, 'to', currentBaseCurrency);
    logDbg('установлена активная валюта: '+currentBaseCurrency);
  }
  norm.forEach(cur=>{
    console.log('[RENDER_TABS] 🔨 Создаём вкладку для валюты:', cur.code);
    const el=document.createElement('div');
    el.className='tab-item'+(cur.code===currentBaseCurrency?' active':'');
    el.dataset.code=cur.code;
    
    // Создаем кнопку включения/выключения валюты
    const permBtn = document.createElement('span');
    permBtn.className = 'perm-indicator';
    permBtn.title = 'Включить/выключить торговлю';
    permBtn.onclick = (e) => toggleTradingPermission(cur.code, e);
    
    el.innerHTML=`<span class='code-label'>${cur.code}</span>${cur.symbol?`<span class='symbol-label'>${cur.symbol}</span>`:''}`;
    el.insertBefore(permBtn, el.firstChild); // Вставляем кнопку в начало
    
    // 🔥 КРИТИЧЕСКИ ВАЖНО: Применяем синий цвет для валют с неактивным циклом СРАЗУ при создании вкладки
    const cycleActive = activeCycles[cur.code]; // Используем статус цикла
    const isCycleInactive = (cycleActive === false); // Синий ТОЛЬКО если явно false
    
    if(isCycleInactive){
      el.classList.add('inactive-currency');
      const codeLabel = el.querySelector('.code-label');
      if(codeLabel){
        const isActive = el.classList.contains('active');
        const blueColor = isActive ? '#64B5F6' : '#2196F3'; // Темно-синий для активной, ярко-синий для неактивной
        
        // Применяем синий цвет МАКСИМАЛЬНО агрессивно сразу при создании элемента
        codeLabel.style.cssText = `color: ${blueColor} !important; text-shadow: 0 0 2px rgba(33,150,243,0.5) !important;`;
        codeLabel.setAttribute('style', `color: ${blueColor} !important; text-shadow: 0 0 2px rgba(33,150,243,0.5) !important;`);
        
        console.log(`[RENDER_TAB] ${cur.code}: создана вкладка с НЕАКТИВНЫМ циклом, СИНИЙ цвет ${blueColor} (cycleActive=${cycleActive})`);
      }
    } else {
      console.log(`[RENDER_TAB] ${cur.code}: создана вкладка с АКТИВНЫМ циклом (cycleActive=${cycleActive})`);
    }
    
    el.onclick=()=>switchBaseCurrency(cur.code);
    cont.appendChild(el);
    console.log('[RENDER_TABS] ✅ Вкладка добавлена в контейнер:', cur.code);
  });
  console.log('[RENDER_TABS] 🎉 Все вкладки созданы, всего:', norm.length);
  updatePairNameUI();
  updateTabsPermissionsUI();
  // 🔥 ПРИНУДИТЕЛЬНО применяем синий цвет после создания вкладок
  setTimeout(() => forceApplyInactiveColors(), 50);
}
function updatePairNameUI(){
  const pair=`${currentBaseCurrency}_${currentQuoteCurrency}`;
  const nameEl=$('currentPairName');
  const baseSym=$('baseSymbol');
  const quoteSym=$('quoteSymbol');
  const obQuote=$('obQuoteSymbol');
  if(nameEl){ nameEl.childNodes[0].nodeValue=pair+' '; }
  if(baseSym) baseSym.textContent=currentBaseCurrency;
  if(quoteSym) quoteSym.textContent=currentQuoteCurrency;
  if(obQuote) obQuote.textContent=currentQuoteCurrency;
}

function updateTabsPermissionsUI(){
  // Обновление индикаторов разрешений на вкладках валют
  // Эта функция обновляет визуальные индикаторы (точки, иконки и т.д.) 
  // на вкладках валют в зависимости от их состояния (активные шаги, диагностика и т.д.)
  
  const cont=$('currencyTabsContainer');
  if(!cont) return;
  
  const tabs = cont.querySelectorAll('.tab-item');
  tabs.forEach(tab => {
    const code = tab.dataset.code;
    if(!code) return;
    
    // Получаем данные для этой валюты
    const activeStep = activeSteps[code];
    const decision = diagnosticDecisions[code];
    const permissionEnabled = window.tradingPermissions && window.tradingPermissions[code];
    
    // 🔍 ДИАГНОСТИКА: Логируем permission для отладки
    if(code === 'ANIME' || permissionEnabled === false || permissionEnabled === undefined){
      console.log(`[PERMISSION_DEBUG] ${code}:`, {
        permissionEnabled: permissionEnabled,
        tradingPermissions: window.tradingPermissions,
        specificValue: window.tradingPermissions ? window.tradingPermissions[code] : 'no tradingPermissions'
      });
    }
    
    // Обновляем кнопку разрешения торговли
    const permBtn = tab.querySelector('.perm-indicator');
    if(permBtn){
      permBtn.classList.toggle('on', permissionEnabled === true);
      permBtn.classList.toggle('off', permissionEnabled !== true);  // undefined/null/false = off
      permBtn.title = (permissionEnabled === true) ? 'Торговля разрешена (клик для запрета)' : 'Торговля запрещена (клик для разрешения)';
    }
    
    // Очищаем старые индикаторы шага
    const oldIndicator = tab.querySelector('.step-indicator');
    if(oldIndicator) oldIndicator.remove();
    
    // Добавляем индикатор если есть активный шаг
    if(activeStep !== undefined && activeStep >= 0){
      const indicator = document.createElement('span');
      indicator.className = 'step-indicator';
      indicator.textContent = activeStep;
      indicator.title = `Активный шаг: ${activeStep}`;
      tab.appendChild(indicator);
    }
    
    // Добавляем класс для диагностического решения
    tab.classList.remove('decision-buy', 'decision-sell', 'decision-wait');
    if(decision === 'BUY'){
      tab.classList.add('decision-buy');
    } else if(decision === 'SELL'){
      tab.classList.add('decision-sell');
    } else if(decision === 'WAIT'){
      tab.classList.add('decision-wait');
    }
    
    // === НОВАЯ ЛОГИКА: динамическое изменение цвета бордюра по цене ===
    // Удаляем старые классы готовности к продаже/покупке/отключения WS
    tab.classList.remove('ready-to-sell', 'ready-to-buy', 'ws-disconnected', 'inactive-currency');
    
    // Получаем цены для этой валюты
    const currentPrice = currentPrices[code];
    const sellPrice = sellPrices[code];
    const buyPrice = buyPrices[code];
    
    // 🔥 ИСПОЛЬЗУЕМ СТАТУС ЦИКЛА (а не разрешение торговли!)
    const cycleActive = activeCycles[code]; // true = активен, false = неактивен, undefined = нет данных
    const isCycleInactive = (cycleActive === false); // Синий ТОЛЬКО если явно false
    
    // 🔥 КРИТИЧЕСКИ ВАЖНАЯ ПРОВЕРКА: Если цена отсутствует или равна 0 → WS отключён (светло-синий бордюр)
    const hasValidPrice = currentPrice !== undefined && currentPrice !== null && currentPrice > 0;
    const hasSellPrice = sellPrice !== undefined && sellPrice !== null && sellPrice > 0;
    const hasBuyPrice = buyPrice !== undefined && buyPrice !== null && buyPrice > 0;
    
    if (!hasValidPrice || !hasSellPrice || !hasBuyPrice) {
      // ❌ Нет цены или она равна 0 → считаем, что WS отключён
      tab.classList.add('ws-disconnected');
      console.log(`[BORDER] ${code}: ws-disconnected (currentPrice=${currentPrice}, sell=${sellPrice}, buy=${buyPrice})`);
    } else {
      // ✅ Цена есть и валидна → проверяем условия покупки/продажи
      
      // Зелёный бордюр: цена выше или равна цене продажи (готов к продаже)
      if(currentPrice >= sellPrice){
        tab.classList.add('ready-to-sell');
        console.log(`[BORDER] ${code}: ready-to-sell (current=${currentPrice} >= sell=${sellPrice})`);
      }
      // Красный бордюр: цена ниже или равна цене покупки (готов к покупке/докупке)
      else if(currentPrice <= buyPrice){
        tab.classList.add('ready-to-buy');
        console.log(`[BORDER] ${code}: ready-to-buy (current=${currentPrice} <= buy=${buyPrice})`);
      }
      // Обычный бордюр: цена между покупкой и продажей
      else {
        // Убираем все цветные бордюры
        console.log(`[BORDER] ${code}: normal (buy=${buyPrice} < current=${currentPrice} < sell=${sellPrice})`);
      }
    }
    
    // Теперь применяем синий текст для неактивных циклов (не влияет на бордюр!)
    if(isCycleInactive){
      // ✅ Для валют с НЕАКТИВНЫМ циклом - красим название валюты в ярко-синий цвет
      tab.classList.add('inactive-currency');
      
      const codeLabel = tab.querySelector('.code-label');
      if(codeLabel){
        const isActive = tab.classList.contains('active');
        const blueColor = isActive ? '#64B5F6' : '#2196F3'; // Светло-синий для активной, ярко-синий для неактивной
        const shadow = isActive ? '0 0 3px rgba(66,165,245,0.6)' : '0 0 2px rgba(33,150,243,0.5)';
        
        // Множественная установка для гарантии с text-shadow
        const styleText = `color: ${blueColor} !important; text-shadow: ${shadow} !important;`;
        codeLabel.style.cssText = styleText;
        codeLabel.setAttribute('style', styleText);
      }
    } else {
      // ✅ Для валют с АКТИВНЫМ циклом убираем inline-стиль
      const codeLabel = tab.querySelector('.code-label');
      if(codeLabel && codeLabel.hasAttribute('style')){
        // Убираем inline-стиль полностью, если есть цвет или тень
        const style = codeLabel.getAttribute('style');
        if(style && (style.includes('color') || style.includes('text-shadow'))){
          codeLabel.removeAttribute('style');
        }
      }
    }
  });
  
  // 🔥 ДОПОЛНИТЕЛЬНАЯ МЕРА: Повторно применяем синий цвет через 100ms
  // на случай если какие-то стили применяются асинхронно
  setTimeout(() => {
    tabs.forEach(tab => {
      const code = tab.dataset.code;
      if(!code) return;
      const cycleActive = activeCycles[code]; // Используем статус цикла
      const isCycleInactive = (cycleActive === false); // Синий ТОЛЬКО если явно false
      if(isCycleInactive){
        const codeLabel = tab.querySelector('.code-label');
        if(codeLabel){
          const isActive = tab.classList.contains('active');
          const blueColor = isActive ? '#64B5F6' : '#2196F3'; // Светло-синий для активной, ярко-синий для неактивной
          codeLabel.style.cssText = `color: ${blueColor} !important;`;
          console.log(`[DELAYED_STYLE] ${code}: повторно установлен синий цвет через 100ms (cycleActive=${cycleActive})`);
        }
      }
    });
  }, 100);
}

async function switchBaseCurrency(code){
  const requestedCurrency = code.toUpperCase();
  
  // Если уже переключаем валюту - запоминаем последний запрос и выходим
  if (isSwitchingCurrency) {
    console.log('[SWITCH] Уже идёт переключение, запоминаем запрос:', requestedCurrency);
    pendingSwitchCurrency = requestedCurrency;
    return;
  }
  
  // Если кликнули на уже активную валюту - ничего не делаем
  if (requestedCurrency === currentBaseCurrency) {
    console.log('[SWITCH] Валюта уже активна:', requestedCurrency);
    return;
  }
  
  // Устанавливаем блокировку
  isSwitchingCurrency = true;
  const oldCurrency = currentBaseCurrency;
  currentBaseCurrency = requestedCurrency;
  
  // Находим вкладку и добавляем класс загрузки
  const cont = $('currencyTabsContainer');
  let targetTab = null;
  if(cont){
    targetTab = cont.querySelector(`.tab-item[data-code="${requestedCurrency}"]`);
    if(targetTab) {
      targetTab.classList.add('switching');
    }
  }
  
  try {
    // keep window property in sync so other modules using window.currentBaseCurrency see correct value
    try{ window.currentBaseCurrency = currentBaseCurrency; }catch(_){/* noop */}
    currencySetByUser = true; // Валюта установлена пользователем
    console.log('[SWITCH] Переключение с', oldCurrency, 'на', currentBaseCurrency);
    
    // Моментально обновляем UI (вкладки, название пары)
    if(cont){
      [...cont.querySelectorAll('.tab-item')].forEach(n=>n.classList.toggle('active',n.dataset.code===currentBaseCurrency));
    }
    updatePairNameUI();
    logDbg(`switchBaseCurrency -> ${currentBaseCurrency}_${currentQuoteCurrency}`);
    
    // Запускаем подписку БЕЗ await (не блокируем выполнение)
    subscribeToPairData(currentBaseCurrency, currentQuoteCurrency).catch(e => console.error('[SWITCH] subscribe error:', e));
    
    // Параллельно загружаем все необходимые данные СРАЗУ (не ждем подписки)
    const loadPromises = [
      loadMarketData(true).catch(e => console.error('[SWITCH] loadMarketData error:', e)),
      loadPairBalances().catch(e => console.error('[SWITCH] loadPairBalances error:', e)),
      loadPairParams(true).catch(e => console.error('[SWITCH] loadPairParams error:', e)),
      loadTradeParams().catch(e => console.error('[SWITCH] loadTradeParams error:', e)),
      loadBreakEvenTable().catch(e => console.error('[SWITCH] loadBreakEvenTable error:', e))
    ];
    
    // Обновляем прибыль сессии
    if (typeof updateSessionProfit === 'function') {
      loadPromises.push(updateSessionProfit().catch(e => console.error('[SWITCH] updateSessionProfit error:', e)));
    }
    
    // Сохранение UI state тоже делаем параллельно (не критично для отображения)
    loadPromises.push(UIStateManager.savePartial({active_base_currency: currentBaseCurrency}).catch(e => console.error('[SWITCH] UIState save error:', e)));
    
    // Ждём завершения всех загрузок параллельно (быстрее чем по очереди)
    await Promise.all(loadPromises);
    
    console.log('[SWITCH] ✅ Переключение завершено:', currentBaseCurrency);
  } catch (error) {
    console.error('[SWITCH] ❌ Ошибка при переключении валюты:', error);
  } finally {
    // Убираем класс загрузки
    if(targetTab) {
      targetTab.classList.remove('switching');
    }
    
    // Снимаем блокировку
    isSwitchingCurrency = false;
    
    // Если во время переключения был запрос на другую валюту - выполняем его
    if (pendingSwitchCurrency && pendingSwitchCurrency !== currentBaseCurrency) {
      const nextCurrency = pendingSwitchCurrency;
      pendingSwitchCurrency = null;
      console.log('[SWITCH] Выполняем отложенный запрос на:', nextCurrency);
      setTimeout(() => switchBaseCurrency(nextCurrency), 0);
    } else {
      pendingSwitchCurrency = null;
    }
  }
}
async function changeQuoteCurrency(){
  const sel=document.querySelector('#quoteCurrency');
  if(!sel) return;
  currentQuoteCurrency=sel.value.toUpperCase();
  try{ window.currentQuoteCurrency = currentQuoteCurrency; }catch(_){/* noop */}
  updatePairNameUI();
  logDbg(`changeQuoteCurrency -> ${currentBaseCurrency}_${currentQuoteCurrency}`);
  
  // Запускаем подписку БЕЗ await (не блокируем)
  subscribeToPairData(currentBaseCurrency,currentQuoteCurrency).catch(e => console.error('[QUOTE] subscribe error:', e));
  
  // Параллельная загрузка всех данных
  await Promise.all([
    loadMarketData(true).catch(e => console.error('[QUOTE] loadMarketData error:', e)),
    loadPairBalances().catch(e => console.error('[QUOTE] loadPairBalances error:', e)),
    loadPairParams(true).catch(e => console.error('[QUOTE] loadPairParams error:', e)),
    loadTradeParams().catch(e => console.error('[QUOTE] loadTradeParams error:', e)),
    loadBreakEvenTable().catch(e => console.error('[QUOTE] loadBreakEvenTable error:', e))
  ]);
}
// Функция для нового селектора котируемой валюты в заголовке "Рынок и стакан"
async function switchQuoteCurrency(newQuote){
  if(!newQuote) return;
  currentQuoteCurrency=newQuote.toUpperCase();
  try{ window.currentQuoteCurrency = currentQuoteCurrency; }catch(_){/* noop */}
  
  // Синхронизируем оба селектора, если старый существует
  const oldSel=document.querySelector('#quoteCurrency');
  if(oldSel && oldSel.value!==currentQuoteCurrency){
    oldSel.value=currentQuoteCurrency;
  }
  
  updatePairNameUI();
  logDbg(`switchQuoteCurrency -> ${currentBaseCurrency}_${currentQuoteCurrency}`);
  
  // Запускаем подписку БЕЗ await (не блокируем)
  subscribeToPairData(currentBaseCurrency,currentQuoteCurrency).catch(e => console.error('[QUOTE] subscribe error:', e));
  
  // Параллельная загрузка всех данных
  await Promise.all([
    loadMarketData(true).catch(e => console.error('[QUOTE] loadMarketData error:', e)),
    loadPairBalances().catch(e => console.error('[QUOTE] loadPairBalances error:', e)),
    loadPairParams(true).catch(e => console.error('[QUOTE] loadPairParams error:', e)),
    loadTradeParams().catch(e => console.error('[QUOTE] loadTradeParams error:', e)),
    loadBreakEvenTable().catch(e => console.error('[QUOTE] loadBreakEvenTable error:', e))
  ]);
}

async function loadPairParams(force){
  try{
    // Сначала попытка получить подробную инфу по паре (/api/pair/info)
    let info = null;
    try{
      const r=await fetch(`/api/pair/info?base_currency=${currentBaseCurrency}&quote_currency=${currentQuoteCurrency}${force?'&force=1':''}`);
      const d=await r.json();
      if(d && d.success && d.data){
        info = d.data;
      }
    }catch(e){ logDbg('loadPairParams info fetch err '+e); }

    // Если данных по паре нет — делаем fallback к /api/pair/data (используем ticker/orderbook для вычислений)
    if(!info){
      try{
        const r2 = await fetch(`/api/pair/data?base_currency=${currentBaseCurrency}&quote_currency=${currentQuoteCurrency}${force?'&force=1':''}`);
        const d2 = await r2.json();
        const market = d2 && d2.data ? d2.data : null;
        info = {
          min_quote_amount: null,
          min_base_amount: null,
          amount_precision: null,
          price_precision: null
        };

        // Попробуем вычислить price_precision по текущей цене
        const last = market && market.ticker && market.ticker.last ? parseFloat(market.ticker.last) : null;
        if(last && isFinite(last)){
          // использовать ту же логику, что и в loadMarketData
          let pp = 5;
          if(last >= 10) pp = 2;
          else if(last >= 1) pp = 3;
          else if(last >= 0.1) pp = 4;
          info.price_precision = pp;
        }

        // Для amount_precision посмотрим на первый элемент стакана (asks/bids) и посчитаем дробную длину
        const sampleAmount = (market && market.orderbook && Array.isArray(market.orderbook.asks) && market.orderbook.asks[0] && market.orderbook.asks[0][1])
          || (market && market.orderbook && Array.isArray(market.orderbook.bids) && market.orderbook.bids[0] && market.orderbook.bids[0][1]);
        if(sampleAmount){
          const s = String(sampleAmount);
          if(s.indexOf('.')>=0){
            info.amount_precision = s.split('.')[1].length;
          } else info.amount_precision = 0;
        }

        // If still empty, pick reasonable defaults
        if(info.amount_precision==null) info.amount_precision = 8;
        if(info.price_precision==null) info.price_precision = 2;
      }catch(e){ logDbg('loadPairParams data fallback err '+e); }
    }

    // Применяем info (если есть)
    if(info){
      if($('minQuoteAmount')) $('minQuoteAmount').textContent=info.min_quote_amount!=null?String(info.min_quote_amount):'-';
      if($('minBaseAmount')) $('minBaseAmount').textContent=info.min_base_amount!=null?String(info.min_base_amount):'-';
      if($('amountPrecision')) $('amountPrecision').textContent=info.amount_precision!=null?String(info.amount_precision):'-';
      if($('pricePrecision')) $('pricePrecision').textContent=info.price_precision!=null?String(info.price_precision):'-';

      // Сохраняем точность цены для использования в таблице безубыточности
      if(info.price_precision!=null){
        currentPairPricePrecision = parseInt(info.price_precision);
        console.log(`[PAIR_PARAMS] Price Precision для ${currentBaseCurrency}_${currentQuoteCurrency}: ${currentPairPricePrecision}`);
      }
    }
  }catch(e){ logDbg('loadPairParams exc '+e) }
}

// Функция для обновления WebSocket статуса вкладки валюты
function updateCurrencyTabWSStatus(currency, isConnected) {
  if (!currency) return;
  const cont = document.getElementById('currencyTabsContainer');
  if (!cont) return;
  const tab = cont.querySelector(`.tab-item[data-code="${currency.toUpperCase()}"]`);
  if (!tab) return;
  
  if (isConnected) {
    tab.classList.remove('ws-disconnected');
  } else {
    tab.classList.add('ws-disconnected');
  }
}

async function subscribeToPairData(base,quote){
  try{
    logDbg(`subscribeToPairData ${base}_${quote}`);
    setNetworkConnectionState('pending');
    const wsStatus=$('wsStatus');
    if(wsStatus){ wsStatus.textContent='🔄 Подключение...'; wsStatus.style.color='#ffa500'; }
    // Добавляем класс ws-disconnected к вкладке валюты
    updateCurrencyTabWSStatus(base, false);
    const data = await api.subscribeToPair(base, quote);
    if(data.success){
      if(wsStatus){ wsStatus.textContent='✅ WebSocket подключен'; wsStatus.style.color='#4caf50'; }
      // Убираем класс ws-disconnected при успешном подключении
      updateCurrencyTabWSStatus(base, true);
      setNetworkConnectionState('connected');
      setTimeout(()=>{
        try{
          loadMarketData();
          loadPairBalances();
          loadPairParams(true);
        }catch(e){ logDbg('post-subscribe load err '+e); }
      },800);
    }else{
      logDbg('subscribe error '+data.error);
      if(wsStatus){ wsStatus.textContent='❌ Ошибка подключения'; wsStatus.style.color='#f44336'; }
      updateCurrencyTabWSStatus(base, false);
      setNetworkConnectionState('error');
    }
  }catch(e){
    logDbg('subscribe exception '+e);
    const wsStatus=$('wsStatus');
    if(wsStatus){ wsStatus.textContent='❌ Ошибка подключения'; wsStatus.style.color='#f44336'; }
    updateCurrencyTabWSStatus(base || currentBaseCurrency, false);
    setNetworkConnectionState('error');
  }
}
async function loadMarketData(forceRefresh=false){
  try{
    const forceParam = forceRefresh ? '&force=1' : '';
    const r=await fetch(`/api/pair/data?base_currency=${currentBaseCurrency}&quote_currency=${currentQuoteCurrency}${forceParam}`);
    const d=await r.json();
    if(!d.success){ logDbg('loadMarketData fail '+(d.error||'')); return; }
    // Данные всегда в d.data
    const ob=d.data?.orderbook;
    const ticker=d.data?.ticker;
    if(ob && ob.asks && ob.bids) { 
      updateOrderBook(ob); 
      logDbg(`orderbook updated: ${ob.asks.length} asks, ${ob.bids.length} bids`);
    } else {
      logDbg('orderbook missing or empty');
    }
    if(ticker){
      const last=parseFloat(ticker.last||ticker.last_price||ticker.close||ticker.price||0);
      
      // Определяем точность автоматически из цены
      if(last > 0){
        if(last >= 10) currentPricePrecision = 2;
        else if(last >= 1) currentPricePrecision = 3;
        else if(last >= 0.1) currentPricePrecision = 4;
        else currentPricePrecision = 5;
      }
      
      const priceStr=formatPrice(last, currentPricePrecision);
      const cp=$('currentPrice'); if(cp) cp.textContent=priceStr;
      // Цена в заголовке "Рынок и стакан" с точностью 2 знака после запятой
      const pp=$('currentPairPrice'); 
      if(pp) pp.textContent='$'+(isNaN(last) ? '0.00' : last.toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2}));
      const sell=parseFloat(ticker.lowest_ask||ticker.ask||0);
      const bid=parseFloat(ticker.highest_bid||ticker.bid||0);
      const spread=(isFinite(sell)&&isFinite(bid)&&sell>0)?((sell-bid)/sell*100):null;
      const sv=$('spreadValue'); if(sv) sv.textContent=spread==null?'-':spread.toFixed(3)+'%';
      // Обновляем только цену, не трогая autotrade_levels
      const priceEl=$('indPrice');
      if(priceEl) priceEl.textContent=formatPrice(last, currentPricePrecision);
    }
    loadPerBaseIndicators();
  }catch(e){ logDbg('loadMarketData exc '+e) }
}



// Редактирование баланса котируемой валюты (только в тестовом режиме)
async function editQuoteBalance(){
  alert('Редактирование баланса отключено. Используются только данные из API Gate.io');
}

// Загрузка тестового баланса с сервера (только для test режима)
async function loadTestBalance(){ return null; }

// Обновление отображения баланса в заголовке
function updateHeaderQuoteBalance(balance){
  const balanceEl=$('headerQuoteBalance');
  console.log('[BALANCE] updateHeaderQuoteBalance called, balance=', balance, 'element=', balanceEl);
  if(balanceEl){
    const bal=parseFloat(balance)||0;
    balanceEl.textContent=bal.toFixed(2);
    console.log('[BALANCE] headerQuoteBalance updated to:', bal.toFixed(2));
    
    // В тестовом режиме делаем баланс кликабельным
    if(currentNetworkMode==='test'){
      balanceEl.style.cursor='pointer';
      balanceEl.title='🖱️ Клик для редактирования (ТЕСТОВЫЙ режим)';
    }else{
      balanceEl.style.cursor='default';
      balanceEl.title='Баланс котируемой валюты из API';
    }
  } else {
    console.error('[BALANCE] ❌ Element headerQuoteBalance NOT FOUND in DOM!');
  }
}

async function loadPerBaseIndicators(){
  try{
    const r=await fetch(`/api/trade/indicators?base_currency=${currentBaseCurrency}&quote_currency=${currentQuoteCurrency}`);
    const d=await r.json();
    console.log('[INDICATORS] Ответ сервера:', d);
    console.log('[INDICATORS] autotrade_levels:', d.autotrade_levels);
    if(d.success&&d.indicators){ 
      // Передаём autotrade_levels вместе с indicators
      d.indicators.autotrade_levels = d.autotrade_levels;
      console.log('[INDICATORS] Передаём в updateTradeIndicators:', d.indicators);
      updateTradeIndicators(d.indicators); 
    }
  }catch(e){ logDbg('loadPerBaseIndicators err '+e) }
}

// Функция для загрузки индикаторов для всех валют
async function loadAllIndicators(){
  if(!Array.isArray(currenciesList) || currenciesList.length===0) return;
  console.log('[INDICATORS] Загружаем индикаторы для всех валют...');
  for(const cur of currenciesList){
       const code = typeof cur==='string' ? cur : cur.code;
    if(code){
      try{
        const r=await fetch(`/api/trade/indicators?base_currency=${code}&quote_currency=${currentQuoteCurrency}`);
        const d=await r.json();
        if(d.success&&d.autotrade_levels){
          // Сохраняем данные для каждой валюты
          activeSteps[code] = d.autotrade_levels.active_step;
          diagnosticDecisions[code] = d.autotrade_levels.diagnostic_decision;
          sellPrices[code] = d.autotrade_levels.sell_price;
          buyPrices[code] = d.autotrade_levels.next_buy_price;
          currentPrices[code] = d.autotrade_levels.current_price;
          activeCycles[code] = d.autotrade_levels.active_cycle; // 🔥 СОХРАНЯЕМ СТАТУС ЦИКЛА ДЛЯ КАЖДОЙ ВАЛЮТЫ
          console.log(`[INDICATORS] Загружены данные для ${code}: step=${d.autotrade_levels.active_step}, decision=${d.autotrade_levels.diagnostic_decision}, cycle=${d.autotrade_levels.active_cycle}`);
        }
      }catch(e){
        console.log(`[INDICATORS] Ошибка загрузки для ${code}:`, e);
      }
    }
  }
  // Обновляем UI после загрузки всех данных
  updateTabsPermissionsUI();
  // 🔥 ПРИНУДИТЕЛЬНО применяем цвета после загрузки всех индикаторов
  setTimeout(() => forceApplyInactiveColors(), 100);
  console.log('[INDICATORS] Загрузка индикаторов для всех валют завершена');
  console.log('[INDICATORS] Статус циклов:', activeCycles);
}
async function loadPairBalances(){
  if(!currentBaseCurrency||!currentQuoteCurrency) return;
  try{
    const r=await fetch(`/api/pair/balances?base_currency=${currentBaseCurrency}&quote_currency=${currentQuoteCurrency}`);
    const d=await r.json();
    if(d.success){
      const baseBalEl=document.getElementById('baseBalance');
      const baseUsdEl=document.getElementById('baseBalanceUSD');
      const quoteBalEl=document.getElementById('quoteBalance');
      const quoteSymEl=document.getElementById('quoteSymbol');
      const inlineEl=document.getElementById('quoteBalanceInline');
      
      let baseAvail = parseFloat(d.balances?.base?.available||'0');
      let quoteAvail = parseFloat(d.balances?.quote?.available||'0');
      const baseEq=d.base_equivalent||0;
      
      // Обновляем элементы балансов
      if(baseBalEl) baseBalEl.textContent=(isFinite(baseAvail)?baseAvail:0).toFixed(8);
      if(baseUsdEl) baseUsdEl.textContent=`≈ $${(isFinite(baseEq)?baseEq:0).toFixed(2)}`;
      if(quoteBalEl) quoteBalEl.textContent=(isFinite(quoteAvail)?quoteAvail:0).toFixed(8);
      if(quoteSymEl) quoteSymEl.textContent=currentQuoteCurrency;
      if(inlineEl) inlineEl.textContent=`Баланс: ${(isFinite(baseAvail)?baseAvail:0).toFixed(8)} ${currentBaseCurrency} ≈ $${(isFinite(baseEq)?baseEq:0).toFixed(2)}`;
      updateHeaderQuoteBalance(quoteAvail);
      
      logDbg(`loadPairBalances: base=${baseAvail} ${currentBaseCurrency}, quote=${quoteAvail} ${currentQuoteCurrency}`);
    }
  }catch(e){ logDbg('loadPairBalances err '+e) }
}
function renderBreakEvenTable(tableData){
  const body=$('breakEvenBody');
  
  if(!body){
    console.error('[BREAKEVEN] Элемент breakEvenBody не найден в DOM');
    return;
  }
  
  body.innerHTML='';
  
  if(!Array.isArray(tableData)||tableData.length===0){
    body.innerHTML=`<tr><td colspan="10" style='padding:12px;text-align:center;color:#999;'>Нет данных</td></tr>`;
    return;
  }
  
  // 🔍 ОТЛАДКА: Проверяем наличие ключевых полей
  console.log('[BREAKEVEN RENDER] Данные получены, строк:', tableData.length);
  if (tableData.length > 0) {
    const row0 = tableData[0];
    console.log('[BREAKEVEN RENDER] Первая строка:', row0);
    console.log('[BREAKEVEN RENDER] total_invested:', row0.total_invested !== undefined ? '✅ ЕСТЬ' : '❌ НЕТ', row0.total_invested);
    console.log('[BREAKEVEN RENDER] breakeven_pct:', row0.breakeven_pct !== undefined ? '✅ ЕСТЬ' : '❌ НЕТ', row0.breakeven_pct);
  }
  
  // Получаем текущее значение параметра "Стакан"
  const orderbookLevel = parseFloat($('paramOrderbookLevel')?.value) || 1;
  
  tableData.forEach((row,idx)=>{
    const tr=document.createElement('tr');
    const stepNum = row.step !== undefined ? row.step : idx;
    
    // Выделяем активный шаг ярким цветом, иначе чередуем строки
    const isActiveStep = globalActiveStep !== null && stepNum === globalActiveStep;
    if(isActiveStep){
      tr.style.background = '#2a4a2a'; // Яркий зелёный для активного шага
      tr.style.borderLeft = '4px solid #4CAF50';
      tr.style.fontWeight = '600';
    } else {
      tr.style.background = idx===0 ? '#1f2f1f' : (idx%2===0?'#1a1a1a':'transparent');
    }
    tr.style.borderBottom = '1px solid #2a2a2a';
    
    // Динамическая точность для курсов: Price Precision + 1
    const pricePrecisionPlus1 = currentPairPricePrecision + 1;
    
    // Уровень стакана берём НАПРЯМУЮ из данных таблицы (без пересчёта!)
    // Значение соответствует индексу массива: 0 = bids[0], 1 = bids[1], и т.д.
    const orderbookLevelForStep = row.orderbook_level !== undefined ? row.orderbook_level : 0;
    
    // DEBUG: Выводим для первых 3 шагов
    if (stepNum <= 2) {
      console.log(`[TABLE_ROW] Шаг ${stepNum}: orderbook_level из данных = ${row.orderbook_level}, отображаем = ${orderbookLevelForStep}`);
    }
    
    // ↓, % - накопленная сумма процентов снижения
    const cumulativeDecrease = row.cumulative_decrease_pct !== undefined ? row.cumulative_decrease_pct.toFixed(3) : '—';
    // ↓Δ,% - шаг процента снижения
    const decreaseStep = row.decrease_step_pct !== undefined ? row.decrease_step_pct.toFixed(3) : '—';
    
    const rate = row.rate !== undefined ? row.rate.toFixed(pricePrecisionPlus1) : '—';
    const purchase = row.purchase_usd !== undefined ? row.purchase_usd.toFixed(2) : '—';
    const totalInv = row.total_invested !== undefined ? row.total_invested.toFixed(2) : '—';
    const breakEvenPrice = row.breakeven_price !== undefined ? row.breakeven_price.toFixed(pricePrecisionPlus1) : '—';
    const breakEvenPct = row.breakeven_pct !== undefined ? row.breakeven_pct.toFixed(2) : '—';
    const targetDelta = row.target_delta_pct !== undefined ? row.target_delta_pct.toFixed(2) : '—';
    
    // Цвета для процентов
    const cumulativeColor = row.cumulative_decrease_pct < 0 ? '#f44336' : '#999';
    const decreaseColor = row.decrease_step_pct < 0 ? '#ff6b6b' : '#999';
    const breakEvenColor = row.breakeven_pct > 0 ? '#4CAF50' : '#999';
    const targetColor = row.target_delta_pct > 0 ? '#4CAF50' : (row.target_delta_pct < 0 ? '#f44336' : '#999');
    
    tr.innerHTML = `
      <td style='padding:6px 8px;text-align:center;color:#e0e0e0;font-weight:600;'>${stepNum}</td>
      <td style='padding:6px 8px;text-align:center;color:#9C27B0;font-weight:600;' title='Уровень стакана (для пользователя): ${orderbookLevelForStep} → код использует массив[${orderbookLevelForStep - 1}]'>${orderbookLevelForStep}</td>
      <td style='padding:6px 8px;text-align:right;color:${cumulativeColor};font-weight:600;' title='Накопленная сумма процентов снижения'>${cumulativeDecrease}</td>
      <td style='padding:6px 8px;text-align:right;color:${decreaseColor};' title='Шаг процента: -((${stepNum} × Rk) + R)'>${decreaseStep}</td>
      <td style='padding:6px 8px;text-align:right;color:#e0e0e0;font-family:monospace;'>${rate}</td>
      <td style='padding:6px 8px;text-align:right;color:#4CAF50;'>${purchase}</td>
      <td style='padding:6px 8px;text-align:right;color:#2196F3;font-weight:600;'>${totalInv}</td>
      <td style='padding:6px 8px;text-align:right;color:#FF9800;font-family:monospace;'>${breakEvenPrice}</td>
      <td style='padding:6px 8px;text-align:right;color:${breakEvenColor};'>${breakEvenPct}</td>
      <td style='padding:6px 8px;text-align:right;color:${targetColor};font-weight:600;'>${targetDelta}</td>
    `;
    body.appendChild(tr);
  });
}
async function loadBreakEvenTable(){
  try{
    // Проверяем, что базовая валюта установлена
    if(!currentBaseCurrency){
      console.warn('[BREAKEVEN] Базовая валюта не установлена, устанавливаем WLD');
      currentBaseCurrency = 'WLD'; // Принудительная установка дефолтной валюты
    }
    
    // 🔴 КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Сначала проверяем, есть ли активный цикл с таблицей
    // Если цикл активен - используем СОХРАНЁННУЮ таблицу из /api/trade/indicators
    // Это предотвращает пересчёт таблицы с текущей ценой!
    try {
      // ✅ ИСПРАВЛЕНИЕ: Передаём include_table=1 для получения таблицы
      const indicatorsResp = await fetch(`/api/trade/indicators?base_currency=${currentBaseCurrency}&quote_currency=${currentQuoteCurrency}&include_table=1`);
      const indicatorsData = await indicatorsResp.json();
      
      // ✅ ИСПРАВЛЕНИЕ: Правильный путь к данным - autotrade_levels, а не indicators.cycle
      if (indicatorsData.success && indicatorsData.autotrade_levels) {
        const levels = indicatorsData.autotrade_levels;
        
        if (levels.active_cycle && levels.table && levels.table.length > 0) {
          // ✅ Цикл активен и таблица есть - используем её!
          console.log(`[BREAKEVEN] ✅ Используем сохранённую таблицу цикла (${levels.table.length} шагов, P0=${levels.table[0].rate}, start_price=${levels.start_price})`);
          
          // � МИГРАЦИЯ: Если в старой таблице нет orderbook_level - добавляем на лету!
          const needsMigration = levels.table[0] && levels.table[0].orderbook_level === undefined;
          if (needsMigration) {
            console.log(`[BREAKEVEN] 🔧 МИГРАЦИЯ: Добавляем orderbook_level в старую таблицу`);
            const orderbookLevelParam = parseFloat($('paramOrderbookLevel')?.value) || 0;
            levels.table.forEach((row, idx) => {
              row.orderbook_level = Math.round((idx * orderbookLevelParam) + 1);
            });
            console.log(`[BREAKEVEN] ✅ Миграция завершена: добавлено поле orderbook_level`);
          }
          
          // �🔴 КРИТИЧЕСКИ ВАЖНО: Обновляем поле start_price в форме!
          // Это гарантирует, что пользователь видит актуальный P0 для активного цикла
          const startPriceField = $('paramStartPrice');
          if (startPriceField && levels.start_price) {
            startPriceField.value = levels.start_price;
            console.log(`[BREAKEVEN] 📝 Поле start_price обновлено: ${levels.start_price}`);
          }
          
          renderBreakEvenTable(levels.table);
          return; // Выходим, не делаем пересчёт!
        } else {
          console.log(`[BREAKEVEN] Цикл неактивен (active=${levels.active_cycle}) или таблица отсутствует (table=${levels.table ? levels.table.length : 'null'})`);
        }
      }
    } catch (e) {
      console.warn('[BREAKEVEN] Не удалось проверить indicators:', e);
      // Продолжаем выполнение - попробуем пересчитать таблицу
    }
    
    // Если дошли сюда - цикл НЕ активен или таблица отсутствует
    // Пересчитываем таблицу с текущими параметрами
    console.log('[BREAKEVEN] Цикл неактивен или таблица отсутствует - пересчитываем с текущими параметрами');
    
    // Читаем текущие значения из полей формы (для мгновенного предпросмотра)
    const currentParams = {
      steps: parseInt($('paramSteps')?.value) || 16,
      start_volume: parseFloat($('paramStartVolume')?.value) || 3,
      start_price: parseFloat($('paramStartPrice')?.value) || 0,
      pprof: parseFloat($('paramPprof')?.value) || 0.6,
      kprof: parseFloat($('paramKprof')?.value) || 0.02,
      target_r: parseFloat($('paramTargetR')?.value) || 3.65,
      rk: parseFloat($('paramRk')?.value) || 0.0,
      geom_multiplier: parseFloat($('paramGeomMultiplier')?.value) || 2,
      rebuy_mode: $('paramRebuyMode')?.value || 'geometric',
      orderbook_level: parseFloat($('paramOrderbookLevel')?.value) || 1
    };
    
    // 🔍 ОТЛАДКА: Выводим прочитанные параметры
    console.log('[BREAKEVEN] 📊 Параметры из формы:', currentParams);
    console.log('[BREAKEVEN] 🔢 geom_multiplier:', currentParams.geom_multiplier);
    
    // Формируем URL с параметрами из формы
    const params = new URLSearchParams({
      base_currency: currentBaseCurrency,
      steps: currentParams.steps,
      start_volume: currentParams.start_volume,
      // start_price НЕ передаём, чтобы API использовал сохранённое значение из state_manager
      // это позволяет корректно отображать P0 после стартовой покупки
      pprof: currentParams.pprof,
      kprof: currentParams.kprof,
      target_r: currentParams.target_r,
      rk: currentParams.rk,
      geom_multiplier: currentParams.geom_multiplier,
      rebuy_mode: currentParams.rebuy_mode,
      orderbook_level: currentParams.orderbook_level
    });
    
    const url = `/api/breakeven/table?${params.toString()}`;
    
    // 🔍 ОТЛАДКА: Выводим финальный URL запроса
    console.log('[BREAKEVEN] 🌐 URL запроса:', url);
    
    const r = await fetch(url);
    const d = await r.json();
    
    // 🔍 ОТЛАДКА: Выводим ответ от сервера
    console.log('[BREAKEVEN] 📥 Ответ от сервера:', d);
    if(d.params) {
      console.log('[BREAKEVEN] 📋 Параметры из ответа:', d.params);
      console.log('[BREAKEVEN] 🔢 geom_multiplier из ответа:', d.params.geom_multiplier);
    }
    if(d.table && d.table.length > 0) {
      console.log('[BREAKEVEN] 📊 Первая строка таблицы:', d.table[0]);
      console.log('[BREAKEVEN] 📊 Вторая строка таблицы:', d.table[1]);
    }
    
    if(d.success && d.table){
      renderBreakEvenTable(d.table);
    }else{
      console.error('[BREAKEVEN] Ошибка:', d.error);
      logDbg('loadBreakEvenTable fail '+(d.error||''));
      renderBreakEvenTable([]);
    }
  }catch(e){ 
    console.error('[BREAKEVEN] Исключение:', e);
    logDbg('loadBreakEvenTable err '+e);
    renderBreakEvenTable([]);
  }
}

// Функции для работы с параметрами торговли
async function loadTradeParams(){
  try{
    // Загружаем параметры для текущей валюты (per-currency)
    const url = currentBaseCurrency 
      ? `/api/trade/params?base_currency=${currentBaseCurrency}` 
      : '/api/trade/params';
    
    console.log('[PARAMS] Загрузка параметров для:', currentBaseCurrency || 'DEFAULT', 'URL:', url);
    
    const r=await fetch(url);
    const d=await r.json();
    
    console.log('[PARAMS] Ответ получен:', d);
    
    if(d.success && d.params){
      console.log('[PARAMS] Заполнение полей формы...');
      const fields = {
        'paramSteps': d.params.steps || 16,
        'paramStartVolume': d.params.start_volume || 3,
        'paramStartPrice': d.params.start_price || 0,
        'paramPprof': d.params.pprof || 0.6,
        'paramKprof': d.params.kprof || 0.02,
        'paramTargetR': d.params.target_r || 3.65,
        'paramRk': d.params.rk || 0.0,
        'paramGeomMultiplier': d.params.geom_multiplier || 2,
        'paramRebuyMode': d.params.rebuy_mode || 'geometric',
        'paramKeep': d.params.keep || 0,
        'paramOrderbookLevel': d.params.orderbook_level || 1
      };
      
      for(const [id, value] of Object.entries(fields)){
        const el = $(id);
        if(el){
          el.value = value;
          console.log(`[PARAMS] ${id} = ${value}`);
        } else {
          console.warn(`[PARAMS] Элемент ${id} не найден!`);
        }
      }
      console.log('[PARAMS] Параметры успешно загружены');
    } else {
      console.warn('[PARAMS] Параметры отсутствуют в ответе');
    }
  }catch(e){ 
    console.error('[PARAMS] Ошибка загрузки:', e);
    logDbg('loadTradeParams err '+e);
  }
}

async function saveTradeParams(){
  const statusEl = $('paramsSaveStatus');
  try{
    const params = {
      base_currency: currentBaseCurrency, // Добавляем текущую валюту
      steps: parseInt($('paramSteps').value) || 16,
      start_volume: parseFloat($('paramStartVolume').value) || 3,
      start_price: parseFloat($('paramStartPrice').value) || 0,
      pprof: parseFloat($('paramPprof').value) || 0.6,
      kprof: parseFloat($('paramKprof').value) || 0.02,
      target_r: parseFloat($('paramTargetR').value) || 3.65,
      rk: parseFloat($('paramRk').value) || 0.0,
      geom_multiplier: parseFloat($('paramGeomMultiplier').value) || 2,
      rebuy_mode: $('paramRebuyMode').value || 'geometric',
      keep: parseFloat($('paramKeep').value) || 0,
      orderbook_level: parseFloat($('paramOrderbookLevel').value) || 1
    };
    
    statusEl.textContent = 'Сохранение...';
    statusEl.className = 'params-save-status';
    
    const d = await api.saveTradeParams(params);
    
    if(d.success){
      statusEl.textContent = '✓ Сохранено';
      statusEl.className = 'params-save-status';
      setTimeout(()=>{ statusEl.textContent = ''; }, 1500);
      
      // Сохраняем также в UI state для восстановления после перезагрузки
      await UIStateManager.savePartial({
        breakeven_params: {
          currency: currentBaseCurrency,
          ...params
        }
      });
      
      // Перезагружаем таблицу break-even после сохранения параметров
      await loadBreakEvenTable();
    }else{
      statusEl.textContent = '✗ ' + (d.error || 'Ошибка');
      statusEl.className = 'params-save-status error';
      console.error('[PARAMS] Ошибка сохранения:', d.error);
    }
  }catch(e){ 
    statusEl.textContent = '✗ ' + e.message;
    statusEl.className = 'params-save-status error';
    console.error('[PARAMS] Исключение:', e);
    logDbg('saveTradeParams err '+e);
  }
}

// Новая функция для переключения режима с явным указанием
async function switchNetworkMode(targetMode){
  if(!targetMode || !['work','test'].includes(targetMode)) return;
  if(currentNetworkMode === targetMode) return; // уже в этом режиме
  
  console.log('========================================');
  console.log('[NETWORK] Переключение на режим:', targetMode);
 
  
  try{
    const data = await api.setNetworkMode(targetMode);
    logDbg('network POST resp '+JSON.stringify(data));
    
    if(data.success){
      currentNetworkMode=data.mode;
      
      // Выводим подробную информацию о подключении
      console.log('[NETWORK] ✓ Режим переключен:', data.mode);
      if(data.api_host) console.log('[NETWORK]   API Host:', data.api_host);
      if(data.api_key) console.log('[NETWORK]   API Key:', data.api_key);
      if(data.keys_loaded !== undefined) {
        console.log('[NETWORK]   Ключи загружены:', data.keys_loaded ? 'ДА' : 'НЕТ');
      }
      console.log('========================================');
      
      updateNetworkUI();
      
      // Сохраняем состояние в UI state
      await UIStateManager.savePartial({networkMode: data.mode});
      
      setNetworkConnectionState('pending');
      await loadCurrenciesFromServer();
      // Подписываемся на ВСЕ валюты при переключении режима
      await subscribeToAllCurrencies();
      
      // Даём время на подписку и подключение WebSocket
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      // Принудительно обновляем все данные с сервера
      console.log('[NETWORK] Обновление данных после переключения режима...');
      await loadMarketData(true);  // force=true
      await loadPairBalances();
      await loadPairParams(true);
      await loadBreakEvenTable();
      
      setNetworkConnectionState('ok');
      console.log('[NETWORK] Переключение завершено успешно ✅');
    }else{
      console.error('[NETWORK] ❌ Ошибка переключения:', data.error || 'неизвестная ошибка');
      console.log('========================================');
      logDbg('network switch fail '+(data.error||''));
      setNetworkConnectionState('error');
    }
  }catch(e){
    console.error('[NETWORK] ❌ Исключение при переключении:', e);
    console.log('========================================');
    logDbg('switchNetworkMode exception '+e);
    setNetworkConnectionState('error');
  }
}

// Старая функция для совместимости (toggle между work/test)
async function toggleNetworkMode(){
  const next=currentNetworkMode==='work'?'test':'work';
  await switchNetworkMode(next);
}

// === Trading mode switcher (normal/copy) ===
let currentTradingMode = 'normal';

async function switchTradingMode(targetMode){
  if(!targetMode || !['normal','copy'].includes(targetMode)) return;
  if(currentTradingMode === targetMode) {
    console.log('[TRADE MODE] Уже в режиме:', targetMode);
    return; // уже в этом режиме
  }
  
  console.log('[TRADE MODE] Переключение:', currentTradingMode, '->', targetMode);
  logDbg('switchTradingMode -> '+targetMode);
  try{
    // Преобразуем 'normal' -> 'trade' для API
    const apiMode = targetMode === 'normal' ? 'trade' : targetMode;
    console.log('[TRADE MODE] Отправка на сервер:', apiMode);
    const data = await api.setTradingMode(apiMode);
    console.log('[TRADE MODE] Ответ сервера:', data);
    logDbg('trading mode POST resp '+JSON.stringify(data));
    if(data.success){
      // Преобразуем 'trade' -> 'normal' для UI
      currentTradingMode = data.mode === 'trade' ? 'normal' : data.mode;
      console.log('[TRADE MODE] Установлен новый режим (нормализованный):', currentTradingMode);
      updateTradingModeUI();
      // Сохраняем состояние в UI state
      await UIStateManager.savePartial({tradingMode: data.mode});
    }else{
      console.error('[TRADE MODE] Ошибка переключения:', data.error);
      logDbg('trading mode switch fail '+(data.error||''));
    }
  }catch(e){
    console.error('[TRADE MODE] Исключение:', e);
    logDbg('switchTradingMode exception '+e);
  }
}

function updateTradingModeUI(){
  const sw=$('tradingModeSwitcher');
  if(!sw) return;
  
  // Обновляем активность кнопок
  const normalBtn = sw.querySelector('[data-mode="normal"]');
  const copyBtn = sw.querySelector('[data-mode="copy"]');
  if(normalBtn && copyBtn){
    // Явно удаляем класс active у обеих кнопок
    normalBtn.classList.remove('active');
    copyBtn.classList.remove('active');
    
    // Добавляем класс active только активной кнопке
    if(currentTradingMode==='normal' || currentTradingMode==='trade'){
      normalBtn.classList.add('active');
    }else if(currentTradingMode==='copy'){
      copyBtn.classList.add('active');
    }
    
    logDbg('Trading mode UI updated: ' + currentTradingMode);
  }
}
async function loadTradingMode(){
  try{
    const d = await api.getTradingMode();
    console.log('[TRADE MODE] Загружен режим с сервера:', d);
    if(d.mode){
      // Преобразуем 'trade' -> 'normal' для совместимости с UI
      currentTradingMode = d.mode === 'trade' ? 'normal' : d.mode;
      updateTradingModeUI();
      console.log('[TRADE MODE] Текущий режим (нормализованный):', currentTradingMode);
      logDbg('trading mode='+currentTradingMode);
    }
  }catch(e){ 
    console.error('[TRADE MODE] Ошибка загрузки:', e);
    logDbg('loadTradingMode err '+e);
  }
}

// === AutoTrade switcher ===

async function toggleAutoTrade(){
  autoTradeEnabled = !autoTradeEnabled;
  updateAutoTradeUI();
  logDbg('AutoTrade toggled: ' + (autoTradeEnabled ? 'ON' : 'OFF'));
  
  // Отправляем запрос на сервер
  try {
    const endpoint = autoTradeEnabled ? '/api/autotrade/start' : '/api/autotrade/stop';
    const response = await fetch(endpoint, { method: 'POST' });
    const result = await response.json();
    if (result.success) {
      logDbg('AutoTrade: ' + (autoTradeEnabled ? 'запущен' : 'остановлен'));
      // Сохраняем состояние в UI state
      await UIStateManager.savePartial({autoTradeEnabled: autoTradeEnabled});
    } else {
      logDbg('AutoTrade: ошибка - ' + (result.error || 'неизвестная ошибка'));
      // Откатываем состояние при ошибке
      autoTradeEnabled = !autoTradeEnabled;
      updateAutoTradeUI();
    }
  } catch (error) {
    logDbg('AutoTrade: ошибка запроса - ' + error);
    // Откатываем состояние при ошибке
    autoTradeEnabled = !autoTradeEnabled;
    updateAutoTradeUI();
  }
}

function updateAutoTradeUI(){
  const sw=$('autoTradeSwitcher');
  if(!sw) return;
  
  const offBtn = sw.querySelector('[data-state="off"]');
  const onBtn = sw.querySelector('[data-state="on"]');
  if(offBtn && onBtn){
    offBtn.classList.toggle('active', !autoTradeEnabled);
    onBtn.classList.toggle('active', autoTradeEnabled);
  }
}

// Загрузка состояния UI с сервера
async function loadUIState() {
  console.log('[DEBUG] loadUIState called, currencySetByUser:', currencySetByUser, 'currentBaseCurrency:', currentBaseCurrency);
  try {
    const result = await api.loadUIState();
    if (result.success && result.state) {
      const state = result.state;
      
      // ВАЖНО: Восстанавливаем режим сети ПЕРВЫМ
      if (state.network_mode) {
        currentNetworkMode = state.network_mode;
        updateNetworkUI();
        logDbg('UI State: режим сети восстановлен - ' + currentNetworkMode);
      }
      
      // Восстанавливаем состояние автотрейдинга
      if (typeof state.auto_trade_enabled === 'boolean') {
        autoTradeEnabled = state.auto_trade_enabled;
        updateAutoTradeUI();
        logDbg('UI State: автотрейдинг восстановлен - ' + (autoTradeEnabled ? 'ON' : 'OFF'));
      }
      
      // Восстанавливаем разрешения торговли для валют
      if (state.enabled_currencies && typeof state.enabled_currencies === 'object') {
        Object.assign(tradingPermissions, state.enabled_currencies);
        updateTabsPermissionsUI();
        logDbg('UI State: разрешения торговли восстановлены');
      }
      
      // Восстанавливаем активную валютную пару
      if (state.active_base_currency && !currencySetByUser) {
        const oldCurrency = currentBaseCurrency;
        currentBaseCurrency = state.active_base_currency;
        try{ window.currentBaseCurrency = currentBaseCurrency; }catch(_){/* noop */}
        console.log('[DEBUG] loadUIState: changed currentBaseCurrency from', oldCurrency, 'to', currentBaseCurrency);
        logDbg('UI State: базовая валюта восстановлена - ' + currentBaseCurrency);
      }
      if (state.active_quote_currency) {
        currentQuoteCurrency = state.active_quote_currency;
        console.log('[DEBUG] loadUIState: set currentQuoteCurrency to', currentQuoteCurrency);
        // Синхронизируем селектор котируемой валюты в заголовке
        const quoteSel = document.querySelector('#quoteCurrencySelect');
        if (quoteSel) quoteSel.value = currentQuoteCurrency;
        logDbg('UI State: котировочная валюта восстановлена - ' + currentQuoteCurrency);
      }
      
      // Восстанавливаем режим торговли
      if (state.trading_mode) {
        // Нормализуем режим ('trade' -> 'normal' для UI)
        currentTradingMode = state.trading_mode === 'trade' ? 'normal' : state.trading_mode;
        updateTradingModeUI();
        logDbg('UI State: режим торговли восстановлен - ' + currentTradingMode);
      }
      
      // Восстанавливаем параметры безубыточности для текущей валюты
      if (state.breakeven_params && currentBaseCurrency) {
        const params = state.breakeven_params[currentBaseCurrency];
        if (params) {
          if (params.steps !== undefined) $('paramSteps').value = params.steps;
          if (params.start_volume !== undefined) $('paramStartVolume').value = params.start_volume;
                   if (params.start_price !== undefined) $('paramStartPrice').value = params.start_price;
          if (params.pprof !== undefined) $('paramPprof').value = params.pprof;
          if (params.kprof !== undefined) $('paramKprof').value = params.kprof;
          if (params.target_r !== undefined) $('paramTargetR').value = params.target_r;
          if (params.rk !== undefined) $('paramRk').value = params.rk;
          if (params.geom_multiplier !== undefined) $('paramGeomMultiplier').value = params.geom_multiplier;
          if (params.rebuy_mode !== undefined) $('paramRebuyMode').value = params.rebuy_mode;
          if (params.keep !== undefined) $('paramKeep').value = params.keep;
          if (params.orderbook_level !== undefined) $('paramOrderbookLevel').value = params.orderbook_level;
          logDbg('UI State: параметры безубыточности восстановлены для ' + currentBaseCurrency);
        }
      }
      
      logDbg('UI State: состояние успешно загружено');
    }
  } catch (error) {
    logDbg('UI State: ошибка загрузки - ' + error);
  }
}

function openCurrencyManager(){buildCurrencyManagerRows();$('currencyManagerModal').style.display='flex';}
function closeCurrencyManager(){$('currencyManagerModal').style.display='none';}

// Популярные символы для криптовалют
const popularCryptoEmojis = [
  '₿', '💎', '🚀', '🌐', 'Ξ', '◎', '🔶', '✕', '₳', 
  '🔺', '⬤', '💠', '🔷', '💰', '🪙', '💵', '💴', '💶',
  '💷', '⚡', '🔥', '🌟', '⭐', '💫', '✨', '🎯', '🎪',
  '🎨', '🔮', '🌈', '🦄', '🐉', '🦅', '🦊', '🐺', '🦁'
];

let currentEmojiPickerRow = -1;

function showEmojiPicker(rowIdx){
  currentEmojiPickerRow = rowIdx;
  
  // Получаем текущий символ из строки
  const rows = $('currencyManagerRows');
  const row = [...rows.querySelectorAll('.cm-row')].find(r => r.dataset.index == rowIdx);
  const currentSymbol = row ? row.querySelector('.cm-symbol').value.trim() : '';
  
  // Импортируем и показываем новый picker
  import('./currency-symbols.js').then(module => {
    module.showSymbolPicker((selectedSymbol) => {
      selectEmoji(selectedSymbol);
    }, currentSymbol);
  }).catch(err => {
    console.error('Failed to load symbol picker:', err);
    // Fallback to old picker
    showEmojiPickerFallback(rowIdx, currentSymbol);
  });
}

function showEmojiPickerFallback(rowIdx, currentSymbol){
  currentEmojiPickerRow = rowIdx;
  // Удаляем старый picker если есть
  const oldPicker = document.querySelector('.emoji-picker-popup');
  if(oldPicker) oldPicker.remove();
  
  // Создаём popup
  const picker = document.createElement('div');
  picker.className = 'emoji-picker-popup';
  picker.innerHTML = `
    <div class="emoji-picker-header">Выберите символ</div>
    <div class="emoji-picker-grid">
      ${popularCryptoEmojis.map(e => `<div class="emoji-item" onclick="selectEmoji('${e}')">${e}</div>`).join('')}
    </div>
    <div class="emoji-picker-custom">
      <input type="text" id="customEmojiInput" placeholder="Или введите свой символ" maxlength="4" value="${currentSymbol}">
      <button onclick="selectCustomEmoji()">✓</button>
    </div>
    <button class="emoji-picker-close" onclick="closeEmojiPicker()">✖</button>
  `;
  document.body.appendChild(picker);
}

function selectEmoji(emoji){
  const rows = $('currencyManagerRows');
  const row = [...rows.querySelectorAll('.cm-row')].find(r => r.dataset.index == currentEmojiPickerRow);
  if(row){
    const input = row.querySelector('.cm-symbol');
    if(input) input.value = emoji;
  }
  closeEmojiPicker();
}

function selectCustomEmoji(){
  const input = document.getElementById('customEmojiInput');
  if(input && input.value.trim()){
    selectEmoji(input.value.trim());
  }
}

function closeEmojiPicker(){
  const picker = document.querySelector('.emoji-picker-popup');
  if(picker) picker.remove();
  currentEmojiPickerRow = -1;
}

function buildCurrencyManagerRows(){const rows=$('currencyManagerRows');if(!rows)return;rows.innerHTML='';const arr=Array.isArray(currenciesList)?currenciesList:[];arr.forEach((c,i)=>{const code=(c.code||c||'').toUpperCase();const symbol=(c.symbol||c.code||c||'');const row=document.createElement('div');row.className='cm-row';row.dataset.index=i;row.innerHTML=`<input type='text' class='cm-code' value='${code}' placeholder='Код'><div class='cm-symbol-picker'><input type='text' class='cm-symbol' value='${symbol}' placeholder='Символ' readonly onclick='showEmojiPicker(${i})'><button class='cm-emoji-btn' onclick='showEmojiPicker(${i})' title='Выбрать символ'>😀</button></div><div style='color:#888;font-size:11px;'>${tradingPermissions[code]!==false?'Торговля: ✅':'Торговля: ❌'}</div><button class='cm-btn delete' onclick='deleteCurrencyRow(${i})'>🗑️</button>`;rows.appendChild(row);});}
function addCurrencyRow(){const rows=$('currencyManagerRows');const i=rows.querySelectorAll('.cm-row').length;const row=document.createElement('div');row.className='cm-row';row.dataset.index=i;row.innerHTML=`<input type='text' class='cm-code' value='' placeholder='Код'><div class='cm-symbol-picker'><input type='text' class='cm-symbol' value='' placeholder='Символ' readonly onclick='showEmojiPicker(${i})'><button class='cm-emoji-btn' onclick='showEmojiPicker(${i})' title='Выбрать символ'>😀</button></div><div style='color:#888;font-size:11px;'>Новая</div><button class='cm-btn delete' onclick='deleteCurrencyRow(${i})'>🗑️</button>`;rows.appendChild(row);}
function deleteCurrencyRow(idx){const rows=$('currencyManagerRows');const row=[...rows.querySelectorAll('.cm-row')].find(r=>r.dataset.index==idx);if(row)row.remove();}
async function saveCurrenciesList(){const rows=$('currencyManagerRows');const items=[...rows.querySelectorAll('.cm-row')].map(r=>({code:r.querySelector('.cm-code').value.trim().toUpperCase(),symbol:r.querySelector('.cm-symbol').value.trim()})).filter(o=>o.code);if(!items.length){alert('Нужна минимум 1 валюта');return;}const codes=items.map(i=>i.code);const dup=codes.filter((c,i)=>codes.indexOf(c)!==i);if(dup.length){alert('Дубликаты: '+dup.join(','));return;}try{const d=await api.saveCurrencies(items);if(d.success){currenciesList=items;renderCurrencyTabs(currenciesList);closeCurrencyManager();logDbg('currencies saved');}else alert('Ошибка: '+(d.error||'fail'));}catch(e){alert('Ошибка сохранения: '+e);}}

async function syncCurrenciesFromGateIO() {
  const syncBtn = event.target;
  const originalText = syncBtn.innerHTML;
  
  syncBtn.disabled = true;
  syncBtn.innerHTML = '⏳ Синхронизация...';
  
  try {
    // Отправляем текущую котируемую валюту для проверки торговых пар
    const result = await api.syncCurrenciesFromGateIO(currentQuoteCurrency || 'USDT');
    
    if (result.success) {
      alert(`✅ Синхронизация символов завершена!\n\n` +
            `Котируемая валюта: ${result.quote_currency}\n` +
            `Обновлено символов: ${result.updated}\n` +
            `Пропущено валют: ${result.skipped}\n` +
            `Торгуемых пар: ${result.tradeable_count}\n` +
            `Всего валют: ${result.total}\n\n` +
            `Время: ${new Date(result.timestamp).toLocaleString('ru-RU')}\n\n` +
            `Примечание: Названия валют НЕ изменялись, обновлены только символы для валют, торгующихся с ${result.quote_currency}`);
      await loadCurrenciesFromServer();
      buildCurrencyManagerRows();
      updateSyncInfo();
    } else {
      alert(`❌ Ошибка синхронизации:\n\n${result.error}`);
    }
  } catch (e) {
    alert(`❌ Ошибка синхронизации:\n\n${e.message}`);
  } finally {
    syncBtn.disabled = false;
    syncBtn.innerHTML = originalText;
  }
}

async function updateSyncInfo() {
  try {
    const data = await api.getSyncInfo();
    
    if (data.success && data.info) {
      const info = data.info;
      const syncInfoEl = $('syncInfo');
      
      if (syncInfoEl) {
        if (info.last_update) {
          const date = new Date(info.last_update);
          syncInfoEl.innerHTML = `
            <div style="text-align:right;">
              <div>Обновлено: ${date.toLocaleDateString('ru-RU')} ${date.toLocaleTimeString('ru-RU')}</div>
              <div>Валют: ${info.total_currencies} | Изменённых: ${info.custom_symbols}</div>
            </div>
          `;
        } else {
          syncInfoEl.innerHTML = '<div style="color:#ff9800;">Синхронизация не выполнялась</div>';
        }
      }
    }
  } catch (e) {
    logDbg('updateSyncInfo error: ' + e);
  }
}

// Обновляем информацию о синхронизации при открытии менеджера валют
const originalOpenCurrencyManager = window.openCurrencyManager;
window.openCurrencyManager = function() {
  if (originalOpenCurrencyManager) {
    originalOpenCurrencyManager();
  }
  updateSyncInfo();
};

// === Subscribe to all currencies (как было в рабочей версии) ===
async function subscribeToAllCurrencies(){
  if(!Array.isArray(currenciesList) || currenciesList.length===0){
    logDbg('subscribeToAllCurrencies: нет валют для подписки');
    return;
  }
  logDbg(`subscribeToAllCurrencies: подписываемся на ${currenciesList.length} валют с ${currentQuoteCurrency}`);
  for(const cur of currenciesList){
    const code = typeof cur==='string' ? cur : cur.code;
    if(code){
      try{
        await subscribeToPairData(code.toUpperCase(), currentQuoteCurrency);
        await new Promise(resolve => setTimeout(resolve, 300));
      }catch(e){
        logDbg(`subscribeToAllCurrencies: ошибка для ${code}: ${e}`);
      }
    }
  }
  logDbg('subscribeToAllCurrencies: завершено');
}

// === Quick Trade / Server controls / Uptime и инициализация UI ===

// Обработчики для кнопок "Купить мин. ордер", "Продать все", "Перезагрузить сервер", "Остановить сервер"
async function handleServerRestart() {
  try {
    if (!confirm('Перезагрузить сервер? Текущие соединения будут разорваны.')) return;
    const data = await api.restartServer();
    // Небольшая задержка и попытка перезагрузить страницу
    setTimeout(() => {
      try { window.location.reload(); } catch (e) {}
    }, 3000);
  } catch (e) {
    console.error('[SERVER] Ошибка перезапуска сервера:', e);
    alert('Ошибка при попытке перезапуска сервера: ' + e);
  }
}

async function handleServerShutdown() {
  try {
    if (!confirm('Остановить сервер? После остановки страница станет недоступной.')) return;
    const data = await api.shutdownServer().catch(() => ({ success: false }));
    logDbg('[SERVER] shutdown response: ' + JSON.stringify(data));
    alert(data.message || 'Команда остановки сервера отправлена.');
  } catch (e) {
    console.error('[SERVER] Ошибка остановки сервера:', e);
    alert('Ошибка при попытке остановки сервера: ' + e);
  }
}

async function handleResetBotSession() {
  try {
    if (!confirm('Сбросить сессию бота? Это обнулит время сессии и прибыль всех валют.')) return;
    const response = await fetch('/api/reset-session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    const data = await response.json();
    
    if (data.status === 'success') {
      // Сбрасываем локальный счётчик времени сессии бота
      _botSessionUptimeSeconds = 0;
      
      // Обновляем отображение
      const botSessionUptimeEl = document.getElementById('botSessionUptime');
      if(botSessionUptimeEl) botSessionUptimeEl.textContent = formatUptime(0);
      
      // Обновляем данные торговли для текущей валюты
      if(currentBaseCurrency) {
        loadTradeData(currentBaseCurrency, currentQuoteCurrency);
      }
      
      alert('✅ Сессия бота сброшена успешно');
      logDbg('[SESSION] Сессия бота сброшена: ' + JSON.stringify(data));
    } else {
      alert('❌ Ошибка при сбросе сессии: ' + (data.error || 'Неизвестная ошибка'));
    }
  } catch (e) {
    console.error('[SESSION] Ошибка сброса сессии бота:', e);
    alert('Ошибка при попытке сброса сессии бота: ' + e);
  }
}

// Периодическое обновление статуса сервера (PID и Uptime)
let _serverStatusTimer = null;
let _serverUptimeSeconds = 0;
let _botSessionUptimeSeconds = 0;

async function fetchServerStatusOnce(){
  try{
    const data = await api.getServerStatus();
    logDbg('[SERVER] status: '+JSON.stringify(data));
    const pidEl = document.getElementById('serverPID');
    const serverUptimeEl = document.getElementById('serverUptime');
    const botSessionUptimeEl = document.getElementById('botSessionUptime');
    
    if(pidEl) pidEl.textContent = (data.pid != null ? String(data.pid) : '---');
    
    if(typeof data.uptime === 'number'){
      _serverUptimeSeconds = data.uptime;
      if(serverUptimeEl) serverUptimeEl.textContent = formatUptime(_serverUptimeSeconds);
    }
    
    if(typeof data.bot_session_uptime === 'number'){
      _botSessionUptimeSeconds = data.bot_session_uptime;
      if(botSessionUptimeEl) botSessionUptimeEl.textContent = formatUptime(_botSessionUptimeSeconds);
    }
  }catch(e){
    console.error('[SERVER] status error', e);
  }
}

function startUptimeLoops(){
  // Первичный запрос
  fetchServerStatusOnce();
  // Раз в 5 секунд обновляем данные с сервера
  if(_serverStatusTimer) clearInterval(_serverStatusTimer);
  _serverStatusTimer = setInterval(fetchServerStatusOnce, 5000);
  // Локальный таймер тикает каждую секунду между опросами
  setInterval(()=>{
    const serverUptimeEl = document.getElementById('serverUptime');
    const botSessionUptimeEl = document.getElementById('botSessionUptime');
    
    _serverUptimeSeconds += 1;
    _botSessionUptimeSeconds += 1;
    
    if(serverUptimeEl) serverUptimeEl.textContent = formatUptime(_serverUptimeSeconds);
    if(botSessionUptimeEl) botSessionUptimeEl.textContent = formatUptime(_botSessionUptimeSeconds);
  }, 1000);
  
  // Запускаем обновление общей прибыли
  updateTotalProfit();
  setInterval(updateTotalProfit, 5000);
}

// Функция для обновления общей прибыли всех валют
async function updateTotalProfit(){
  try{
    const response = await fetch('/api/session-profit');
    const data = await response.json();
    
    if(data.success){
      const totalProfit = data.total_profit ?? 0;
      const profitEl = document.getElementById('totalProfit');
      
      if(profitEl){
        const formatted = (typeof totalProfit === 'number' ? totalProfit : 0).toFixed(2);
        
        if(totalProfit > 0){
          profitEl.style.color = '#4CAF50';
          profitEl.textContent = '+' + formatted;
        } else if(totalProfit < 0){
          profitEl.style.color = '#f44336';
          profitEl.textContent = formatted;
        } else {
          profitEl.style.color = '#999';
          profitEl.textContent = '0.00';
        }
      }
    }
  } catch(e){
    console.error('[PROFIT] Update error:', e);
  }
}

// === Quick Trade Functions (Быстрая торговля) ===
async function handleBuyMinOrder(){
  try{
    if(!currentBaseCurrency){
      alert('❌ Выберите базовую валюту');
      return;
    }
    if(!confirm(`Купить минимальный ордер ${currentBaseCurrency}/${currentQuoteCurrency}?`)){
      return;
    }
    
    const payload = {
      base_currency: currentBaseCurrency,
      quote_currency: currentQuoteCurrency
    };
    
    console.log('[BUY-MIN] Отправка запроса:', payload);
    
    const data = await api.buyMinOrder(currentBaseCurrency, currentQuoteCurrency);
    console.log('[BUY-MIN] Ответ сервера:', data);
    
    if(data.success){
      alert(`✅ Покупка выполнена!\n\n${data.message || ''}\n\nОрдер ID: ${data.order_id || 'N/A'}`);
      // Обновляем балансы и индикаторы
      await loadPairBalances();
      await loadPerBaseIndicators();
    } else {
      alert(`❌ Ошибка покупки: ${data.error || 'Неизвестная ошибка'}`);
    }
  } catch(e){
    console.error('[BUY-MIN] Исключение:', e);
    alert(`❌ Ошибка при покупке: ${e.message}`);
  }
}

async function handleSellAll(){
  try{
    if(!currentBaseCurrency){
      alert('❌ Выберите базовую валюту');
      return;
    }
    if(!confirm(`Продать ВСЕ монеты ${currentBaseCurrency}?`)){
      return;
    }
    
    const payload = {
      base_currency: currentBaseCurrency,
      quote_currency: currentQuoteCurrency
    };
    
    console.log('[SELL-ALL] Отправка запроса:', payload);
    
    const data = await api.sellAll(currentBaseCurrency, currentQuoteCurrency);
    console.log('[SELL-ALL] Ответ сервера:', data);
    
    if(data.success){
      alert(`✅ Продажа выполнена!\n\n${data.message || ''}\n\nОрдер ID: ${data.order_id || 'N/A'}`);
      // Обновляем балансы и индикаторы
      await loadPairBalances();
      await loadPerBaseIndicators();
    } else {
      alert(`❌ Ошибка продажи: ${data.error || 'Неизвестная ошибка'}`);
    }
  } catch(e){
    console.error('[SELL-ALL] Исключение:', e);
    alert(`❌ Ошибка при продаже: ${e.message}`);
  }
}

const rb=$('restartServerBtn'); if(rb){ rb.title='Перезагрузка сервера'; rb.addEventListener('click', (ev)=>{ ev.preventDefault(); handleServerRestart(); }); }
const sb=$('shutdownServerBtn'); if(sb){ sb.title='Остановить сервер'; sb.addEventListener('click', (ev)=>{ ev.preventDefault(); handleServerShutdown(); }); }
const rsb=$('resetBotSessionBtn'); if(rsb){ rsb.title='Сбросить сессию бота'; rsb.addEventListener('click', (ev)=>{ ev.preventDefault(); handleResetBotSession(); }); }
const spb=$('saveParamsBtn'); if(spb){ spb.addEventListener('click', (ev)=>{ ev.preventDefault(); saveTradeParams(); }); }

const buyBtn=$('buyMinOrderBtn'); if(buyBtn){ buyBtn.addEventListener('click', (ev)=>{ ev.preventDefault(); handleBuyMinOrder(); }); }
const sellBtn=$('sellAllBtn'); if(sellBtn){ sellBtn.addEventListener('click', (ev)=>{ ev.preventDefault(); handleSellAll(); }); }

// Обработчики для полей параметров (автообновление таблицы безубыточности)
let paramsUpdateTimeout = null;
const paramsInputIds = ['paramSteps', 'paramStartVolume', 'paramStartPrice', 'paramPprof', 'paramKprof', 'paramTargetR', 'paramGeomMultiplier', 'paramRebuyMode', 'paramKeep', 'paramOrderbookLevel'];

paramsInputIds.forEach(id => {
  const input = $(id);
  if(input) {
    input.addEventListener('input', () => {
      // 🔍 ОТЛАДКА: Выводим изменённое поле и его новое значение
      console.log(`[PARAMS_CHANGE] 🔄 Поле "${id}" изменено на: ${input.value}`);
      
      if(paramsUpdateTimeout) clearTimeout(paramsUpdateTimeout);
      const statusEl = $('paramsSaveStatus');
      if(statusEl) {
        statusEl.textContent = '⏳ Обновление...';
        statusEl.className = 'params-save-status';
      }
      paramsUpdateTimeout = setTimeout(async () => {
        try {
          // 🔍 ОТЛАДКА: Выводим все параметры перед обновлением таблицы
          console.log('[PARAMS_CHANGE] ⚙️ Все параметры перед обновлением таблицы:');
          paramsInputIds.forEach(paramId => {
            const el = $(paramId);
            if(el) console.log(`  - ${paramId}: ${el.value}`);
          });
          
          await loadBreakEvenTable();
          if(statusEl) {
            statusEl.textContent = '✓ Обновлено';
            setTimeout(() => { statusEl.textContent = ''; }, 1000);
          }
        } catch(e) {
          console.error('[PARAMS] Ошибка обновления таблицы:', e);
          if(statusEl) statusEl.textContent = '✗ Ошибка';
        }
      }, 500);
    });
  }
});

// DOMContentLoaded – единая точка старта UI
async function initApp(){
  try{
    // 1. Загружаем состояние UI (режим сети, автотрейд, разрешения, активная пара, breakeven)
    await loadUIState();

    // 2. Актуальный режим сети и режим торговли с сервера
    await loadNetworkMode();
    await loadTradingMode();

    // 3. Инициализация переключателя AutoTrade по текущему состоянию
    updateAutoTradeUI();

    // 4. Синхронизируем текущую котируемую валюту из селектора (если есть)
    const sel=document.querySelector('#quoteCurrencySelect') || document.querySelector('#quoteCurrency');
    if(sel) {
      currentQuoteCurrency=sel.value.toUpperCase();
      try{ window.currentQuoteCurrency = currentQuoteCurrency; }catch(_){/* noop */}
    }

    // 5. Загружаем список валют и строим вкладки
    await loadCurrenciesFromServer();

    // 6. Загружаем разрешения торговли и обновляем индикаторы на вкладках
    await loadTradingPermissions();

    // 7. Загружаем индикаторы для всех валют (шаги и диагностические решения)
    await loadAllIndicators();

    // 8. Подписываемся на все валюты (для прогрева WS), а затем на активную пару
    await subscribeToAllCurrencies();
    
    // 🔧 HOTFIX: Немедленно переподключаем известные проблемные валюты
    const problemCurrencies = ['XRP', 'ADA', 'LINK', 'TAO', 'ANIME', 'ICP'];
    console.log('[WS_HOTFIX] Переподключение проблемных валют:', problemCurrencies);
    for(const code of problemCurrencies){
      if(currenciesList.some(c => (typeof c === 'string' ? c : c.code) === code)){
        try{
          console.log(`[WS_HOTFIX] Переподключение ${code}...`);
          await subscribeToPairData(code, currentQuoteCurrency);
          await new Promise(resolve => setTimeout(resolve, 400));
        }catch(e){
          console.error(`[WS_HOTFIX] Ошибка для ${code}:`, e);
        }
      }
    }
    console.log('[WS_HOTFIX] Переподключение завершено');

    // 8. Загружаем данные для текущей пары (рынок, баланс, параметры, таблица)
    await Promise.all([
      loadMarketData(true),
      loadPairBalances(),
      loadPairParams(true),
      loadBreakEvenTable(),
      loadTradeParams(),
      loadPerBaseIndicators()
    ]);
    await loadPairBalances(); // Повторный вызов для гарантии отрисовки баланса

    setInterval(()=>{ loadMarketData(); },2500);
    setInterval(()=>{ loadPairBalances(); },7500);
    setInterval(()=>{ loadBreakEvenTable(); },3000);
    setInterval(()=>{ loadPerBaseIndicators(); },3500);
    setInterval(()=>{ loadTradingPermissions(); },10000);
    // Периодически обновляем индикаторы для всех валют, чтобы табы обновлялись автоматически
    setInterval(()=>{ try{ loadAllIndicators(); }catch(e){ console.error('periodic loadAllIndicators failed', e); } }, 5000);
    
    // 🔄 АВТОМАТИЧЕСКОЕ ПЕРЕПОДКЛЮЧЕНИЕ WS для отключенных валют
    setInterval(async ()=>{
      try{
        const disconnectedTabs = document.querySelectorAll('.tab-item.ws-disconnected');
        if(disconnectedTabs.length > 0){
          console.log(`[WS_RECONNECT] Найдено ${disconnectedTabs.length} отключенных валют, переподключаем...`);
          for(const tab of disconnectedTabs){
            const code = tab.dataset.code;
            if(code){
              console.log(`[WS_RECONNECT] Переподключение ${code}...`);
              await subscribeToPairData(code, currentQuoteCurrency);
              await new Promise(resolve => setTimeout(resolve, 300));
            }
          }
        }
      }catch(e){
        console.error('[WS_RECONNECT] Ошибка:', e);
      }
    }, 30000); // Каждые 30 секунд проверяем и переподключаем
    
    // Единоразовый стартовый вызов (в дополнение к загрузке при инициализации)
    try{ loadAllIndicators(); }catch(e){ console.error('initial loadAllIndicators failed', e); }
  }catch(e){
    console.error('[INIT] Ошибка инициализации:', e);
    logDbg('initApp exc '+e);
  }
}

// === СБРОС ЦИКЛА ===
async function handleResetCycle(){
  if(!currentBaseCurrency){
    alert('Выберите валюту для сброса цикла');
    return;
  }
  
  const confirmMsg = `Вы уверены, что хотите сбросить цикл для ${currentBaseCurrency}?\n\nЭто удалит текущее состояние цикла и позволит начать новый цикл.\nУбедитесь, что вы уже продали все монеты!`;
  
  if(!confirm(confirmMsg)){
    return;
  }
  
  console.log(`[RESET] Отправка запроса на сброс цикла для ${currentBaseCurrency}...`);
  
  try{
    const data = await api.resetCycle(currentBaseCurrency, currentQuoteCurrency);
    console.log('[RESET] Данные ответа:', data);
    
    if(data.success){
      alert(`✅ Цикл ${currentBaseCurrency} успешно сброшен!\n\n${data.message}`);
      loadPerBaseIndicators();
      loadPairBalances();
      console.log('[RESET] Цикл сброшен успешно');
    } else {
      alert(`❌ Ошибка сброса цикла: ${data.error}`);
    }
  } catch(e){
    alert(`❌ Ошибка при сбросе цикла: ${e.message}`);
    console.error('[RESET] Исключение:', e);
  }
}

async function handleResumeCycle(){
  if(!currentBaseCurrency){
    alert('Выберите валюту для старта цикла');
    return;
  }
  
  const confirmMsg = `Вы уверены, что хотите запустить цикл для ${currentBaseCurrency}?\n\nАвтотрейдер начнёт автоматически покупать монеты согласно стратегии.`;
  
  if(!confirm(confirmMsg)){
    return;
  }
  
  console.log(`[RESUME] Отправка запроса на старт цикла для ${currentBaseCurrency}...`);
  
  try{
    const data = await api.resumeCycle(currentBaseCurrency, currentQuoteCurrency);
    console.log('[RESUME] Данные ответа:', data);
    
    if(data.success){
      alert(`✅ Цикл ${currentBaseCurrency} успешно запущен!\n\n${data.message}`);
      loadPerBaseIndicators();
      loadPairBalances();
      console.log('[RESUME] Цикл запущен успешно');
    } else {
      alert(`❌ Ошибка старта цикла: ${data.error}`);
    }
  } catch(e){
    alert(`❌ Ошибка при старте цикла: ${e.message}`);
    console.error('[RESUME] Исключение:', e);
  }
}

// === Привязка обработчиков к кнопкам ===
const resetCycleBtn = $('resetCycleBtn');
if(resetCycleBtn){
  resetCycleBtn.addEventListener('click', (e) => {
    e.preventDefault();
    handleResetCycle();
  });
}

const resumeCycleBtn = $('resumeCycleBtn');
if(resumeCycleBtn){
  resumeCycleBtn.addEventListener('click', (e) => {
    e.preventDefault();
    handleResumeCycle();
  });
}

const resetSessionBtn = $('resetSessionBtn');
if(resetSessionBtn){
  resetSessionBtn.addEventListener('click', async (e) => {
    e.preventDefault();
    if (!confirm('🔄 Вы уверены, что хотите сбросить время старта сессии?\n\nПрибыль и длительность сессии будут пересчитаны с текущего момента.')) {
      return;
    }
    try {
      const response = await fetch('/api/reset-session', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'}
      });
      const data = await response.json();
      if (data.success) {
        alert('✅ Время старта сессии сброшено!\n\nПрибыль и длительность обнулены.');
        // Немедленно обновляем отображение прибыли
        if (typeof updateSessionProfit === 'function') {
          updateSessionProfit();
        }
      } else {
        alert('❌ Ошибка: ' + (data.error || 'Неизвестная ошибка'));
      }
    } catch (error) {
      console.error('Ошибка сброса сессии:', error);
      alert('❌ Ошибка связи с сервером: ' + error.message);
    }
  });
}

// === Инициализация приложения при загрузке страницы ===
console.log('[APP] 🚀 Скрипт app.js загружен, ожидание DOMContentLoaded...');

if (document.readyState === 'loading') {
  // DOM ещё не загружен, ждём события
  document.addEventListener('DOMContentLoaded', () => {
    console.log('[APP] ✅ DOMContentLoaded сработал, запуск initApp()...');
    initApp();
    startUptimeLoops(); // Запуск таймера uptime
  });
} else {
  // DOM уже загружен (скрипт выполняется после загрузки)
  console.log('[APP] ⚡ DOM уже загружен, немедленный запуск initApp()...');
  initApp();
  startUptimeLoops();
}

console.log('[APP] 📝 app.js полностью загружен и готов к работе');
