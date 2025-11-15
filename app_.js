window.__diagLogs=[];
function logDbg(m){
  try{
    __diagLogs.push(Date.now()+': '+m);
    if(__diagLogs.length>200) __diagLogs.shift();
  }catch(_){/* noop */}
  console.log('[DBG]',m);
}
const $=id=>document.getElementById(id);
let currentNetworkMode='work';
let currentBaseCurrency=null; // Будет установлено после загрузки currencies
let currentQuoteCurrency='USDT';
let currenciesList=[];
let autoTradeActive=false;
let autoTradeEnabled = true; // По умолчанию включено (ON), будет загружено из state
let tradingPermissions = {}; // статус разрешений торговли

// UI State Manager - простой менеджер для сохранения состояния UI
const UIStateManager = {
  async savePartial(updates) {
    try {
      // Преобразуем ключи в формат, ожидаемый сервером
      const stateUpdates = {};
      if (updates.baseCurrency) stateUpdates.active_base_currency = updates.baseCurrency;
      if (updates.quoteCurrency) stateUpdates.active_quote_currency = updates.quoteCurrency;
      if (updates.autoTradeEnabled !== undefined) stateUpdates.auto_trade_enabled = updates.autoTradeEnabled;
      if (updates.networkMode) stateUpdates.network_mode = updates.networkMode;
      if (updates.tradingMode) stateUpdates.trading_mode = updates.tradingMode;
      if (updates.breakeven_params) stateUpdates.breakeven_params = updates.breakeven_params;
      
      const response = await fetch('/api/ui/state/partial', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(stateUpdates)
      });
      const result = await response.json();
      if (result.success) {
        logDbg('UI State: частичное сохранение успешно - ' + JSON.stringify(stateUpdates));
      } else {
        logDbg('UI State: ошибка частичного сохранения - ' + (result.error || 'unknown'));
      }
      return result;
    } catch (error) {
      logDbg('UI State: исключение при сохранении - ' + error);
      return {success: false, error: String(error)};
    }
  }
};

