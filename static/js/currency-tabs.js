/**
 * Currency tabs rendering logic.
 * Migrated out of `static/app.js` incrementally.
 */

export function renderCurrencyTabs(
  list,
  {
    $, // id helper
    logDbg,
    activeCycles,
    getCurrentBaseCurrency,
    setCurrentBaseCurrency, // (code, {setByUser?:boolean}) => void
    getCurrencySetByUser,
    switchBaseCurrency, // (code) => void
    toggleTradingPermission, // (code, event) => void
    updatePairNameUI,
    updateTabsPermissionsUI,
    forceApplyInactiveColors,
    doc = document,
    log = console
  } = {}
) {
  log?.log?.('[RENDER_TABS] 🎯 renderCurrencyTabs вызвана, list:', list);

  if (typeof $ !== 'function') {
    log?.error?.('[renderCurrencyTabs] missing dependency: $');
    return;
  }
  if (typeof logDbg !== 'function') {
    log?.error?.('[renderCurrencyTabs] missing dependency: logDbg');
    return;
  }
  if (typeof getCurrentBaseCurrency !== 'function' || typeof setCurrentBaseCurrency !== 'function') {
    log?.error?.('[renderCurrencyTabs] missing dependency: get/setCurrentBaseCurrency');
    return;
  }
  if (typeof getCurrencySetByUser !== 'function') {
    log?.error?.('[renderCurrencyTabs] missing dependency: getCurrencySetByUser');
    return;
  }
  if (typeof switchBaseCurrency !== 'function') {
    log?.error?.('[renderCurrencyTabs] missing dependency: switchBaseCurrency');
    return;
  }
  if (typeof toggleTradingPermission !== 'function') {
    log?.error?.('[renderCurrencyTabs] missing dependency: toggleTradingPermission');
    return;
  }

  const cont = $('currencyTabsContainer');
  if (!cont) {
    log?.error?.('[RENDER_TABS] ❌ Элемент currencyTabsContainer НЕ НАЙДЕН!');
    return;
  }

  log?.log?.('[RENDER_TABS] ✅ Контейнер найден:', cont);
  cont.innerHTML = '';

  const arr = Array.isArray(list) ? list : [];
  log?.log?.('[RENDER_TABS] 📊 Массив валют, длина:', arr.length, 'данные:', arr);
  logDbg('renderCurrencyTabs raw len=' + arr.length);

  let norm = arr
    .map((c) => {
      if (typeof c === 'string') return { code: c.toUpperCase(), symbol: '' };
      return { code: (c.code || '').toUpperCase(), symbol: (c.symbol || '').trim() };
    })
    .filter((o) => o.code);

  log?.log?.('[RENDER_TABS] 📋 Нормализованные валюты:', norm);

  if (!norm.length) {
    log?.warn?.('[RENDER_TABS] ⚠️ Список пуст, загружаем дефолтные валюты');
    logDbg('список пуст – добавляю дефолтные');
    norm = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'AVAX', 'DOT', 'MATIC', 'LINK'].map((c) => ({
      code: c,
      symbol: ''
    }));
    log?.log?.('[RENDER_TABS] 📋 Дефолтные валюты загружены:', norm);
  }

  const currentBaseCurrency = getCurrentBaseCurrency();
  const currencySetByUser = getCurrencySetByUser();

  const codes = new Set(norm.map((o) => o.code));
  log?.log?.('[DEBUG] renderCurrencyTabs: currentBaseCurrency:', currentBaseCurrency, 'currencySetByUser:', currencySetByUser, 'codes:', Array.from(codes));

  if ((!currentBaseCurrency || !codes.has(currentBaseCurrency)) && !currencySetByUser) {
    const oldCurrency = currentBaseCurrency;
    const nextCurrency = norm[0].code;

    setCurrentBaseCurrency(nextCurrency, { setByUser: false });
    log?.log?.('[DEBUG] renderCurrencyTabs: changed currentBaseCurrency from', oldCurrency, 'to', nextCurrency);
    logDbg('установлена активная валюта: ' + nextCurrency);
  }

  const finalCurrentBaseCurrency = getCurrentBaseCurrency();

  norm.forEach((cur) => {
    log?.log?.('[RENDER_TABS] 🔨 Создаём вкладку для валюты:', cur.code);

    const el = doc.createElement('div');
    el.className = 'tab-item' + (cur.code === finalCurrentBaseCurrency ? ' active' : '');
    el.dataset.code = cur.code;

    const permBtn = doc.createElement('span');
    permBtn.className = 'perm-indicator';
    permBtn.title = 'Включить/выключить торговлю';
    permBtn.onclick = (e) => toggleTradingPermission(cur.code, e);

    el.innerHTML = `<span class='code-label'>${cur.code}</span>${cur.symbol ? `<span class='symbol-label'>${cur.symbol}</span>` : ''}`;
    el.insertBefore(permBtn, el.firstChild);

    // apply blue text immediately for inactive cycles
    const cycleActive = activeCycles?.[cur.code];
    const isCycleInactive = cycleActive === false;

    if (isCycleInactive) {
      el.classList.add('inactive-currency');
      const codeLabel = el.querySelector('.code-label');
      if (codeLabel) {
        const isActive = el.classList.contains('active');
        const blueColor = isActive ? '#64B5F6' : '#2196F3';
        codeLabel.style.cssText = `color: ${blueColor} !important; text-shadow: 0 0 2px rgba(33,150,243,0.5) !important;`;
        codeLabel.setAttribute(
          'style',
          `color: ${blueColor} !important; text-shadow: 0 0 2px rgba(33,150,243,0.5) !important;`
        );
        log?.log?.(
          `[RENDER_TAB] ${cur.code}: создана вкладка с НЕАКТИВНЫМ циклом, СИНИЙ цвет ${blueColor} (cycleActive=${cycleActive})`
        );
      }
    } else {
      log?.log?.(`[RENDER_TAB] ${cur.code}: создана вкладка с АКТИВНЫМ циклом (cycleActive=${cycleActive})`);
    }

    el.onclick = () => switchBaseCurrency(cur.code);

    cont.appendChild(el);
    log?.log?.('[RENDER_TABS] ✅ Вкладка добавлена в контейнер:', cur.code);
  });

  log?.log?.('[RENDER_TABS] 🎉 Все вкладки созданы, всего:', norm.length);

  if (typeof updatePairNameUI === 'function') updatePairNameUI();
  if (typeof updateTabsPermissionsUI === 'function') updateTabsPermissionsUI();

  if (typeof forceApplyInactiveColors === 'function') {
    setTimeout(() => forceApplyInactiveColors(), 50);
  }
}
