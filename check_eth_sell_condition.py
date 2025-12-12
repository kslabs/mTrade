#!/usr/bin/env python3
"""
Реальная диагностика: почему ETH сейчас не продаёт
"""

import json
import sys
import os
from datetime import datetime

def check_eth_state():
    """Проверяем реальное состояние ETH в системе"""
    
    print("=" * 80)
    print("🔍 ДИАГНОСТИКА: Почему ETH не продаёт?")
    print("=" * 80)
    
    # 1. Проверяем файл состояния
    STATE_FILE = "autotrader_cycles_state.json"
    
    if not os.path.exists(STATE_FILE):
        print("\n❌ Файл состояния не найден!")
        return
    
    print(f"\n📋 Шаг 1: Состояние цикла ETH")
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
        
        if "ETH" not in state:
            print("   ❌ ETH отсутствует в файле состояния!")
            return
        
        eth_state = state["ETH"]
        
        print(f"   Активен: {eth_state.get('active')}")
        print(f"   Шаг: {eth_state.get('active_step')}")
        print(f"   Start price: {eth_state.get('start_price')}")
        print(f"   Base volume: {eth_state.get('base_volume')}")
        print(f"   Invested: {eth_state.get('total_invested_usd')}")
        print(f"   Manual pause: {eth_state.get('manual_pause')}")
        
        # 2. Проверяем таблицу breakeven
        table = eth_state.get('table', [])
        if table and len(table) > 0:
            current_step = eth_state.get('active_step', 0)
            if current_step >= 0 and current_step < len(table):
                row = table[current_step]
                print(f"\n📊 Шаг 2: Текущая строка таблицы (шаг {current_step})")
                print(f"   Breakeven %: {row.get('breakeven_pct')}%")
                print(f"   Orderbook level: {row.get('orderbook_level')}")
                print(f"   Rate: {row.get('rate')}")
                
                # Вычисляем цену продажи
                start_price = eth_state.get('start_price', 0)
                if start_price > 0:
                    breakeven_pct = float(row.get('breakeven_pct', 0))
                    sell_price = start_price * (1 + breakeven_pct / 100)
                    print(f"\n💰 Цена продажи (расчётная):")
                    print(f"   Start price: {start_price:.8f}")
                    print(f"   Breakeven %: {breakeven_pct:.4f}%")
                    print(f"   Sell price: {sell_price:.8f}")
                    
                    # Проверяем текущую цену
                    from gate_api_client import GateAPIClient
                    client = GateAPIClient(api_key=None, api_secret=None, network_mode='work')
                    ticker = client._request('GET', '/spot/tickers', params={'currency_pair': 'ETH_USDT'})
                    
                    if ticker and len(ticker) > 0:
                        current_price = float(ticker[0].get('last', 0))
                        print(f"\n📈 Текущая рыночная цена:")
                        print(f"   {current_price:.8f}")
                        
                        if current_price >= sell_price:
                            print(f"\n✅ УСЛОВИЕ ПРОДАЖИ ВЫПОЛНЕНО!")
                            print(f"   {current_price:.8f} >= {sell_price:.8f}")
                            print(f"\n🔍 Почему не продаёт?")
                            print(f"   1. Возможно, FOK ордер отклоняется (недостаточно объёма в стакане)")
                            print(f"   2. Возможно, флаг _selling_in_progress установлен")
                            print(f"   3. Проверьте логи трейдера на наличие ошибок")
                        else:
                            print(f"\n⚠️ УСЛОВИЕ ПРОДАЖИ НЕ ВЫПОЛНЕНО")
                            print(f"   {current_price:.8f} < {sell_price:.8f}")
                            print(f"   Нужен рост: {((sell_price - current_price) / current_price * 100):.4f}%")
        else:
            print("\n❌ Таблица breakeven пуста!")
    
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)

if __name__ == '__main__':
    check_eth_state()
