/**
 * Trade Logs Manager - Управление отображением логов торговли
 * Переключение между таблицей безубыточности и логами
 */

// DIAG: пометка о загрузке файла
console.debug('[TradeLogsManager] script loaded');
if(window.uiDebugLog) window.uiDebugLog('trade-logs-manager loaded');

class TradeLogsManager {
    constructor() {
        // DIAG: экземпляр создаётся
        console.debug('[TradeLogsManager] constructor');
        if(window.uiDebugLog) window.uiDebugLog('TradeLogsManager constructor');

        this.currentView = 'breakeven'; // 'breakeven' или 'logs'
        this.logs = [];
        this.refreshInterval = null;
        this.AUTO_REFRESH_INTERVAL = 5000; // 5 секунд
    }

    /**
     * Инициализация менеджера логов
     */
    init() {
        console.debug('[TradeLogsManager] Инициализация');
        if(window.uiDebugLog) window.uiDebugLog('TradeLogsManager init');
        this.injectToggleStyles();
        this.injectLogsStyles();
        this.setupEventListeners();
    }

    // Получить активную базовую валюту из доступных источников
    getActiveBaseCurrency() {
        // Prefer top-level identifier if exists, otherwise fallback to window property
        try{
            if (typeof currentBaseCurrency !== 'undefined' && currentBaseCurrency) return currentBaseCurrency;
        }catch(e){ /* ignored */ }
        if (window.currentBaseCurrency) return window.currentBaseCurrency;
        // compatibility: older UI state reference
        if (window.app && window.app.state && window.app.state.activeCurrency) return window.app.state.activeCurrency;
        return null;
    }

    /**
     * Настроить обработчики событий
     */
    setupEventListeners() {
        // Переключатель вида
        const btnBreakeven = document.getElementById('btn-view-breakeven');
        const btnLogs = document.getElementById('btn-view-logs');

        if (btnBreakeven) {
            btnBreakeven.addEventListener('click', () => this.switchView('breakeven'));
        }

        if (btnLogs) {
            btnLogs.addEventListener('click', () => this.switchView('logs'));
        }

        // Кнопки управления логами
        const btnRefresh = document.getElementById('btn-refresh-logs');
        const btnClear = document.getElementById('btn-clear-logs');

        if (btnRefresh) {
            btnRefresh.addEventListener('click', () => this.refreshLogs());
        }

        if (btnClear) {
            btnClear.addEventListener('click', () => this.clearLogs());
        }
    }

    /**
     * Переключить вид (таблица/логи)
     */
    switchView(view) {
        if (this.currentView === view) return;

        this.currentView = view;
        console.debug(`[TradeLogsManager] Переключение на ${view}`);
        if(window.uiDebugLog) window.uiDebugLog(`switchView -> ${view}`);

        const btnBreakeven = document.getElementById('btn-view-breakeven');
        const btnLogs = document.getElementById('btn-view-logs');
        const breakevenTable = document.querySelector('.breakeven-table-content');
        const logsContainer = document.getElementById('trade-logs-container');
        const paramsEditor = document.querySelector('.trade-params-editor');
        const saveBtn = document.getElementById('saveParamsBtn');

        if (view === 'breakeven') {
            // Показать таблицу и параметры, скрыть логи
            if (btnBreakeven) btnBreakeven.classList.add('active');
            if (btnLogs) btnLogs.classList.remove('active');
            if (breakevenTable) breakevenTable.style.display = 'block';
            if (logsContainer) logsContainer.style.display = 'none';
            if (paramsEditor) paramsEditor.style.display = 'block';
            if (saveBtn) saveBtn.style.display = 'inline-block';

            // Остановить авто-обновление логов
            this.stopAutoRefresh();
        } else {
            // Показать логи, скрыть таблицу и параметры
            if (btnBreakeven) btnBreakeven.classList.remove('active');
            if (btnLogs) btnLogs.classList.add('active');
            if (breakevenTable) breakevenTable.style.display = 'none';
            if (logsContainer) logsContainer.style.display = 'block';
            if (paramsEditor) paramsEditor.style.display = 'none';
            if (saveBtn) saveBtn.style.display = 'none';

            // Загрузить и запустить авто-обновление логов (по текущей валюте)
            console.debug('[TradeLogsManager] About to load logs, currentBaseCurrency:', window.currentBaseCurrency);
            if(window.uiDebugLog) window.uiDebugLog('About to load logs, baseCurrency=' + (window.currentBaseCurrency || 'null'));
            console.debug('[TradeLogsManager] window.app?.state?.activeCurrency:', window.app?.state?.activeCurrency);
            const currencyToLoad = this.getActiveBaseCurrency() || 'ETH'; // fallback to ETH
            console.debug('[TradeLogsManager] Loading logs for currency:', currencyToLoad);
            if(window.uiDebugLog) window.uiDebugLog('Loading logs for currency: '+currencyToLoad);
            this.loadLogs(currencyToLoad);
            this.startAutoRefresh();
        }
    }

