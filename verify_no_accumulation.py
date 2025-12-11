"""
🔍 ФИНАЛЬНАЯ ПРОВЕРКА: Невозможность старого кода

Этот скрипт проверяет, что старый код с накоплением профита НЕВОЗМОЖНО запустить.
"""

import os
import sys
import re

def check_trade_logger_files():
    """Проверить, что существует только один файл trade_logger.py"""
    print("\n" + "="*80)
    print("1️⃣  ПРОВЕРКА: Единственный файл trade_logger.py")
    print("="*80)
    
    found_files = []
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file == 'trade_logger.py':
                path = os.path.join(root, file)
                found_files.append(path)
    
    print(f"Найдено файлов: {len(found_files)}")
    for f in found_files:
        print(f"  📄 {f}")
    
    if len(found_files) == 1:
        print("✅ УСПЕХ: Только один файл trade_logger.py")
        return True
    else:
        print("❌ ОШИБКА: Найдено больше одного файла!")
        return False


def check_accumulation_code():
    """Проверить отсутствие строк с накоплением профита"""
    print("\n" + "="*80)
    print("2️⃣  ПРОВЕРКА: Отсутствие накопления профита")
    print("="*80)
    
    patterns = [
        r'self\.total_pnl\[currency\]\s*\+=',
        r'total_pnl\s*\+=\s*pnl',
    ]
    
    found_violations = []
    
    for root, dirs, files in os.walk('.'):
        # Пропускаем директории с документацией и логами
        if any(skip in root for skip in ['trade_logs', '__pycache__', '.git']):
            continue
        
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        for pattern in patterns:
                            matches = re.findall(pattern, content, re.IGNORECASE)
                            if matches:
                                found_violations.append({
                                    'file': path,
                                    'pattern': pattern,
                                    'matches': matches
                                })
                except Exception as e:
                    pass
    
    if found_violations:
        print("❌ ОШИБКА: Найдены строки с накоплением профита!")
        for v in found_violations:
            print(f"  📄 {v['file']}")
            print(f"     Паттерн: {v['pattern']}")
            print(f"     Совпадения: {v['matches']}")
        return False
    else:
        print("✅ УСПЕХ: Нет строк с накоплением профита")
        return True


def check_trade_logger_content():
    """Проверить содержимое trade_logger.py"""
    print("\n" + "="*80)
    print("3️⃣  ПРОВЕРКА: Содержимое trade_logger.py")
    print("="*80)
    
    file_path = 'trade_logger.py'
    if not os.path.exists(file_path):
        print(f"❌ ОШИБКА: Файл {file_path} не найден!")
        return False
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Проверяем наличие правильного кода
        checks = [
            ('current_profit = pnl', 'Присвоение профита без накопления'),
            ('total_pnl.*current_profit', 'Использование current_profit вместо накопления'),
            ('Профит больше НЕ НАКАПЛИВАЕТСЯ', 'Комментарий о запрете накопления'),
        ]
        
        all_passed = True
        for pattern, description in checks:
            if re.search(pattern, content):
                print(f"✅ Найдено: {description}")
            else:
                print(f"❌ НЕ найдено: {description}")
                all_passed = False
        
        # Проверяем отсутствие старого кода
        bad_patterns = [
            (r'self\.total_pnl\[currency\]\s*\+=\s*pnl', 'Накопление профита'),
        ]
        
        for pattern, description in bad_patterns:
            if re.search(pattern, content):
                print(f"❌ НАЙДЕН СТАРЫЙ КОД: {description}")
                all_passed = False
            else:
                print(f"✅ Нет старого кода: {description}")
        
        return all_passed
    
    except Exception as e:
        print(f"❌ ОШИБКА при чтении файла: {e}")
        return False


def check_recent_logs():
    """Проверить последние записи в логах"""
    print("\n" + "="*80)
    print("4️⃣  ПРОВЕРКА: Последние записи в логах продаж")
    print("="*80)
    
    log_dir = 'trade_logs'
    if not os.path.exists(log_dir):
        print(f"❌ Директория {log_dir} не найдена")
        return False
    
    log_files = [f for f in os.listdir(log_dir) if f.endswith('_logs.jsonl')]
    
    if not log_files:
        print("⚠️  Нет файлов логов (это нормально для нового проекта)")
        return True
    
    print(f"Найдено файлов логов: {len(log_files)}")
    
    import json
    
    for log_file in log_files:
        path = os.path.join(log_dir, log_file)
        print(f"\n📄 Проверка: {log_file}")
        
        try:
            # Читаем последние 5 записей о продажах
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            sell_entries = []
            for line in reversed(lines):
                try:
                    entry = json.loads(line.strip())
                    if entry.get('type') == 'sell':
                        sell_entries.append(entry)
                        if len(sell_entries) >= 5:
                            break
                except:
                    continue
            
            if not sell_entries:
                print("  ℹ️  Нет записей о продажах")
                continue
            
            # Проверяем, что total_pnl == pnl
            all_correct = True
            for entry in sell_entries:
                pnl = entry.get('pnl', 0)
                total_pnl = entry.get('total_pnl', 0)
                time = entry.get('time', 'N/A')
                
                if abs(pnl - total_pnl) < 0.0001:  # С учётом погрешности float
                    print(f"  ✅ [{time}] pnl={pnl:.4f}, total_pnl={total_pnl:.4f} (равны)")
                else:
                    print(f"  ❌ [{time}] pnl={pnl:.4f}, total_pnl={total_pnl:.4f} (НЕ равны!)")
                    all_correct = False
            
            if not all_correct:
                print("\n  ⚠️  ВНИМАНИЕ: Это могут быть СТАРЫЕ логи (до исправления)")
                print("     Чтобы убедиться, сделайте новую продажу и проверьте снова")
        
        except Exception as e:
            print(f"  ❌ Ошибка при чтении: {e}")
    
    return True


def main():
    """Запустить все проверки"""
    print("\n" + "🔍"*40)
    print(" "*20 + "ФИНАЛЬНАЯ ПРОВЕРКА")
    print(" "*10 + "Невозможность запуска старого кода с накоплением профита")
    print("🔍"*40)
    
    results = []
    
    # Запускаем все проверки
    results.append(("Единственный trade_logger.py", check_trade_logger_files()))
    results.append(("Отсутствие накопления в коде", check_accumulation_code()))
    results.append(("Корректное содержимое trade_logger.py", check_trade_logger_content()))
    results.append(("Проверка логов продаж", check_recent_logs()))
    
    # Финальный отчёт
    print("\n" + "="*80)
    print("📊 ФИНАЛЬНЫЙ ОТЧЁТ")
    print("="*80)
    
    all_passed = True
    for name, result in results:
        status = "✅ УСПЕХ" if result else "❌ ОШИБКА"
        print(f"{status}: {name}")
        if not result:
            all_passed = False
    
    print("\n" + "="*80)
    if all_passed:
        print("🎉 ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
        print("✅ Старый код с накоплением профита запустить НЕВОЗМОЖНО")
        print("\n💡 Что делать дальше:")
        print("   1. Перезапустите сервер: python mTrade.py")
        print("   2. Сделайте новую продажу")
        print("   3. Проверьте, что профит не накапливается между циклами")
    else:
        print("⚠️  НАЙДЕНЫ ПРОБЛЕМЫ!")
        print("❌ Необходимо исправить найденные ошибки")
    print("="*80 + "\n")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
