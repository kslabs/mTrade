from flask import request, jsonify
import time
from typing import List

from config import Config
from gate_api_client import GateAPIClient
from gateio_websocket import init_websocket_manager, get_websocket_manager
import threading

# Local caches and watchlist for websocket-related handlers
WATCHED_PAIRS = set()
MULTI_PAIRS_CACHE = {}


def _init_default_watchlist():
    try:
        bases = Config.load_currencies()
        default_pairs = []
        for c in bases:
            code = (c or {}).get('code')
            if code:
                default_pairs.append(f"{str(code).upper()}_USDT")
        if default_pairs:
            for pair in default_pairs:
                WATCHED_PAIRS.add(pair)
    except Exception:
        pass


def subscribe_pair_impl():
    try:
        data = request.json
        base_currency = data.get('base_currency', 'BTC')
        quote_currency = data.get('quote_currency', 'USDT')
        currency_pair = f"{base_currency}_{quote_currency}"
        ws_manager = get_websocket_manager()
        # lazy init
        if not ws_manager:
            ak, sk = Config.load_secrets_by_mode(Config.load_network_mode())
            init_websocket_manager(ak, sk, Config.load_network_mode())
            ws_manager = get_websocket_manager()
            _init_default_watchlist()
        if not ws_manager:
            return jsonify({"success": False, "error": "WebSocket менеджер не инициализирован"})
        ws_manager.create_connection(currency_pair)
        return jsonify({"success": True, "pair": currency_pair, "message": f"Подписка на {currency_pair} создана"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


def get_pair_data_impl():
    try:
        base_currency = request.args.get('base_currency', 'BTC')
        quote_currency = request.args.get('quote_currency', 'USDT')
        force_refresh = request.args.get('force', '0') == '1'
        currency_pair = f"{base_currency}_{quote_currency}"
        ws_manager = get_websocket_manager()
        data = None
        if ws_manager:
            data = ws_manager.get_data(currency_pair)
            if data is None or force_refresh:
                ws_manager.create_connection(currency_pair)
                time.sleep(0.5)
                data = ws_manager.get_data(currency_pair)
        if not data:
            api_key, api_secret = Config.load_secrets_by_mode(Config.load_network_mode())
            market_data_client = GateAPIClient(api_key, api_secret, 'work')
            try:
                ob = market_data_client._request('GET', '/spot/order_book', params={'currency_pair': currency_pair.upper(), 'limit': 20})
                ticker = market_data_client._request('GET', '/spot/tickers', params={'currency_pair': currency_pair.upper()})
                data = {
                    'ticker': ticker[0] if isinstance(ticker, list) and ticker else {},
                    'orderbook': {'asks': ob.get('asks', []), 'bids': ob.get('bids', [])} if isinstance(ob, dict) else ob,
                    'trades': []
                }
            except Exception as rest_err:
                return jsonify({'success': False, 'error': f'Не удалось загрузить данные рынка: {str(rest_err)}'})
        return jsonify({'success': True, 'pair': currency_pair, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


def unsubscribe_pair_impl():
    try:
        data = request.json
        base_currency = data.get('base_currency', 'BTC')
        quote_currency = data.get('quote_currency', 'USDT')
        currency_pair = f"{base_currency}_{quote_currency}"
        ws_manager = get_websocket_manager()
        if not ws_manager:
            return jsonify({"success": False, "error": "WebSocket менеджер не инициализирован"})
        ws_manager.close_connection(currency_pair)
        return jsonify({"success": True, "pair": currency_pair, "message": f"Отписка от {currency_pair} выполнена"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


def _add_pairs_to_watchlist(pairs: List[str]):
    ws = get_websocket_manager()
    for p in (pairs or []):
        pair = str(p).upper()
        WATCHED_PAIRS.add(pair)
        try:
            if ws:
                ws.create_connection(pair)
        except Exception:
            pass


def _remove_pairs_from_watchlist(pairs: List[str]):
    ws = get_websocket_manager()
    for p in (pairs or []):
        pair = str(p).upper()
        WATCHED_PAIRS.discard(pair)
        try:
            if ws:
                ws.close_connection(pair)
        except Exception:
            pass


class _PairsUpdater:
    def run(self):
        while True:
            try:
                ws = get_websocket_manager()
                if ws:
                    for pair in list(WATCHED_PAIRS):
                        try:
                            ws.create_connection(pair)
                            data = ws.get_data(pair)
                            if data is not None:
                                MULTI_PAIRS_CACHE[pair] = {"ts": time.time(), "data": data}
                        except Exception:
                            pass
                time.sleep(1.0)
            except Exception:
                time.sleep(1.0)


def api_get_watchlist_impl():
    return jsonify({"success": True, "pairs": sorted(list(WATCHED_PAIRS))})


def api_watch_pairs_impl():
    try:
        payload = request.get_json(silent=True) or {}
        pairs = payload.get('pairs', [])
        if not pairs:
            return jsonify({"success": False, "error": "pairs[] пуст"}), 400
        _add_pairs_to_watchlist(pairs)
        return jsonify({"success": True, "added": [p.upper() for p in pairs]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def api_unwatch_pairs_impl():
    try:
        payload = request.get_json(silent=True) or {}
        pairs = payload.get('pairs', [])
        if not pairs:
            return jsonify({"success": False, "error": "pairs[] пуст"}), 400
        _remove_pairs_from_watchlist(pairs)
        return jsonify({"success": True, "removed": [p.upper() for p in pairs]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def api_pairs_data_impl():
    try:
        pairs_qs = request.args.get('pairs', '').strip()
        fresh = str(request.args.get('fresh', '0')).lower() in ('1', 'true', 'yes')
        if pairs_qs:
            pairs = [p.strip().upper() for p in pairs_qs.split(',') if p.strip()]
        else:
            pairs = sorted(list(WATCHED_PAIRS))

        ws = get_websocket_manager()
        result = {}
        for pair in pairs:
            if fresh and ws:
                try:
                    ws.create_connection(pair)
                    data_now = ws.get_data(pair)
                    if data_now is not None:
                        MULTI_PAIRS_CACHE[pair] = {"ts": time.time(), "data": data_now}
                except Exception:
                    pass
            cached = MULTI_PAIRS_CACHE.get(pair, {})
            result[pair] = {"ts": cached.get('ts'), "data": cached.get('data')}
        return jsonify({"success": True, "pairs": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# Start background updater thread on import
try:
    t = __import__('threading').Thread(target=_PairsUpdater().run, daemon=True)
    t.start()
except Exception:
    pass


# --- Convenience helpers (thin wrappers around gateio_websocket API) ---
def get_ws_manager():
    """Return current websocket manager instance (may be None)."""
    return get_websocket_manager()


def ensure_ws_initialized():
    """Ensure manager is initialized (lazy init using Config secrets)."""
    ws = get_websocket_manager()
    if not ws:
        ak, sk = Config.load_secrets_by_mode(Config.load_network_mode())
        try:
            init_websocket_manager(ak, sk, Config.load_network_mode())
        except Exception:
            pass
        ws = get_websocket_manager()
    return ws


def ws_close_all():
    ws = get_websocket_manager()
    if ws:
        try:
            ws.close_all()
        except Exception:
            pass


def ws_create_connection(pair: str):
    ws = ensure_ws_initialized()
    if not ws:
        return False
    try:
        ws.create_connection(pair)
        return True
    except Exception:
        return False


def ws_get_data(pair: str):
    ws = get_websocket_manager()
    if not ws:
        return None
    try:
        return ws.get_data(pair)
    except Exception:
        return None


def ws_close_connection(pair: str):
    ws = get_websocket_manager()
    if not ws:
        return False
    try:
        ws.close_connection(pair)
        return True
    except Exception:
        return False
