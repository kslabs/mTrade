// === Модуль обработки стакана заявок ===
import { formatPrice, $, logDbg } from './utils.js';

// Глобальные переменные для отслеживания уровней покупки/продажи
let globalBuyPrice = null;
let globalSellPrice = null;

/**
 * Устанавливает глобальный уровень покупки для подсветки в стакане
 * @param {number|null} price - Цена уровня покупки
 */
export function setGlobalBuyPrice(price) {
  globalBuyPrice = price;
}

/**
 * Устанавливает глобальный уровень продажи для подсветки в стакане
 * @param {number|null} price - Цена уровня продажи
 */
export function setGlobalSellPrice(price) {
  globalSellPrice = price;
}

/**
 * Обновляет отображение стакана заявок
 * @param {Object} ob - Объект со стаканом: {asks: [[price, amount], ...], bids: [[price, amount], ...]}
 */
export function updateOrderBook(ob) {
  try {
    if (!ob || !Array.isArray(ob.asks) || !Array.isArray(ob.bids)) return;
    const asksEl = $('orderbookAsks');
    const bidsEl = $('orderbookBids');
    if (asksEl) asksEl.innerHTML = '';
    if (bidsEl) bidsEl.innerHTML = '';

    // Нормализуем и фильтруем данные
    const asksAll = ob.asks.map(r => [parseFloat(r[0]), parseFloat(r[1])]).filter(r => isFinite(r[0]) && isFinite(r[1]));
    const bidsAll = ob.bids.map(r => [parseFloat(r[0]), parseFloat(r[1])]).filter(r => isFinite(r[0]) && isFinite(r[1]));
    if (!asksAll.length && !bidsAll.length) return;

    // Центральная цена (mid) = среднее между лучшим бидом и лучшим аском
    const bestAsk = asksAll.length ? Math.min.apply(null, asksAll.map(r => r[0])) : NaN;
    const bestBid = bidsAll.length ? Math.max.apply(null, bidsAll.map(r => r[0])) : NaN;
    let mid = NaN;
    if (isFinite(bestAsk) && isFinite(bestBid)) mid = (bestAsk + bestBid) / 2;
    else if (isFinite(bestAsk)) mid = bestAsk; else if (isFinite(bestBid)) mid = bestBid;

    // Сортируем по близости к центральной цене (минимальная разница первее)
    const asksSorted = isFinite(mid)
      ? asksAll.slice().sort((a, b) => Math.abs(a[0] - mid) - Math.abs(b[0] - mid))
      : asksAll.slice().sort((a, b) => a[0] - b[0]);
    const bidsSorted = isFinite(mid)
      ? bidsAll.slice().sort((a, b) => Math.abs(a[0] - mid) - Math.abs(b[0] - mid))
      : bidsAll.slice().sort((a, b) => b[0] - a[0]);

    // Кумулятивы: для асков снизу вверх, для бидов сверху вниз
    // Asks: разворачиваем массив, чтобы лучшие цены (ближе к спреду) были ВНИЗУ списка
    // (так они окажутся ближе к центральной линии спреда)
    const asksReversed = asksSorted.slice().reverse();
    const asksCum = [];
    let cumA = 0;
    for (let i = asksReversed.length - 1; i >= 0; i--) {
      cumA += asksReversed[i][1];
      asksCum[i] = cumA;
    }
    asksReversed.forEach((r, idx) => {
      const p = r[0], a = r[1], t = p * a;
      const div = document.createElement('div');
      div.className = 'orderbook-row';
      
      // Проверяем, является ли эта строка уровнем продажи
      if (globalSellPrice && Math.abs(p - globalSellPrice) / globalSellPrice < 0.001) {
        div.classList.add('orderbook-sell-level');
      }
      
      div.innerHTML = `<div class='price'>${formatPrice(p)}</div><div class='amount'>${a.toFixed(6)}</div><div class='total'>${t.toFixed(6)}</div><div class='cumulative'>${(asksCum[idx] || 0).toFixed(4)}</div>`;
      if (asksEl) asksEl.appendChild(div);
    });

    let cumB = 0;
    bidsSorted.forEach(r => {
      const p = r[0], a = r[1], t = p * a; cumB += a;
      const div = document.createElement('div');
      div.className = 'orderbook-row';
      
      // Проверяем, является ли эта строка уровнем покупки
      if (globalBuyPrice && Math.abs(p - globalBuyPrice) / globalBuyPrice < 0.001) {
        div.classList.add('orderbook-buy-level');
      }
      
      div.innerHTML = `<div class='price'>${formatPrice(p)}</div><div class='amount'>${a.toFixed(6)}</div><div class='total'>${t.toFixed(6)}</div><div class='cumulative'>${cumB.toFixed(4)}</div>`;
      if (bidsEl) bidsEl.appendChild(div);
    });
    
    // Прокрутка к лучшим ценам:
    // Для asks: лучшие цены теперь ВНИЗУ списка (после reverse), прокручиваем вниз так, чтобы они были видны
    // Для bids: лучшие цены ВВЕРХУ списка, оставляем прокрутку в начале
    if (asksEl && asksEl.scrollHeight > asksEl.clientHeight) {
      // Прокручиваем так, чтобы последние ~10 строк (лучшие цены) были видны
      asksEl.scrollTop = Math.max(0, asksEl.scrollHeight - asksEl.clientHeight);
    }
    if (bidsEl) bidsEl.scrollTop = 0; // прокрутка вверх к началу (к лучшим ценам)
  } catch (e) { logDbg('updateOrderBook err ' + e) }
}
