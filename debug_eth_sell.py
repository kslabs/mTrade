#!/usr/bin/env python3
"""
Диагностика: почему ETH не продаётся
"""

import json
import sys
from gate_api_client import GateAPIClient

def check_eth_orderbook():
    """Проверяем стакан ETH и возможность продажи"""
    
    print("=" * 80)
    print("🔍 ДИАГНОСТИКА ПРОДАЖИ ETH")
    print("=" * 80)
    
    # Создаём публичный клиент
    client = GateAPIClient(api_key=None, api_secret=None, network_mode='work')
    
    # 1. Получаем текущую цену
    print("\n📊 Шаг 1: Текущая цена")
    ticker = client._request('GET', '/spot/tickers', params={'currency_pair': 'ETH_USDT'})
    if ticker and len(ticker) > 0:
        last_price = float(ticker[0].get('last', 0))
        print(f"   Ticker last: {last_price:.8f}")
    else:
        print("   ❌ Не удалось получить ticker")
        return
    
    # 2. Получаем стакан
    print("\n📚 Шаг 2: Стакан ордеров (bids - покупатели)")
    orderbook = client._request('GET', '/spot/order_book', params={'currency_pair': 'ETH_USDT', 'limit': 10})
    
    if not orderbook:
        print("   ❌ Не удалось получить orderbook")
        return
    
    bids = orderbook.get('bids', [])
    
    if not bids:
        print("   ❌ Нет bid-ордеров в стакане")
        return
    
    print("\n   Топ-5 уровней bid (цена покупки):")
    for i, bid in enumerate(bids[:5]):
        price = float(bid[0])
        volume = float(bid[1])
        print(f"   [{i}] Цена: {price:.8f}, Объём: {volume:.8f} ETH")
    
    # 3. Проверяем, можно ли продать на уровне 1 (orderbook_level=0)
    print("\n🎯 Шаг 3: Проверка возможности продажи")
    
    target_volume = 0.0031  # Объём из вашего примера
    orderbook_level = 0  # Уровень 1 в UI = индекс 0
    
    if orderbook_level < len(bids):
        target_price = float(bids[orderbook_level][0])
        available_volume = float(bids[orderbook_level][1])
        
        print(f"   Целевой уровень: {orderbook_level} (уровень 1 в UI)")
        print(f"   Цена на этом уровне: {target_price:.8f}")
        print(f"   Доступный объём: {available_volume:.8f} ETH")
        print(f"   Требуется продать: {target_volume:.8f} ETH")
        
        if available_volume >= target_volume:
            print(f"   ✅ Объёма достаточно! ({available_volume:.8f} >= {target_volume:.8f})")
            total_usdt = target_price * target_volume
            print(f"   💰 Можно продать за: {total_usdt:.4f} USDT")
        else:
            print(f"   ❌ НЕДОСТАТОЧНО ОБЪЁМА! ({available_volume:.8f} < {target_volume:.8f})")
            print(f"   ⚠️  FOK ордер будет отклонён!")
            print(f"   💡 Решение: использовать MARKET ордер или уровень 0 (best bid)")
    else:
        print(f"   ❌ Уровень {orderbook_level} недоступен")
    
    # 4. Рекомендация
    print("\n💡 РЕКОМЕНДАЦИЯ:")
    best_bid = float(bids[0][0])
    best_volume = float(bids[0][1])
    
    print(f"   Best bid (уровень 0): {best_bid:.8f}")
    print(f"   Объём: {best_volume:.8f} ETH")
    
    if best_volume >= target_volume:
        print(f"   ✅ На best bid достаточно объёма!")
        print(f"   💡 Используйте orderbook_level=0 вместо 1")
    else:
        print(f"   ⚠️  Даже на best bid недостаточно объёма")
        print(f"   💡 Используйте MARKET ордер вместо FOK")
    
    # 5. Проверяем, какой уровень стакана указан в таблице
    print("\n📋 Шаг 4: Проверка параметров ETH")
    try:
        with open('breakeven_params.json', 'r', encoding='utf-8') as f:
            params = json.load(f)
            eth_params = params.get('ETH', {})
            orderbook_level_param = eth_params.get('orderbook_level', 1)
            print(f"   orderbook_level в параметрах: {orderbook_level_param}")
            
            if orderbook_level_param > 1:
                print(f"   ⚠️  Уровень {orderbook_level_param} слишком глубокий!")
                print(f"   💡 Установите orderbook_level=1 (best bid)")
    except Exception as e:
        print(f"   ⚠️  Не удалось прочитать параметры: {e}")
    
    print("\n" + "=" * 80)

if __name__ == '__main__':
    try:
        check_eth_orderbook()
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
