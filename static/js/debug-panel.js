/**
 * debug-panel.js
 *
 * Отладочная панель и watcher за сменой базовой валюты.
 * Вынесено из static/app.js, чтобы уменьшить размер основного файла.
 *
 * Экспортирует:
 * - installDebugPanel() -> ставит window.uiDebugLog
 * - installCurrencyWatcher(getCurrencyFn) -> логирует смену валюты + stack
 */

export function installDebugPanel() {
  // Не переопределяем если уже есть
  if (window.uiDebugLog) return window.uiDebugLog;

  window.__diagLogs = window.__diagLogs || [];

  window.uiDebugLog = function (msg, level = 'DEBUG') {
    try {
      if (!window.__uiDebugPanel) {
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
        panel.style.transform = 'translateX(100%)';

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

        tab.onmouseenter = () => {
          tab.style.background = 'rgba(74,158,255,0.2)';
        };
        tab.onmouseleave = () => {
          tab.style.background = 'rgba(18,18,18,0.95)';
        };

        let isOpen = false;
        tab.onclick = () => {
          isOpen = !isOpen;
          if (isOpen) {
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
        clearBtn.onclick = () => {
          panel.querySelector('.dbg-body').innerHTML = '';
        };

        const copyBtn = document.createElement('button');
        copyBtn.textContent = 'Copy';
        copyBtn.style.background = '#1f6feb';
        copyBtn.style.color = '#fff';
        copyBtn.style.border = 'none';
        copyBtn.style.padding = '4px 8px';
        copyBtn.style.borderRadius = '4px';
        copyBtn.style.cursor = 'pointer';
        copyBtn.onclick = () => {
          const text = [...panel.querySelectorAll('.dbg-row')]
            .map((n) => n.textContent)
            .join('\n');
          navigator.clipboard?.writeText(text).then(() => {
            copyBtn.textContent = 'Copied!';
            setTimeout(() => (copyBtn.textContent = 'Copy'), 800);
          });
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

      const body = window.__uiDebugPanel.querySelector('.dbg-body');
      body.insertBefore(row, body.firstChild);
      window.__uiDebugBuffer.unshift(row.textContent);
      if (window.__uiDebugBuffer.length > 400) {
        window.__uiDebugBuffer.pop();
        const nodes = body.querySelectorAll('.dbg-row');
        if (nodes.length > 400) nodes[nodes.length - 1].remove();
      }
      return true;
    } catch (e) {
      console.error('uiDebugLog err', e);
      return false;
    }
  };

  return window.uiDebugLog;
}

export function installCurrencyWatcher(getCurrencyFn) {
  try {
    if (typeof getCurrencyFn !== 'function') {
      console.warn('[currency-watcher] getCurrencyFn is not a function');
      return;
    }

    window.__lastObservedBaseCurrency = getCurrencyFn();
    setInterval(() => {
      try {
        const current = getCurrencyFn();
        if (window.__lastObservedBaseCurrency !== current) {
          const from = window.__lastObservedBaseCurrency;
          const to = current;
          window.__lastObservedBaseCurrency = current;
          const stack = new Error().stack || '';
          const shortStack = stack
            .split('\n')
            .slice(2, 7)
            .map((s) => s.trim())
            .join(' | ');
          if (window.uiDebugLog) window.uiDebugLog(`currentBaseCurrency changed ${from} -> ${to}  stack: ${shortStack}`, 'CHANGE');
          else console.debug('currentBaseCurrency changed', from, '->', to);
        }
      } catch (_) {
        /* noop */
      }
    }, 400);
  } catch (e) {
    console.warn('currency watcher not started', e);
  }
}
