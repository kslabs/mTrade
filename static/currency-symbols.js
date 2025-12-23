/**
 * Модуль для работы с символами валют
 * 
 * ВАЖНО: С версии 1.8 символы валют загружаются автоматически с Gate.io API
 * через функцию синхронизации (кнопка "🔄 Синхронизация с Gate.io").
 * 
 * Этот файл содержит:
 * - Официальные символы валют Unicode
 * - Рекомендуемые символы для популярных криптовалют
 * - Emoji picker для ручного выбора символов
 * 
 * Ссылки:
 * - Unicode Currency Symbols: https://en.wikipedia.org/wiki/Currency_Symbols_(Unicode_block)
 * - Gate.io API: https://www.gate.io/docs/developers/apiv4
 */

// Официальные символы валют Unicode (U+20A0—U+20CF)
export const OFFICIAL_CURRENCY_SYMBOLS = [
    { symbol: '$', code: 'U+0024', name: 'Dollar Sign' },
    { symbol: '¢', code: 'U+00A2', name: 'Cent Sign' },
    { symbol: '£', code: 'U+00A3', name: 'Pound Sign' },
    { symbol: '¤', code: 'U+00A4', name: 'Currency Sign' },
    { symbol: '¥', code: 'U+00A5', name: 'Yen Sign' },
    { symbol: '₠', code: 'U+20A0', name: 'Euro-Currency Sign' },
    { symbol: '₡', code: 'U+20A1', name: 'Colon Sign' },
    { symbol: '₢', code: 'U+20A2', name: 'Cruzeiro Sign' },
    { symbol: '₣', code: 'U+20A3', name: 'French Franc Sign' },
    { symbol: '₤', code: 'U+20A4', name: 'Lira Sign' },
    { symbol: '₥', code: 'U+20A5', name: 'Mill Sign' },
    { symbol: '₦', code: 'U+20A6', name: 'Naira Sign' },
    { symbol: '₧', code: 'U+20A7', name: 'Peseta Sign' },
    { symbol: '₨', code: 'U+20A8', name: 'Rupee Sign' },
    { symbol: '₩', code: 'U+20A9', name: 'Won Sign' },
    { symbol: '₪', code: 'U+20AA', name: 'New Sheqel Sign' },
    { symbol: '₫', code: 'U+20AB', name: 'Dong Sign' },
    { symbol: '€', code: 'U+20AC', name: 'Euro Sign' },
    { symbol: '₭', code: 'U+20AD', name: 'Kip Sign' },
    { symbol: '₮', code: 'U+20AE', name: 'Tugrik Sign' },
    { symbol: '₯', code: 'U+20AF', name: 'Drachma Sign' },
    { symbol: '₰', code: 'U+20B0', name: 'German Penny Sign' },
    { symbol: '₱', code: 'U+20B1', name: 'Peso Sign' },
    { symbol: '₲', code: 'U+20B2', name: 'Guarani Sign' },
    { symbol: '₳', code: 'U+20B3', name: 'Austral Sign' },
    { symbol: '₴', code: 'U+20B4', name: 'Hryvnia Sign' },
    { symbol: '₵', code: 'U+20B5', name: 'Cedi Sign' },
    { symbol: '₶', code: 'U+20B6', name: 'Livre Tournois Sign' },
    { symbol: '₷', code: 'U+20B7', name: 'Spesmilo Sign' },
    { symbol: '₸', code: 'U+20B8', name: 'Tenge Sign' },
    { symbol: '₹', code: 'U+20B9', name: 'Indian Rupee Sign' },
    { symbol: '₺', code: 'U+20BA', name: 'Turkish Lira Sign' },
    { symbol: '₻', code: 'U+20BB', name: 'Nordic Mark Sign' },
    { symbol: '₼', code: 'U+20BC', name: 'Manat Sign' },
    { symbol: '₽', code: 'U+20BD', name: 'Ruble Sign' },
    { symbol: '₾', code: 'U+20BE', name: 'Lari Sign' },
    { symbol: '₿', code: 'U+20BF', name: 'Bitcoin Sign' },
];

