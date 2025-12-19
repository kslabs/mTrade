# Читаем файл
with open('gate_api_client.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"До: {len(lines)} строк")

# Убираем ВСЕ пустые строки между строками кода
# Оставляем только одну пустую строку между методами/блоками
result = []
prev_line = ""
skip_next_empty = False

for i, line in enumerate(lines):
    stripped = line.strip()
    
    # Если это пустая строка
    if not stripped:
        # Пропускаем, если предыдущая строка тоже была пустой
        if prev_line.strip():
            result.append('\n')
        prev_line = line
        continue
    
    # Обычная строка - добавляем
    result.append(line)
    prev_line = line

print(f"После: {len(result)} строк")
print(f"Удалено: {len(lines) - len(result)} строк")

# Сохраняем
with open('gate_api_client.py', 'w', encoding='utf-8') as f:
    f.writelines(result)

print("✅ Файл исправлен!")
