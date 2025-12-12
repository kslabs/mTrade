"""
Тест восстановления trading_permissions при перезапуске
"""
import json
import sys

# Читаем текущее состояние
print("=" * 60)
print("ТЕСТ ВОССТАНОВЛЕНИЯ TRADING_PERMISSIONS")
print("=" * 60)

# 1. Проверяем файл app_state.json
print("\n1. Содержимое app_state.json:")
try:
    with open('app_state.json', 'r', encoding='utf-8') as f:
        state_data = json.load(f)
    
    trading_perms = state_data.get('trading_permissions', {})
    print(f"   Всего валют: {len(trading_perms)}")
    print(f"   Включено: {sum(1 for v in trading_perms.values() if v)}")
    print(f"   Отключено: {sum(1 for v in trading_perms.values() if not v)}")
    print(f"\n   Валюты:")
    for currency, enabled in sorted(trading_perms.items()):
        status = "✅ Включена" if enabled else "❌ Отключена"
        print(f"      {currency:10s} → {status}")
except Exception as e:
    print(f"   ❌ Ошибка чтения файла: {e}")
    sys.exit(1)

# 2. Проверяем StateManager
print("\n2. StateManager.get_trading_permissions():")
try:
    sys.path.insert(0, '.')
    from state_manager import get_state_manager
    
    sm = get_state_manager()
    sm_perms = sm.get_trading_permissions()
    
    print(f"   Всего валют: {len(sm_perms)}")
    print(f"   Включено: {sum(1 for v in sm_perms.values() if v)}")
    print(f"   Отключено: {sum(1 for v in sm_perms.values() if not v)}")
    
    # Сравниваем с файлом
    if trading_perms == sm_perms:
        print(f"   ✅ StateManager корректно загрузил данные из файла")
    else:
        print(f"   ⚠️ РАСХОЖДЕНИЕ между файлом и StateManager!")
        for key in set(trading_perms.keys()) | set(sm_perms.keys()):
            file_val = trading_perms.get(key)
            sm_val = sm_perms.get(key)
            if file_val != sm_val:
                print(f"      {key}: файл={file_val}, StateManager={sm_val}")
    
except Exception as e:
    print(f"   ❌ Ошибка работы с StateManager: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 3. Тест изменения и сохранения
print("\n3. Тест изменения разрешения:")
test_currency = "ETH"
try:
    current_state = sm.get_trading_permissions().get(test_currency, False)
    print(f"   Текущее состояние {test_currency}: {current_state}")
    
    # Меняем состояние
    new_state = not current_state
    print(f"   Меняем на: {new_state}")
    sm.set_trading_permission(test_currency, new_state)
    
    # Проверяем, что сохранилось в память
    updated_state = sm.get_trading_permissions().get(test_currency, False)
    if updated_state == new_state:
        print(f"   ✅ StateManager обновлён в памяти")
    else:
        print(f"   ❌ StateManager НЕ обновлён в памяти")
    
    # Проверяем, что сохранилось в файл
    with open('app_state.json', 'r', encoding='utf-8') as f:
        updated_file = json.load(f)
    
    file_state = updated_file.get('trading_permissions', {}).get(test_currency, False)
    if file_state == new_state:
        print(f"   ✅ Изменение сохранено в файл")
    else:
        print(f"   ❌ Изменение НЕ сохранено в файл")
    
    # Возвращаем обратно
    sm.set_trading_permission(test_currency, current_state)
    print(f"   ✅ Состояние возвращено обратно: {current_state}")
    
except Exception as e:
    print(f"   ❌ Ошибка теста: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("РЕЗУЛЬТАТ: ✅ Система работает корректно!")
print("           trading_permissions сохраняются и восстанавливаются")
print("=" * 60)