function formatPrice(v){
  const n=parseFloat(v);
  if(isNaN(n)) return '-';
  if(n<0.0001 && n>0) return n.toExponential(4);
  if(n>=1000) return n.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:8});
  return n.toFixed(8).replace(/\.0+$/,'').replace(/0+$/,'')
}
function updateTradeIndicators(d){
  d=d||{};
  const priceEl=$('indPrice');
  if(priceEl&&d.price) priceEl.textContent=formatPrice(d.price);
  ['sell','be','last','start','buy'].forEach(k=>{
    const el=$('ind'+k.charAt(0).toUpperCase()+k.slice(1));
    if(el&&d[k]!==undefined){
      const v=d[k];
      el.textContent=(v===null||v===undefined)?'-':formatPrice(v)
    }
  })
}
function updateNetworkUI(){
  const sw=$('networkSwitcher');
  if(!sw) return;
  sw.classList.remove('work','test');
  sw.classList.add(currentNetworkMode==='test'?'test':'work');
  
  // Обновляем активность кнопок
  const workBtn = sw.querySelector('[data-mode="work"]');
  const testBtn = sw.querySelector('[data-mode="test"]');
  if(workBtn && testBtn){
    workBtn.classList.toggle('active', currentNetworkMode==='work');
    testBtn.classList.toggle('active', currentNetworkMode==='test');
  }
}
function setNetworkConnectionState(st){
  const sw=$('networkSwitcher');
  const cs=$('networkConnStatus');
  if(!sw) return;
  sw.classList.remove('pending','error');
  if(st==='pending'){
    sw.classList.add('pending');
    if(cs) cs.textContent='подключение...';
  }else if(st==='error'){
    sw.classList.add('error');
    if(cs) cs.textContent='ошибка';
  }else{
    if(cs) cs.textContent='';
  }
}
async function loadNetworkMode(){
  try{
    const r=await fetch('/api/network');
    const d=await r.json();
    if(d.success){
      currentNetworkMode=d.mode;
      updateNetworkUI();
      
      // Выводим информацию о текущем режиме и подключении
      console.log('========================================');
      console.log('[NETWORK] Текущий режим:', d.mode);
      if(d.api_host) console.log('[NETWORK] API Host:', d.api_host);
      if(d.api_key) console.log('[NETWORK] API Key:', d.api_key);
      if(d.keys_loaded !== undefined) {
        console.log('[NETWORK] Ключи загружены:', d.keys_loaded ? 'ДА' : 'НЕТ');
      }
      console.log('========================================');
      
      logDbg('network mode='+currentNetworkMode);
    }
  }catch(e){ 
    console.error('[NETWORK] Ошибка загрузки режима:', e);
    logDbg('loadNetworkMode err '+e);
  }
}
async function loadCurrenciesFromServer(){
  try{
    const r=await fetch('/api/currencies');
    const d=await r.json();
    if(d.success&&Array.isArray(d.currencies)){
      currenciesList=d.currencies;
      renderCurrencyTabs(currenciesList);
    } else {
      logDbg('loadCurrencies fail');
    }
  }catch(e){ logDbg('loadCurrencies exc '+e) }
}
function renderCurrencyTabs(list){
  const cont=$('currencyTabsContainer');
  if(!cont) return;
  cont.innerHTML='';
  const arr=Array.isArray(list)?list:[];
  logDbg('renderCurrencyTabs raw len='+(arr.length));
  let norm=arr.map(c=>{if(typeof c==='string')return {code:c.toUpperCase(),symbol:''};return {code:(c.code||'').toUpperCase(),symbol:(c.symbol||'').trim()};}).filter(o=>o.code);
  // Если список пуст – загрузить дефолтные
  if(!norm.length){
    logDbg('список пуст – добавляю дефолтные');
    norm=['BTC','ETH','SOL','BNB','XRP','ADA','AVAX','DOT','MATIC','LINK'].map(c=>({code:c,symbol:''}));
  }
  // Установить активную валюту: если текущая есть в списке - оставляем, иначе - первая из списка
  const codes=new Set(norm.map(o=>o.code));
  if(!currentBaseCurrency || !codes.has(currentBaseCurrency)){
    currentBaseCurrency=norm[0].code;
    logDbg('установлена активная валюта: '+currentBaseCurrency);
  }
  norm.forEach(cur=>{
    const el=document.createElement('div');
    el.className='tab-item'+(cur.code===currentBaseCurrency?' active':'');
    el.dataset.code=cur.code;
    el.innerHTML=`<span class='code-label'>${cur.code}</span>${cur.symbol?`<span class='symbol-label'>${cur.symbol}</span>`:''}`;
    el.onclick=()=>switchBaseCurrency(cur.code);
    cont.appendChild(el);
  });
  updatePairNameUI();
  updateTabsPermissionsUI();
}
function updatePairNameUI(){
  const pair=`${currentBaseCurrency}_${currentQuoteCurrency}`;
  const nameEl=$('currentPairName');
  const baseSym=$('baseSymbol');
  const quoteSym=$('quoteSymbol');
  const obQuote=$('obQuoteSymbol');
  if(nameEl){ nameEl.childNodes[0].nodeValue=pair+' '; }
  if(baseSym) baseSym.textContent=currentBaseCurrency;
  if(quoteSym) quoteSym.textContent=currentQuoteCurrency;
  if(obQuote) obQuote.textContent=currentQuoteCurrency;
}
async function switchBaseCurrency(code){
  currentBaseCurrency=code.toUpperCase();
  const cont=$('currencyTabsContainer');
  if(cont){
    [...cont.querySelectorAll('.tab-item')].forEach(n=>n.classList.toggle('active',n.dataset.code===currentBaseCurrency));
  }
  updatePairNameUI();
  logDbg(`switchBaseCurrency -> ${currentBaseCurrency}_${currentQuoteCurrency}`);
  await subscribeToPairData(currentBaseCurrency,currentQuoteCurrency);
  // Даём время WebSocket получить данные, затем загружаем их с force=true
  await new Promise(resolve => setTimeout(resolve, 1000));
  await loadMarketData(true);  // force refresh
  await loadPairBalances();
  await loadPairParams(true);
  await loadTradeParams();  // Загружаем параметры торговли для новой валюты
  await loadBreakEvenTable();  // Таблица автоматически обновится с новыми параметрами
  
  // Сохраняем выбор базовой валюты в UI state
  await UIStateManager.savePartial({baseCurrency: currentBaseCurrency});
}
async function changeQuoteCurrency(){
  const sel=document.querySelector('#quoteCurrency');
  if(!sel) return;
  currentQuoteCurrency=sel.value.toUpperCase();
  updatePairNameUI();
  logDbg(`changeQuoteCurrency -> ${currentBaseCurrency}_${currentQuoteCurrency}`);
  await subscribeToPairData(currentBaseCurrency,currentQuoteCurrency);
  // Даём время WebSocket получить данные, затем загружаем их с force=true
  await new Promise(resolve => setTimeout(resolve, 1000));
  await loadMarketData(true);  // force refresh
  await loadPairBalances();
  await loadPairParams(true);
  await loadTradeParams();  // Перезагружаем параметры для отображения правильной таблицы
  await loadBreakEvenTable();
}
// Функция для нового селектора котируемой валюты в заголовке "Рынок и стакан"
async function switchQuoteCurrency(newQuote){
  if(!newQuote) return;
  currentQuoteCurrency=newQuote.toUpperCase();
  
  // Синхронизируем оба селектора, если старый существует
  const oldSel=document.querySelector('#quoteCurrency');
  if(oldSel && oldSel.value!==currentQuoteCurrency){
    oldSel.value=currentQuoteCurrency;
  }
  
  updatePairNameUI();
  logDbg(`switchQuoteCurrency -> ${currentBaseCurrency}_${currentQuoteCurrency}`);
  await subscribeToPairData(currentBaseCurrency,currentQuoteCurrency);
  // Даём время WebSocket получить данные, затем загружаем их с force=true
  await new Promise(resolve => setTimeout(resolve, 1000));
  await loadMarketData(true);  // force refresh
  await loadPairBalances();
  await loadPairParams(true);
  await loadTradeParams();  // Обновляем параметры при смене валюты
  await loadBreakEvenTable();
  
  // Сохраняем выбор котируемой валюты в UI state
  await UIStateManager.savePartial({quoteCurrency: currentQuoteCurrency});
}
async function loadPairParams(force){
  try{
    const r=await fetch(`/api/pair/info?base_currency=${currentBaseCurrency}&quote_currency=${currentQuoteCurrency}${force?'&force=1':''}`);
    const d=await r.json();
    if(d.success){
      const info=d.data||{};
      if($('minQuoteAmount')) $('minQuoteAmount').textContent=info.min_quote_amount!=null?String(info.min_quote_amount):'-';
      if($('minBaseAmount')) $('minBaseAmount').textContent=info.min_base_amount!=null?String(info.min_base_amount):'-';
      if($('amountPrecision')) $('amountPrecision').textContent=info.amount_precision!=null?String(info.amount_precision):'-';
      if($('pricePrecision')) $('pricePrecision').textContent=info.price_precision!=null?String(info.price_precision):'-';
    }
  }catch(e){ logDbg('loadPairParams exc '+e) }
}
async function subscribeToPairData(base,quote){
  try{
    logDbg(`subscribeToPairData ${base}_${quote}`);
    setNetworkConnectionState('pending');
    const wsStatus=$('wsStatus');
    if(wsStatus){ wsStatus.textContent='🔄 Подключение...'; wsStatus.style.color='#ffa500'; }
    const resp=await fetch('/api/pair/subscribe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({base_currency:base,quote_currency:quote})});
    const data=await resp.json();
    if(data.success){
      if(wsStatus){ wsStatus.textContent='✅ WebSocket подключен'; wsStatus.style.color='#4caf50'; }
      setNetworkConnectionState('connected');
      setTimeout(()=>{
        try{
          loadMarketData();
          loadPairBalances();
          loadPairParams(true);
        }catch(e){ logDbg('post-subscribe load err '+e); }
      },800);
    }else{
      logDbg('subscribe error '+data.error);
      if(wsStatus){ wsStatus.textContent='❌ Ошибка подключения'; wsStatus.style.color='#f44336'; }
      setNetworkConnectionState('error');
    }
  }catch(e){
    logDbg('subscribe exception '+e);
    const wsStatus=$('wsStatus');
    if(wsStatus){ wsStatus.textContent='❌ Ошибка подключения'; wsStatus.style.color='#f44336'; }
    setNetworkConnectionState('error');
  }
}
async function loadMarketData(forceRefresh=false){
  try{
    const forceParam = forceRefresh ? '&force=1' : '';
    const r=await fetch(`/api/pair/data?base_currency=${currentBaseCurrency}&quote_currency=${currentQuoteCurrency}${forceParam}`);
    const d=await r.json();
    if(!d.success){ logDbg('loadMarketData fail '+(d.error||'')); return; }
    // Данные всегда в d.data
    const ob=d.data?.orderbook;
    const ticker=d.data?.ticker;
    if(ob && ob.asks && ob.bids) { 
      updateOrderBook(ob); 
      logDbg(`orderbook updated: ${ob.asks.length} asks, ${ob.bids.length} bids`);
    } else {
      logDbg('orderbook missing or empty');
    }
    if(ticker){
      const last=parseFloat(ticker.last||ticker.last_price||ticker.close||ticker.price||0);
      const priceStr=formatPrice(last);
      const cp=$('currentPrice'); if(cp) cp.textContent=priceStr;
      // Цена в заголовке "Рынок и стакан" с точностью 2 знака после запятой
      const pp=$('currentPairPrice'); 
      if(pp) pp.textContent='$'+(isNaN(last) ? '0.00' : last.toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2}));
      const sell=parseFloat(ticker.lowest_ask||ticker.ask||0);
      const bid=parseFloat(ticker.highest_bid||ticker.bid||0);
      const spread=(isFinite(sell)&&isFinite(bid)&&sell>0)?((sell-bid)/sell*100):null;
      const sv=$('spreadValue'); if(sv) sv.textContent=spread==null?'-':spread.toFixed(3)+'%';
      updateTradeIndicators({price:last});
    }
    loadPerBaseIndicators();
  }catch(e){ logDbg('loadMarketData exc '+e) }
}



