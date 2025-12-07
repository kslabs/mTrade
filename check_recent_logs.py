"""
Простая проверка последних логов сервера
"""
import json
import os
from datetime import datetime

def check_recent_logs():
    """Проверка последних событий в state файлах и логах"""
    
    print("\n=== ПРОВЕРКА ПОСЛЕДНИХ ЛОГОВ ===\n")
    
    # Проверяем файл состояния автотрейдера
    state_file = 'autotrader_cycles_state.json'
    if os.path.exists(state_file):
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            print(f"📄 Файл состояния: {state_file}")
            print(f"   Последнее обновление: {datetime.fromtimestamp(os.path.getmtime(state_file))}")
            
            # Проверяем статусы циклов
            if 'cycles' in state:
                for currency, cycle_info in state['cycles'].items():
                    print(f"\n💱 {currency}:")
                    print(f"   Статус: {cycle_info.get('status', 'N/A')}")
                    print(f"   Ручная пауза: {cycle_info.get('manual_pause', False)}")
                    print(f"   Автостарт после сброса: {cycle_info.get('auto_restart_after_reset', False)}")
                    
                    if 'start_buy_order' in cycle_info:
                        print(f"   Start buy order: {cycle_info['start_buy_order']}")
                    
        except Exception as e:
            print(f"❌ Ошибка чтения {state_file}: {e}")
    
    # Проверяем app_state.json
    app_state_file = 'app_state.json'
    if os.path.exists(app_state_file):
        try:
            with open(app_state_file, 'r', encoding='utf-8') as f:
                app_state = json.load(f)
            
            print(f"\n📄 Файл состояния приложения: {app_state_file}")
            print(f"   Последнее обновление: {datetime.fromtimestamp(os.path.getmtime(app_state_file))}")
            
            if 'autotrader' in app_state:
                autotrader = app_state['autotrader']
                print(f"   Автотрейдер активен: {autotrader.get('enabled', False)}")
                print(f"   Последняя итерация: {autotrader.get('last_iteration', 'N/A')}")
                
        except Exception as e:
            print(f"❌ Ошибка чтения {app_state_file}: {e}")
    
    print("\n" + "="*50)
    print("\n💡 Что проверить в консоли сервера:")
    print("   1. Ищите строки с [RESET_CYCLE] или [RESUME_CYCLE]")
    print("   2. Ищите строки с [START_BUY] или [BUYING]")
    print("   3. Проверьте наличие ошибок или исключений")
    print("   4. Обратите внимание на временные метки событий")
    
if __name__ == '__main__':
    check_recent_logs()
