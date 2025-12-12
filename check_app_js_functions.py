#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка наличия ключевых функций в app.js
"""

import os
import re

def check_functions():
    """Проверяет наличие ключевых функций в app.js"""
    app_js_path = r'c:\Users\Администратор\Documents\bGate.mTrade\static\app.js'
    
    if not os.path.exists(app_js_path):
        print(f"❌ Файл не найден: {app_js_path}")
        return
    
    with open(app_js_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Список функций для проверки
    functions = [
        'loadTradingPermissions',
        'updateTabsPermissionsUI',
        'handleResetCycle',
        'handleResumeCycle',
        'initApp'
    ]
    
    print("=" * 60)
    print("ПРОВЕРКА НАЛИЧИЯ ФУНКЦИЙ В app.js")
    print("=" * 60)
    
    for func_name in functions:
        # Ищем объявление функции
        patterns = [
            rf'async\s+function\s+{func_name}\s*\(',
            rf'function\s+{func_name}\s*\(',
            rf'const\s+{func_name}\s*=',
            rf'let\s+{func_name}\s*=',
            rf'var\s+{func_name}\s*='
        ]
        
        found = False
        line_num = 0
        
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                # Найдем номер строки
                line_num = content[:match.start()].count('\n') + 1
                found = True
                break
        
        if found:
            print(f"✅ {func_name:30} найдена (строка {line_num})")
        else:
            print(f"❌ {func_name:30} НЕ НАЙДЕНА!")
    
    # Проверяем баланс скобок
    print("\n" + "=" * 60)
    print("ПРОВЕРКА СИНТАКСИСА")
    print("=" * 60)
    
    opens = content.count('{')
    closes = content.count('}')
    balance = opens - closes
    
    print(f"Открывающих скобок {{ : {opens}")
    print(f"Закрывающих скобок }}: {closes}")
    print(f"Баланс: {balance}")
    
    if balance == 0:
        print("✅ Баланс скобок в порядке")
    else:
        print(f"❌ Дисбаланс скобок: {balance}")
    
    # Проверяем размер файла
    file_size = len(content)
    lines_count = content.count('\n') + 1
    
    print(f"\nРазмер файла: {file_size} байт")
    print(f"Количество строк: {lines_count}")
    
    print("\n" + "=" * 60)

if __name__ == '__main__':
    check_functions()