// Редактирование баланса котируемой валюты (только в тестовом режиме)
async function editQuoteBalance(){
  alert('Редактирование баланса отключено. Используются только данные из API Gate.io');
}

// Загрузка тестового баланса с сервера (только для test режима)
async function loadTestBalance(){ return null; }

// Обновление отображения баланса в заголовке
function updateHeaderQuoteBalance(balance){
  const balanceEl=$('headerQuoteBalance');
  if(balanceEl){
    const bal=parseFloat(balance)||0;
    balanceEl.textContent=bal.toFixed(2);
    
    // В тестовом режиме делаем баланс кликабельным
    if(currentNetworkMode==='test'){
      balanceEl.style.cursor='pointer';
      balanceEl.title='🖱️ Клик для редактирования (ТЕСТОВЫЙ режим)';
    }else{
      balanceEl.style.cursor='default';
      balanceEl.title='Баланс котируемой валюты из API';
    }
  }
}

function updateOrderBook(ob){
  try{
    if(!ob||!Array.isArray(ob.asks)||!Array.isArray(ob.bids)) return;
    const asksEl=$('orderbookAsks');
    const bidsEl=$('orderbookBids');
    if(asksEl) asksEl.innerHTML='';
    if(bidsEl) bidsEl.innerHTML='';

    // Нормализуем и фильтруем данные
    const asksAll = ob.asks.map(r=>[parseFloat(r[0]), parseFloat(r[1])]).filter(r=>isFinite(r[0])&&isFinite(r[1]));
    const bidsAll = ob.bids.map(r=>[parseFloat(r[0]), parseFloat(r[1])]).filter(r=>isFinite(r[0])&&isFinite(r[1]));
    if(!asksAll.length && !bidsAll.length) return;

    // Центральная цена (mid) = среднее между лучшим бидом и лучшим аском
    const bestAsk = asksAll.length ? Math.min.apply(null, asksAll.map(r=>r[0])) : NaN;
    const bestBid = bidsAll.length ? Math.max.apply(null, bidsAll.map(r=>r[0])) : NaN;
    let mid = NaN;
    if(isFinite(bestAsk) && isFinite(bestBid)) mid = (bestAsk + bestBid)/2;
    else if(isFinite(bestAsk)) mid = bestAsk; else if(isFinite(bestBid)) mid = bestBid;

    // Сортируем по близости к центральной цене (минимальная разница первее)
    const asksSorted = isFinite(mid)
      ? asksAll.slice().sort((a,b)=>Math.abs(a[0]-mid)-Math.abs(b[0]-mid))
      : asksAll.slice().sort((a,b)=>a[0]-b[0]);
    const bidsSorted = isFinite(mid)
      ? bidsAll.slice().sort((a,b)=>Math.abs(a[0]-mid)-Math.abs(b[0]-mid))
      : bidsAll.slice().sort((a,b)=>b[0]-a[0]);

    // Кумулятивы: для асков снизу вверх, для бидов сверху вниз
    // Asks: разворачиваем массив, чтобы лучшие цены (ближе к спреду) были ВНИЗУ списка
    // (так они окажутся ближе к центральной линии спреда)
    const asksReversed = asksSorted.slice().reverse();
    const asksCum = [];
    let cumA = 0;
    for(let i = asksReversed.length - 1; i >= 0; i--) {
      cumA += asksReversed[i][1];
      asksCum[i] = cumA;
    }
    asksReversed.forEach((r, idx) => {
      const p=r[0], a=r[1], t=p*a;
      const div=document.createElement('div');
      div.className='orderbook-row';
      div.innerHTML=`<div class='price'>${formatPrice(p)}</div><div class='amount'>${a.toFixed(6)}</div><div class='total'>${t.toFixed(6)}</div><div class='cumulative'>${(asksCum[idx]||0).toFixed(4)}</div>`;
      if(asksEl) asksEl.appendChild(div);
    });

    let cumB=0;
    bidsSorted.forEach(r=>{
      const p=r[0], a=r[1], t=p*a; cumB+=a;
      const div=document.createElement('div');
      div.className='orderbook-row';
      div.innerHTML=`<div class='price'>${formatPrice(p)}</div><div class='amount'>${a.toFixed(6)}</div><div class='total'>${t.toFixed(6)}</div><div class='cumulative'>${cumB.toFixed(4)}</div>`;
      if(bidsEl) bidsEl.appendChild(div);
    });
    
    // Прокрутка к лучшим ценам:
    // Для asks: лучшие цены теперь ВНИЗУ списка (после reverse), прокручиваем вниз так, чтобы они были видны
    // Для bids: лучшие цены ВВЕРХУ списка, оставляем прокрутку в начале
    if(asksEl && asksEl.scrollHeight > asksEl.clientHeight){
      // Прокручиваем так, чтобы последние ~10 строк (лучшие цены) были видны
      asksEl.scrollTop = Math.max(0, asksEl.scrollHeight - asksEl.clientHeight);
    }
    if(bidsEl) bidsEl.scrollTop = 0; // прокрутка вверх к началу (к лучшим ценам)
  }catch(e){ logDbg('updateOrderBook err '+e) }
}
async function loadPerBaseIndicators(){
  try{
    const r=await fetch(`/api/trade/indicators?base_currency=${currentBaseCurrency}&quote_currency=${currentQuoteCurrency}`);
    const d=await r.json();
    if(d.success&&d.indicators){ updateTradeIndicators(d.indicators); }
  }catch(e){ logDbg('loadPerBaseIndicators err '+e) }
}
async function loadPairBalances(){
  if(!currentBaseCurrency||!currentQuoteCurrency) return;
  try{
    const r=await fetch(`/api/pair/balances?base_currency=${currentBaseCurrency}&quote_currency=${currentQuoteCurrency}`);
    const d=await r.json();
    if(d.success){
      const baseBalEl=document.getElementById('baseBalance');
      const baseUsdEl=document.getElementById('baseBalanceUSD');
      const quoteBalEl=document.getElementById('quoteBalance');
      const quoteSymEl=document.getElementById('quoteSymbol');
      const inlineEl=document.getElementById('quoteBalanceInline');
      const source=d.source||'empty';
      let baseAvail = parseFloat(d.balances?.base?.available||'0');
      let quoteAvail = parseFloat(d.balances?.quote?.available||'0');
      const baseEq=d.base_equivalent||0;
      // Если данных нет (source=empty) — показываем прочерки
      if(source==='empty'){
        if(baseBalEl) baseBalEl.textContent = '-'; else {}
        if(baseUsdEl) baseUsdEl.textContent = '≈ $-';
        if(quoteBalEl) quoteBalEl.textContent = '-';
        if(quoteSymEl) quoteSymEl.textContent=currentQuoteCurrency;
        if(inlineEl) inlineEl.textContent=`Баланс: - ${currentBaseCurrency} ≈ $-`;
        updateHeaderQuoteBalance('-');
        return;
      }
      if(baseBalEl) baseBalEl.textContent=(isFinite(baseAvail)?baseAvail:0).toFixed(8);
      if(baseUsdEl) baseUsdEl.textContent=`≈ $${(isFinite(baseEq)?baseEq:0).toFixed(2)}`;
      if(quoteBalEl) quoteBalEl.textContent=(isFinite(quoteAvail)?quoteAvail:0).toFixed(8);
      if(quoteSymEl) quoteSymEl.textContent=currentQuoteCurrency;
      if(inlineEl) inlineEl.textContent=`Баланс: ${(isFinite(baseAvail)?baseAvail:0).toFixed(8)} ${currentBaseCurrency} ≈ $${(isFinite(baseEq)?baseEq:0).toFixed(2)}`;
      updateHeaderQuoteBalance(quoteAvail);
    }
  }catch(e){ logDbg('loadPairBalances err '+e) }
}
function renderBreakEvenTable(tableData){
  console.log('[BREAKEVEN] === НАЧАЛО ОТРИСОВКИ ТАБЛИЦЫ ===');
  console.log('[BREAKEVEN] Получено строк:', tableData ? tableData.length : 'null');
  
  const body=$('breakEvenBody');
  console.log('[BREAKEVEN] Элемент #breakEvenBody:', body ? 'найден ✅' : 'НЕ НАЙДЕН ❌');
  
  if(!body){
    console.error('[BREAKEVEN] ❌ Элемент breakEvenBody не найден в DOM');
    console.error('[BREAKEVEN] Проверка document.getElementById:', document.getElementById('breakEvenBody'));
    return;
  }
  
  console.log('[BREAKEVEN] Очистка содержимого tbody...');
  body.innerHTML='';
  
  if(!Array.isArray(tableData)||tableData.length===0){
    console.warn('[BREAKEVEN] ⚠️ Нет данных для отображения');
    body.innerHTML=`<tr><td colspan="8" style='padding:12px;text-align:center;color:#999;'>Нет данных</td></tr>`;
    console.log('[BREAKEVEN] === КОНЕЦ ОТРИСОВКИ (нет данных) ===');
    return;
  }
  
  console.log('[BREAKEVEN] 🎨 Отрисовка таблицы, строк:', tableData.length);
  
  tableData.forEach((row,idx)=>{
    const tr=document.createElement('tr');
    tr.style.background = idx===0 ? '#1f2f1f' : (idx%2===0?'#1a1a1a':'transparent');
    tr.style.borderBottom = '1px solid #2a2a2a';
    
    // Форматируем значения
    const stepNum = row.step !== undefined ? row.step : idx;
    const decrease = row.decrease_pct !== undefined ? row.decrease_pct.toFixed(2) : '—';
    const rate = row.rate !== undefined ? row.rate.toFixed(8) : '—';
    const purchase = row.purchase_usd !== undefined ? row.purchase_usd.toFixed(2) : '—';
    const totalInv = row.total_invested !== undefined ? row.total_invested.toFixed(2) : '—';
    const breakEvenPrice = row.breakeven_price !== undefined ? row.breakeven_price.toFixed(8) : '—';
    const breakEvenPct = row.breakeven_pct !== undefined ? row.breakeven_pct.toFixed(2) : '—';
    const targetDelta = row.target_delta_pct !== undefined ? row.target_delta_pct.toFixed(2) : '—';
    
    // Цвета для процентов
    const decreaseColor = row.decrease_pct < 0 ? '#f44336' : '#999';
    const breakEvenColor = row.breakeven_pct > 0 ? '#4CAF50' : '#999';
    const targetColor = row.target_delta_pct > 0 ? '#4CAF50' : (row.target_delta_pct < 0 ? '#f44336' : '#999');
    
    tr.innerHTML = `
      <td style='padding:6px 8px;text-align:center;color:#e0e0e0;font-weight:600;'>${stepNum}</td>
      <td style='padding:6px 8px;text-align:right;color:${decreaseColor};'>${decrease}</td>
      <td style='padding:6px 8px;text-align:right;color:#e0e0e0;font-family:monospace;'>${rate}</td>
      <td style='padding:6px 8px;text-align:right;color:#4CAF50;'>${purchase}</td>
      <td style='padding:6px 8px;text-align:right;color:#2196F3;font-weight:600;'>${totalInv}</td>
      <td style='padding:6px 8px;text-align:right;color:#FF9800;font-family:monospace;'>${breakEvenPrice}</td>
      <td style='padding:6px 8px;text-align:right;color:${breakEvenColor};'>${breakEvenPct}</td>
      <td style='padding:6px 8px;text-align:right;color:${targetColor};font-weight:600;'>${targetDelta}</td>
    `;
    body.appendChild(tr);
  });
  
  console.log('[BREAKEVEN] ✅ Все строки добавлены в DOM');
  console.log('[BREAKEVEN] Итого строк в tbody:', body.children.length);
  console.log('[BREAKEVEN] === КОНЕЦ ОТРИСОВКИ ===');
}
async function loadBreakEvenTable(){
  console.log('[BREAKEVEN] === НАЧАЛО ЗАГРУЗКИ ТАБЛИЦЫ ===');
  console.log('[BREAKEVEN] currentBaseCurrency =', currentBaseCurrency);
  
  try{
    // Проверяем, что базовая валюта установлена
    if(!currentBaseCurrency){
      console.warn('[BREAKEVEN] ❌ Базовая валюта не установлена, пропускаем загрузку');
      console.warn('[BREAKEVEN] Устанавливаем дефолтную валюту WLD');
      currentBaseCurrency = 'WLD'; // Принудительная установка дефолтной валюты
    }
    
    // Читаем текущие значения из полей формы (для мгновенного предпросмотра)
    const currentParams = {
      steps: parseInt($('paramSteps')?.value) || 16,
      start_volume: parseFloat($('paramStartVolume')?.value) || 3,
      start_price: parseFloat($('paramStartPrice')?.value) || 0,
      pprof: parseFloat($('paramPprof')?.value) || 0.6,
      kprof: parseFloat($('paramKprof')?.value) || 0.02,
      target_r: parseFloat($('paramTargetR')?.value) || 3.65,
      geom_multiplier: parseFloat($('paramGeomMultiplier')?.value) || 2,
      rebuy_mode: $('paramRebuyMode')?.value || 'geometric'
    };
    
    // Формируем URL с параметрами из формы
    const params = new URLSearchParams({
      base_currency: currentBaseCurrency,
      steps: currentParams.steps,
      start_volume: currentParams.start_volume,
      start_price: currentParams.start_price,
      pprof: currentParams.pprof,
      kprof: currentParams.kprof,
      target_r: currentParams.target_r,
      geom_multiplier: currentParams.geom_multiplier,
      rebuy_mode: currentParams.rebuy_mode
    });
    
    const url = `/api/breakeven/table?${params.toString()}`;
    console.log('[BREAKEVEN] 📡 Запрос:', url);
    console.log('[BREAKEVEN] 📊 Параметры:', currentParams);
    
    const r = await fetch(url);
    console.log('[BREAKEVEN] 📥 Статус ответа:', r.status, r.statusText);
    
    const d = await r.json();
    console.log('[BREAKEVEN] 📦 Данные получены:', {
      success: d.success,
      currency: d.currency,
      table_length: d.table ? d.table.length : 0,
      current_price: d.current_price,
      legacy: d.legacy
    });
    
    if(d.success && d.table){
      console.log('[BREAKEVEN] ✅ Таблица получена, строк:', d.table.length);
      console.log('[BREAKEVEN] Первая строка:', d.table[0]);
      console.log('[BREAKEVEN] Последняя строка:', d.table[d.table.length - 1]);
      console.log('[BREAKEVEN] 🎨 Вызов renderBreakEvenTable...');
      renderBreakEvenTable(d.table);
      console.log('[BREAKEVEN] ✅ renderBreakEvenTable завершен');
    }else{
      console.error('[BREAKEVEN] ❌ Ошибка:', d.error);
      logDbg('loadBreakEvenTable fail '+(d.error||''));
      renderBreakEvenTable([]);
    }
  }catch(e){ 
    console.error('[BREAKEVEN] ❌ Исключение:', e);
    console.error('[BREAKEVEN] Stack trace:', e.stack);
    logDbg('loadBreakEvenTable err '+e);
    renderBreakEvenTable([]);
  }
  
  console.log('[BREAKEVEN] === КОНЕЦ ЗАГРУЗКИ ТАБЛИЦЫ ===');
}

