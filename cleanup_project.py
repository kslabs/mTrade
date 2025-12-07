"""
Скрипт для очистки проекта от устаревших файлов
Удаляет старые документационные и диагностические файлы
"""
import os
from pathlib import Path

# Основная директория проекта
BASE_DIR = Path(__file__).parent

# Файлы, которые нужно сохранить (основные рабочие файлы)
KEEP_FILES = {
    # Основные исполняемые файлы
    'mTrade.py',
    'autotrader.py',
    'api_routes.py',
    'breakeven_calculator.py',
    'balance_cache.py',
    'config.py',
    'currency_sync.py',
    'currency_reservation_manager.py',
    'data_limits.py',
    'gateio_websocket.py',
    'gate_api_client.py',
    'orders.py',
    'price_feed.py',
    'process_manager.py',
    'server_control_routes.py',
    'state_manager.py',
    'trade_events.py',
    'trade_logger.py',
    'trading_engine.py',
    'trade_params_routes.py',
    'timing_logger.py',
    'websocket_routes.py',
    'debug_panel_logger.py',
    
    # Основные конфигурационные файлы
    'app_state.json',
    'accounts.json',
    'accounts.json.example',
    'config.json',
    'config.json.example',
    'currencies.json',
    'currency_sync_info.json',
    'pair_minimums.json',
    'network_mode.json',
    'ui_state.json',
    'autotrader_cycles_state.json',
    
    # Основная документация
    'README.md',
    'CHANGELOG.md',
    'ARCHITECTURE.md',
    'QUICKSTART.md',
    'CONTRIBUTING.md',
    'TROUBLESHOOTING.md',
    'LICENSE',
    
    # Рабочие батники и скрипты запуска
    'START.bat',
    'STOP.bat',
    'STATUS.bat',
    'restart_server.bat',
    'restart_autotrader.bat',
    'start.py',
    'stop.py',
    'status.py',
    'restart.py',
    'requirements.txt',
    'VERSION',
    '.gitignore',
    '.gitattributes',
    
    # Полезные утилиты
    'quick_check_autotrader.py',
    'monitor_autotrader.py',
    'monitor_live.py',
    'cleanup_logs.py',
    'restart_fresh.ps1',
}

# Паттерны файлов для удаления (устаревшие MD документы)
DELETE_PATTERNS = [
    # Старые фиксы и отчёты
    '*_FIX.md',
    '*_FIX_*.md',
    '*_FIXED.md',
    '*_COMPLETE.md',
    '*_FINAL.md',
    '*_SUMMARY.md',
    '*_QUICKSTART.md',
    '*_QUICKTEST.md',
    '*_QUICKCHECK.md',
    '*_REPORT.md',
    '*_GUIDE.md',
    '*_CHEATSHEET.md',
    '*_CHECKLIST.md',
    '*_STATUS.md',
    '*_READY.md',
    '*_SUCCESS.md',
    '*_DIAGNOSIS.md',
    '*_DIAGNOSTICS.md',
    '*_DEBUG.md',
    '*_INSTRUCTIONS.md',
    '*_MEMO.md',
    '*_TODO.md',
    '*_PLAN.md',
    '*_TESTING.md',
    '*_TEST.md',
    
    # Версионные документы
    '*_v1.*.md',
    'CHANGELOG_v*.md',
    'README_v*.md',
    'VERSION_*.md',
    'COMPLETE_v*.md',
    'DONE_v*.md',
    'READY_v*.md',
    
    # Временные файлы
    '*.backup',
    '*.broken_*',
    '*_backup_*.json',
    '*.log',
    'out_pair.txt',
    '*.pid',
    
    # Диагностические скрипты (оставим только главные)
    'analyze_*.py',
    'calculate_*.py',
    'check_*.py',
    'compare_*.py',
    'deep_diagnostic_*.py',
    'diagnose_*.py',
    'debug_*.py',
    'find_*.py',
    'fix_*.py',
    'force_*.py',
    'integrate_*.py',
    'optimize_*.py',
    'restore_*.py',
    'show_*.py',
    'test_*.py',
    'verify_*.py',
    'wait_*.py',
    'monitor_*.py',  # Кроме тех, что в KEEP_FILES
    'build_*.py',
    'enable_*.py',
    'convert_*.py',
    'setup_*.py',
    'update_*.py',
    'add_*.py',
    'run_*.py',
    'auto_fix_*.py',
    
    # HTML тесты
    'test_*.html',
    '*.patch',
]

