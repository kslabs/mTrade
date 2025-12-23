#!/usr/bin/env python3
"""
Скрипт для проверки, что log_sell теперь вызывается с правильными параметрами
"""

import sys
import re
from pathlib import Path

def check_log_sell_calls():
    """Проверяем все вызовы log_sell в коде"""
    print("🔍 Проверка вызовов log_sell...\n")
    
    # Читаем autotrader_v2.py
    autotrader_file = Path(__file__).parent / "autotrader_v2.py"
    
    if not autotrader_file.exists():
        print(f"❌ Файл не найден: {autotrader_file}")
        return False
    
    content = autotrader_file.read_text(encoding='utf-8')
    
    # Ищем вызовы log_sell
    pattern = r'self\.logger\.log_sell\s*\('
    matches = list(re.finditer(pattern, content))
    
    if not matches:
        print("❌ Не найдено вызовов log_sell в autotrader_v2.py")
        return False
    
    print(f"✅ Найдено {len(matches)} вызовов log_sell\n")
    
    # Проверяем каждый вызов
    errors = []
    for i, match in enumerate(matches, 1):
        start = match.start()
        # Берём следующие 500 символов после начала вызова
        snippet = content[start:start+500]
        
        print(f"📍 Вызов #{i}:")
        print(f"   Позиция: {start}")
        
        # Проверяем, что используется delta_percent, а не growth_percent
        if 'growth_percent=' in snippet:
            print(f"   ❌ ОШИБКА: используется 'growth_percent=' вместо 'delta_percent='")
            errors.append(i)
            # Показываем фрагмент
            lines = snippet.split('\n')[:10]
            for line in lines:
                print(f"      {line}")
        elif 'delta_percent=' in snippet:
            print(f"   ✅ OK: используется правильный параметр 'delta_percent='")
        else:
            print(f"   ⚠️  ВНИМАНИЕ: не найден ни delta_percent, ни growth_percent")
            print(f"      Возможно, используются позиционные аргументы (что ПЛОХО)")
            # Показываем фрагмент
            lines = snippet.split('\n')[:10]
            for line in lines:
                print(f"      {line}")
        
        print()
    
    if errors:
        print(f"\n❌ НАЙДЕНЫ ОШИБКИ в вызовах: {errors}")
        print("   Нужно заменить 'growth_percent=' на 'delta_percent='")
        return False
    else:
        print("\n✅ ВСЕ ВЫЗОВЫ log_sell ПРАВИЛЬНЫЕ!")
        print("   Теперь все продажи должны логироваться корректно.")
        return True

if __name__ == '__main__':
    success = check_log_sell_calls()
    sys.exit(0 if success else 1)
