"""
Модуль мониторинга ошибок логирования
Автоматически отслеживает и сохраняет все ошибки логирования продаж
"""

import os
import json
import time
from datetime import datetime
from threading import Lock
from typing import Dict, Any, Optional


class LoggingMonitor:
    """Мониторинг ошибок логирования с автоматическим сохранением"""
    
    def __init__(self, log_dir: str = None):
        """
        Args:
            log_dir: Директория для хранения логов ошибок (по умолчанию: ./logging_errors/)
        """
        self.lock = Lock()
        
        # Определяем директорию для логов ошибок
        if log_dir is None:
            log_dir = os.path.join(os.path.dirname(__file__), 'logging_errors')
        
        self.log_dir = log_dir
        
        # Создаём директорию, если не существует
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Файл с последней ошибкой (для быстрого доступа)
        self.latest_error_file = os.path.join(self.log_dir, 'LATEST_ERROR.json')
        
        # Файл сводки (список всех ошибок)
        self.summary_file = os.path.join(self.log_dir, 'ERRORS_SUMMARY.json')
        
        # Счётчик ошибок
        self.error_count = 0
        
        # Загружаем существующую сводку
        self._load_summary()
        
        print(f"[LOGGING_MONITOR] Инициализирован (log_dir={self.log_dir})")
    
    def _load_summary(self):
        """Загрузить существующую сводку ошибок"""
        try:
            if os.path.exists(self.summary_file):
                with open(self.summary_file, 'r', encoding='utf-8') as f:
                    summary = json.load(f)
                    self.error_count = summary.get('total_errors', 0)
                    print(f"[LOGGING_MONITOR] Загружена сводка: {self.error_count} ошибок")
        except Exception as e:
            print(f"[LOGGING_MONITOR] Ошибка загрузки сводки: {e}")
            self.error_count = 0
    
    def log_error(self, 
                  currency: str,
                  error_type: str,
                  error_message: str,
                  sell_data: Dict[str, Any],
                  traceback_str: str = None,
                  context: Dict[str, Any] = None) -> str:
        """
        Записать ошибку логирования в постоянное хранилище
        
        Args:
            currency: Валюта
            error_type: Тип ошибки (например, IOError, PermissionError)
            error_message: Сообщение об ошибке
            sell_data: Данные продажи (volume, price, delta_percent, pnl, и т.д.)
            traceback_str: Полная трассировка ошибки
            context: Дополнительный контекст (опционально)
        
        Returns:
            Путь к файлу с записанной ошибкой
        """
        with self.lock:
            try:
                # Генерируем уникальное имя файла с временной меткой
                timestamp = datetime.now()
                timestamp_str = timestamp.strftime('%Y%m%d_%H%M%S')
                self.error_count += 1
                
                error_filename = f"ERROR_{self.error_count:04d}_{currency}_{timestamp_str}.json"
                error_filepath = os.path.join(self.log_dir, error_filename)
                
                # Формируем полные данные ошибки
                error_record = {
                    'error_id': self.error_count,
                    'timestamp': timestamp.isoformat(),
                    'timestamp_unix': time.time(),
                    'currency': currency,
                    'error_type': error_type,
                    'error_message': error_message,
                    'sell_data': sell_data,
                    'traceback': traceback_str,
                    'context': context or {},
                    'file': error_filename
                }
                
                # Записываем в файл ошибки
                with open(error_filepath, 'w', encoding='utf-8') as f:
                    json.dump(error_record, f, ensure_ascii=False, indent=2)
                
                # Обновляем файл последней ошибки
                with open(self.latest_error_file, 'w', encoding='utf-8') as f:
                    json.dump(error_record, f, ensure_ascii=False, indent=2)
                
                # Обновляем сводку
                self._update_summary(error_record)
                
                print(f"[LOGGING_MONITOR] ✅ Ошибка #{self.error_count} записана: {error_filepath}")
                
                return error_filepath
                
            except Exception as e:
                # Критическая ошибка: не можем даже записать ошибку логирования!
                print(f"[LOGGING_MONITOR] ❌❌❌ КРИТИЧЕСКАЯ ОШИБКА МОНИТОРИНГА: {e}")
                import traceback
                traceback.print_exc()
                return None
    
    def _update_summary(self, error_record: Dict[str, Any]):
        """Обновить файл сводки"""
        try:
            # Загружаем существующую сводку
            summary = {
                'total_errors': 0,
                'last_updated': None,
                'errors_by_currency': {},
                'errors_by_type': {},
                'recent_errors': []
            }
            
            if os.path.exists(self.summary_file):
                try:
                    with open(self.summary_file, 'r', encoding='utf-8') as f:
                        summary = json.load(f)
                except Exception:
                    pass
            
            # Обновляем счётчики
            summary['total_errors'] = self.error_count
            summary['last_updated'] = datetime.now().isoformat()
            
            # Счётчик по валютам
            currency = error_record['currency']
            if currency not in summary['errors_by_currency']:
                summary['errors_by_currency'][currency] = 0
            summary['errors_by_currency'][currency] += 1
            
            # Счётчик по типам ошибок
            error_type = error_record['error_type']
            if error_type not in summary['errors_by_type']:
                summary['errors_by_type'][error_type] = 0
            summary['errors_by_type'][error_type] += 1
            
            # Добавляем в список последних ошибок (храним последние 50)
            recent_error = {
                'error_id': error_record['error_id'],
                'timestamp': error_record['timestamp'],
                'currency': error_record['currency'],
                'error_type': error_record['error_type'],
                'error_message': error_record['error_message'],
                'file': error_record['file']
            }
            
            if 'recent_errors' not in summary:
                summary['recent_errors'] = []
            
            summary['recent_errors'].insert(0, recent_error)
            summary['recent_errors'] = summary['recent_errors'][:50]  # Храним последние 50
            
            # Сохраняем сводку
            with open(self.summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            
            print(f"[LOGGING_MONITOR] Сводка обновлена: {self.error_count} ошибок (по валютам: {summary['errors_by_currency']})")
            
        except Exception as e:
            print(f"[LOGGING_MONITOR] Ошибка обновления сводки: {e}")
    
    def get_summary(self) -> Dict[str, Any]:
        """Получить сводку ошибок"""
        try:
            if os.path.exists(self.summary_file):
                with open(self.summary_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {
                'total_errors': 0,
                'last_updated': None,
                'errors_by_currency': {},
                'errors_by_type': {},
                'recent_errors': []
            }
        except Exception as e:
            print(f"[LOGGING_MONITOR] Ошибка чтения сводки: {e}")
            return {}
    
    def get_latest_error(self) -> Optional[Dict[str, Any]]:
        """Получить последнюю ошибку"""
        try:
            if os.path.exists(self.latest_error_file):
                with open(self.latest_error_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return None
        except Exception as e:
            print(f"[LOGGING_MONITOR] Ошибка чтения последней ошибки: {e}")
            return None


# Глобальный экземпляр монитора
_monitor = None
_monitor_lock = Lock()


def get_logging_monitor() -> LoggingMonitor:
    """Получить глобальный экземпляр монитора логирования (singleton)"""
    global _monitor
    
    if _monitor is None:
        with _monitor_lock:
            if _monitor is None:
                _monitor = LoggingMonitor()
    
    return _monitor
