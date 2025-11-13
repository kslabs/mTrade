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
        const breakevenHeader = document.querySelector('.breakeven-table h2');
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
                <div class="logs-stats">
                    <span id="logs-count">Загрузка...</span>
                    <button id="btn-refresh-logs" class="btn-refresh" title="Обновить логи">
                        🔄
                    </button>
                    <button id="btn-clear-logs" class="btn-clear" title="Очистить логи">
                        🗑️
                    </button>
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

        if (view === 'breakeven') {
            // Показать таблицу, скрыть логи
            if (btnBreakeven) btnBreakeven.classList.add('active');
            if (btnLogs) btnLogs.classList.remove('active');
            if (breakevenTable) breakevenTable.style.display = 'block';
            if (logsContainer) logsContainer.style.display = 'none';

            // Остановить авто-обновление логов
            this.stopAutoRefresh();
        } else {
            // Показать логи, скрыть таблицу
            if (btnBreakeven) btnBreakeven.classList.remove('active');
            if (btnLogs) btnLogs.classList.add('active');
            if (breakevenTable) breakevenTable.style.display = 'none';
            if (logsContainer) logsContainer.style.display = 'block';

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
        const countElement = document.getElementById('logs-count');
        if (!countElement) return;

        const text = `Записей: ${stats.total_entries} | ` +
                    `Покупок: ${stats.total_buys} | ` +
                    `Продаж: ${stats.total_sells} | ` +
                    `PnL: ${stats.total_pnl.toFixed(4)}`;

        countElement.textContent = text;
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
                color: #666;
                font-size: 18px;
                font-weight: 600;
                cursor: pointer;
                padding: 4px 12px;
                transition: all 0.2s;
                border-radius: 4px;
            }

            .view-toggle-btn:hover {
                color: #333;
                background: rgba(52, 152, 219, 0.1);
            }

            .view-toggle-btn.active {
                color: #3498db;
                background: rgba(52, 152, 219, 0.15);
            }

            .view-toggle-separator {
                color: #ccc;
                font-size: 18px;
                font-weight: 600;
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
                padding: 10px 15px;
                background: #f8f9fa;
                border-radius: 8px 8px 0 0;
                border: 1px solid #dee2e6;
            }

            .logs-stats {
                display: flex;
                align-items: center;
                gap: 10px;
                font-size: 14px;
                color: #666;
            }

            .btn-refresh, .btn-clear {
                background: none;
                border: none;
                font-size: 18px;
                cursor: pointer;
                padding: 4px 8px;
                transition: transform 0.2s;
            }

            .btn-refresh:hover, .btn-clear:hover {
                transform: scale(1.2);
            }

            .logs-content {
                max-height: 500px;
                overflow-y: auto;
                padding: 15px;
                background: white;
                border: 1px solid #dee2e6;
                border-top: none;
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
            }

            .log-buy {
                background: rgba(231, 76, 60, 0.05);
                border-left: 3px solid #e74c3c;
            }

            .log-sell {
                background: rgba(46, 204, 113, 0.05);
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
                background: #f1f1f1;
                border-radius: 4px;
            }

            .logs-content::-webkit-scrollbar-thumb {
                background: #888;
                border-radius: 4px;
            }

            .logs-content::-webkit-scrollbar-thumb:hover {
                background: #555;
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
