/**
 * utils.js - Утилитарные функции для mTrade
 * Простые хелперы без зависимостей от глобального состояния
 */

/**
 * Логирование для отладки
 * @param {string} m - Сообщение
 */
export function logDbg(m) {
  try {
    if (!window.__diagLogs) window.__diagLogs = [];
    window.__diagLogs.push(Date.now() + ': ' + m);
    if (window.__diagLogs.length > 200) window.__diagLogs.shift();
  } catch (_) { /* noop */ }
  console.log('[DBG]', m);
}

/**
 * Форматирование цены с учётом точности
 * @param {number|string} v - Значение
 * @param {number} precision - Точность (количество знаков после запятой)
 * @returns {string} Отформатированная цена
 */
export function formatPrice(v, precision) {
  const n = parseFloat(v);
  if (isNaN(n)) return '-';
  if (n === 0) return '0';
  
  // Используем указанную точность или автоматическую
  if (precision !== undefined && precision >= 0) {
    return n.toFixed(precision);
  }
  
  if (n < 0.0001 && n > 0) return n.toExponential(4);
  if (n >= 1000) return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 8 });
  return n.toFixed(8).replace(/\.0+$/, '').replace(/0+$/, '');
}

/**
 * Быстрый доступ к элементу по ID
 * @param {string} id - ID элемента
 * @returns {HTMLElement|null} Элемент или null
 */
export function $(id) {
  return document.getElementById(id);
}

/**
 * Форматирование времени работы сервера
 * @param {number} sec - Количество секунд
 * @returns {string} Отформатированное время (например, "1d 12:34:56" или "12:34:56")
 */
export function formatUptime(sec) {
  sec = Math.max(0, Math.floor(sec || 0));
  const d = Math.floor(sec / 86400); sec %= 86400;
  const h = Math.floor(sec / 3600); sec %= 3600;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  const pad = n => n.toString().padStart(2, '0');
  if (d > 0) return `${d}d ${pad(h)}:${pad(m)}:${pad(s)}`;
  return `${pad(h)}:${pad(m)}:${pad(s)}`;
}
