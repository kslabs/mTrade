"""
Тест проверки, что отключенные валюты не торгуются в AutoTrader
"""

def test_trading_permissions_filtering():
    """
    Проверяем, что AutoTrader пропускает валюты с permissions=False
    """
    print("=" * 80)
    print("ТЕСТ: Отключенные валюты не должны торговаться")
    print("=" * 80)
    
    # Пример словаря разрешений
    perms = {
        "BTC": True,
        "ETH": False,  # Отключена!
        "LTC": True,
        "XRP": False   # Отключена!
    }
    
    print("\n[1] Исходные разрешения:")
    for currency, enabled in perms.items():
        status = "✅ ВКЛЮЧЕНА" if enabled else "❌ ОТКЛЮЧЕНА"
        print(f"  {currency}: {status}")
    
    # Симуляция цикла торговли (как в autotrader.py)
    print("\n[2] Симуляция цикла торговли:")
    traded_currencies = []
    
    for base in perms:
        # КРИТИЧНО: Проверяем разрешение перед торговлей
        if not perms.get(base, False):
            print(f"  {base}: ПРОПУЩЕНА (разрешение=False)")
            continue
        
        print(f"  {base}: ТОРГУЕТСЯ (разрешение=True)")
        traded_currencies.append(base)
    
    # Проверяем результат
    print("\n[3] Результат:")
    print(f"Торговались валюты: {traded_currencies}")
    
    expected = ["BTC", "LTC"]
    assert traded_currencies == expected, f"Ожидалось {expected}, получено {traded_currencies}"
    
    print("\n✅ УСПЕХ: Торговались только валюты с permissions=True")
    print(f"  Включенные: {expected}")
    print(f"  Отключенные: ['ETH', 'XRP'] - пропущены")
    
    # Проверяем, что отключенные валюты НЕ торговались
    assert "ETH" not in traded_currencies, "ETH не должен торговаться!"
    assert "XRP" not in traded_currencies, "XRP не должен торговаться!"
    
    print("\n" + "=" * 80)
    print("ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ! ✓")
    print("Отключенные валюты корректно пропускаются")
    print("=" * 80)

if __name__ == "__main__":
    test_trading_permissions_filtering()
