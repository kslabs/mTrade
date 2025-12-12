"""
Проверка последних записей в логе автотрейдера
"""
import os
import json
from datetime import datetime

LOG_DIR = "logs"

def check_recent_logs():
    """Проверить последние записи в логе"""
    print("=" * 70)
    print("ПРОВЕРКА ЛОГОВ АВТОТРЕЙДЕРА")
    print("=" * 70)
    
    if not os.path.exists(LOG_DIR):
        print(f"\n❌ Папка {LOG_DIR} не найдена")
        return
    
    # Находим последний лог-файл
    log_files = [f for f in os.listdir(LOG_DIR) if f.startswith('autotrader_') and f.endswith('.log')]
    
    if not log_files:
        print(f"\n❌ Лог-файлы не найдены в папке {LOG_DIR}")
        return
    
    # Сортируем по дате (самый новый первым)
    log_files.sort(reverse=True)
    latest_log = log_files[0]
    log_path = os.path.join(LOG_DIR, latest_log)
    
    print(f"\n📄 Последний лог: {latest_log}")
    print()
    
    # Читаем последние 20 строк
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        print(f"Всего записей в файле: {len(lines)}")
        print(f"\nПоследние 20 записей:\n")
        print("-" * 70)
        
        for line in lines[-20:]:
            try:
                entry = json.loads(line.strip())
                timestamp = datetime.fromtimestamp(entry.get('timestamp', 0)).strftime('%H:%M:%S')
                currency = entry.get('base_currency', '???')
                action = entry.get('action_type', '???')
                details = entry.get('details', {})
                message = details.get('message', '')
                
                print(f"[{timestamp}] [{currency}] {action}")
                if message:
                    print(f"  └─ {message}")
                
                # Дополнительная информация для покупок
                if action in ['START_BUY', 'REBUY']:
                    print(f"     Цена: {details.get('price', 'N/A')}")
                    print(f"     Количество: {details.get('amount', 'N/A')}")
                    print(f"     Стоимость: {details.get('cost_usd', 'N/A')} USDT")
                    if 'cycle_id' in details:
                        print(f"     Цикл ID: #{details.get('cycle_id')}")
                
                print()
                
            except json.JSONDecodeError:
                print(f"⚠️ Не удалось разобрать строку: {line[:50]}...")
        
        print("-" * 70)
        
    except Exception as e:
        print(f"❌ Ошибка чтения лога: {e}")

if __name__ == "__main__":
    check_recent_logs()