// Криптовалютные символы (официальные и рекомендованные)
// Примечание: теперь символы загружаются автоматически с Gate.io API
// Этот список используется только для выбора вручную или как fallback
export const CRYPTO_SYMBOLS = [
    // Основные криптовалюты
    { symbol: '₿', code: 'U+20BF', name: 'Bitcoin' },
    { symbol: 'Ξ', code: 'U+039E', name: 'Ethereum (Xi)' },
    { symbol: '₳', code: 'U+20B3', name: 'Cardano (Austral)' },
    { symbol: 'Ł', code: 'U+0141', name: 'Litecoin' },
    { symbol: 'Ɖ', code: 'U+0189', name: 'Dogecoin' },
    { symbol: '◎', code: 'U+25CE', name: 'Solana' },
    { symbol: 'Ⓜ', code: 'U+24C2', name: 'Monero' },
    { symbol: '✕', code: 'U+2715', name: 'XRP (Ripple)' },
    { symbol: '⬤', code: 'U+2B24', name: 'Polkadot' },
    { symbol: '◆', code: 'U+25C6', name: 'BNB (Binance)' },
    { symbol: '⬡', code: 'U+2B21', name: 'Polygon (MATIC)' },
    { symbol: '▲', code: 'U+25B2', name: 'Avalanche' },
    { symbol: '★', code: 'U+2605', name: 'Stellar (XLM)' },
    { symbol: '●', code: 'U+25CF', name: 'Filled Circle (Generic)' },
    { symbol: '○', code: 'U+25CB', name: 'White Circle (Generic)' },
    { symbol: '◇', code: 'U+25C7', name: 'White Diamond (Generic)' },
    { symbol: '▪', code: 'U+25AA', name: 'Black Square (Generic)' },
    { symbol: '⬢', code: 'U+2B22', name: 'Black Hexagon (Generic)' },
];

// Популярные эмодзи для криптовалют
export const EMOJI_SYMBOLS = [
    { symbol: '🌐', name: 'Globe with Meridians' },
    { symbol: '💎', name: 'Gem Stone' },
    { symbol: '💠', name: 'Diamond with a Dot' },
    { symbol: '🔶', name: 'Large Orange Diamond' },
    { symbol: '🔷', name: 'Large Blue Diamond' },
    { symbol: '🔸', name: 'Small Orange Diamond' },
    { symbol: '🔹', name: 'Small Blue Diamond' },
    { symbol: '🔺', name: 'Red Triangle Pointed Up' },
    { symbol: '🔻', name: 'Red Triangle Pointed Down' },
    { symbol: '🔰', name: 'Japanese Symbol for Beginner' },
    { symbol: '⚡', name: 'High Voltage' },
    { symbol: '🚀', name: 'Rocket' },
    { symbol: '💰', name: 'Money Bag' },
    { symbol: '💵', name: 'Dollar Banknote' },
    { symbol: '💶', name: 'Euro Banknote' },
    { symbol: '💷', name: 'Pound Banknote' },
    { symbol: '💴', name: 'Yen Banknote' },
    { symbol: '💸', name: 'Money with Wings' },
    { symbol: '🪙', name: 'Coin' },
];

// Все символы для выбора
export const ALL_SYMBOLS = [
    { category: 'Официальные валюты', symbols: OFFICIAL_CURRENCY_SYMBOLS },
    { category: 'Криптовалюты', symbols: CRYPTO_SYMBOLS },
    { category: 'Эмодзи', symbols: EMOJI_SYMBOLS },
];

/**
 * Создает и отображает модальное окно выбора символа валюты
 * @param {Function} onSelect - Callback функция при выборе символа
 * @param {string} currentSymbol - Текущий выбранный символ
 */