    /**
     * Загрузить логи с сервера
     */
    async loadLogs(currency = null) {
        console.debug('[TradeLogsManager] loadLogs called with currency:', currency);
        if(window.uiDebugLog) window.uiDebugLog('loadLogs called with currency:'+String(currency));

        try {
            const params = new URLSearchParams({
                limit: '100',
                formatted: '1'
            });

            if (currency) {
                params.append('currency', currency);
                console.debug('[TradeLogsManager] Using provided currency:', currency);
                if(window.uiDebugLog) window.uiDebugLog('Using provided currency: '+currency);
            } else {
                console.log('[TradeLogsManager] No currency provided, will try to auto-detect');
            }

            const url = `/api/trade/logs?${params}`;
            console.debug('[TradeLogsManager] Fetching URL:', url);
            if(window.uiDebugLog) window.uiDebugLog('Fetching logs URL: '+url);

            const response = await fetch(url);
            console.debug('[TradeLogsManager] Response status:', response.status);
            if(window.uiDebugLog) window.uiDebugLog('logs response status: '+response.status);

            const data = await response.json();
            console.debug('[TradeLogsManager] Response data:', data);
            if(window.uiDebugLog) window.uiDebugLog('response currency='+String(data.currency)+ ' logs='+ (data.logs?data.logs.length:0));

            if (data.success) {
                this.logs = data.logs || [];
                console.debug('[TradeLogsManager] Loaded', this.logs.length, 'logs');
                if(window.uiDebugLog) window.uiDebugLog('Loaded ' + this.logs.length + ' logs for ' + (currency || window.currentBaseCurrency));
                this.renderLogs();
                await this.loadStats(currency);
            } else {
                console.error('[TradeLogsManager] Ошибка загрузки логов:', data.error);
                if(window.uiDebugLog) window.uiDebugLog('Ошибка загрузки логов: '+(data.error||'unknown'));
                this.showError('Ошибка загрузки логов: ' + (data.error || 'неизвестная ошибка'));
            }
        } catch (error) {
            console.error('[TradeLogsManager] Ошибка загрузки логов:', error);
            if(window.uiDebugLog) window.uiDebugLog('Ошибка связи с сервером: '+(error && error.message?error.message:String(error)));
            this.showError('Ошибка связи с сервером: ' + error.message);
        }
    }

    /**
     * Загрузить статистику
     */
    async loadStats(currency = null) {
        try {
            const params = currency ? `?currency=${currency}` : '';
            const response = await fetch(`/api/trade/logs/stats${params}`);
            const data = await response.json();

            if (data.success) {
                this.updateStats(data.stats);
            }
        } catch (error) {
            console.error('[TradeLogsManager] Ошибка загрузки статистики:', error);
        }
    }

    /**
     * Обновить отображение статистики
     */
    updateStats(stats) {
        // Обновляем счётчик записей
        const countElement = document.getElementById('logs-count');
        if (countElement) {
            countElement.textContent = `${stats.total_entries} записей`;
        }

        // Обновляем статистику (пока моки, позже будем брать из API)
        const pnlEl = document.getElementById('stat-pnl');
        const equityEl = document.getElementById('stat-equity');
        const startEl = document.getElementById('stat-start');
        const deltaEqEl = document.getElementById('stat-delta-eq');
        const durationEl = document.getElementById('stat-duration');

        if (pnlEl) {
            const pnl = stats.total_pnl || 0;
            pnlEl.textContent = pnl.toFixed(3);
            pnlEl.style.color = pnl >= 0 ? '#2ecc71' : '#e74c3c';
        }

        if (equityEl) {
            // Пока показываем 0, позже добавим реальные данные
            equityEl.textContent = '0.00';
        }

        if (startEl) {
            startEl.textContent = '0.00';
        }

        if (deltaEqEl) {
            deltaEqEl.textContent = '+0.000 (+0.00%)';
        }

        if (durationEl) {
            // Пока показываем 0, позже добавим реальный расчёт
            durationEl.textContent = '0d 0h 0m 0s';
        }
    }

