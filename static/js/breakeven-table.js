/**
 * BreakEven Table Module
 * 
 * Модуль для работы с таблицей безубыточности (breakeven table).
 * Отвечает за загрузку и отображение таблицы расчёта шагов докупки.
 * 
 * Функции:
 * - loadBreakEvenTable() - Загружает таблицу с сервера или использует сохранённую
 * - renderBreakEvenTable(table) - Отрисовывает таблицу в DOM
 * 
 * Зависимости:
 * - utils.js: $, logDbg
 * - ui-helpers.js: (косвенно через глобальные переменные)
 * 
 * Глобальные переменные:
 * - currentBaseCurrency
 * - currentQuoteCurrency
 */

import { $, logDbg } from './utils.js';

/**
 * Загружает таблицу безубыточности
 * - Если цикл активен - использует сохранённую таблицу из /api/trade/indicators
 * - Если цикл неактивен - пересчитывает таблицу с текущими параметрами
 */
export async function loadBreakEvenTable(){
  try{
    // Проверяем, что базовая валюта установлена
    if(!window.currentBaseCurrency){
      console.warn('[BREAKEVEN] Базовая валюта не установлена, устанавливаем WLD');
      window.currentBaseCurrency = 'WLD'; // Принудительная установка дефолтной валюты
    }
    
    // 🔴 КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Сначала проверяем, есть ли активный цикл с таблицей
    // Если цикл активен - используем СОХРАНЁННУЮ таблицу из /api/trade/indicators
    // Это предотвращает пересчёт таблицы с текущей ценой!
    try {
      // ✅ ИСПРАВЛЕНИЕ: Передаём include_table=1 для получения таблицы
      const indicatorsResp = await fetch(`/api/trade/indicators?base_currency=${window.currentBaseCurrency}&quote_currency=${window.currentQuoteCurrency}&include_table=1`);
      const indicatorsData = await indicatorsResp.json();
      
      // ✅ ИСПРАВЛЕНИЕ: Правильный путь к данным - autotrade_levels, а не indicators.cycle
      if (indicatorsData.success && indicatorsData.autotrade_levels) {
        const levels = indicatorsData.autotrade_levels;
        
        if (levels.active_cycle && levels.table && levels.table.length > 0) {
          // ✅ Цикл активен и таблица есть - используем её!
          console.log(`[BREAKEVEN] ✅ Используем сохранённую таблицу цикла (${levels.table.length} шагов, P0=${levels.table[0].rate}, start_price=${levels.start_price})`);
          
          // 🔧 МИГРАЦИЯ: Если в старой таблице нет orderbook_level - добавляем на лету!
          const needsMigration = levels.table[0] && levels.table[0].orderbook_level === undefined;
          if (needsMigration) {
            console.log(`[BREAKEVEN] 🔧 МИГРАЦИЯ: Добавляем orderbook_level в старую таблицу`);
            const orderbookLevelParam = parseFloat($('paramOrderbookLevel')?.value) || 0;
            levels.table.forEach((row, idx) => {
              row.orderbook_level = Math.round((idx * orderbookLevelParam) + 1);
            });
            console.log(`[BREAKEVEN] ✅ Миграция завершена: добавлено поле orderbook_level`);
          }
          
          // 🔴 КРИТИЧЕСКИ ВАЖНО: Обновляем поле start_price в форме!
          // Это гарантирует, что пользователь видит актуальный P0 для активного цикла
          const startPriceField = $('paramStartPrice');
          if (startPriceField && levels.start_price) {
            startPriceField.value = levels.start_price;
            console.log(`[BREAKEVEN] 📝 Поле start_price обновлено: ${levels.start_price}`);
          }
          
          renderBreakEvenTable(levels.table);
          return; // Выходим, не делаем пересчёт!
        } else {
          console.log(`[BREAKEVEN] Цикл неактивен (active=${levels.active_cycle}) или таблица отсутствует (table=${levels.table ? levels.table.length : 'null'})`);
        }
      }
    } catch (e) {
      console.warn('[BREAKEVEN] Не удалось проверить indicators:', e);
      // Продолжаем выполнение - попробуем пересчитать таблицу
    }
    
    // Если дошли сюда - цикл НЕ активен или таблица отсутствует
    // Пересчитываем таблицу с текущими параметрами
    console.log('[BREAKEVEN] Цикл неактивен или таблица отсутствует - пересчитываем с текущими параметрами');
    
    // Читаем текущие значения из полей формы (для мгновенного предпросмотра)
    const currentParams = {
      steps: parseInt($('paramSteps')?.value) || 16,
      start_volume: parseFloat($('paramStartVolume')?.value) || 3,
      start_price: parseFloat($('paramStartPrice')?.value) || 0,
      pprof: parseFloat($('paramPprof')?.value) || 0.6,
      kprof: parseFloat($('paramKprof')?.value) || 0.02,
      target_r: parseFloat($('paramTargetR')?.value) || 3.65,
      rk: parseFloat($('paramRk')?.value) || 0.0,
      geom_multiplier: parseFloat($('paramGeomMultiplier')?.value) || 2,
      rebuy_mode: $('paramRebuyMode')?.value || 'geometric',
      orderbook_level: parseFloat($('paramOrderbookLevel')?.value) || 1
    };
    
    // 🔍 ОТЛАДКА: Выводим прочитанные параметры
    console.log('[BREAKEVEN] 📊 Параметры из формы:', currentParams);
    console.log('[BREAKEVEN] 🔢 geom_multiplier:', currentParams.geom_multiplier);
    
    // Формируем URL с параметрами из формы
    const params = new URLSearchParams({
      base_currency: window.currentBaseCurrency,
      steps: currentParams.steps,
      start_volume: currentParams.start_volume,
      // start_price НЕ передаём, чтобы API использовал сохранённое значение из state_manager
      // это позволяет корректно отображать P0 после стартовой покупки
      pprof: currentParams.pprof,
      kprof: currentParams.kprof,
      target_r: currentParams.target_r,
      rk: currentParams.rk,
      geom_multiplier: currentParams.geom_multiplier,
      rebuy_mode: currentParams.rebuy_mode,
      orderbook_level: currentParams.orderbook_level
    });
    
    const url = `/api/breakeven/table?${params.toString()}`;
    
    // 🔍 ОТЛАДКА: Выводим финальный URL запроса
    console.log('[BREAKEVEN] 🌐 URL запроса:', url);
    
    const r = await fetch(url);
    const d = await r.json();
    
    // 🔍 ОТЛАДКА: Выводим ответ от сервера
    console.log('[BREAKEVEN] 📥 Ответ от сервера:', d);
    if(d.params) {
      console.log('[BREAKEVEN] 📋 Параметры из ответа:', d.params);
      console.log('[BREAKEVEN] 🔢 geom_multiplier из ответа:', d.params.geom_multiplier);
    }
    if(d.table && d.table.length > 0) {
      console.log('[BREAKEVEN] 📊 Первая строка таблицы:', d.table[0]);
      console.log('[BREAKEVEN] 📊 Вторая строка таблицы:', d.table[1]);
    }
    
    if(d.success && d.table){
      renderBreakEvenTable(d.table);
    }else{
      console.error('[BREAKEVEN] Ошибка:', d.error);
      logDbg('loadBreakEvenTable fail '+(d.error||''));
      renderBreakEvenTable([]);
    }
  }catch(e){ 
    console.error('[BREAKEVEN] Исключение:', e);
    logDbg('loadBreakEvenTable err '+e);
    renderBreakEvenTable([]);
  }
}

