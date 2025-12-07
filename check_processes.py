"""Проверка запущенных процессов Python"""
import subprocess
import sys

print("=" * 70)
print("ПРОВЕРКА ЗАПУЩЕННЫХ ПРОЦЕССОВ PYTHON")
print("=" * 70)

try:
    # Для Windows
    result = subprocess.run(
        ['tasklist', '/FI', 'IMAGENAME eq python.exe', '/FO', 'CSV'],
        capture_output=True,
        text=True,
        encoding='cp866'
    )
    
    lines = result.stdout.strip().split('\n')
    
    if len(lines) > 1:
        print(f"\nНайдено процессов Python: {len(lines) - 1}\n")
        for line in lines:
            print(line)
    else:
        print("\n❌ Процессы Python не найдены")
    
    print("\n" + "=" * 70)
    print("ПРОВЕРКА ПОРТОВ 5000-5003")
    print("=" * 70)
    
    # Проверка портов
    result = subprocess.run(
        ['netstat', '-ano', '|', 'findstr', ':500'],
        capture_output=True,
        text=True,
        shell=True,
        encoding='cp866'
    )
    
    if result.stdout:
        print("\nЗанятые порты:\n")
        print(result.stdout)
    else:
        print("\n❌ Порты 5000-5003 свободны")
    
except Exception as e:
    print(f"❌ Ошибка: {e}")