    /**
     * Отобразить логи
     */
    renderLogs() {
        console.log('[TradeLogsManager] renderLogs called, logs count:', this.logs.length);
        const logsContent = document.getElementById('logs-content');
        if (!logsContent) {
            console.error('[TradeLogsManager] logs-content element not found');
            return;
        }

        if (this.logs.length === 0) {
            logsContent.innerHTML = '<div class="logs-empty">Логов пока нет</div>';
            console.log('[TradeLogsManager] No logs to display');
            return;
        }

        console.log('[TradeLogsManager] Rendering', this.logs.length, 'logs');
        console.log('[TradeLogsManager] First log sample:', this.logs[0]);

        // Создаём список логов
        const logsHtml = this.logs.map(log => {
            const logClass = log.includes('Buy') ? 'log-buy' : 'log-sell';
            return `<div class="log-entry ${logClass}">${this.escapeHtml(log)}</div>`;
        }).join('');

        logsContent.innerHTML = `<div class="logs-list">${logsHtml}</div>`;

        console.log('[TradeLogsManager] Logs rendered successfully');

        // Прокрутка к последнему (свежему) логу
        logsContent.scrollTop = 0;
    }

    /**
     * Обновить логи
     */
    async refreshLogs(currency = null) {
        console.debug('[TradeLogsManager] Обновление логов');
        if(window.uiDebugLog) window.uiDebugLog('Обновление логов');
        const finalCurrency = currency || this.getActiveBaseCurrency() || null;
        console.log('[TradeLogsManager] refreshLogs using currency:', finalCurrency);
        await this.loadLogs(finalCurrency);
    }

    /**
     * Очистить логи
     */
    async clearLogs() {
        if (!confirm('Вы уверены, что хотите очистить все логи?')) {
            return;
        }

        try {
            const response = await fetch('/api/trade/logs/clear', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });

            const data = await response.json();

            if (data.success) {
                console.debug('[TradeLogsManager] Логи очищены');
                if(window.uiDebugLog) window.uiDebugLog('Логи очищены');
                this.logs = [];
                this.renderLogs();
                await this.loadStats();
            } else {
                console.error('[TradeLogsManager] Ошибка очистки логов:', data.error);
                if(window.uiDebugLog) window.uiDebugLog('Ошибка очистки логов: '+(data.error||'unknown'));
                alert('Ошибка очистки логов');
            }
        } catch (error) {
            console.error('[TradeLogsManager] Ошибка очистки логов:', error);
            if(window.uiDebugLog) window.uiDebugLog('Ошибка очистки логов: '+(error && error.message?error.message:String(error)));
            alert('Ошибка связи с сервером');
        }
    }

    /**
     * Запустить авто-обновление логов
     */
    startAutoRefresh() {
        if (this.refreshInterval) return;

        this.refreshInterval = setInterval(() => {
            if (this.currentView === 'logs') {
                this.refreshLogs();
            }
        }, this.AUTO_REFRESH_INTERVAL);

        console.debug('[TradeLogsManager] Авто-обновление запущено');
        if(window.uiDebugLog) window.uiDebugLog('Auto-refresh started');
    }

    /**
     * Остановить авто-обновление
     */
    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
            console.debug('[TradeLogsManager] Авто-обновление остановлено');
            if(window.uiDebugLog) window.uiDebugLog('Auto-refresh stopped');
        }
    }

    /**
     * Показать ошибку
     */
    showError(message) {
        const logsContent = document.getElementById('logs-content');
        if (logsContent) {
            logsContent.innerHTML = `<div class="logs-error">${this.escapeHtml(message)}</div>`;
        }
    }

    /**
     * Экранировать HTML
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Внедрить стили для переключателя
     */
    injectToggleStyles() {
        if (document.getElementById('trade-logs-toggle-styles')) return;

        const style = document.createElement('style');
        style.id = 'trade-logs-toggle-styles';
        style.textContent = `
            .view-toggle-group {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
            }

            .view-toggle-btn {
                background: none;
                border: none;
                color: #aaa;
                font-size: 12px;
                font-weight: 500;
                cursor: pointer;
                padding: 4px 12px;
                transition: all 0.2s;
                border-radius: 4px;
            }

            .view-toggle-btn:hover {
                color: #fff;
                background: rgba(52, 152, 219, 0.15);
            }

            .view-toggle-btn.active {
                color: #3498db;
                background: rgba(52, 152, 219, 0.2);
            }

            .view-toggle-separator {
                color: #666;
                font-size: 12px;
                font-weight: 500;
            }
        `;
        document.head.appendChild(style);
    }

    /**
     * Внедрить стили для логов
     */
    injectLogsStyles() {
        if (document.getElementById('trade-logs-styles')) return;

        const style = document.createElement('style');
        style.id = 'trade-logs-styles';
        style.textContent = `
            .trade-logs-container {
                margin-top: 15px;
            }

            .logs-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 8px 15px;
                background: #1a1a1a;
                border-radius: 8px 8px 0 0;
                border-bottom: 1px solid #3a3a3a;
                gap: 15px;
            }

            .logs-toolbar {
                display: flex;
                align-items: center;
                gap: 8px;
                font-size: 12px;
                color: #aaa;
            }

            .logs-statistics {
                display: flex;
                align-items: center;
                gap: 12px;
                font-size: 11px;
                color: #aaa;
                flex-wrap: wrap;
            }

            .stat-item {
                display: flex;
                align-items: center;
                gap: 4px;
                white-space: nowrap;
            }

            .stat-item span {
                color: #4a9eff;
                font-weight: 600;
            }

            .logs-divider {
                color: #555;
                margin: 0 4px;
            }

            .logs-info {
                color: #aaa;
                font-size: 11px;
            }

            .btn-action {
                background: none;
                border: none;
                font-size: 16px;
                cursor: pointer;
                padding: 4px;
                transition: all 0.2s;
                color: #aaa;
                width: 24px;
                height: 24px;
                display: flex;
                align-items: center;
                justify-content: center;
                border-radius: 4px;
            }

            .btn-action:hover {
                background: rgba(74, 158, 255, 0.2);
                color: #fff;
                transform: scale(1.1);
            }

            .btn-secondary {
                background: #4a9eff;
                color: #fff;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 12px;
                transition: all 0.2s;
            }

            .btn-secondary:hover {
                background: #3a8eef;
                transform: translateY(-1px);
            }

            .btn-danger {
                background: #e74c3c;
                color: #fff;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 12px;
                transition: all 0.2s;
            }

            .btn-danger:hover {
                background: #c0392b;
                transform: translateY(-1px);
            }

            .logs-content {
                min-height: 600px;
                max-height: 800px;
                overflow-y: auto;
                padding: 15px;
                background: #1a1a1a;
                border-radius: 0 0 8px 8px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 13px;
            }

            .logs-list {
                display: flex;
                flex-direction: column;
                gap: 4px;
            }

            .log-entry {
                padding: 6px 10px;
                border-radius: 4px;
                line-height: 1.5;
                color: #ddd;
            }

            .log-buy {
                background: rgba(231, 76, 60, 0.1);
                border-left: 3px solid #e74c3c;
            }

            .log-sell {
                background: rgba(46, 204, 113, 0.1);
                border-left: 3px solid #2ecc71;
            }

            .logs-empty, .logs-error, .logs-loading {
                text-align: center;
                padding: 40px;
                color: #999;
                font-size: 14px;
            }

            .logs-error {
                color: #e74c3c;
            }

            /* Прокрутка */
            .logs-content::-webkit-scrollbar {
                width: 8px;
            }

            .logs-content::-webkit-scrollbar-track {
                background: #2a2a2a;
                border-radius: 4px;
            }

            .logs-content::-webkit-scrollbar-thumb {
                background: #555;
                border-radius: 4px;
            }

            .logs-content::-webkit-scrollbar-thumb:hover {
                background: #777;
            }
        `;
        document.head.appendChild(style);
    }
}

