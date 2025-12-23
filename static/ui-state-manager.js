/**

 * UI State Manager - Управление состоянием интерфейса

 * Автоматическое сохранение и восстановление настроек

 */



class UIStateManager {

  constructor() {

    this.state = null;

    this.saveDebounceTimer = null;

    this.saveDebounceDelay = 500; // мс

  }



  /**

   * Инициализация - загрузка сохраненного состояния

   */

  async init() {

    try {

      const response = await fetch('/api/ui/state');

      const result = await response.json();

      

      if (result.success) {

        this.state = result.state;

        this.applyState();

        console.log('[UI State] Состояние загружено:', this.state);

        return true;

      } else {

        console.error('[UI State] Ошибка загрузки:', result.error);

        return false;

      }

    } catch (error) {

      console.error('[UI State] Ошибка при загрузке состояния:', error);

      return false;

    }

  }



  /**

   * Применить загруженное состояние к UI

   */

  applyState() {

    if (!this.state) return;



    // Восстанавливаем тему

    if (this.state.theme) {

      this.applyTheme(this.state.theme);

    }



    // Восстанавливаем активную валютную пару

    if (this.state.active_base_currency && this.state.active_quote_currency) {

      this.selectCurrencyPair(

        this.state.active_base_currency, 

        this.state.active_quote_currency

      );

    }



    // Восстанавливаем состояние автотрейдинга

    if (typeof this.state.auto_trade_enabled === 'boolean') {

      this.updateAutoTradeButton(this.state.auto_trade_enabled);

    }



    // Восстанавливаем разрешения торговли для валют

    if (this.state.enabled_currencies) {

      this.restoreCurrencyToggles(this.state.enabled_currencies);

    }



    // Восстанавливаем видимость панелей

    this.restorePanelVisibility();



    // Восстанавливаем глубину стакана

    if (this.state.orderbook_depth) {

      this.setOrderbookDepth(this.state.orderbook_depth);

    }



    console.log('[UI State] Состояние применено к интерфейсу');

  }



  /**

   * Сохранить изменение в состоянии (с debounce)

   */

  async save(key, value) {

    if (!this.state) this.state = {};

    this.state[key] = value;



    // Отменяем предыдущий таймер

    if (this.saveDebounceTimer) {

      clearTimeout(this.saveDebounceTimer);

    }



    // Ставим новый таймер для отложенного сохранения

    this.saveDebounceTimer = setTimeout(async () => {

      await this.saveToServer();

    }, this.saveDebounceDelay);

  }



  /**

   * Сохранить несколько изменений одновременно

   */

  async saveMultiple(updates) {

    if (!this.state) this.state = {};

    Object.assign(this.state, updates);



    // Отменяем предыдущий таймер

    if (this.saveDebounceTimer) {

      clearTimeout(this.saveDebounceTimer);

    }



    // Ставим новый таймер

    this.saveDebounceTimer = setTimeout(async () => {

      await this.saveToServer();

    }, this.saveDebounceDelay);

  }



  /**

   * Немедленное сохранение на сервер

   */

  async saveToServer() {

    try {

      const response = await fetch('/api/ui/state/partial', {

        method: 'POST',

        headers: { 'Content-Type': 'application/json' },

        body: JSON.stringify({ updates: this.state })

      });



      const result = await response.json();

      if (result.success) {

        console.log('[UI State] Состояние сохранено на сервер');

      } else {

        console.error('[UI State] Ошибка сохранения:', result.error);

      }

    } catch (error) {

      console.error('[UI State] Ошибка при сохранении:', error);

    }

  }



  /**

   * Сбросить состояние к значениям по умолчанию

   */

  async reset() {

    try {

      const response = await fetch('/api/ui/state/reset', { method: 'POST' });

      const result = await response.json();

      

      if (result.success) {

        this.state = result.state;

        this.applyState();

        console.log('[UI State] Состояние сброшено к значениям по умолчанию');

        return true;

      } else {

        console.error('[UI State] Ошибка сброса:', result.error);

        return false;

      }

    } catch (error) {

      console.error('[UI State] Ошибка при сбросе:', error);

      return false;

    }

  }



  // =================== Методы применения состояния ===================



  applyTheme(theme) {

    document.body.setAttribute('data-theme', theme);

    const themeToggle = document.getElementById('themeToggle');

    if (themeToggle) {

      themeToggle.checked = (theme === 'light');

    }

  }



