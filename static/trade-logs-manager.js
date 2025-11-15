/**
 * Trade Logs Manager - Управление отображением логов торговли
 * Переключение между таблицей безубыточности и логами
 */

class TradeLogsManager {
    constructor() {
        this.currentView = 'breakeven'; // 'breakeven' или 'logs'
        this.logs = [];
        this.refreshInterval = null;
        this.AUTO_REFRESH_INTERVAL = 5000; // 5 секунд
    }

    /**
     * Инициализация менеджера логов
     */
    init() {
        console.log('[TradeLogsManager] Инициализация');
        this.createToggleButton();
        this.createLogsContainer();
        this.setupEventListeners();
    }

    /**
     * Создать кнопку-переключатель между таблицей и логами
     */
    createToggleButton() {
        const breakevenHeader = document.querySelector('.breakeven-table h3');
        if (!breakevenHeader) {
            console.warn('[TradeLogsManager] Заголовок таблицы безубыточности не найден');
            return;
        }

        // Заменяем текст заголовка на кнопки-переключатели
        breakevenHeader.innerHTML = `
            <div class="view-toggle-group">
                <button id="btn-view-breakeven" class="view-toggle-btn active">
                    Таблица безубыточности
                </button>
                <span class="view-toggle-separator">/</span>
                <button id="btn-view-logs" class="view-toggle-btn">
                    Логи
                </button>
            </div>
        `;

        // Добавляем стили для переключателя
        this.injectToggleStyles();
    }

    /**
     * Создать контейнер для отображения логов
     */
    createLogsContainer() {
        const breakevenContainer = document.querySelector('.breakeven-table');
        if (!breakevenContainer) return;

        // Создаём контейнер логов (изначально скрыт)
        const logsContainer = document.createElement('div');
        logsContainer.id = 'trade-logs-container';
        logsContainer.className = 'trade-logs-container';
        logsContainer.style.display = 'none';
        logsContainer.innerHTML = `
            <div class="logs-header">
                <div class="logs-toolbar">
                    <button id="btn-refresh-logs" class="btn-action" title="Обновить">🔄</button>
                    <button id="btn-clear-logs" class="btn-action" title="Очистить">🗑️</button>
                    <span class="logs-divider">|</span>
                    <span id="logs-count" class="logs-info">0 записей</span>
                </div>
                <div class="logs-statistics" id="logs-statistics">
                    <span class="stat-item">PnL: <span id="stat-pnl">0.000</span></span>
                    <span class="stat-item">Equity: <span id="stat-equity">0.00</span></span>
                    <span class="stat-item">Start: <span id="stat-start">0.00</span></span>
                    <span class="stat-item">ΔEq: <span id="stat-delta-eq">+0.000 (+0.00%)</span></span>
                    <span class="stat-item">Dur: <span id="stat-duration">0d 0h 0m 0s</span></span>
                </div>
            </div>
            <div class="logs-content" id="logs-content">
                <div class="logs-loading">Загрузка логов...</div>
            </div>
        `;

        // Вставляем контейнер логов после таблицы безубыточности
        const tableContainer = breakevenContainer.querySelector('.breakeven-table-content');
        if (tableContainer) {
            tableContainer.parentNode.insertBefore(logsContainer, tableContainer.nextSibling);
        }

        this.injectLogsStyles();
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
        console.log(`[TradeLogsManager] Переключение на ${view}`);

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

            // Загрузить и запустить авто-обновление логов
            this.loadLogs();
            this.startAutoRefresh();
        }
    }

    /**
     * Загрузить логи с сервера
     */
    async loadLogs(currency = null) {
        try {
            const params = new URLSearchParams({
                limit: '100',
                formatted: '1'
            });

            if (currency) {
                params.append('currency', currency);
            }

            const response = await fetch(`/api/trade/logs?${params}`);
            const data = await response.json();

            if (data.success) {
                this.logs = data.logs || [];
                this.renderLogs();
                await this.loadStats(currency);
            } else {
                console.error('[TradeLogsManager] Ошибка загрузки логов:', data.error);
                this.showError('Ошибка загрузки логов');
            }
        } catch (error) {
            console.error('[TradeLogsManager] Ошибка загрузки логов:', error);
            this.showError('Ошибка связи с сервером');
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
        const logsContent = document.getElementById('logs-content');
        if (!logsContent) return;

        if (this.logs.length === 0) {
            logsContent.innerHTML = '<div class="logs-empty">Логов пока нет</div>';
            return;
        }

        // Создаём список логов
        const logsHtml = this.logs.map(log => {
            const logClass = log.includes('Buy') ? 'log-buy' : 'log-sell';
            return `<div class="log-entry ${logClass}">${this.escapeHtml(log)}</div>`;
        }).join('');

        logsContent.innerHTML = `<div class="logs-list">${logsHtml}</div>`;

        // Прокрутка к последнему (свежему) логу
        logsContent.scrollTop = 0;
    }

    /**
     * Обновить логи
     */
    async refreshLogs() {
        console.log('[TradeLogsManager] Обновление логов');
        const currency = window.app?.state?.activeCurrency || null;
        await this.loadLogs(currency);
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
                console.log('[TradeLogsManager] Логи очищены');
                this.logs = [];
                this.renderLogs();
                await this.loadStats();
            } else {
                console.error('[TradeLogsManager] Ошибка очистки логов:', data.error);
                alert('Ошибка очистки логов');
            }
        } catch (error) {
            console.error('[TradeLogsManager] Ошибка очистки логов:', error);
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

        console.log('[TradeLogsManager] Авто-обновление запущено');
    }

    /**
     * Остановить авто-обновление
     */
    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
            console.log('[TradeLogsManager] Авто-обновление остановлено');
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
                font-size: 16px;
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
                font-size: 16px;
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
window.tradeLogsManager = null;

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    window.tradeLogsManager = new TradeLogsManager();
    window.tradeLogsManager.init();
});