// Глобальный экземпляр
window.tradeLogsManager = window.tradeLogsManager || new TradeLogsManager();

// Инициализация: если документ уже загружен, инициализируем сразу,
// иначе ждём события DOMContentLoaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        try { window.tradeLogsManager.init(); } catch (e) { console.error('TradeLogsManager init error', e); }
    });
} else {
    try { window.tradeLogsManager.init(); } catch (e) { console.error('TradeLogsManager init error', e); }
}

// Дополнительная инициализация: подписываемся на изменения валюты
(function() {
    function setupCurrencyChangeHandler() {
        // Переопределяем функцию switchBaseCurrency из app.js, чтобы она обновляла логи
        const originalSwitchBaseCurrency = window.switchBaseCurrency;
        if (originalSwitchBaseCurrency) {
            window.switchBaseCurrency = async function(code) {
                console.log('[TradeLogsManager] Currency changing to:', code);
                const result = await originalSwitchBaseCurrency.call(this, code);
                
                // Если вкладка логов активна, обновляем логи для новой валюты
                if (window.tradeLogsManager && window.tradeLogsManager.currentView === 'logs') {
                    console.log('[TradeLogsManager] Logs view active, reloading logs for new currency:', code);
                    setTimeout(() => {
                        window.tradeLogsManager.loadLogs(code);
                    }, 500); // Небольшая задержка, чтобы валюта успела установиться
                }
                
                return result;
            };
            console.log('[TradeLogsManager] Currency change handler attached');
        } else {
            // Если функция еще не загружена, ждем
            setTimeout(setupCurrencyChangeHandler, 1000);
        }
    }
    
    setupCurrencyChangeHandler();
})();