// Функции для работы с параметрами торговли
async function loadTradeParams(){
  try{
    console.log('[PARAMS] === ЗАГРУЗКА ПАРАМЕТРОВ ===');
    console.log('[PARAMS] currentBaseCurrency =', currentBaseCurrency);
    
    // Загружаем параметры для текущей валюты (per-currency)
    const url = currentBaseCurrency 
      ? `/api/trade/params?base_currency=${currentBaseCurrency}` 
      : '/api/trade/params';
    
    console.log('[PARAMS] 📡 Запрос:', url);
    
    const r=await fetch(url);
    const d=await r.json();
    
    console.log('[PARAMS] 📦 Данные получены:', d);
    
    if(d.success && d.params){
      $('paramSteps').value = d.params.steps || 16;
      $('paramStartVolume').value = d.params.start_volume || 3;
      $('paramStartPrice').value = d.params.start_price || 0;
      $('paramPprof').value = d.params.pprof || 0.6;
      $('paramKprof').value = d.params.kprof || 0.02;
      $('paramTargetR').value = d.params.target_r || 3.65;
      $('paramGeomMultiplier').value = d.params.geom_multiplier || 2;
      $('paramRebuyMode').value = d.params.rebuy_mode || 'geometric';
      $('paramKeep').value = d.params.keep || 0;
      console.log('[PARAMS] ✅ Параметры загружены для', d.currency || 'LEGACY');
    } else {
      console.warn('[PARAMS] ⚠️ Не удалось загрузить параметры');
    }
  }catch(e){ 
    console.error('[PARAMS] ❌ Ошибка загрузки:', e);
    logDbg('loadTradingMode err '+e);
  }
}

