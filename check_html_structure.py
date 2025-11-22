# -*- coding: utf-8 -*-
"""
Скрипт проверки корректности HTML файла
Проверяет наличие ключевых элементов в index.html
"""

import os
import re

def check_html_file():
    """Проверка файла templates/index.html"""
    
    file_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
    
    print("=" * 60)
    print("ПРОВЕРКА ФАЙЛА templates/index.html")
    print("=" * 60)
    print(f"\nПуть к файлу: {file_path}")
    print(f"Файл существует: {os.path.exists(file_path)}")
    
    if not os.path.exists(file_path):
        print("❌ ОШИБКА: Файл не найден!")
        return False
    
    # Читаем файл
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"Размер файла: {len(content)} байт")
    print(f"Строк в файле: {content.count(chr(10)) + 1}")
    
    # Проверяемые элементы
    checks = [
        {
            'name': 'Заголовок "Таблица безубыточности"',
            'pattern': r'<span>📊 Таблица безубыточности</span>',
            'required': True
        },
        {
            'name': 'Кнопка "Сохранить" (id=saveParamsBtn)',
            'pattern': r'<button\s+id="saveParamsBtn"[^>]*>💾\s*Сохранить</button>',
            'required': True
        },
        {
            'name': 'Статус сохранения (id=paramsSaveStatus)',
            'pattern': r'<div\s+id="paramsSaveStatus"[^>]*>',
            'required': True
        },
        {
            'name': 'H3 с flexbox для таблицы безубыточности',
            'pattern': r'<h3\s+style="[^"]*display:flex[^"]*">\s*<span>📊 Таблица безубыточности',
            'required': True
        },
        {
            'name': 'Правый блок с кнопками (gap:8px)',
            'pattern': r'<div\s+style="[^"]*display:flex[^"]*gap:8px[^"]*">.*?paramsSaveStatus',
            'required': True
        },
        {
            'name': 'CSS класс save-params-btn-compact',
            'pattern': r'class="save-params-btn-compact"',
            'required': True
        }
    ]
    
    print("\n" + "=" * 60)
    print("РЕЗУЛЬТАТЫ ПРОВЕРКИ:")
    print("=" * 60)
    
    all_ok = True
    
    for check in checks:
        found = re.search(check['pattern'], content, re.DOTALL | re.IGNORECASE)
        status = "✅ ОК" if found else "❌ НЕ НАЙДЕНО"
        
        print(f"\n{status} - {check['name']}")
        
        if found:
            # Показываем найденный фрагмент (первые 100 символов)
            match_text = found.group(0)[:100].replace('\n', ' ').strip()
            print(f"   Найдено: {match_text}...")
        else:
            if check['required']:
                all_ok = False
                print(f"   ⚠️  КРИТИЧНО: Обязательный элемент отсутствует!")
    
    # Дополнительная проверка структуры заголовка
    print("\n" + "=" * 60)
    print("ПРОВЕРКА СТРУКТУРЫ ЗАГОЛОВКА:")
    print("=" * 60)
    
    # Ищем секцию с таблицей безубыточности
    breakeven_section = re.search(
        r'<div class="card breakeven-table">.*?</h3>',
        content,
        re.DOTALL
    )
    
    if breakeven_section:
        section_text = breakeven_section.group(0)
        print("\n📋 Найденная структура заголовка:\n")
        # Форматируем для читаемости
        lines = section_text.split('\n')
        for i, line in enumerate(lines[:15], 1):  # Первые 15 строк
            print(f"   {i:2d}: {line.strip()}")
        
        # Проверяем отсутствие старой структуры
        if '<div class="params-header">' in section_text:
            print("\n❌ ПРЕДУПРЕЖДЕНИЕ: Найден старый контейнер .params-header!")
            all_ok = False
        else:
            print("\n✅ Старый контейнер .params-header отсутствует (хорошо)")
    
    print("\n" + "=" * 60)
    if all_ok:
        print("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ УСПЕШНО!")
        print("\nФайл корректен. Если изменения не видны в браузере:")
        print("1. Остановите сервер (Ctrl+C)")
        print("2. Очистите кэш браузера (Ctrl+Shift+Delete)")
        print("3. Или откройте в режиме инкогнито (Ctrl+Shift+N)")
        print("4. Запустите сервер заново: python mTrade.py")
    else:
        print("❌ ОБНАРУЖЕНЫ ПРОБЛЕМЫ!")
        print("\nНеобходимо исправить отсутствующие элементы.")
    print("=" * 60)
    
    return all_ok


if __name__ == '__main__':
    check_html_file()
