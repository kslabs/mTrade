/**
 * Trading permissions fetch/toggle logic.
 * Migrated out of `static/app.js` incrementally.
 */

export async function loadTradingPermissions({
  api,
  setTradingPermissions, // (permissionsObj) => void
  refreshTabsUI, // () => void
  forceApplyInactiveColors, // () => void
  log = console
} = {}) {
  log?.log?.('[DEBUG] loadTradingPermissions called');

  if (!api?.getTradingPermissions) {
    log?.error?.('[loadTradingPermissions] missing dependency: api.getTradingPermissions');
    return;
  }
  if (typeof setTradingPermissions !== 'function') {
    log?.error?.('[loadTradingPermissions] missing dependency: setTradingPermissions');
    return;
  }
  if (typeof refreshTabsUI !== 'function') {
    log?.error?.('[loadTradingPermissions] missing dependency: refreshTabsUI');
    return;
  }

  try {
    const d = await api.getTradingPermissions();
    log?.log?.('[DEBUG] loadTradingPermissions response:', d);

    if (d?.success && d.permissions) {
      setTradingPermissions(d.permissions);
      refreshTabsUI();
      if (typeof forceApplyInactiveColors === 'function') {
        setTimeout(() => forceApplyInactiveColors(), 50);
      }
    } else {
      log?.warn?.('[WARN] loadTradingPermissions failed:', d?.error || 'unknown');
    }
  } catch (e) {
    log?.error?.('[ERROR] loadTradingPermissions exception:', e);
  }
}

export async function toggleTradingPermission(code, event, {
  api,
  getTradingPermissions, // () => object
  setTradingPermission, // (code, value) => void
  refreshTabsUI, // () => void
  forceApplyInactiveColors, // () => void
  alertFn = (msg) => alert(msg),
  log = console
} = {}) {
  if (event) event.stopPropagation();
  if (!code) return;

  if (!api?.toggleTradingPermission) {
    log?.error?.('[toggleTradingPermission] missing dependency: api.toggleTradingPermission');
    return;
  }
  if (typeof getTradingPermissions !== 'function') {
    log?.error?.('[toggleTradingPermission] missing dependency: getTradingPermissions');
    return;
  }
  if (typeof setTradingPermission !== 'function') {
    log?.error?.('[toggleTradingPermission] missing dependency: setTradingPermission');
    return;
  }
  if (typeof refreshTabsUI !== 'function') {
    log?.error?.('[toggleTradingPermission] missing dependency: refreshTabsUI');
    return;
  }

  const permissions = getTradingPermissions() || {};
  const currentState = permissions[code] === true;
  const newState = !currentState;

  log?.log?.(`[DEBUG] toggleTradingPermission: ${code} ${currentState} -> ${newState}`);

  try {
    const d = await api.toggleTradingPermission(code, newState);

    if (d?.success) {
      setTradingPermission(code, newState);
      log?.log?.(`[SUCCESS] Торговля для ${code}: ${newState ? 'разрешена' : 'запрещена'}`);
      refreshTabsUI();
      if (typeof forceApplyInactiveColors === 'function') {
        setTimeout(() => forceApplyInactiveColors(), 50);
      }
    } else {
      log?.error?.('[ERROR] toggleTradingPermission failed:', d?.error);
      alertFn('Ошибка: ' + (d?.error || 'Не удалось изменить разрешение'));
    }
  } catch (e) {
    log?.error?.('[ERROR] toggleTradingPermission exception:', e);
    alertFn('Ошибка при изменении разрешения: ' + e);
  }
}
