// Temporary placeholder module.
// This file is intentionally minimal.
// The implementation will be migrated from static/app.js step-by-step.

/**
 * Обновляет визуальную шкалу с маркерами (sell/be/current/last/start/buy).
 * Вынесено из `static/app.js` для уменьшения размера основного файла.
 *
 * Зависимости передаются явно, чтобы модуль не зависел от глобалов:
 * - $: shorthand для document.getElementById
 * - formatPrice: форматирование цены
 */
export function updateVisualIndicatorScale(levels, { $, formatPrice } = {}) {
  if (!levels) {
    console.warn('[SCALE] levels не переданы!');
    return;
  }

  if (typeof $ !== 'function') {
    console.error('[SCALE] missing dependency: $');
    return;
  }
  if (typeof formatPrice !== 'function') {
    console.error('[SCALE] missing dependency: formatPrice');
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

  // Проверяем, что все маркеры существуют
  const allMarkersExist = Object.values(markers).every((m) => m !== null);
  if (!allMarkersExist) {
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

  // Фильтруем валидные цены
  const validPrices = Object.values(prices).filter(
    (p) => p !== null && p !== undefined && !isNaN(p) && p > 0
  );

  if (validPrices.length === 0) {
    // Нет валидных цен - скрываем все маркеры
    Object.values(markers).forEach((marker) => {
      marker.style.bottom = '50%';
      marker.style.opacity = '0.3';
    });
    return;
  }

  // Определяем диапазон цен с небольшим запасом
  const minPrice = Math.min(...validPrices);
  const maxPrice = Math.max(...validPrices);
  const range = maxPrice - minPrice;
  const padding = range * 0.1; // 10% padding сверху и снизу
  const displayMin = minPrice - padding;
  const displayMax = maxPrice + padding;
  const displayRange = displayMax - displayMin;

  // Функция для вычисления позиции маркера (0-100%)
  function calculatePosition(price) {
    if (!price || price <= 0) return null;
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
  for (const [key, marker] of Object.entries(markers)) {
    const pos = positions[key];
    const price = prices[key === 'price' ? 'current' : key];

    if (pos !== null && price) {
      marker.style.bottom = pos + '%';
      marker.style.opacity = '1';

      // Обновляем тултип
      const tooltip = marker.querySelector('.marker-tooltip');
      if (tooltip) {
        const label = key.charAt(0).toUpperCase() + key.slice(1);
        tooltip.textContent = `${label}: ${formatPrice(price)}`;
      }
    } else {
      marker.style.bottom = '50%';
      marker.style.opacity = '0.3';

      const tooltip = marker.querySelector('.marker-tooltip');
      if (tooltip) {
        tooltip.textContent = `${key}: -`;
      }
    }
  }

  // Добавляем анимацию при обновлении
  Object.values(markers).forEach((marker) => {
    marker.style.transition = 'bottom 0.3s ease-out, opacity 0.3s ease-out';
  });
}

/**
 * Обновляет индикаторы торговли на странице (цены, статусы, бордюры вкладок).
 * Вынесено из `static/app.js`.
 *
 * Зависимости передаются явно:
 * - $: helper получения элемента по id
 * - formatPrice: форматирование цены
 * - updateAutoTradeLevels: обновление autotrade уровней (остаётся в app.js)
 * - getCurrentBaseCurrency: возвращает currentBaseCurrency (fallback)
 * - getCurrentPricePrecision: возвращает текущую точность
 */
export function updateTradeIndicators(
  d,
  {
    $,
    formatPrice,
    updateAutoTradeLevels,
    getCurrentBaseCurrency,
    getCurrentPricePrecision
  } = {}
) {
  d = d || {};

  if (typeof $ !== 'function') {
    console.error('[updateTradeIndicators] missing dependency: $');
    return;
  }
  if (typeof formatPrice !== 'function') {
    console.error('[updateTradeIndicators] missing dependency: formatPrice');
    return;
  }
  if (typeof updateAutoTradeLevels !== 'function') {
    console.error('[updateTradeIndicators] missing dependency: updateAutoTradeLevels');
    return;
  }

  const currentBaseCurrency =
    typeof getCurrentBaseCurrency === 'function' ? getCurrentBaseCurrency() : null;
  const currentPricePrecision =
    typeof getCurrentPricePrecision === 'function' ? getCurrentPricePrecision() : 5;

  const priceEl = $('indPrice');
  if (priceEl && d.price) priceEl.textContent = formatPrice(d.price, currentPricePrecision);

  // Поддерживаем старый формат: autotrade_levels внутри d
  const levels = d.autotrade_levels || {};

  // Если в WS-пакете указана валюта — используем её как целевую вкладку.
  // Фолбэк — currentBaseCurrency.
  const targetCurrency = (
    levels.base_currency || d.base_currency || d.currency || currentBaseCurrency || ''
  )
    .toString()
    .toUpperCase();

  // Обновляем значения в футере индикатора с единой точностью
  const updates = {
    sell: levels.sell_price,
    be: levels.breakeven_price,
    last: levels.current_price,
    start: levels.start_price,
    buy: levels.next_buy_price
  };

  for (const [key, value] of Object.entries(updates)) {
    const elementId = key === 'be' ? 'indBE' : 'ind' + key.charAt(0).toUpperCase() + key.slice(1);
    const el = $(elementId);
    if (el) {
      if (value === null || value === undefined || value === 0) {
        el.textContent = '-';
      } else {
        el.textContent = formatPrice(value, currentPricePrecision);
      }
    }
  }

  // Обновляем autotrade_levels если есть
  if (d.autotrade_levels) {
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
          const shouldSell = (levels.last_detected && levels.last_detected.sell) || levels.should_sell === true;
          const shouldBuy = (levels.last_detected && levels.last_detected.buy) || levels.should_buy === true;
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
    if (targetCurrency) {
      const tab = document.querySelector(`.tab-item[data-code="${targetCurrency}"]`);
      if (tab) {
        tab.classList.remove('ready-to-sell', 'ready-to-buy', 'price-normal', 'ws-disconnected');

        const hasValidPrice = currentPrice !== undefined && !isNaN(currentPrice) && currentPrice > 0;
        const hasSellPrice = sellPrice !== null && !isNaN(sellPrice) && sellPrice > 0;
        const hasBuyPrice = buyPrice !== null && !isNaN(buyPrice) && buyPrice > 0;

        if (!hasValidPrice || !hasSellPrice || !hasBuyPrice) {
          tab.classList.add('ws-disconnected');
          console.log(
            `[BORDER_WS] ${targetCurrency}: ws-disconnected (currentPrice=${currentPrice}, sell=${sellPrice}, buy=${buyPrice})`
          );
        } else if (currentPrice >= sellPrice) {
          tab.classList.add('ready-to-sell');
          console.log(
            `[BORDER_WS] ${targetCurrency}: ready-to-sell (YELLOW) (current=${currentPrice} >= sell=${sellPrice})`
          );
        } else if (currentPrice <= buyPrice) {
          tab.classList.add('ready-to-buy');
          console.log(
            `[BORDER_WS] ${targetCurrency}: ready-to-buy (RED) (current=${currentPrice} <= buy=${buyPrice})`
          );
        } else {
          tab.classList.add('price-normal');
          console.log(
            `[BORDER_WS] ${targetCurrency}: price-normal (GREEN) (buy=${buyPrice} < current=${currentPrice} < sell=${sellPrice})`
          );
        }
      } else {
        console.warn('[BORDER_WS] Вкладка для валюты не найдена:', targetCurrency);
      }
    }
  } catch (e) {
    console.error('apply diag color failed', e);
  }
}