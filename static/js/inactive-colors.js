/**
 * Helpers for applying "inactive cycle" blue appearance to currency tabs.
 * Migrated out of `static/app.js` incrementally.
 */

export function forceApplyInactiveColors({
  activeCycles,
  doc = document,
  win = window,
  log = console
} = {}) {
  log?.log?.('[FORCE_COLOR] Принудительное применение синего цвета для валют с неактивным циклом');

  const cont = doc.getElementById('currencyTabsContainer');
  if (!cont) {
    log?.warn?.('[FORCE_COLOR] currencyTabsContainer не найден');
    return;
  }

  const tabs = cont.querySelectorAll('.tab-item');
  let processedCount = 0;

  tabs.forEach((tab) => {
    const code = tab.dataset.code;
    if (!code) return;

    const cycleActive = activeCycles?.[code];
    const isCycleInactive = cycleActive === false; // blue only when explicitly false

    log?.log?.(`[FORCE_COLOR] ${code}: cycleActive=${cycleActive}, isCycleInactive=${isCycleInactive}`);

    if (isCycleInactive) {
      const codeLabel = tab.querySelector('.code-label');
      if (codeLabel) {
        const isActive = tab.classList.contains('active');
        const blueColor = isActive ? '#64B5F6' : '#2196F3';
        const shadow = isActive ? '0 0 3px rgba(66,165,245,0.6)' : '0 0 2px rgba(33,150,243,0.5)';

        const styleText = `color: ${blueColor} !important; text-shadow: ${shadow} !important;`;
        codeLabel.style.cssText = styleText;
        codeLabel.setAttribute('style', styleText);

        tab.classList.add('inactive-currency');

        const finalColor = win.getComputedStyle(codeLabel).color;
        log?.log?.(`[FORCE_COLOR] ${code}: установлен синий цвет ${blueColor}, computed="${finalColor}"`);
        processedCount++;
      } else {
        log?.warn?.(`[FORCE_COLOR] ${code}: .code-label не найден!`);
      }
    } else {
      tab.classList.remove('inactive-currency');
      const codeLabel = tab.querySelector('.code-label');
      if (codeLabel && codeLabel.hasAttribute('style')) {
        const style = codeLabel.getAttribute('style');
        if (style && (style.includes('color') || style.includes('text-shadow'))) {
          codeLabel.removeAttribute('style');
          log?.log?.(`[FORCE_COLOR] ${code}: убран inline-стиль (цикл активен)`);
        }
      }
    }
  });

  log?.log?.(`[FORCE_COLOR] Обработано валют с неактивным циклом: ${processedCount}`);
}