async function saveTradeParams(){
  const statusEl = $('paramsSaveStatus');
  try{
    console.log('[PARAMS] === НАЧАЛО СОХРАНЕНИЯ ПАРАМЕТРОВ ===');
    console.log('[PARAMS] currentBaseCurrency =', currentBaseCurrency);
    
    const params = {
      base_currency: currentBaseCurrency, // Добавляем текущую валюту
      steps: parseInt($('paramSteps').value) || 16,
      start_volume: parseFloat($('paramStartVolume').value) || 3,
      start_price: parseFloat($('paramStartPrice').value) || 0,
      pprof: parseFloat($('paramPprof').value) || 0.6,
      kprof: parseFloat($('paramKprof').value) || 0.02,
      target_r: parseFloat($('paramTargetR').value) || 3.65,
      geom_multiplier: parseFloat($('paramGeomMultiplier').value) || 2,
      rebuy_mode: $('paramRebuyMode').value || 'geometric',
      keep: parseFloat($('paramKeep').value) || 0
    };
    
    console.log('[PARAMS] Параметры для сохранения:', params);
    
    statusEl.textContent = 'Сохранение...';
    statusEl.className = 'params-save-status';
    
    const r = await fetch('/api/trade/params', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(params)
    });
    
    const d = await r.json();
    console.log('[PARAMS] Ответ сервера:', d);
    
    if(d.success){
      statusEl.textContent = '✓ Сохранено';
      statusEl.className = 'params-save-status';
      setTimeout(()=>{ statusEl.textContent = ''; }, 3000);
      console.log('[PARAMS] ✅ Параметры сохранены, перезагрузка таблицы...');
      
      // Сохраняем также в UI state для восстановления после перезагрузки
      await UIStateManager.savePartial({
        breakeven_params: {
          currency: currentBaseCurrency,
          ...params
        }
      });
      
      // Перезагружаем таблицу break-even после сохранения параметров
      await loadBreakEvenTable();
      console.log('[PARAMS] ✅ Таблица перезагружена');
    }else{
      statusEl.textContent = '✗ ' + (d.error || 'Ошибка');
      statusEl.className = 'params-save-status error';
      console.error('[PARAMS] ❌ Ошибка сохранения:', d.error);
    }
  }catch(e){ 
    statusEl.textContent = '✗ ' + e.message;
    statusEl.className = 'params-save-status error';
    console.error('[PARAMS] ❌ Исключение:', e);
    logDbg('saveTradeParams err '+e);
  }
  console.log('[PARAMS] === КОНЕЦ СОХРАНЕНИЯ ПАРАМЕТРОВ ===');
}