# Исключения из удаления (даже если попадают под паттерн)
EXCEPTIONS = KEEP_FILES.union({
    'cleanup_project.py',  # Этот скрипт
    'cleanup_logs.py',
})

def should_delete(filepath: Path) -> bool:
    """Проверяет, нужно ли удалить файл"""
    filename = filepath.name
    
    # Не удаляем файлы из списка исключений
    if filename in EXCEPTIONS:
        return False
    
    # Не удаляем директории
    if filepath.is_dir():
        return False
    
    # Проверяем паттерны для удаления
    for pattern in DELETE_PATTERNS:
        if filepath.match(pattern):
            return True
    
    return False

def cleanup_project(dry_run=True):
    """
    Очищает проект от устаревших файлов
    
    Args:
        dry_run: Если True, только показывает что будет удалено, но не удаляет
    """
    files_to_delete = []
    
    # Сканируем директорию
    for item in BASE_DIR.iterdir():
        if item.is_file() and should_delete(item):
            files_to_delete.append(item)
    
    # Сортируем для удобства просмотра
    files_to_delete.sort()
    
    print(f"{'=' * 80}")
    print(f"Найдено файлов для удаления: {len(files_to_delete)}")
    print(f"{'=' * 80}\n")
    
    if not files_to_delete:
        print("✓ Нет файлов для удаления")
        return
    
    # Группируем по типам
    by_extension = {}
    for f in files_to_delete:
        ext = f.suffix or 'no_extension'
        if ext not in by_extension:
            by_extension[ext] = []
        by_extension[ext].append(f)
    
    # Показываем статистику
    print("Статистика по типам файлов:")
    print("-" * 40)
    for ext, files in sorted(by_extension.items()):
        print(f"  {ext:15s}: {len(files):4d} файлов")
    print()
    
    if dry_run:
        print("РЕЖИМ ПРЕДПРОСМОТРА (файлы НЕ будут удалены)")
        print("Для реального удаления запустите: python cleanup_project.py --delete")
        print()
        print("Файлы для удаления:")
        print("-" * 80)
        for f in files_to_delete:
            print(f"  {f.name}")
    else:
        print("УДАЛЕНИЕ ФАЙЛОВ...")
        deleted = 0
        errors = 0
        
        for f in files_to_delete:
            try:
                f.unlink()
                deleted += 1
                print(f"  ✓ Удалено: {f.name}")
            except Exception as e:
                errors += 1
                print(f"  ✗ Ошибка при удалении {f.name}: {e}")
        
        print()
        print(f"{'=' * 80}")
        print(f"Удалено файлов: {deleted}")
        if errors:
            print(f"Ошибок: {errors}")
        print(f"{'=' * 80}")

if __name__ == '__main__':
    import sys
    
    # Проверяем аргументы
    delete_mode = '--delete' in sys.argv or '-d' in sys.argv
    
    if delete_mode:
        print("\n⚠️  ВНИМАНИЕ: Вы собираетесь УДАЛИТЬ файлы!")
        print("Это действие необратимо!")
        response = input("\nПродолжить? (yes/no): ")
        
        if response.lower() in ['yes', 'y', 'да', 'д']:
            cleanup_project(dry_run=False)
        else:
            print("Отменено")
    else:
        cleanup_project(dry_run=True)
