#!/usr/bin/env python3
"""Проверка открытых ордеров XRP на бирже"""
import sys
import json

# Добавляем путь к модулям
sys.path.insert(0, '.')

from gate_api_client import GateAPIClient

# Загружаем конфигурацию
with open('accounts.json', 'r', encoding='utf-8') as f:
    accounts = json.load(f)

# Инициализируем API клиент
account = accounts['Auto_test']
api_client = GateAPIClient(
    api_key=account['api_key'],
    api_secret=account['api_secret'],
    network_mode='work'
)

print("=" * 70)
print("  ПРОВЕРКА ОТКРЫТЫХ ОРДЕРОВ XRP")
print("=" * 70)
print()

# Проверяем открытые ордера
try:
    open_orders = api_client.get_spot_orders('XRP_USDT', status='open')
    print(f"Открытых ордеров: {len(open_orders)}")
    print()
    
    if open_orders:
        for order in open_orders:
            order_id = order.get('id')
            side = order.get('side')
            order_type = order.get('type')
            amount = order.get('amount')
            price = order.get('price')
            left = order.get('left')
            status = order.get('status')
            create_time = order.get('create_time')
            
            print(f"Order ID: {order_id}")
            print(f"  Side: {side}")
            print(f"  Type: {order_type}")
            print(f"  Amount: {amount}")
            print(f"  Price: {price}")
            print(f"  Left: {left}")
            print(f"  Status: {status}")
            print(f"  Created: {create_time}")
            print()
    else:
        print("✅ Нет открытых ордеров")
        
except Exception as e:
    print(f"❌ Ошибка при проверке ордеров: {e}")

print()
print("=" * 70)
print("  ПРОВЕРКА БАЛАНСА XRP")
print("=" * 70)
print()

# Проверяем баланс
try:
    balances = api_client.get_account_balance()
    xrp_balance = next((b for b in balances if b.get('currency') == 'XRP'), None)
    
    if xrp_balance:
        available = float(xrp_balance.get('available', 0))
        locked = float(xrp_balance.get('locked', 0))
        total = available + locked
        
        print(f"Available: {available:.8f} XRP")
        print(f"Locked: {locked:.8f} XRP")
        print(f"Total: {total:.8f} XRP")
        
        if available < 0.001:
            print()
            print("⚠️ Баланс XRP практически нулевой!")
            print("   Это подтверждает, что продажа уже произошла.")
    else:
        print("❌ XRP не найден в балансе")
        
except Exception as e:
    print(f"❌ Ошибка при проверке баланса: {e}")

print()
print("=" * 70)
print("  ИСТОРИЯ ПОСЛЕДНИХ ОРДЕРОВ XRP")
print("=" * 70)
print()

# Проверяем последние исполненные ордера
try:
    closed_orders = api_client.get_spot_orders('XRP_USDT', status='finished')[:5]
    print(f"Последних исполненных ордеров: {len(closed_orders)}")
    print()
    
    for order in closed_orders:
        order_id = order.get('id')
        side = order.get('side')
        order_type = order.get('type')
        amount = order.get('amount')
        price = order.get('price')
        avg_deal_price = order.get('avg_deal_price')
        filled_amount = order.get('filled_amount')
        status = order.get('status')
        create_time = order.get('create_time')
        finish_time = order.get('finish_time')
        
        print(f"Order ID: {order_id}")
        print(f"  Side: {side.upper()}")
        print(f"  Type: {order_type}")
        print(f"  Amount: {amount}")
        print(f"  Price: {price}")
        print(f"  Avg Deal Price: {avg_deal_price}")
        print(f"  Filled: {filled_amount}")
        print(f"  Status: {status}")
        print(f"  Created: {create_time}")
        print(f"  Finished: {finish_time}")
        print()
        
except Exception as e:
    print(f"❌ Ошибка при проверке истории: {e}")

print("=" * 70)
