import sys
sys.path.insert(0, '.')

# Имитируем получение таблицы из автотрейдера
import json

with open('autotrader_cycles_state.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

eth_cycle = data.get('ETH', {})
table = eth_cycle.get('table', [])

if table:
    print(f'Таблица содержит {len(table)} шагов')
    print(f'\nПервая строка:')
    row = table[0]
    for key, value in row.items():
        print(f'  {key}: {value}')
else:
    print('Таблица не найдена!')
