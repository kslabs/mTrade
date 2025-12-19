/**
 * Logic for currency tabs UI badges and border/status styling.
 * Migrated out of `static/app.js` incrementally.
 */

/**
 * Updates UI indicators (permission toggle state, active step badge, diagnostic classes,
 * and border readiness classes) for each currency tab.
 *
 * Dependencies are injected to keep module decoupled from globals.
 */
export function updateTabsPermissionsUI(
  {
    $, // element by id helper
    activeSteps,
    diagnosticDecisions,
    sellPrices,
    buyPrices,
    currentPrices,
    activeCycles,
    getTradingPermissions, // () => object
    log = console
  } = {}
) {
  if (typeof $ !== 'function') {
    log?.error?.('[updateTabsPermissionsUI] missing dependency: $');
    return;
  }

  const cont = $('currencyTabsContainer');
  if (!cont) return;

  const tabs = cont.querySelectorAll('.tab-item');
  tabs.forEach((tab) => {
    const code = tab.dataset.code;
    if (!code) return;

    const activeStep = activeSteps?.[code];
    const decision = diagnosticDecisions?.[code];
    const permissions = typeof getTradingPermissions === 'function' ? getTradingPermissions() : null;
    const permissionEnabled = permissions ? permissions[code] : undefined;

    // Update permission button on/off
    const permBtn = tab.querySelector('.perm-indicator');
    if (permBtn) {
      permBtn.classList.toggle('on', permissionEnabled === true);
      permBtn.classList.toggle('off', permissionEnabled !== true); // undefined/null/false = off
      permBtn.title =
        permissionEnabled === true
          ? 'Торговля разрешена (клик для запрета)'
          : 'Торговля запрещена (клик для разрешения)';
    }

    // Remove existing step badge
    const oldIndicator = tab.querySelector('.step-indicator');
    if (oldIndicator) oldIndicator.remove();

    // Add step badge
    if (activeStep !== undefined && activeStep >= 0) {
      const indicator = document.createElement('span');
      indicator.className = 'step-indicator';
      indicator.textContent = activeStep;
      indicator.title = `Активный шаг: ${activeStep}`;
      tab.appendChild(indicator);
    }

    // Diagnostic decision classes
    tab.classList.remove('decision-buy', 'decision-sell', 'decision-wait');
    if (decision === 'BUY') tab.classList.add('decision-buy');
    else if (decision === 'SELL') tab.classList.add('decision-sell');
    else if (decision === 'WAIT') tab.classList.add('decision-wait');

    // Status border classes
    tab.classList.remove('ready-to-sell', 'ready-to-buy', 'ws-disconnected', 'inactive-currency');

    const currentPrice = currentPrices?.[code];
    const sellPrice = sellPrices?.[code];
    const buyPrice = buyPrices?.[code];

    const cycleActive = activeCycles?.[code];
    const isCycleInactive = cycleActive === false; // blue only when explicitly false

    const hasValidPrice = currentPrice !== undefined && currentPrice !== null && currentPrice > 0;
    const hasSellPrice = sellPrice !== undefined && sellPrice !== null && sellPrice > 0;
    const hasBuyPrice = buyPrice !== undefined && buyPrice !== null && buyPrice > 0;

    if (!hasValidPrice || !hasSellPrice || !hasBuyPrice) {
      tab.classList.add('ws-disconnected');
      log?.log?.(
        `[BORDER] ${code}: ws-disconnected (currentPrice=${currentPrice}, sell=${sellPrice}, buy=${buyPrice})`
      );
    } else if (currentPrice >= sellPrice) {
      tab.classList.add('ready-to-sell');
      log?.log?.(`[BORDER] ${code}: ready-to-sell (current=${currentPrice} >= sell=${sellPrice})`);
    } else if (currentPrice <= buyPrice) {
      tab.classList.add('ready-to-buy');
      log?.log?.(`[BORDER] ${code}: ready-to-buy (current=${currentPrice} <= buy=${buyPrice})`);
    } else {
      log?.log?.(
        `[BORDER] ${code}: normal (buy=${buyPrice} < current=${currentPrice} < sell=${sellPrice})`
      );
    }

    // Apply blue text for inactive cycles (does not affect border)
    if (isCycleInactive) {
      tab.classList.add('inactive-currency');
      const codeLabel = tab.querySelector('.code-label');
      if (codeLabel) {
        const isActive = tab.classList.contains('active');
        const blueColor = isActive ? '#64B5F6' : '#2196F3';
        const shadow = isActive ? '0 0 3px rgba(66,165,245,0.6)' : '0 0 2px rgba(33,150,243,0.5)';
        const styleText = `color: ${blueColor} !important; text-shadow: ${shadow} !important;`;
        codeLabel.style.cssText = styleText;
        codeLabel.setAttribute('style', styleText);
      }
    } else {
      const codeLabel = tab.querySelector('.code-label');
      if (codeLabel && codeLabel.hasAttribute('style')) {
        const style = codeLabel.getAttribute('style');
        if (style && (style.includes('color') || style.includes('text-shadow'))) {
          codeLabel.removeAttribute('style');
        }
      }
    }
  });

  // Optional delayed re-apply for inactive cycles (keeps old behavior)
  setTimeout(() => {
    tabs.forEach((tab) => {
      const code = tab.dataset.code;
      if (!code) return;
      const cycleActive = activeCycles?.[code];
      const isCycleInactive = cycleActive === false;
      if (!isCycleInactive) return;

      const codeLabel = tab.querySelector('.code-label');
      if (!codeLabel) return;

      const isActive = tab.classList.contains('active');
      const blueColor = isActive ? '#64B5F6' : '#2196F3';
      codeLabel.style.cssText = `color: ${blueColor} !important;`;
      log?.log?.(`[DELAYED_STYLE] ${code}: повторно установлен синий цвет через 100ms (cycleActive=${cycleActive})`);
    });
  }, 100);
}
