#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для проверки состояния всех активных валют
"""

import json
import sys

def main():
    state_file = r"c:\Users\Администратор\Documents\bGate.mTrade\autotrader_cycles_state.json"
    
    try:
        with open(state_file, 'r', encoding='utf-8') as f:
            state = json.load(f)
        
        print("=" * 80)
        print("ПРОВЕРКА СОСТОЯНИЯ ВСЕХ ВАЛЮТ")
        print("=" * 80)
        print()
        
        active_currencies = []
        inactive_currencies = []
        broken_currencies = []
        
        for currency, data in state.items():
            active = data.get('active', False)
            active_step = data.get('active_step', -1)
            cycle_id = data.get('cycle_id', 0)
            total_cycles = data.get('total_cycles_count', 0)
            total_invested = data.get('total_invested_usd', 0)
            
            info = {
                'currency': currency,
                'active': active,
                'active_step': active_step,
                'cycle_id': cycle_id,
                'total_cycles': total_cycles,
                'total_invested': total_invested
            }
            
            if active and active_step == -1:
                broken_currencies.append(info)
            elif active:
                active_currencies.append(info)
            else:
                inactive_currencies.append(info)
        
        # Выводим сломанные валюты
        if broken_currencies:
            print("🚨 СЛОМАННЫЕ ВАЛЮТЫ (active=true, active_step=-1):")
            print("-" * 80)
            for info in broken_currencies:
                print(f"  {info['currency']:8s} | cycle_id: {info['cycle_id']:3d} | "
                      f"total_cycles: {info['total_cycles']:3d} | "
                      f"invested: ${info['total_invested']:.2f}")
            print()
        
        # Выводим активные валюты
        if active_currencies:
            print(f"✅ АКТИВНЫЕ ВАЛЮТЫ (active=true, active_step >= 0): {len(active_currencies)}")
            print("-" * 80)
            for info in active_currencies:
                print(f"  {info['currency']:8s} | step: {info['active_step']:2d} | "
                      f"cycle_id: {info['cycle_id']:3d} | "
                      f"total_cycles: {info['total_cycles']:3d} | "
                      f"invested: ${info['total_invested']:.2f}")
            print()
        
        # Выводим неактивные валюты
        if inactive_currencies:
            print(f"💤 НЕАКТИВНЫЕ ВАЛЮТЫ (active=false): {len(inactive_currencies)}")
            print("-" * 80)
            for info in inactive_currencies:
                print(f"  {info['currency']:8s} | cycle_id: {info['cycle_id']:3d} | "
                      f"total_cycles: {info['total_cycles']:3d}")
            print()
        
        # Итоговая статистика
        print("=" * 80)
        print("ИТОГОВАЯ СТАТИСТИКА:")
        print(f"  Всего валют: {len(state)}")
        print(f"  Активные: {len(active_currencies)}")
        print(f"  Неактивные: {len(inactive_currencies)}")
        print(f"  Сломанные (требуют исправления): {len(broken_currencies)}")
        print("=" * 80)
        
        if broken_currencies:
            print()
            print("⚠️  ВНИМАНИЕ: Обнаружены сломанные валюты!")
            print("   Они помечены как активные, но имеют active_step=-1")
            print("   Это блокирует их торговлю. Необходимо исправление!")
            return 1
        
        return 0
        
    except FileNotFoundError:
        print(f"❌ Файл состояния не найден: {state_file}")
        return 1
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка чтения JSON: {e}")
        return 1
    except Exception as e:
        print(f"❌ Непредвиденная ошибка: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