// Новая функция для переключения режима с явным указанием
async function switchNetworkMode(targetMode){
  if(!targetMode || !['work','test'].includes(targetMode)) return;
  if(currentNetworkMode === targetMode) return; // уже в этом режиме
  
  console.log('========================================');
  console.log('[NETWORK] Переключение на режим:', targetMode);
  logDbg('switchNetworkMode -> '+targetMode);
  
  try{
    const resp=await fetch('/api/network',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode:targetMode})});
    const data=await resp.json();
    logDbg('network POST resp '+JSON.stringify(data));
    
    if(data.success){
      currentNetworkMode=data.mode;
      
      // Выводим подробную информацию о подключении
      console.log('[NETWORK] ✓ Режим переключен:', data.mode);
      if(data.api_host) console.log('[NETWORK]   API Host:', data.api_host);
      if(data.api_key) console.log('[NETWORK]   API Key:', data.api_key);
      if(data.keys_loaded !== undefined) {
        console.log('[NETWORK]   Ключи загружены:', data.keys_loaded ? 'ДА' : 'НЕТ');
      }
      console.log('========================================');
      
      updateNetworkUI();
      
      // Сохраняем состояние в UI state
      await UIStateManager.savePartial({networkMode: data.mode});
      
      setNetworkConnectionState('pending');
      await loadCurrenciesFromServer();
      // Подписываемся на ВСЕ валюты при переключении режима
      await subscribeToAllCurrencies();
      
      // Даём время на подписку и подключение WebSocket
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      // Принудительно обновляем все данные с сервера
      console.log('[NETWORK] Обновление данных после переключения режима...');
      await loadMarketData(true);  // force=true
      await loadPairBalances();
      await loadPairParams(true);
      await loadBreakEvenTable();
      
      setNetworkConnectionState('ok');
      console.log('[NETWORK] Переключение завершено успешно ✅');
    }else{
      console.error('[NETWORK] ❌ Ошибка переключения:', data.error || 'неизвестная ошибка');
      console.log('========================================');
      logDbg('network switch fail '+(data.error||''));
      setNetworkConnectionState('error');
    }
  }catch(e){
    console.error('[NETWORK] ❌ Исключение при переключении:', e);
    console.log('========================================');
    logDbg('switchNetworkMode exception '+e);
    setNetworkConnectionState('error');
  }
}

// Старая функция для совместимости (toggle между work/test)
async function toggleNetworkMode(){
  const next=currentNetworkMode==='work'?'test':'work';
  await switchNetworkMode(next);
}

// === Trading mode switcher (normal/copy) ===
let currentTradingMode = 'normal';

async function switchTradingMode(targetMode){
  if(!targetMode || !['normal','copy'].includes(targetMode)) return;
  if(currentTradingMode === targetMode) {
    console.log('[TRADE MODE] Уже в режиме:', targetMode);
    return; // уже в этом режиме
  }
  
  console.log('[TRADE MODE] Переключение:', currentTradingMode, '->', targetMode);
  logDbg('switchTradingMode -> '+targetMode);
  try{
    // Преобразуем 'normal' -> 'trade' для API
    const apiMode = targetMode === 'normal' ? 'trade' : targetMode;
    console.log('[TRADE MODE] Отправка на сервер:', apiMode);
    const resp=await fetch('/api/mode',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode:apiMode})});
    const data=await resp.json();
    console.log('[TRADE MODE] Ответ сервера:', data);
    logDbg('trading mode POST resp '+JSON.stringify(data));
    if(data.success){
      // Преобразуем 'trade' -> 'normal' для UI
      currentTradingMode = data.mode === 'trade' ? 'normal' : data.mode;
      console.log('[TRADE MODE] Установлен новый режим (нормализованный):', currentTradingMode);
      updateTradingModeUI();
      // Сохраняем состояние в UI state
      await UIStateManager.savePartial({tradingMode: data.mode});
    }else{
      console.error('[TRADE MODE] Ошибка переключения:', data.error);
      logDbg('trading mode switch fail '+(data.error||''));
    }
  }catch(e){
    console.error('[TRADE MODE] Исключение:', e);
    logDbg('switchTradingMode exception '+e);
  }
}

