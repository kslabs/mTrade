#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка актуальной версии app.js через HTTP
"""

import requests
import re

def check_loaded_app_js():
    """Проверяет, что сервер отдает актуальную версию app.js"""
    
    base_url = "http://localhost:5000"
    
    print("=" * 60)
    print("ПРОВЕРКА ЗАГРУЖАЕМОГО app.js")
    print("=" * 60)
    
    try:
        # Сначала получаем главную страницу, чтобы узнать cache_buster
        index_response = requests.get(base_url, timeout=5)
        index_html = index_response.text
        
        # Ищем URL app.js с cache_buster
        match = re.search(r'/static/app\.js\?v=(\d+)', index_html)
        if match:
            cache_buster = match.group(1)
            print(f"Cache buster: {cache_buster}")
            app_js_url = f"{base_url}/static/app.js?v={cache_buster}"
        else:
            print("⚠️ Cache buster не найден, используем URL без параметров")
            app_js_url = f"{base_url}/static/app.js"
        
        print(f"URL: {app_js_url}")
        print()
        
        # Загружаем app.js
        response = requests.get(app_js_url, timeout=5)
        
        if response.status_code != 200:
            print(f"❌ Ошибка загрузки: статус {response.status_code}")
            return
        
        content = response.text
        
        # Список функций для проверки
        functions = [
            'loadTradingPermissions',
            'updateTabsPermissionsUI',
            'handleResetCycle',
            'handleResumeCycle',
            'initApp'
        ]
        
        print("ПРОВЕРКА НАЛИЧИЯ ФУНКЦИЙ В ЗАГРУЖЕННОМ ФАЙЛЕ:")
        print("-" * 60)
        
        for func_name in functions:
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
                    line_num = content[:match.start()].count('\n') + 1
                    found = True
                    break
            
            if found:
                print(f"✅ {func_name:30} найдена (строка {line_num})")
            else:
                print(f"❌ {func_name:30} НЕ НАЙДЕНА!")
        
        print("\n" + "-" * 60)
        print(f"Размер загруженного файла: {len(content)} байт")
        print(f"Количество строк: {content.count(chr(10)) + 1}")
        
        # Проверяем баланс скобок
        opens = content.count('{')
        closes = content.count('}')
        balance = opens - closes
        
        print(f"Баланс скобок: {balance} ({{: {opens}, }}: {closes})")
        
        if balance == 0:
            print("✅ Баланс скобок в порядке")
        else:
            print(f"❌ Дисбаланс скобок!")
        
        print("\n" + "=" * 60)
        print("✅ ПРОВЕРКА ЗАВЕРШЕНА")
        print("=" * 60)
        print("\nЕсли все функции найдены, но браузер выдает ошибку,")
        print("попробуйте:")
        print("1. Очистить кеш браузера (Ctrl+Shift+Delete)")
        print("2. Открыть страницу в режиме инкогнито")
        print("3. Использовать 'Hard Refresh' (Ctrl+F5)")
        
    except Exception as e:
        print(f"❌ Ошибка при проверке: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    check_loaded_app_js()
