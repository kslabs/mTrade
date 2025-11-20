"""
Модуль расчета таблицы безубыточности для multi-trading бота
"""

def calculate_breakeven_table(params: dict, current_price: float = 0.0) -> list:
    """
    Рассчитать таблицу безубыточности на основе параметров.
    
    Параметры из params:
    - steps: Число шагов (вкл. 0)
    - start_volume: Стартовый объём
    - start_price: Начальная цена (P0), 0 = использовать current_price
    - pprof: Pprof, %
    - kprof: Kprof
    - target_r: ↑ БезУб, % (цель R)
    - geom_multiplier: Множитель геометрии
    - rebuy_mode: Режим сумм докупок (fixed, geometric, martingale)
    
    Возвращает список строк таблицы с полями:
    - step: номер шага (0, 1, 2, ...)
    - decrease_pct: ↓, % (процент снижения)
    - rate: Курс
    - purchase_usd: Покупка, $
    - total_invested: Инв.Сумм,$
    - breakeven_price: Ц.БезУб,$
    - breakeven_pct: ↑ БезУб,%
    - target_delta_pct: tΔPsell, %
    """
    
    steps = params.get('steps', 16)
    start_volume = params.get('start_volume', 3.0)
    start_price = params.get('start_price', 0.0)
    pprof = params.get('pprof', 0.6)
    kprof = params.get('kprof', 0.02)
    target_r = params.get('target_r', 3.65)
    geom_multiplier = params.get('geom_multiplier', 2.0)
    rebuy_mode = params.get('rebuy_mode', 'geometric')
    
    # Если start_price = 0, используем current_price
    if start_price == 0 or start_price is None:
        start_price = current_price if current_price > 0 else 1.0
    
    # Вычисляем шаг снижения из target_r и количества шагов
    # target_r - это целевой процент роста для безубытка
    # Формула: step_decrease = target_r / steps
    step_decrease = target_r / steps if steps > 0 else 0.5
    
    table_data = []
    
    for step in range(steps + 1):
        # 1. # - номер шага
        step_num = step
        
        # 2. ↓, % - процент снижения курса на каждом шаге
        decrease_pct = -step * step_decrease if step > 0 else 0.0
        
        # 3. Курс - расчетный курс относительно стартового
        rate = start_price * (1 + decrease_pct / 100.0)
        
        # 4. Покупка, $ - сумма покупки на этом шаге
        if step == 0:
            purchase_usd = start_volume
        else:
            if rebuy_mode == 'fixed':
                purchase_usd = start_volume
            elif rebuy_mode == 'geometric':
                purchase_usd = start_volume * (geom_multiplier ** step)
            elif rebuy_mode == 'martingale':
                purchase_usd = start_volume * (2 ** step)
            else:
                purchase_usd = start_volume * (geom_multiplier ** step)
        
        # 5. Инв.Сумм,$ - общая сумма инвестирована до этого шага включительно
        total_invested = 0
        for s in range(step + 1):
            if s == 0:
                total_invested += start_volume
            else:
                if rebuy_mode == 'fixed':
                    total_invested += start_volume
                elif rebuy_mode == 'geometric':
                    total_invested += start_volume * (geom_multiplier ** s)
                elif rebuy_mode == 'martingale':
                    total_invested += start_volume * (2 ** s)
                else:
                    total_invested += start_volume * (geom_multiplier ** s)
        
        # 6. Ц.БезУб,$ - цена безубыточности (с учетом комиссий)
        # Рассчитываем общее количество купленных монет
        total_coins = 0
        for s in range(step + 1):
            if s == 0:
                step_purchase = start_volume
            else:
                if rebuy_mode == 'fixed':
                    step_purchase = start_volume
                elif rebuy_mode == 'geometric':
                    step_purchase = start_volume * (geom_multiplier ** s)
                elif rebuy_mode == 'martingale':
                    step_purchase = start_volume * (2 ** s)
                else:
                    step_purchase = start_volume * (geom_multiplier ** s)
            
            step_rate = start_price * (1 - s * step_decrease / 100.0)
            if step_rate > 0:
                total_coins += step_purchase / step_rate
        
        if total_coins > 0:
            # Цена безубыточности (средняя цена покупки)
            breakeven_price = total_invested / total_coins
        else:
            breakeven_price = 0.0
        
        # 7. ↑ БезУб,% - на сколько % должен вырасти курс для безубытка
        if rate > 0:
            breakeven_pct = ((breakeven_price - rate) / rate) * 100.0
        else:
            breakeven_pct = 0.0
        
        # 8. tΔPsell, % - процент роста для получения профита
        # Формула: ↑ БезУб,% + Pprof,% - (# * Kprof)
        target_delta_pct = breakeven_pct + pprof - (step * kprof)
        
        table_data.append({
            'step': step_num,
            'decrease_pct': decrease_pct,
            'rate': rate,
            'purchase_usd': purchase_usd,
            'total_invested': total_invested,
            'breakeven_price': breakeven_price,
            'breakeven_pct': breakeven_pct,
            'target_delta_pct': target_delta_pct
        })
    
    return table_data