function updateTradingModeUI(){
  const sw=$('tradingModeSwitcher');
  if(!sw) return;
  
  // Обновляем активность кнопок
  const normalBtn = sw.querySelector('[data-mode="normal"]');
  const copyBtn = sw.querySelector('[data-mode="copy"]');
  if(normalBtn && copyBtn){
    // Явно удаляем класс active у обеих кнопок
    normalBtn.classList.remove('active');
    copyBtn.classList.remove('active');
    
    // Добавляем класс active только активной кнопке
    if(currentTradingMode==='normal' || currentTradingMode==='trade'){
      normalBtn.classList.add('active');
    }else if(currentTradingMode==='copy'){
      copyBtn.classList.add('active');
    }
    
    logDbg('Trading mode UI updated: ' + currentTradingMode);
  }
}
async function loadTradingMode(){
  try{
    const r=await fetch('/api/mode');
    const d=await r.json();
    console.log('[TRADE MODE] Загружен режим с сервера:', d);
    if(d.mode){
      // Преобразуем 'trade' -> 'normal' для совместимости с UI
      currentTradingMode = d.mode === 'trade' ? 'normal' : d.mode;
      updateTradingModeUI();
      console.log('[TRADE MODE] Текущий режим (нормализованный):', currentTradingMode);
      logDbg('trading mode='+currentTradingMode);
    }
  }catch(e){ 
    console.error('[TRADE MODE] Ошибка загрузки:', e);
    logDbg('loadTradingMode err '+e);
  }
}

// === AutoTrade switcher ===

async function toggleAutoTrade(){
  autoTradeEnabled = !autoTradeEnabled;
  updateAutoTradeUI();
  logDbg('AutoTrade toggled: ' + (autoTradeEnabled ? 'ON' : 'OFF'));
  
  // Отправляем запрос на сервер
  try {
    const endpoint = autoTradeEnabled ? '/api/autotrade/start' : '/api/autotrade/stop';
    const response = await fetch(endpoint, { method: 'POST' });
    const result = await response.json();
    if (result.success) {
      logDbg('AutoTrade: ' + (autoTradeEnabled ? 'запущен' : 'остановлен'));
      // Сохраняем состояние в UI state
      await UIStateManager.savePartial({autoTradeEnabled: autoTradeEnabled});
    } else {
      logDbg('AutoTrade: ошибка - ' + (result.error || 'неизвестная ошибка'));
      // Откатываем состояние при ошибке
      autoTradeEnabled = !autoTradeEnabled;
      updateAutoTradeUI();
    }
  } catch (error) {
    logDbg('AutoTrade: ошибка запроса - ' + error);
    // Откатываем состояние при ошибке
    autoTradeEnabled = !autoTradeEnabled;
    updateAutoTradeUI();
  }
}

function updateAutoTradeUI(){
  const sw=$('autoTradeSwitcher');
  if(!sw) return;
  
  const offBtn = sw.querySelector('[data-state="off"]');
  const onBtn = sw.querySelector('[data-state="on"]');
  if(offBtn && onBtn){
    offBtn.classList.toggle('active', !autoTradeEnabled);
    onBtn.classList.toggle('active', autoTradeEnabled);
  }
}

// Загрузка состояния UI с сервера
async function loadUIState() {
  try {
    const response = await fetch('/api/ui/state');
    const result = await response.json();
    if (result.success && result.state) {
      const state = result.state;
      
      // ВАЖНО: Восстанавливаем режим сети ПЕРВЫМ
      if (state.network_mode) {
        currentNetworkMode = state.network_mode;
        updateNetworkUI();
        logDbg('UI State: режим сети восстановлен - ' + currentNetworkMode);
      }
      
      // Восстанавливаем состояние автотрейдинга
      if (typeof state.auto_trade_enabled === 'boolean') {
        autoTradeEnabled = state.auto_trade_enabled;
        updateAutoTradeUI();
        logDbg('UI State: автотрейдинг восстановлен - ' + (autoTradeEnabled ? 'ON' : 'OFF'));
      }
      
      // Восстанавливаем разрешения торговли для валют
      if (state.enabled_currencies && typeof state.enabled_currencies === 'object') {
        Object.assign(tradingPermissions, state.enabled_currencies);
        updateTabsPermissionsUI();
        logDbg('UI State: разрешения торговли восстановлены');
      }
      
      // Восстанавливаем активную валютную пару
      if (state.active_base_currency) {
        currentBaseCurrency = state.active_base_currency;
        logDbg('UI State: базовая валюта восстановлена - ' + currentBaseCurrency);
      }
      if (state.active_quote_currency) {
        currentQuoteCurrency = state.active_quote_currency;
        // Синхронизируем селектор котируемой валюты в заголовке
        const quoteSel = document.querySelector('#quoteCurrencySelect');
        if (quoteSel) quoteSel.value = currentQuoteCurrency;
        logDbg('UI State: котировочная валюта восстановлена - ' + currentQuoteCurrency);
      }
      
      // Восстанавливаем режим торговли
      if (state.trading_mode) {
        // Нормализуем режим ('trade' -> 'normal' для UI)
        currentTradingMode = state.trading_mode === 'trade' ? 'normal' : state.trading_mode;
        updateTradingModeUI();
        logDbg('UI State: режим торговли восстановлен - ' + currentTradingMode);
      }
      
      // Восстанавливаем параметры безубыточности для текущей валюты
      if (state.breakeven_params && currentBaseCurrency) {
        const params = state.breakeven_params[currentBaseCurrency];
        if (params) {
          if (params.steps !== undefined) $('paramSteps').value = params.steps;
          if (params.start_volume !== undefined) $('paramStartVolume').value = params.start_volume;
          if (params.start_price !== undefined) $('paramStartPrice').value = params.start_price;
          if (params.pprof !== undefined) $('paramPprof').value = params.pprof;
          if (params.kprof !== undefined) $('paramKprof').value = params.kprof;
          if (params.target_r !== undefined) $('paramTargetR').value = params.target_r;
          if (params.geom_multiplier !== undefined) $('paramGeomMultiplier').value = params.geom_multiplier;
          if (params.rebuy_mode !== undefined) $('paramRebuyMode').value = params.rebuy_mode;
          if (params.keep !== undefined) $('paramKeep').value = params.keep;
          logDbg('UI State: параметры безубыточности восстановлены для ' + currentBaseCurrency);
        }
      }
      
      logDbg('UI State: состояние успешно загружено');
    }
  } catch (error) {
    logDbg('UI State: ошибка загрузки - ' + error);
  }
}

