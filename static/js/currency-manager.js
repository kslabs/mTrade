// static/js/currency-manager.js
// Выделено из static/app.js (currency manager + emoji picker fallback)

/**
 * Инициализирует менеджер валют и утилиты выбора символов.
 *
 * ВНИМАНИЕ: модуль хранит внутренний state (currentEmojiPickerRow), поэтому
 * нужно вызывать initCurrencyManager один раз при старте.
 */
export function initCurrencyManager(deps){
  const {
    $,
    api,
    alert,
    logDbg,
    getCurrenciesList,
    setCurrenciesList,
    renderCurrencyTabs,
    getTradingPermissions,
    getCurrentQuoteCurrency,
    loadCurrenciesFromServer
  } = deps;

  // Популярные символы для криптовалют
  const popularCryptoEmojis = [
    '₿', '💎', '🚀', '🌐', 'Ξ', '◎', '🔶', '✕', '₳',
    '🔺', '⬤', '💠', '🔷', '💰', '🪙', '💵', '💴', '💶',
    '💷', '⚡', '🔥', '🌟', '⭐', '💫', '✨', '🎯', '🎪',
    '🎨', '🔮', '🌈', '🦄', '🐉', '🦅', '🦊', '🐺', '🦁'
  ];

  let currentEmojiPickerRow = -1;

  function openCurrencyManager(){
    buildCurrencyManagerRows();
    $('currencyManagerModal').style.display='flex';
  }

  function closeCurrencyManager(){
    $('currencyManagerModal').style.display='none';
  }

  function showEmojiPicker(rowIdx){
    currentEmojiPickerRow = rowIdx;

    // Получаем текущий символ из строки
    const rows = $('currencyManagerRows');
    const row = [...rows.querySelectorAll('.cm-row')].find(r => r.dataset.index == rowIdx);
    const currentSymbol = row ? row.querySelector('.cm-symbol').value.trim() : '';

    // Импортируем и показываем новый picker
    import('./currency-symbols.js').then(module => {
      module.showSymbolPicker((selectedSymbol) => {
        selectEmoji(selectedSymbol);
      }, currentSymbol);
    }).catch(err => {
      console.error('Failed to load symbol picker:', err);
      // Fallback to old picker
      showEmojiPickerFallback(rowIdx, currentSymbol);
    });
  }

  function showEmojiPickerFallback(rowIdx, currentSymbol){
    currentEmojiPickerRow = rowIdx;
    // Удаляем старый picker если есть
    const oldPicker = document.querySelector('.emoji-picker-popup');
    if(oldPicker) oldPicker.remove();

    // Создаём popup
    const picker = document.createElement('div');
    picker.className = 'emoji-picker-popup';
    picker.innerHTML = `
      <div class="emoji-picker-header">Выберите символ</div>
      <div class="emoji-picker-grid">
        ${popularCryptoEmojis.map(e => `<div class="emoji-item" data-emoji="${e}">${e}</div>`).join('')}
      </div>
      <div class="emoji-picker-custom">
        <input type="text" id="customEmojiInput" placeholder="Или введите свой символ" maxlength="4" value="${currentSymbol}">
        <button id="customEmojiApply">✓</button>
      </div>
      <button class="emoji-picker-close" id="emojiPickerClose">✖</button>
    `;

    picker.querySelectorAll('.emoji-item').forEach(el => {
      el.addEventListener('click', () => selectEmoji(el.dataset.emoji));
    });
    picker.querySelector('#customEmojiApply')?.addEventListener('click', () => selectCustomEmoji());
    picker.querySelector('#emojiPickerClose')?.addEventListener('click', () => closeEmojiPicker());

    document.body.appendChild(picker);
  }

  function selectEmoji(emoji){
    const rows = $('currencyManagerRows');
    const row = [...rows.querySelectorAll('.cm-row')].find(r => r.dataset.index == currentEmojiPickerRow);
    if(row){
      const input = row.querySelector('.cm-symbol');
      if(input) input.value = emoji;
    }
    closeEmojiPicker();
  }

  function selectCustomEmoji(){
    const input = document.getElementById('customEmojiInput');
    if(input && input.value.trim()){
      selectEmoji(input.value.trim());
    }
  }

  function closeEmojiPicker(){
    const picker = document.querySelector('.emoji-picker-popup');
    if(picker) picker.remove();
    currentEmojiPickerRow = -1;
  }

  function buildCurrencyManagerRows(){
    const rows = $('currencyManagerRows');
    if(!rows) return;

    rows.innerHTML = '';

    const arr = Array.isArray(getCurrenciesList()) ? getCurrenciesList() : [];
    const tradingPermissions = getTradingPermissions?.() || {};

    arr.forEach((c, i) => {
      const code = (c.code || c || '').toUpperCase();
      const symbol = (c.symbol || c.code || c || '');

      const row = document.createElement('div');
      row.className = 'cm-row';
      row.dataset.index = String(i);
      row.innerHTML = `
        <input type='text' class='cm-code' value='${code}' placeholder='Код'>
        <div class='cm-symbol-picker'>
          <input type='text' class='cm-symbol' value='${symbol}' placeholder='Символ' readonly>
          <button class='cm-emoji-btn' type='button' title='Выбрать символ'>😀</button>
        </div>
        <div style='color:#888;font-size:11px;'>${tradingPermissions[code]!==false?'Торговля: ✅':'Торговля: ❌'}</div>
        <button class='cm-btn delete' type='button'>🗑️</button>
      `;

      row.querySelector('.cm-emoji-btn')?.addEventListener('click', () => showEmojiPicker(i));
      row.querySelector('.cm-symbol')?.addEventListener('click', () => showEmojiPicker(i));
      row.querySelector('.cm-btn.delete')?.addEventListener('click', () => deleteCurrencyRow(i));

      rows.appendChild(row);
    });
  }

  function addCurrencyRow(){
    const rows = $('currencyManagerRows');
    const i = rows.querySelectorAll('.cm-row').length;

    const row = document.createElement('div');
    row.className = 'cm-row';
    row.dataset.index = String(i);
    row.innerHTML = `
      <input type='text' class='cm-code' value='' placeholder='Код'>
      <div class='cm-symbol-picker'>
        <input type='text' class='cm-symbol' value='' placeholder='Символ' readonly>
        <button class='cm-emoji-btn' type='button' title='Выбрать символ'>😀</button>
      </div>
      <div style='color:#888;font-size:11px;'>Новая</div>
      <button class='cm-btn delete' type='button'>🗑️</button>
    `;

    row.querySelector('.cm-emoji-btn')?.addEventListener('click', () => showEmojiPicker(i));
    row.querySelector('.cm-symbol')?.addEventListener('click', () => showEmojiPicker(i));
    row.querySelector('.cm-btn.delete')?.addEventListener('click', () => deleteCurrencyRow(i));

    rows.appendChild(row);
  }

  function deleteCurrencyRow(idx){
    const rows = $('currencyManagerRows');
    const row = [...rows.querySelectorAll('.cm-row')].find(r => r.dataset.index == String(idx));
    if(row) row.remove();
  }

  async function saveCurrenciesList(){
    const rows = $('currencyManagerRows');
    const items = [...rows.querySelectorAll('.cm-row')]
      .map(r => ({
        code: r.querySelector('.cm-code').value.trim().toUpperCase(),
        symbol: r.querySelector('.cm-symbol').value.trim()
      }))
      .filter(o => o.code);

    if(!items.length){
      alert('Нужна минимум 1 валюта');
      return;
    }

    const codes = items.map(i => i.code);
    const dup = codes.filter((c, i) => codes.indexOf(c) !== i);
    if(dup.length){
      alert('Дубликаты: ' + dup.join(','));
      return;
    }

    try{
      const d = await api.saveCurrencies(items);
      if(d.success){
        setCurrenciesList(items);
        renderCurrencyTabs(items);
        closeCurrencyManager();
        logDbg('currencies saved');
      } else {
        alert('Ошибка: ' + (d.error || 'fail'));
      }
    }catch(e){
      alert('Ошибка сохранения: ' + e);
    }
  }

  async function syncCurrenciesFromGateIO(event){
    const syncBtn = event?.target;
    const originalText = syncBtn?.innerHTML;

    if(syncBtn){
      syncBtn.disabled = true;
      syncBtn.innerHTML = '⏳ Синхронизация...';
    }

    try {
      // Отправляем текущую котируемую валюту для проверки торговых пар
      const result = await api.syncCurrenciesFromGateIO(getCurrentQuoteCurrency?.() || 'USDT');

      if (result.success) {
        alert(
          `✅ Синхронизация символов завершена!\n\n` +
          `Котируемая валюта: ${result.quote_currency}\n` +
          `Обновлено символов: ${result.updated}\n` +
          `Пропущено валют: ${result.skipped}\n` +
          `Торгуемых пар: ${result.tradeable_count}\n` +
          `Всего валют: ${result.total}\n\n` +
          `Время: ${new Date(result.timestamp).toLocaleString('ru-RU')}\n\n` +
          `Примечание: Названия валют НЕ изменялись, обновлены только символы для валют, торгующихся с ${result.quote_currency}`
        );
        await loadCurrenciesFromServer();
        buildCurrencyManagerRows();
        updateSyncInfo();
      } else {
        alert(`❌ Ошибка синхронизации:\n\n${result.error}`);
      }
    } catch (e) {
      alert(`❌ Ошибка синхронизации:\n\n${e.message}`);
    } finally {
      if(syncBtn){
        syncBtn.disabled = false;
        syncBtn.innerHTML = originalText;
      }
    }
  }

  async function updateSyncInfo(){
    try {
      const data = await api.getSyncInfo();

      if (data.success && data.info) {
        const info = data.info;
        const syncInfoEl = $('syncInfo');

        if (syncInfoEl) {
          if (info.last_update) {
            const date = new Date(info.last_update);
            syncInfoEl.innerHTML = `
              <div style="text-align:right;">
                <div>Обновлено: ${date.toLocaleDateString('ru-RU')} ${date.toLocaleTimeString('ru-RU')}</div>
                <div>Валют: ${info.total_currencies} | Изменённых: ${info.custom_symbols}</div>
              </div>
            `;
          } else {
            syncInfoEl.textContent = 'Нет данных о синхронизации';
          }
        }
      }
    } catch (e) {
      console.warn('updateSyncInfo error', e);
    }
  }

  // Публичный API модуля (для проброса в window из app.js)
  return {
    openCurrencyManager,
    closeCurrencyManager,
    showEmojiPicker,
    showEmojiPickerFallback,
    selectEmoji,
    selectCustomEmoji,
    closeEmojiPicker,
    buildCurrencyManagerRows,
    addCurrencyRow,
    deleteCurrencyRow,
    saveCurrenciesList,
    syncCurrenciesFromGateIO,
    updateSyncInfo,
  };
}
