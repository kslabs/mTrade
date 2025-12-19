#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Скрипт для чтения логов с правильной кодировкой"""

try:
    # Пробуем разные кодировки
    for encoding in ['utf-8', 'cp1251', 'latin1']:
        try:
            with open('server_debug.log', 'r', encoding=encoding, errors='ignore') as f:
                lines = f.readlines()
            
            # Ищем логи загрузки ICP
            icp_load_logs = [line.strip() for line in lines if '[LOAD_STATE][ICP]' in line or 'cycle.base_volume = 22' in line or 'cycle.total_invested_usd = 68' in line]
            
            if icp_load_logs:
                print(f"\n=== Логи загрузки ICP (кодировка: {encoding}) ===")
                for log in icp_load_logs[:20]:
                    print(log)
            
            # Ищу общую информацию о загрузке
            init_logs = [line.strip() for line in lines[:200] if 'AutoTraderV2' in line or 'Загружено' in line or 'циклов' in line]
            if init_logs:
                print(f"\n=== Логи инициализации (кодировка: {encoding}) ===")
                for log in init_logs[:30]:
                    print(log)
            
            break
        except Exception as e:
            continue
            
except Exception as e:
    print(f"Ошибка: {e}")
