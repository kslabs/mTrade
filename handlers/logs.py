from flask import request, jsonify
from trade_logger import get_trade_logger


def get_trade_logs_impl():
    try:
        trade_logger = get_trade_logger()

        # Параметры запроса
        limit = request.args.get('limit', '100')
        currency = request.args.get('currency')
        formatted = request.args.get('formatted', '0') == '1'

        try:
            limit = int(limit)
        except Exception:
            limit = 100

        # Если валюта не указана, попробуем автоматически выбрать первую валюту с логами
        if not currency:
            available = trade_logger.get_currencies_with_logs()
            if available and len(available) > 0:
                # используем первую найденную валюту
                currency = available[0]
            else:
                # Нет логов ни для одной валюты
                return jsonify({'success': True, 'logs': [], 'count': 0, 'currency': None})

        if formatted:
            logs = trade_logger.get_formatted_logs(limit=limit, currency=currency)
            return jsonify({'success': True, 'logs': logs, 'count': len(logs), 'currency': currency})
        else:
            logs = trade_logger.get_logs(limit=limit, currency=currency)
            return jsonify({'success': True, 'logs': logs, 'count': len(logs), 'currency': currency})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


def get_trade_logs_stats_impl():
    try:
        trade_logger = get_trade_logger()
        currency = request.args.get('currency')
        if not currency:
            available = trade_logger.get_currencies_with_logs()
            currency = available[0] if available else None

        stats = trade_logger.get_stats(currency=currency)

        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


def clear_trade_logs_impl():
    try:
        trade_logger = get_trade_logger()
        data = request.get_json() or {}
        currency = data.get('currency')

        if not currency:
            # Без явного указания валюты - не очищаем все логи (предотвращаем случайное удаление)
            return jsonify({'success': False, 'error': 'Не указана валюта. Для безопасности укажите параметр currency.'}), 400

        trade_logger.clear_logs(currency=currency)

        return jsonify({'success': True, 'message': f"Логи для {currency} очищены", 'currency': currency})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500