  selectCurrencyPair(base, quote) {

    const baseSelect = document.getElementById('baseCurrency');

    const quoteSelect = document.getElementById('quoteCurrency');

    

    if (baseSelect) baseSelect.value = base;

    if (quoteSelect) quoteSelect.value = quote;

    

    // Триггерим событие изменения если нужно обновить данные

    if (baseSelect && typeof window.updateCurrencyPair === 'function') {

      window.updateCurrencyPair();

    }

  }



  updateAutoTradeButton(enabled) {

    const btn = document.getElementById('autoTradeToggle');

    if (btn) {

      btn.classList.toggle('active', enabled);

      btn.textContent = enabled ? 'Автотрейдинг: ВКЛ' : 'Автотрейдинг: ВЫКЛ';

    }

  }



  restoreCurrencyToggles(enabledCurrencies) {

    Object.entries(enabledCurrencies).forEach(([currency, enabled]) => {

      const toggle = document.querySelector(`[data-currency="${currency}"]`);

      if (toggle) {

        toggle.checked = enabled;

        // Обновляем визуальное состояние

        const card = toggle.closest('.currency-card');

        if (card) {

          card.classList.toggle('disabled', !enabled);

        }

      }

    });

  }



  restorePanelVisibility() {

    const panels = {

      'show_indicators': 'indicatorsPanel',

      'show_orderbook': 'orderbookPanel',

      'show_trades': 'tradesPanel'

    };



    Object.entries(panels).forEach(([stateKey, panelId]) => {

      const panel = document.getElementById(panelId);

      if (panel && typeof this.state[stateKey] === 'boolean') {

        panel.style.display = this.state[stateKey] ? 'block' : 'none';

      }

    });

  }



  setOrderbookDepth(depth) {

    const depthSelect = document.getElementById('orderbookDepth');

    if (depthSelect) {

      depthSelect.value = depth;

    }

  }



  // =================== Вспомогательные методы ===================



  get(key, defaultValue = null) {

    return this.state && this.state.hasOwnProperty(key) 

      ? this.state[key] 

      : defaultValue;

  }



  set(key, value) {

    this.save(key, value);

  }

}



// =================== Глобальная инициализация ===================



// Создаем глобальный экземпляр

const uiStateManager = new UIStateManager();



// Инициализация при загрузке страницы

document.addEventListener('DOMContentLoaded', async () => {

  console.log('[UI State] Инициализация...');

  await uiStateManager.init();

});



// =================== Примеры использования ===================



// Пример 1: Сохранение при изменении темы

function setupThemeToggle() {

  const themeToggle = document.getElementById('themeToggle');

  if (themeToggle) {

    themeToggle.addEventListener('change', (e) => {

      const theme = e.target.checked ? 'light' : 'dark';

      uiStateManager.applyTheme(theme);

      uiStateManager.save('theme', theme);

    });

  }

}



// Пример 2: Сохранение при выборе валютной пары

function setupCurrencySelectors() {

  const baseSelect = document.getElementById('baseCurrency');

  const quoteSelect = document.getElementById('quoteCurrency');



  if (baseSelect) {

    baseSelect.addEventListener('change', () => {

      uiStateManager.save('active_base_currency', baseSelect.value);

    });

  }



  if (quoteSelect) {

    quoteSelect.addEventListener('change', () => {

      uiStateManager.save('active_quote_currency', quoteSelect.value);

    });

  }

}



// Пример 3: Сохранение состояния панелей

function setupPanelToggles() {

  const toggles = {

    'indicatorsToggle': 'show_indicators',

    'orderbookToggle': 'show_orderbook',

    'tradesToggle': 'show_trades'

  };



  Object.entries(toggles).forEach(([toggleId, stateKey]) => {

    const toggle = document.getElementById(toggleId);

    if (toggle) {

      toggle.addEventListener('change', (e) => {

        uiStateManager.save(stateKey, e.target.checked);

      });

    }

  });

}



// Пример 4: Сохранение глубины стакана

function setupOrderbookDepth() {

  const depthSelect = document.getElementById('orderbookDepth');

  if (depthSelect) {

    depthSelect.addEventListener('change', (e) => {

      uiStateManager.save('orderbook_depth', parseInt(e.target.value));

    });

  }

}



// Инициализация всех обработчиков

document.addEventListener('DOMContentLoaded', () => {

  setupThemeToggle();

  setupCurrencySelectors();

  setupPanelToggles();

  setupOrderbookDepth();

});



// Экспортируем для использования в других модулях

if (typeof module !== 'undefined' && module.exports) {

  module.exports = { UIStateManager, uiStateManager };

}

