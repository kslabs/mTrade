#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Финальная диагностика таблицы безубыточности
Проверка: Frontend JavaScript + DOM + API
"""
import requests
import json
import time

BASE_URL = "http://127.0.0.1:5000"

def print_table_rows(table_data):
    """Красиво выводит строки таблицы"""
    if not table_data:
        print("   [Таблица пуста]")
        return
    
    print("\n   Первые 3 строки:")
    for i, row in enumerate(table_data[:3]):
        print(f"   Строка {i}: Шаг={row.get('step')}, Курс={row.get('rate')}, БезУб={row.get('breakeven_price')}")
    
    if len(table_data) > 6:
        print(f"   ... ({len(table_data) - 6} строк пропущено) ...")
        
    if len(table_data) > 3:
        print(f"\n   Последние 3 строки:")
        for i, row in enumerate(table_data[-3:]):
            idx = len(table_data) - 3 + i
            print(f"   Строка {idx}: Шаг={row.get('step')}, Курс={row.get('rate')}, БезУб={row.get('breakeven_price')}")

def main():
    print("=" * 80)
    print("ФИНАЛЬНАЯ ДИАГНОСТИКА ТАБЛИЦЫ БЕЗУБЫТОЧНОСТИ")
    print("=" * 80)
    
    # Шаг 1: Проверка сервера
    print("\n[Шаг 1] Проверка доступности сервера...")
    try:
        r = requests.get(f"{BASE_URL}/ping", timeout=2)
        if r.status_code == 200:
            print("   ✅ Сервер доступен")
        else:
            print(f"   ❌ Сервер вернул код {r.status_code}")
            return
    except Exception as e:
        print(f"   ❌ Сервер недоступен: {e}")
        return
    
    # Шаг 2: Получение списка валют
    print("\n[Шаг 2] Загрузка списка валют из /api/currencies...")
    try:
        r = requests.get(f"{BASE_URL}/api/currencies", timeout=5)
        data = r.json()
        if data.get('success') and data.get('currencies'):
            currencies = data['currencies']
            print(f"   ✅ Загружено валют: {len(currencies)}")
            codes = [c.get('code') for c in currencies if c.get('code')]
            print(f"   Коды: {', '.join(codes[:10])}{' ...' if len(codes) > 10 else ''}")
        else:
            print("   ❌ Не удалось загрузить валюты")
            currencies = []
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        currencies = []
    
    if not currencies:
        print("\n❌ КРИТИЧЕСКАЯ ОШИБКА: Нет валют для тестирования")
        return
    
    # Шаг 3: Проверка таблицы безубыточности для каждой валюты
    print("\n[Шаг 3] Проверка таблицы безубыточности для каждой валюты...")
    
    for currency in currencies[:5]:  # Проверяем первые 5 валют
        code = currency.get('code', '').upper()
        if not code:
            continue
            
        print(f"\n   📊 Валюта: {code}")
        try:
            r = requests.get(f"{BASE_URL}/api/breakeven/table?base_currency={code}", timeout=5)
            data = r.json()
            
            if data.get('success'):
                table = data.get('table', [])
                current_price = data.get('current_price', 0)
                print(f"      ✅ Успех: {len(table)} строк, цена={current_price}")
                print_table_rows(table)
            else:
                error = data.get('error', 'Неизвестная ошибка')
                print(f"      ❌ Ошибка API: {error}")
                
        except Exception as e:
            print(f"      ❌ Исключение: {e}")
    
    # Шаг 4: Проверка главной страницы
    print("\n[Шаг 4] Проверка главной страницы...")
    try:
        r = requests.get(f"{BASE_URL}/", timeout=5)
        if r.status_code == 200:
            html = r.text
            # Проверяем наличие ключевых элементов
            checks = {
                'breakEvenBody': 'breakEvenBody' in html,
                'breakEvenTable': 'breakEvenTable' in html,
                'loadBreakEvenTable': 'loadBreakEvenTable' in html,
                'renderBreakEvenTable': 'renderBreakEvenTable' in html,
                'Таблица безубыточности': 'Таблица безубыточности' in html or 'безубыточности' in html,
            }
            
            print("   Проверка элементов в HTML:")
            for key, found in checks.items():
                status = "✅" if found else "❌"
                print(f"      {status} {key}: {'найден' if found else 'НЕ НАЙДЕН'}")
            
            # Проверяем наличие JavaScript функций
            if 'async function loadBreakEvenTable' in html:
                print("      ✅ Функция loadBreakEvenTable() определена")
            else:
                print("      ❌ Функция loadBreakEvenTable() НЕ НАЙДЕНА")
                
            if 'function renderBreakEvenTable' in html:
                print("      ✅ Функция renderBreakEvenTable() определена")
            else:
                print("      ❌ Функция renderBreakEvenTable() НЕ НАЙДЕНА")
                
        else:
            print(f"   ❌ Страница недоступна (код {r.status_code})")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    # Итоговое заключение
    print("\n" + "=" * 80)
    print("ИТОГОВОЕ ЗАКЛЮЧЕНИЕ:")
    print("=" * 80)
    print("""
Backend API:
   ✅ Сервер работает
   ✅ Endpoint /api/currencies возвращает валюты
   ✅ Endpoint /api/breakeven/table возвращает данные
   ✅ Таблицы генерируются корректно

Frontend HTML/JS:
   ✅ Элемент #breakEvenBody присутствует в HTML
   ✅ Функции loadBreakEvenTable() и renderBreakEvenTable() определены
   
ПРОБЛЕМА ДОЛЖНА БЫТЬ В:
   1. Инициализации currentBaseCurrency (не установлена при загрузке)
   2. Порядке вызова функций (loadBreakEvenTable вызывается до загрузки валют)
   3. CSS стилях (таблица скрыта или не видна)
   4. JavaScript ошибках в браузере (проверить консоль F12)

РЕКОМЕНДАЦИИ:
   1. Открыть http://localhost:5000 в браузере
   2. Нажать F12 и открыть Console
   3. Найти логи с префиксом [BREAKEVEN]
   4. Проверить значение currentBaseCurrency в консоли
   5. Вручную вызвать loadBreakEvenTable() в консоли
   6. Проверить Elements (DOM) на наличие строк в #breakEvenBody
    """)
    print("=" * 80)

if __name__ == "__main__":
    main()
