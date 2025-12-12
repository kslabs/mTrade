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

    - target_r: R - шаг изменения процента закупки (точность 3 знака после запятой)

    - rk: Rk - коэффициент изменения шага процента закупки (точность 3 знака после запятой)

    - geom_multiplier: Множитель геометрии

    - rebuy_mode: Режим сумм докупок (fixed, geometric, martingale)

    - orderbook_level: Базовый уровень стакана (по умолчанию 0 = лучшая цена)

    

    Формула расчёта процента снижения на шаге: decrease_step_pct = -((# × Rk) + R)

    

    Возвращает список строк таблицы с полями:

    - step: номер шага (0, 1, 2, ...)

    - orderbook_level: Уровень стакана для этого шага (формула: step × base_orderbook_level)

    - decrease_step_pct: ↓Δ,% (процент снижения на шаге, рассчитывается по формуле выше)

    - cumulative_decrease_pct: ↓, % (накопленная сумма процентов снижения)

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

    target_r = params.get('target_r', 3.65)  # Параметр R - шаг изменения процента закупки

    rk = params.get('rk', 0.0)  # Параметр Rk - коэффициент изменения шага процента закупки

    geom_multiplier = params.get('geom_multiplier', 2.0)

    rebuy_mode = params.get('rebuy_mode', 'geometric')

    base_orderbook_level = params.get('orderbook_level', 1)  # Базовый уровень стакана для расчёта

    

    # DEBUG: Выводим параметр для проверки

    print(f"[BREAKEVEN_CALC] base_orderbook_level = {base_orderbook_level} (из params: {params.get('orderbook_level', 'НЕ УКАЗАН')})")

    

    # 🔴 ИСПРАВЛЕНИЕ: Если передан current_price > 0, ВСЕГДА используем его!

    # Это важно для пересчёта таблицы с реальной ценой покупки

    if current_price > 0:

        start_price = current_price

    elif start_price == 0 or start_price is None:

        start_price = 1.0

    

    table_data = []

    cumulative_decrease = 0.0  # Накопленная сумма процентов снижения

    

    for step in range(steps + 1):

        # 1. # - номер шага

        step_num = step

        

        # 2. ↓Δ,% - процент снижения курса на каждом шаге

        # Формула: -((# × Rk) + R)

        decrease_step_pct = -((step * rk) + target_r) if step > 0 else 0.0

        

        # 2.1. ↓, % - накопленная сумма процентов снижения

        if step > 0:

            cumulative_decrease += decrease_step_pct

        

        # 3. Курс - расчетный курс относительно стартового

        rate = start_price * (1 + cumulative_decrease / 100.0)

        

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

        step_cumulative = 0.0  # Накопленная сумма для расчёта курсов покупки

        

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

            

            # Используем накопленную сумму процентов для расчёта курса покупки

            # Формула шага: -((# × Rk) + R)

            step_decrease = -((s * rk) + target_r) if s > 0 else 0.0

            if s > 0:

                step_cumulative += step_decrease

            

            # Курс покупки на шаге s рассчитывается от накопленной суммы

            step_rate = start_price * (1 + step_cumulative / 100.0)

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

        

        # 9. Уровень стакана для этого шага

        # Формула: (# × base_orderbook_level) + 1

        # ВАЖНО: Это значение ДЛЯ ОТОБРАЖЕНИЯ ПОЛЬЗОВАТЕЛЮ (1-based)

        # В коде при использовании нужно вычесть 1 для индекса массива:

        # - Уровень 1 в таблице = bids[0] (лучшая цена)

        # - Уровень 2 в таблице = bids[1] (вторая по значимости цена)

        # - Уровень 3 в таблице = bids[2] (третья по значимости цена)

        calculated_orderbook_level = round((step * base_orderbook_level) + 1)

        

        # DEBUG: Выводим расчёт для первых 3 шагов

        if step <= 2:

            print(f"[BREAKEVEN_CALC] Шаг {step}: ({step} × {base_orderbook_level}) + 1 = {calculated_orderbook_level}")

        

        table_data.append({

            'step': step_num,

            'orderbook_level': calculated_orderbook_level,

            'decrease_step_pct': decrease_step_pct,

            'cumulative_decrease_pct': cumulative_decrease,

            'rate': rate,

            'purchase_usd': purchase_usd,

            'total_invested': total_invested,

            'breakeven_price': breakeven_price,

            'breakeven_pct': breakeven_pct,

            'target_delta_pct': target_delta_pct

        })

    

    return table_data

