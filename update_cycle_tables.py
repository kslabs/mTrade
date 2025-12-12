"""
Скрипт обновления сохранённых таблиц безубыточности
Добавляет отсутствующие поля (total_invested, breakeven_pct, orderbook_level)
"""

import json
import os
from breakeven_calculator import calculate_breakeven_table

def update_cycle_tables():
    """Обновить таблицы в сохранённых циклах"""
    
    state_file = 'autotrader_cycles_state.json'
    
    if not os.path.exists(state_file):
        print(f"❌ Файл состояния {state_file} не найден")
        return
    
    print(f"📂 Загрузка {state_file}...")
    
    with open(state_file, 'r', encoding='utf-8') as f:
        state = json.load(f)
    
    cycles = state.get('cycles', {})
    
    if not cycles:
        print("ℹ️  Нет активных циклов")
        return
    
    print(f"\n📊 Найдено циклов: {len(cycles)}")
    
    updated_count = 0
    
    for currency, cycle_data in cycles.items():
        print(f"\n{'='*60}")
        print(f"🔍 Проверка цикла {currency}")
        print(f"{'='*60}")
        
        table = cycle_data.get('table', [])
        
        if not table:
            print(f"   ⚠️  Таблица отсутствует, пропускаем")
            continue
        
        print(f"   Таблица: {len(table)} строк")
        
        # Проверяем первую строку
        row0 = table[0]
        has_total_invested = 'total_invested' in row0
        has_breakeven_pct = 'breakeven_pct' in row0
        has_orderbook_level = 'orderbook_level' in row0
        
        print(f"   Поля в первой строке:")
        print(f"     - total_invested: {'✅ ЕСТЬ' if has_total_invested else '❌ НЕТ'}")
        print(f"     - breakeven_pct: {'✅ ЕСТЬ' if has_breakeven_pct else '❌ НЕТ'}")
        print(f"     - orderbook_level: {'✅ ЕСТЬ' if has_orderbook_level else '❌ НЕТ'}")
        
        if has_total_invested and has_breakeven_pct and has_orderbook_level:
            print(f"   ✅ Все поля присутствуют, обновление не требуется")
            continue
        
        # Нужно пересчитать таблицу
        print(f"   🔄 Пересчёт таблицы...")
        
        # Получаем параметры из состояния
        start_price = cycle_data.get('start_price', 0)
        
        if start_price <= 0:
            print(f"   ❌ Некорректная start_price: {start_price}, пропускаем")
            continue
        
        # Восстанавливаем параметры из сохранённой таблицы
        params = {
            'steps': len(table) - 1,  # Количество шагов
            'start_volume': row0.get('purchase_usd', 10.0),  # Стартовый объём
            'start_price': start_price,
            'pprof': 0.6,  # Дефолтное значение
            'kprof': 0.02,  # Дефолтное значение
            'target_r': 3.65,  # Дефолтное значение
            'rk': 0.0,  # Дефолтное значение
            'geom_multiplier': 2.0,  # Дефолтное значение
            'rebuy_mode': 'geometric'  # Дефолтное значение
        }
        
        # Пытаемся вычислить параметры из существующей таблицы
        if len(table) > 1:
            row1 = table[1]
            decrease_step_1 = abs(row1.get('decrease_step_pct', 0))
            
            # target_r ≈ decrease_step_1 (для step=1 и rk=0)
            if decrease_step_1 > 0:
                params['target_r'] = decrease_step_1
                print(f"   📊 Определён target_r ≈ {decrease_step_1:.2f}%")
            
            # Определяем rebuy_mode по изменению покупки
            purchase_0 = row0.get('purchase_usd', 0)
            purchase_1 = row1.get('purchase_usd', 0)
            
            if purchase_0 > 0 and purchase_1 > 0:
                ratio = purchase_1 / purchase_0
                if abs(ratio - 1.0) < 0.01:
                    params['rebuy_mode'] = 'fixed'
                    print(f"   📊 Определён rebuy_mode = fixed")
                elif abs(ratio - 2.0) < 0.1:
                    params['rebuy_mode'] = 'martingale'
                    params['geom_multiplier'] = 2.0
                    print(f"   📊 Определён rebuy_mode = martingale")
                else:
                    params['rebuy_mode'] = 'geometric'
                    params['geom_multiplier'] = ratio
                    print(f"   📊 Определён rebuy_mode = geometric, multiplier = {ratio:.2f}")
        
        # Пересчитываем таблицу
        try:
            new_table = calculate_breakeven_table(params, current_price=start_price)
            
            print(f"   ✅ Таблица пересчитана: {len(new_table)} строк")
            
            # Проверяем новую таблицу
            new_row0 = new_table[0]
            print(f"   📊 Новая таблица содержит:")
            print(f"      - total_invested: {new_row0.get('total_invested', 'НЕТ')}")
            print(f"      - breakeven_pct: {new_row0.get('breakeven_pct', 'НЕТ')}")
            print(f"      - orderbook_level: {'orderbook_level' in new_row0}")
            
            # Обновляем цикл
            cycle_data['table'] = new_table
            updated_count += 1
            
            print(f"   ✅ Цикл {currency} обновлён")
            
        except Exception as e:
            print(f"   ❌ Ошибка пересчёта: {e}")
            import traceback
            traceback.print_exc()
    
    if updated_count > 0:
        # Сохраняем обновлённый файл состояния
        backup_file = state_file + '.backup'
        
        print(f"\n💾 Создание резервной копии: {backup_file}")
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Сохранение обновлённого состояния: {state_file}")
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Обновлено циклов: {updated_count}")
        print(f"ℹ️  Резервная копия сохранена: {backup_file}")
    else:
        print(f"\nℹ️  Обновление не требуется")

if __name__ == '__main__':
    update_cycle_tables()
