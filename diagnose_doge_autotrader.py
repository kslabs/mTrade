"""
Тестовый скрипт для диагностики автотрейдера DOGE
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from state_manager import get_state_manager
from config import Config

print("=" * 60)
print("ДИАГНОСТИКА АВТОТРЕЙДЕРА DOGE")
print("=" * 60)

# 1. Проверка state_manager
state_manager = get_state_manager()

print("\n1. Проверка автоторговли:")
auto_enabled = state_manager.get_auto_trade_enabled()
print(f"   auto_trade_enabled: {auto_enabled}")

print("\n2. Проверка разрешений:")
perms = state_manager.get_trading_permissions()
print(f"   Всего валют: {len(perms)}")
enabled = [k for k, v in perms.items() if v]
disabled = [k for k, v in perms.items() if not v]
print(f"   Включено: {enabled}")
print(f"   Выключено: {disabled}")
print(f"   DOGE включена: {perms.get('DOGE', False)}")

print("\n3. Параметры DOGE:")
doge_params = state_manager.get_breakeven_params('DOGE')
print(f"   steps: {doge_params.get('steps')}")
print(f"   start_volume: {doge_params.get('start_volume')}")
print(f"   start_price: {doge_params.get('start_price')}")
print(f"   pprof: {doge_params.get('pprof')}")
print(f"   kprof: {doge_params.get('kprof')}")
print(f"   target_r: {doge_params.get('target_r')}")
print(f"   geom_multiplier: {doge_params.get('geom_multiplier')}")
print(f"   rebuy_mode: {doge_params.get('rebuy_mode')}")
print(f"   keep: {doge_params.get('keep')}")

print("\n4. Проверка currencies.json:")
currencies = Config.load_currencies()
doge_found = False
for c in currencies:
    if c.get('code') == 'DOGE':
        doge_found = True
        print(f"   DOGE найдена: {c}")
        break
if not doge_found:
    print("   ❌ DOGE НЕ найдена в currencies.json!")

print("\n5. Проверка режима сети:")
network_mode = Config.load_network_mode()
print(f"   network_mode: {network_mode}")

print("\n6. Котировочная валюта:")
quote = state_manager.get_active_quote_currency()
print(f"   active_quote_currency: {quote}")

print("\n" + "=" * 60)
print("ИТОГОВАЯ ПРОВЕРКА:")
print("=" * 60)

issues = []
if not auto_enabled:
    issues.append("❌ Автоторговля ВЫКЛЮЧЕНА")
else:
    print("✅ Автоторговля включена")

if not perms.get('DOGE'):
    issues.append("❌ DOGE не имеет разрешения на торговлю")
else:
    print("✅ DOGE имеет разрешение на торговлю")

if not doge_found:
    issues.append("❌ DOGE отсутствует в currencies.json")
else:
    print("✅ DOGE есть в currencies.json")

if doge_params.get('start_volume', 0) <= 0:
    issues.append("❌ start_volume для DOGE = 0 или не задан")
else:
    print(f"✅ start_volume = {doge_params.get('start_volume')} USDT")

if issues:
    print("\n🔴 НАЙДЕНЫ ПРОБЛЕМЫ:")
    for issue in issues:
        print(f"   {issue}")
else:
    print("\n🎉 ВСЁ НАСТРОЕНО ПРАВИЛЬНО!")
    print("\nВозможные причины, почему не торгует:")
    print("   1. Недостаточно USDT на балансе (нужно >= 10 USDT)")
    print("   2. Цикл уже активен для DOGE")
    print("   3. Не получена цена DOGE_USDT")
    print("   4. Ошибка API при размещении ордера")
    print("\n💡 Запустите сервер и проверьте логи:")
    print("   python mTrade.py")
    print("\n   Логи покажут точную причину!")

print("=" * 60)
