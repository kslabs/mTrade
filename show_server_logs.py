"""
Показать последние 50 строк логов из консоли сервера
"""
import os
import sys

print("=" * 70)
print("ПРОВЕРКА ПОСЛЕДНИХ ЛОГОВ СЕРВЕРА")
print("=" * 70)

# Ищем последний лог-файл с консольным выводом
possible_logs = [
    "server.log",
    "mTrade.log",
    "output.log",
    "console.log"
]

found = False
for log_file in possible_logs:
    if os.path.exists(log_file):
        print(f"\n📄 Найден файл: {log_file}")
        print("-" * 70)
        
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                
            # Показываем последние 50 строк
            for line in lines[-50:]:
                print(line.rstrip())
            
            found = True
            break
        except Exception as e:
            print(f"❌ Ошибка чтения файла: {e}")

if not found:
    print("\n❌ Лог-файлы не найдены")
    print("\nПопробуйте посмотреть консоль, где запущен сервер.")
    print("Ищите строки с ошибками (ERROR, Exception, Traceback)")

print("\n" + "=" * 70)