/**
 * Отрисовывает таблицу безубыточности в DOM
 * @param {Array} tableData - Массив строк таблицы (steps)
 */
export function renderBreakEvenTable(tableData){
  const body = $('breakEvenBody');
  
  if(!body){
    console.error('[BREAKEVEN] Элемент breakEvenBody не найден в DOM');
    return;
  }
  
  body.innerHTML='';
  
  if(!Array.isArray(tableData)||tableData.length===0){
    body.innerHTML=`<tr><td colspan="10" style='padding:12px;text-align:center;color:#999;'>Нет данных</td></tr>`;
    return;
  }
  
  // 🔍 ОТЛАДКА: Проверяем наличие ключевых полей
  console.log('[BREAKEVEN RENDER] Данные получены, строк:', tableData.length);
  if (tableData.length > 0) {
    const row0 = tableData[0];
    console.log('[BREAKEVEN RENDER] Первая строка:', row0);
    console.log('[BREAKEVEN RENDER] total_invested:', row0.total_invested !== undefined ? '✅ ЕСТЬ' : '❌ НЕТ', row0.total_invested);
    console.log('[BREAKEVEN RENDER] breakeven_pct:', row0.breakeven_pct !== undefined ? '✅ ЕСТЬ' : '❌ НЕТ', row0.breakeven_pct);
  }
  
  // Получаем текущее значение параметра "Стакан"
  const orderbookLevel = parseFloat($('paramOrderbookLevel')?.value) || 1;
  
  tableData.forEach((row,idx)=>{
    const tr=document.createElement('tr');
    const stepNum = row.step !== undefined ? row.step : idx;
    
    // Выделяем активный шаг ярким цветом, иначе чередуем строки
    const activeStep = window.getGlobalActiveStep ? window.getGlobalActiveStep() : null;
    const isActiveStep = activeStep !== null && stepNum === activeStep;
    if(isActiveStep){
      tr.style.background = '#2a4a2a'; // Яркий зелёный для активного шага
      tr.style.borderLeft = '4px solid #4CAF50';
      tr.style.fontWeight = '600';
    } else {
      tr.style.background = idx===0 ? '#1f2f1f' : (idx%2===0?'#1a1a1a':'transparent');
    }
    tr.style.borderBottom = '1px solid #2a2a2a';
    
    // Динамическая точность для курсов: Price Precision + 1
    const pricePrecisionPlus1 = (window.currentPairPricePrecision || 6) + 1;
    
    // Уровень стакана берём НАПРЯМУЮ из данных таблицы (без пересчёта!)
    // Значение соответствует индексу массива: 0 = bids[0], 1 = bids[1], и т.д.
    const orderbookLevelForStep = row.orderbook_level !== undefined ? row.orderbook_level : 0;
    
    // DEBUG: Выводим для первых 3 шагов
    if (stepNum <= 2) {
      console.log(`[TABLE_ROW] Шаг ${stepNum}: orderbook_level из данных = ${row.orderbook_level}, отображаем = ${orderbookLevelForStep}`);
    }
    
    // ↓, % - накопленная сумма процентов снижения
    const cumulativeDecrease = row.cumulative_decrease_pct !== undefined ? row.cumulative_decrease_pct.toFixed(3) : '—';
    // ↓Δ,% - шаг процента снижения
    const decreaseStep = row.decrease_step_pct !== undefined ? row.decrease_step_pct.toFixed(3) : '—';
    
    const rate = row.rate !== undefined ? row.rate.toFixed(pricePrecisionPlus1) : '—';
    const purchase = row.purchase_usd !== undefined ? row.purchase_usd.toFixed(2) : '—';
    const totalInv = row.total_invested !== undefined ? row.total_invested.toFixed(2) : '—';
    const breakEvenPrice = row.breakeven_price !== undefined ? row.breakeven_price.toFixed(pricePrecisionPlus1) : '—';
    const breakEvenPct = row.breakeven_pct !== undefined ? row.breakeven_pct.toFixed(2) : '—';
    const targetDelta = row.target_delta_pct !== undefined ? row.target_delta_pct.toFixed(2) : '—';
    
    // Цвета для процентов
    const cumulativeColor = row.cumulative_decrease_pct < 0 ? '#f44336' : '#999';
    const decreaseColor = row.decrease_step_pct < 0 ? '#ff6b6b' : '#999';
    const breakEvenColor = row.breakeven_pct > 0 ? '#4CAF50' : '#999';
    const targetColor = row.target_delta_pct > 0 ? '#4CAF50' : (row.target_delta_pct < 0 ? '#f44336' : '#999');
    
    tr.innerHTML = `
      <td style='padding:6px 8px;text-align:center;color:#e0e0e0;font-weight:600;'>${stepNum}</td>
      <td style='padding:6px 8px;text-align:center;color:#9C27B0;font-weight:600;' title='Уровень стакана (для пользователя): ${orderbookLevelForStep} → код использует массив[${orderbookLevelForStep - 1}]'>${orderbookLevelForStep}</td>
      <td style='padding:6px 8px;text-align:right;color:${cumulativeColor};font-weight:600;' title='Накопленная сумма процентов снижения'>${cumulativeDecrease}</td>
      <td style='padding:6px 8px;text-align:right;color:${decreaseColor};' title='Шаг процента: -((${stepNum} × Rk) + R)'>${decreaseStep}</td>
      <td style='padding:6px 8px;text-align:right;color:#e0e0e0;font-family:monospace;'>${rate}</td>
      <td style='padding:6px 8px;text-align:right;color:#4CAF50;'>${purchase}</td>
      <td style='padding:6px 8px;text-align:right;color:#2196F3;font-weight:600;'>${totalInv}</td>
      <td style='padding:6px 8px;text-align:right;color:#FF9800;font-family:monospace;'>${breakEvenPrice}</td>
      <td style='padding:6px 8px;text-align:right;color:${breakEvenColor};'>${breakEvenPct}</td>
      <td style='padding:6px 8px;text-align:right;color:${targetColor};font-weight:600;'>${targetDelta}</td>
    `;
    body.appendChild(tr);
  });
}