export function showSymbolPicker(onSelect, currentSymbol = '') {
    // Создаем модальное окно
    const modal = document.createElement('div');
    modal.className = 'symbol-picker-modal';
    modal.innerHTML = `
        <div class="symbol-picker-content">
            <div class="symbol-picker-header">
                <h3>Выбор символа валюты</h3>
                <button class="symbol-picker-close">&times;</button>
            </div>
            <div class="symbol-picker-search">
                <input type="text" placeholder="Поиск символа..." id="symbolSearch">
            </div>
            <div class="symbol-picker-tabs">
                <button class="symbol-tab active" data-category="0">Официальные</button>
                <button class="symbol-tab" data-category="1">Крипто</button>
                <button class="symbol-tab" data-category="2">Эмодзи</button>
            </div>
            <div class="symbol-picker-body">
                ${ALL_SYMBOLS.map((cat, catIndex) => `
                    <div class="symbol-category ${catIndex === 0 ? 'active' : ''}" data-category="${catIndex}">
                        <div class="symbol-grid">
                            ${cat.symbols.map(s => `
                                <button class="symbol-item ${s.symbol === currentSymbol ? 'selected' : ''}" 
                                        data-symbol="${s.symbol}" 
                                        title="${s.name || ''} ${s.code || ''}">
                                    <span class="symbol-char">${s.symbol}</span>
                                    <span class="symbol-code">${s.code || ''}</span>
                                </button>
                            `).join('')}
                        </div>
                    </div>
                `).join('')}
            </div>
            <div class="symbol-picker-footer">
                <div class="symbol-picker-preview">
                    <span>Выбрано:</span>
                    <span class="preview-symbol">${currentSymbol || '—'}</span>
                </div>
                <div class="symbol-picker-actions">
                    <button class="btn-cancel">Отмена</button>
                    <button class="btn-confirm" ${!currentSymbol ? 'disabled' : ''}>Выбрать</button>
                </div>
            </div>
        </div>
    `;

    document.body.appendChild(modal);

    // Переменная для хранения выбранного символа
    let selectedSymbol = currentSymbol;

    // Обработчики для табов
    const tabs = modal.querySelectorAll('.symbol-tab');
    const categories = modal.querySelectorAll('.symbol-category');
    
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const categoryIndex = tab.dataset.category;
            tabs.forEach(t => t.classList.remove('active'));
            categories.forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            categories[categoryIndex].classList.add('active');
        });
    });

    // Обработчики для выбора символа
    const symbolItems = modal.querySelectorAll('.symbol-item');
    const previewSymbol = modal.querySelector('.preview-symbol');
    const confirmBtn = modal.querySelector('.btn-confirm');

    symbolItems.forEach(item => {
        item.addEventListener('click', () => {
            symbolItems.forEach(i => i.classList.remove('selected'));
            item.classList.add('selected');
            selectedSymbol = item.dataset.symbol;
            previewSymbol.textContent = selectedSymbol;
            confirmBtn.disabled = false;
        });
    });

    // Поиск
    const searchInput = modal.querySelector('#symbolSearch');
    searchInput.addEventListener('input', (e) => {
        const searchTerm = e.target.value.toLowerCase();
        symbolItems.forEach(item => {
            const symbol = item.dataset.symbol;
            const title = item.title.toLowerCase();
            const matches = symbol.toLowerCase().includes(searchTerm) || 
                          title.includes(searchTerm);
            item.style.display = matches ? 'flex' : 'none';
        });
    });

    // Закрытие модального окна
    const closeModal = () => {
        modal.remove();
    };

    modal.querySelector('.symbol-picker-close').addEventListener('click', closeModal);
    modal.querySelector('.btn-cancel').addEventListener('click', closeModal);
    
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeModal();
        }
    });

    // Подтверждение выбора
    confirmBtn.addEventListener('click', () => {
        if (selectedSymbol) {
            onSelect(selectedSymbol);
            closeModal();
        }
    });
}

/**
 * Получает рекомендуемый символ для кода валюты
 * @param {string} currencyCode - Код валюты (например, 'BTC', 'ETH')
 * @returns {string} - Рекомендуемый символ
 */
export function getRecommendedSymbol(currencyCode) {
    const recommendations = {
        // Криптовалюты
        'BTC': '₿',
        'ETH': 'Ξ',
        'ADA': '₳',
        'LTC': 'Ł',
        'DOGE': 'Ɖ',
        'SOL': '◎',
        'DOT': '⬤',
        'XRP': '✕',
        'BNB': '◆',
        'AVAX': '▲',
        'MATIC': '◇',
        'LINK': '⬡',
        'UNI': '🦄',
        'ATOM': '⚛',
        'XLM': '★',
        
        // Фиатные валюты
        'USD': '$',
        'EUR': '€',
        'GBP': '£',
        'JPY': '¥',
        'CNY': '¥',
        'RUB': '₽',
        'INR': '₹',
        'KRW': '₩',
        'TRY': '₺',
        'UAH': '₴',
        'CHF': '₣',
        'PLN': 'zł',
        'CZK': 'Kč',
        'SEK': 'kr',
        'NOK': 'kr',
        'DKK': 'kr',
        'HUF': 'Ft',
        'RON': 'lei',
        'BGN': 'лв',
        'HRK': 'kn',
        'ILS': '₪',
        'AED': 'د.إ',
        'SAR': 'ر.س',
        'QAR': 'ر.ق',
        'KWD': 'د.ك',
        'BHD': 'د.ب',
        'THB': '฿',
        'SGD': '$',
        'MYR': 'RM',
        'IDR': 'Rp',
        'PHP': '₱',
        'VND': '₫',
        'BRL': 'R$',
        'ARS': '$',
        'CLP': '$',
        'COP': '$',
        'MXN': '$',
        'ZAR': 'R',
        'EGP': '£',
        'NGN': '₦',
        'KES': 'KSh',
        'GHS': '₵',
        'AUD': '$',
        'NZD': '$',
        'CAD': '$',
    };

    return recommendations[currencyCode.toUpperCase()] || '¤';
}
