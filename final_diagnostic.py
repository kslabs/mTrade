#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ФИНАЛЬНАЯ ДИАГНОСТИКА: Проверка значений для логирования
Этот скрипт проверяет, какие значения будут использоваться в логах
при следующей сделке для каждой валюты.
"""

import json
from datetime import datetime

def diagnose_all_currencies():
    """Диагностика всех валют в cycles_state"""
    print("\n" + "="*80)
    print("ФИНАЛЬНАЯ ДИАГНОСТИКА: ЗНАЧЕНИЯ ДЛЯ ЛОГИРОВАНИЯ")
    print("="*80)
    print(f"Время проверки: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # Читаем файл состояния циклов
    try:
        with open('autotrader_cycles_state.json', 'r', encoding='utf-8') as f:
            cycles_state = json.load(f)
    except Exception as e:
        print(f"❌ Ошибка чтения autotrader_cycles_state.json: {e}")
        return
    
    # Список проблемных валют
    problem_currencies = []
    
    # Проверяем каждую валюту
    for currency, cycle in cycles_state.items():
        if not isinstance(cycle, dict):
            continue
        
        print(f"\n{'─'*80}")
        print(f"📊 {currency}")
        print(f"{'─'*80}")
        
        # Получаем критические значения
        active = cycle.get('active', False)
        start_price = cycle.get('start_price', 0.0)
        last_buy_price = cycle.get('last_buy_price', 0.0)
        total_invested = cycle.get('total_invested_usd', 0.0)
        base_volume = cycle.get('base_volume', 0.0)
        active_step = cycle.get('active_step', -1)
        
        print(f"   Активен: {'✅ Да' if active else '❌ Нет'}")
        print(f"   Шаг: {active_step}")
        print(f"   start_price: {start_price}")
        print(f"   last_buy_price: {last_buy_price}")
        print(f"   total_invested_usd: {total_invested}")
        print(f"   base_volume: {base_volume}")
        
        # Флаг проблемы
        has_problem = False
        
        # СИМУЛЯЦИЯ РАСЧЁТОВ ДЛЯ REBUY (ПОКУПКИ)
        print(f"\n   🔹 СИМУЛЯЦИЯ REBUY:")
        
        # Примерная текущая цена (на 1% ниже last_buy_price)
        sim_buy_price = last_buy_price * 0.99 if last_buy_price > 0 else start_price * 0.99
        
        # Проверка fallback логики для rebuy
        last_buy_checked = last_buy_price
        if last_buy_checked <= 0:
            print(f"      ⚠️  last_buy_price = 0 → FALLBACK к start_price")
            last_buy_checked = start_price
            if last_buy_checked <= 0:
                print(f"      ⚠️  start_price = 0 → FALLBACK к sim_buy_price")
                last_buy_checked = sim_buy_price
                has_problem = True
        
        start_price_checked = start_price
        if start_price_checked <= 0:
            print(f"      ⚠️  start_price = 0 → FALLBACK к sim_buy_price")
            start_price_checked = sim_buy_price
            has_problem = True
        
        # Расчёт процентов
        step_drop = (last_buy_checked - sim_buy_price) / last_buy_checked * 100.0 if last_buy_checked > 0 else 0.0
        cumulative_drop = (start_price_checked - sim_buy_price) / start_price_checked * 100.0 if start_price_checked > 0 else 0.0
        
        print(f"      Цена покупки (симуляция): {sim_buy_price:.8f}")
        print(f"      Δ% от last_buy: {step_drop:.2f}%")
        print(f"      Δ% от start: {cumulative_drop:.2f}%")
        
        if step_drop == 0.0 or cumulative_drop == 0.0:
            print(f"      ❌ ПРОБЛЕМА: Нулевые проценты в логах REBUY!")
            has_problem = True
        else:
            print(f"      ✅ Расчёты корректны")
        
        # СИМУЛЯЦИЯ РАСЧЁТОВ ДЛЯ SELL (ПРОДАЖИ)
        print(f"\n   🔹 СИМУЛЯЦИЯ SELL:")
        
        # Примерная цена продажи (на 1% выше last_buy_price)
        sim_sell_price = last_buy_price * 1.01 if last_buy_price > 0 else start_price * 1.01
        
        # Проверка fallback логики для sell
        last_buy_for_sell = last_buy_price
        if last_buy_for_sell <= 0:
            print(f"      ⚠️  last_buy_price = 0 → FALLBACK к start_price")
            last_buy_for_sell = start_price
            if last_buy_for_sell <= 0:
                print(f"      ⚠️  start_price = 0 → FALLBACK к sim_sell_price")
                last_buy_for_sell = sim_sell_price
                has_problem = True
        
        # Расчёт delta_percent
        if last_buy_for_sell > 0:
            delta_from_last_buy = (sim_sell_price - last_buy_for_sell) / last_buy_for_sell * 100.0
        else:
            delta_from_last_buy = 0.0
            has_problem = True
        
        # Расчёт PnL
        if base_volume > 0 and total_invested > 0:
            avg_invest_price = total_invested / base_volume
            pnl = (sim_sell_price - avg_invest_price) * base_volume
        else:
            print(f"      ⚠️  base_volume={base_volume} или total_invested={total_invested} = 0")
            avg_invest_price = start_price if start_price > 0 else sim_sell_price
            pnl = 0.0
            has_problem = True
        
        print(f"      Цена продажи (симуляция): {sim_sell_price:.8f}")
        print(f"      Δ% от last_buy: {delta_from_last_buy:.2f}%")
        print(f"      avg_invest_price: {avg_invest_price:.8f}")
        print(f"      PnL (симуляция): {pnl:.4f} USDT")
        
        if delta_from_last_buy == 0.0 or pnl == 0.0:
            print(f"      ❌ ПРОБЛЕМА: Нулевые значения в логах SELL!")
            has_problem = True
        else:
            print(f"      ✅ Расчёты корректны")
        
        # Добавляем в список проблемных, если есть проблемы
        if has_problem:
            problem_currencies.append(currency)
            print(f"\n   🔴 ВАЛЮТА С ПРОБЛЕМАМИ: {currency}")
        else:
            print(f"\n   🟢 Валюта в порядке")
    
    # Итоговый отчёт
    print(f"\n{'='*80}")
    print("ИТОГОВЫЙ ОТЧЁТ")
    print(f"{'='*80}")
    
    if problem_currencies:
        print(f"\n❌ НАЙДЕНЫ ПРОБЛЕМЫ В СЛЕДУЮЩИХ ВАЛЮТАХ:")
        for curr in problem_currencies:
            print(f"   - {curr}")
        print(f"\nРЕКОМЕНДАЦИЯ:")
        print(f"1. Запустите fix_cycles_prices.py для исправления состояния")
        print(f"2. Перезапустите autotrader")
        print(f"3. Проверьте логи после следующей сделки")
    else:
        print(f"\n✅ ВСЕ ВАЛЮТЫ В ПОРЯДКЕ")
        print(f"   Нулевые значения в логах не должны появляться")
    
    print(f"\n{'='*80}\n")

if __name__ == "__main__":
    diagnose_all_currencies()
