/**
 * autotrade-ui.js
 *
 * Вынесено из static/app.js для уменьшения размера основного файла.
 * Содержит обновление UI автотрейда и диагностическую подсветку.
 */

export function createAutotradeUI({
  $,
  formatPrice,
  setGlobalBuyPrice,
  setGlobalSellPrice,
  updateVisualIndicatorScale,
  updateTabsPermissionsUI,
  documentRef = document
}) {
  if (!$ || !formatPrice || !setGlobalBuyPrice || !setGlobalSellPrice) {
    throw new Error('createAutotradeUI: missing required dependencies');
  }

  const state = {
    globalActiveStep: null,
    activeSteps: {},
    diagnosticDecisions: {},
    sellPrices: {},
    buyPrices: {},
    currentPrices: {},
    activeCycles: {}
  };

  function applyDiagnosticColoring(levels) {
    try {
      const diag = levels.diagnostic_decision;
      const container = documentRef.querySelector('.indicator-card');
      if (!container) return;

      container.style.transition = 'box-shadow 160ms ease, border-color 160ms ease';

      // Preferred: numeric band logic
      const currentPrice = parseFloat(levels.current_price);
      const sellPrice = levels.sell_price !== null && levels.sell_price !== undefined ? parseFloat(levels.sell_price) : null;
      const buyPrice = levels.next_buy_price !== null && levels.next_buy_price !== undefined ? parseFloat(levels.next_buy_price) : null;

      let applied = false;

      if (!Number.isNaN(currentPrice) && sellPrice !== null && !Number.isNaN(sellPrice) && currentPrice >= sellPrice) {
        container.style.border = '3px solid #28a745';
        container.style.boxShadow = '0 6px 18px rgba(40,167,69,0.12)';
        applied = true;
      } else if (!Number.isNaN(currentPrice) && buyPrice !== null && !Number.isNaN(buyPrice) && currentPrice <= buyPrice) {
        container.style.border = '3px solid #dc3545';
        container.style.boxShadow = '0 6px 18px rgba(220,53,69,0.12)';
        applied = true;
      } else if (!Number.isNaN(currentPrice) && (sellPrice !== null || buyPrice !== null)) {
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
    } catch (e) {
      console.error('apply diag color failed', e);
    }
  }

  function updateAutoTradeLevels(levels, currentBaseCurrency) {
    if (!levels) return;

    setGlobalBuyPrice(levels.next_buy_price);
    setGlobalSellPrice(levels.sell_price);

    state.globalActiveStep = levels.active_step;

    // per-currency storage
    if (currentBaseCurrency) {
      state.activeSteps[currentBaseCurrency] = levels.active_step;
      state.diagnosticDecisions[currentBaseCurrency] = levels.diagnostic_decision;
      state.sellPrices[currentBaseCurrency] = levels.sell_price;
      state.buyPrices[currentBaseCurrency] = levels.next_buy_price;
      state.currentPrices[currentBaseCurrency] = levels.current_price;
      state.activeCycles[currentBaseCurrency] = levels.active_cycle;
    }

    if (typeof updateTabsPermissionsUI === 'function') updateTabsPermissionsUI();

    // cycle status
    const activeEl = $('autotradeCycleActive');
    if (activeEl) {
      activeEl.textContent = levels.active_cycle ? 'Активен' : 'Неактивен';
      activeEl.className = 'value ' + (levels.active_cycle ? 'active' : 'inactive');
    }

    // current step
    const stepEl = $('autotradeCurrentStep');
    if (stepEl) {
      if (levels.active_step !== null && levels.total_steps !== null) {
        stepEl.textContent = `${levels.active_step} / ${levels.total_steps}`;
      } else {
        stepEl.textContent = '-';
      }
    }

    // prices
    const priceFields = {
      autotradePriceCurrent: levels.current_price,
      autotradePriceStart: levels.start_price,
      autotradePriceBreakeven: levels.breakeven_price,
      autotradePriceLastBuy: levels.last_buy_price,
      autotradePriceSell: levels.sell_price,
      autotradePriceNextBuy: levels.next_buy_price
    };

    for (const [id, value] of Object.entries(priceFields)) {
      const el = $(id);
      if (el) el.textContent = value === null || value === undefined ? '-' : formatPrice(value);
    }

    // orderbook level
    const orderbookLevelEl = $('autotradeOrderbookLevel');
    if (orderbookLevelEl) {
      orderbookLevelEl.textContent =
        levels.orderbook_level !== null && levels.orderbook_level !== undefined ? levels.orderbook_level : '-';
    }

    // growth pct
    const growthEl = $('autotradeGrowthPct');
    if (growthEl) {
      if (levels.current_growth_pct !== null && levels.current_growth_pct !== undefined) {
        const pct = levels.current_growth_pct;
        growthEl.textContent = pct.toFixed(2) + '%';
        growthEl.className = 'value ' + (pct >= 0 ? 'positive' : 'negative');
      } else {
        growthEl.textContent = '-';
        growthEl.className = 'value';
      }
    }

    // growth from last buy
    const growthFromLastBuyEl = $('autotradeGrowthFromLastBuy');
    if (growthFromLastBuyEl) {
      if (levels.growth_from_last_buy_pct !== null && levels.growth_from_last_buy_pct !== undefined) {
        const pct = levels.growth_from_last_buy_pct;
        growthFromLastBuyEl.textContent = pct.toFixed(2) + '%';
        growthFromLastBuyEl.className = 'value ' + (pct >= 0 ? 'positive' : 'negative');
      } else {
        growthFromLastBuyEl.textContent = '-';
        growthFromLastBuyEl.className = 'value';
      }
    }

    // invested
    const investedEl = $('autotradeInvested');
    if (investedEl) investedEl.textContent = levels.invested_usd !== null ? levels.invested_usd.toFixed(2) + ' USDT' : '-';

    // base volume + locked breakdown
    const volumeEl = $('autotradeBaseVolume');
    let totalBaseVolume = null;
    if (volumeEl) {
      if (levels.real_balance && levels.real_balance.total !== undefined) {
        const total = levels.real_balance.total;
        const available = levels.real_balance.available;
        const locked = levels.real_balance.locked;
        totalBaseVolume = total;

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

    // base volume in USDT
    const volumeUSDTEl = $('autotradeBaseVolumeUSDT');
    if (volumeUSDTEl) {
      const currentPrice = levels.current_price;
      if (totalBaseVolume !== null && totalBaseVolume > 0 && currentPrice !== null && currentPrice !== undefined && currentPrice > 0) {
        const equivalent = totalBaseVolume * parseFloat(currentPrice);
        volumeUSDTEl.textContent = equivalent.toFixed(2) + ' USDT';
      } else {
        volumeUSDTEl.textContent = '-';
      }
    }

    if (typeof updateVisualIndicatorScale === 'function') {
      updateVisualIndicatorScale(levels, { $, formatPrice });
    }

    applyDiagnosticColoring(levels);
  }

  return {
    state,
    updateAutoTradeLevels
  };
}
