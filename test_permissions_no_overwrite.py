"""
Тест проверки, что init_currency_permissions не перезаписывает существующие разрешения
"""

import json
import os
from state_manager import StateManager

def test_init_permissions_no_overwrite():
    """Проверяем, что init_currency_permissions не перезаписывает существующие настройки"""
    
    # Создаём тестовый файл состояния
    test_state_file = "test_app_state_no_overwrite.json"
    
    # Удаляем файл если существует
    if os.path.exists(test_state_file):
        os.remove(test_state_file)
    
    print("=" * 80)
    print("ТЕСТ: init_currency_permissions не должен перезаписывать существующие настройки")
    print("=" * 80)
    
    # Шаг 1: Создаём state_manager с начальными разрешениями
    print("\n[1] Создаём state_manager с пустыми разрешениями")
    sm = StateManager(state_file=test_state_file)
    
    # Шаг 2: Инициализируем разрешения для валют BTC, ETH, LTC
    print("\n[2] Инициализируем разрешения для валют: BTC, ETH, LTC")
    currencies_1 = [
        {"code": "BTC", "name": "Bitcoin"},
        {"code": "ETH", "name": "Ethereum"},
        {"code": "LTC", "name": "Litecoin"}
    ]
    sm.init_currency_permissions(currencies_1)
    perms_1 = sm.get_trading_permissions()
    print(f"Разрешения после инициализации: {perms_1}")
    
    # Проверяем, что все валюты включены по умолчанию
    assert perms_1 == {"BTC": True, "ETH": True, "LTC": True}, "Все валюты должны быть включены по умолчанию"
    print("✓ Все валюты включены по умолчанию")
    
    # Шаг 3: Пользователь отключает торговлю для ETH
    print("\n[3] Пользователь отключает торговлю для ETH")
    sm.set_trading_permission("ETH", False)
    perms_2 = sm.get_trading_permissions()
    print(f"Разрешения после отключения ETH: {perms_2}")
    
    assert perms_2 == {"BTC": True, "ETH": False, "LTC": True}, "ETH должен быть отключен"
    print("✓ ETH успешно отключен")
    
    # Шаг 4: Перезагружаем state_manager (имитация перезапуска сервера)
    print("\n[4] Перезагружаем state_manager (имитация перезапуска сервера)")
    sm2 = StateManager(state_file=test_state_file)
    perms_3 = sm2.get_trading_permissions()
    print(f"Разрешения после перезагрузки: {perms_3}")
    
    assert perms_3 == {"BTC": True, "ETH": False, "LTC": True}, "Настройки должны сохраниться после перезагрузки"
    print("✓ Настройки сохранились после перезагрузки")
    
    # Шаг 5: Инициализируем разрешения снова (имитация повторного вызова init при старте)
    print("\n[5] Вызываем init_currency_permissions снова с теми же валютами")
    sm2.init_currency_permissions(currencies_1)
    perms_4 = sm2.get_trading_permissions()
    print(f"Разрешения после повторной инициализации: {perms_4}")
    
    assert perms_4 == {"BTC": True, "ETH": False, "LTC": True}, "Настройки НЕ должны перезаписаться"
    print("✓ УСПЕХ: Настройки НЕ перезаписались!")
    
    # Шаг 6: Добавляем новую валюту XRP
    print("\n[6] Добавляем новую валюту XRP")
    currencies_2 = [
        {"code": "BTC", "name": "Bitcoin"},
        {"code": "ETH", "name": "Ethereum"},
        {"code": "LTC", "name": "Litecoin"},
        {"code": "XRP", "name": "Ripple"}
    ]
    sm2.init_currency_permissions(currencies_2)
    perms_5 = sm2.get_trading_permissions()
    print(f"Разрешения после добавления XRP: {perms_5}")
    
    assert perms_5 == {"BTC": True, "ETH": False, "LTC": True, "XRP": True}, "XRP должен быть добавлен с True"
    print("✓ Новая валюта XRP добавлена с разрешением True")
    
    # Шаг 7: Проверяем содержимое файла
    print("\n[7] Проверяем содержимое файла app_state.json")
    with open(test_state_file, 'r', encoding='utf-8') as f:
        state_data = json.load(f)
    print(f"Содержимое файла:\n{json.dumps(state_data, indent=2, ensure_ascii=False)}")
    
    assert state_data['trading_permissions'] == {"BTC": True, "ETH": False, "LTC": True, "XRP": True}
    print("✓ Файл содержит корректные разрешения")
    
    # Очистка
    print("\n[CLEANUP] Удаляем тестовый файл")
    os.remove(test_state_file)
    
    print("\n" + "=" * 80)
    print("ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО! ✓")
    print("init_currency_permissions теперь корректно работает:")
    print("  - Не перезаписывает существующие настройки пользователя")
    print("  - Добавляет только новые валюты с разрешением True")
    print("  - Сохраняет отключенные пользователем валюты")
    print("=" * 80)

if __name__ == "__main__":
    test_init_permissions_no_overwrite()