function openCurrencyManager(){buildCurrencyManagerRows();$('currencyManagerModal').style.display='flex';}
function closeCurrencyManager(){$('currencyManagerModal').style.display='none';}

// Популярные символы для криптовалют
const popularCryptoEmojis = [
  '₿', '💎', '🚀', '🌐', 'Ξ', '◎', '🔶', '✕', '₳', 
  '🔺', '⬤', '💠', '🔷', '💰', '🪙', '💵', '💴', '💶',
  '💷', '⚡', '🔥', '🌟', '⭐', '💫', '✨', '🎯', '🎪',
  '🎨', '🔮', '🌈', '🦄', '🐉', '🦅', '🦊', '🐺', '🦁'
];

let currentEmojiPickerRow = -1;

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
      ${popularCryptoEmojis.map(e => `<div class="emoji-item" onclick="selectEmoji('${e}')">${e}</div>`).join('')}
    </div>
    <div class="emoji-picker-custom">
      <input type="text" id="customEmojiInput" placeholder="Или введите свой символ" maxlength="4" value="${currentSymbol}">
      <button onclick="selectCustomEmoji()">✓</button>
    </div>
    <button class="emoji-picker-close" onclick="closeEmojiPicker()">✖</button>
  `;
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

function buildCurrencyManagerRows(){const rows=$('currencyManagerRows');if(!rows)return;rows.innerHTML='';const arr=Array.isArray(currenciesList)?currenciesList:[];arr.forEach((c,i)=>{const code=(c.code||c||'').toUpperCase();const symbol=(c.symbol||c.code||c||'');const row=document.createElement('div');row.className='cm-row';row.dataset.index=i;row.innerHTML=`<input type='text' class='cm-code' value='${code}' placeholder='Код'><div class='cm-symbol-picker'><input type='text' class='cm-symbol' value='${symbol}' placeholder='Символ' readonly onclick='showEmojiPicker(${i})'><button class='cm-emoji-btn' onclick='showEmojiPicker(${i})' title='Выбрать символ'>😀</button></div><div style='color:#888;font-size:11px;'>${tradingPermissions[code]!==false?'Торговля: ✅':'Торговля: ❌'}</div><button class='cm-btn delete' onclick='deleteCurrencyRow(${i})'>🗑️</button>`;rows.appendChild(row);});}
function addCurrencyRow(){const rows=$('currencyManagerRows');const i=rows.querySelectorAll('.cm-row').length;const row=document.createElement('div');row.className='cm-row';row.dataset.index=i;row.innerHTML=`<input type='text' class='cm-code' value='' placeholder='Код'><div class='cm-symbol-picker'><input type='text' class='cm-symbol' value='' placeholder='Символ' readonly onclick='showEmojiPicker(${i})'><button class='cm-emoji-btn' onclick='showEmojiPicker(${i})' title='Выбрать символ'>😀</button></div><div style='color:#888;font-size:11px;'>Новая</div><button class='cm-btn delete' onclick='deleteCurrencyRow(${i})'>🗑️</button>`;rows.appendChild(row);}
function deleteCurrencyRow(idx){const rows=$('currencyManagerRows');const row=[...rows.querySelectorAll('.cm-row')].find(r=>r.dataset.index==idx);if(row)row.remove();}
function saveCurrenciesList(){const rows=$('currencyManagerRows');const items=[...rows.querySelectorAll('.cm-row')].map(r=>({code:r.querySelector('.cm-code').value.trim().toUpperCase(),symbol:r.querySelector('.cm-symbol').value.trim()})).filter(o=>o.code);if(!items.length){alert('Нужна минимум 1 валюта');return;}const codes=items.map(i=>i.code);const dup=codes.filter((c,i)=>codes.indexOf(c)!==i);if(dup.length){alert('Дубликаты: '+dup.join(','));return;}fetch('/api/currencies',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({currencies:items})}).then(r=>r.json()).then(d=>{if(d.success){currenciesList=items;renderCurrencyTabs(currenciesList);closeCurrencyManager();logDbg('currencies saved');}else alert('Ошибка: '+(d.error||'fail'))}).catch(e=>alert('Ошибка сохранения: '+e));}

// === Currency Sync with Gate.io ===
async function syncCurrenciesFromGateIO() {
  const syncBtn = event.target;
  const originalText = syncBtn.innerHTML;
  
  syncBtn.disabled = true;
  syncBtn.innerHTML = '⏳ Синхронизация...';
  
  try {
    const response = await fetch('/api/currencies/sync', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'}
    });
    
    const result = await response.json();
    
    if (result.success) {
      // Показываем результат
      alert(`✅ Синхронизация завершена!\n\n` +
            `Добавлено валют: ${result.added}\n` +
            `Обновлено валют: ${result.updated}\n` +
            `Всего валют: ${result.total}\n\n` +
            `Время: ${new Date(result.timestamp).toLocaleString('ru-RU')}`);
      
      // Перезагружаем список валют
      await loadCurrenciesList();
      buildCurrencyManagerRows();
      updateSyncInfo();
      
    } else {
      alert(`❌ Ошибка синхронизации:\n\n${result.error}`);
    }
    
  } catch (e) {
    alert(`❌ Ошибка синхронизации:\n\n${e.message}`);
  } finally {
    syncBtn.disabled = false;
    syncBtn.innerHTML = originalText;
  }
}

async function updateSyncInfo() {
  try {
    const response = await fetch('/api/currencies/sync-info');
    const data = await response.json();
    
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
          syncInfoEl.innerHTML = '<div style="color:#ff9800;">Синхронизация не выполнялась</div>';
        }
      }
    }
  } catch (e) {
    logDbg('updateSyncInfo error: ' + e);
  }
}

// Обновляем информацию о синхронизации при открытии менеджера валют
const originalOpenCurrencyManager = window.openCurrencyManager;
window.openCurrencyManager = function() {
  if (originalOpenCurrencyManager) {
    originalOpenCurrencyManager();
  }
  updateSyncInfo();
};