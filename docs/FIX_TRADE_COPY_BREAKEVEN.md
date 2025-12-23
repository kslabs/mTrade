# Исправление переключателя Trade/Copy и таблицы безубыточности

## Дата: 10 ноября 2025

## Проблемы:
1. **Trade/Copy переключатель не работал** - режим не переключался
2. **Таблица безубыточности не работала** - ошибка при расчете

## Исправления:

### 1. Переключатель Trade/Copy (mTrade.py)

**Проблема:** Глобальная переменная `AUTO_TRADER` не была инициализирована на уровне модуля.

**Решение:**
```python
# Добавлено после state_manager (строка ~177):
# Глобальный экземпляр автотрейдера (инициализируется позже)
AUTO_TRADER = None
```

**Эндпоинт GET /api/mode:**
```python
@app.route('/api/mode', methods=['GET'])
def get_mode():
    """Получить текущий режим торговли (trade/copy) (совместимость)"""
    mode = state_manager.get_trading_mode()
    internal_mode = 'normal' if mode == 'trade' else 'copy'
    return jsonify({"mode": mode, "internal_mode": internal_mode, "success": True})
```

**Эндпоинт POST /api/mode:**
```python
@app.route('/api/mode', methods=['POST'])
def set_mode():
    """Переключить режим торговли (trade/copy)"""
    global TRADING_MODE
    try:
        data = request.get_json(silent=True) or {}
        mode = str(data.get('mode','')).lower().strip()
        if mode not in ('trade','copy'):
            return jsonify({"success": False, "error": "Неверный режим"}), 400
        TRADING_MODE = mode
        state_manager.set_trading_mode(mode)
        stored = state_manager.get_trading_mode()
        # Применяем ко всем активным движкам
        internal_mode = 'normal' if stored == 'trade' else 'copy'
        for eng in trading_engines.values():
            try:
                eng.set_mode(internal_mode)
            except Exception:
                pass
        print(f"[MODE] Установлен режим: {stored} (internal={internal_mode})")
        return jsonify({"mode": stored, "internal_mode": internal_mode, "success": True})
    except Exception as e:
        import traceback
        print(f"[ERROR] set_mode: {e}\n{traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500
```

**Синхронизация режимов при старте сервера:**
```python
# В if __name__ == '__main__':
try:
    internal_mode = 'normal' if TRADING_MODE == 'trade' else 'copy'
    for eng in trading_engines.values():
        eng.set_mode(internal_mode)
    print(f"[INIT] Синхронизация режимов движков: {TRADING_MODE} -> {internal_mode}")
except Exception as e:
    print(f"[INIT] Ошибка синхронизации режимов движков: {e}")
```

### 2. Таблица безубыточности (mTrade.py)

**Проблема:** Таблица не рассчитывалась корректно, текущая цена не передавалась.

**Решение:**

**Эндпоинт GET /api/breakeven/table:**
- Поддержка legacy режима (без указания currency)
- Получение текущей цены из WebSocket
- Передача current_price в калькулятор

```python
@app.route('/api/breakeven/table', methods=['GET'])
def get_breakeven_table():
    """Рассчитать таблицу безубыточности.
    По умолчанию возвращает per-currency (если указан base_currency / currency),
    если параметры не указаны (старый UI), использует глобальные TRADE_PARAMS.
    """
    try:
        from breakeven_calculator import calculate_breakeven_table
        # Определяем тип запроса (legacy или per-currency)
        has_currency_arg = ('base_currency' in request.args) or ('currency' in request.args)
        base_currency = (request.args.get('base_currency') or request.args.get('currency') or '')
        base_currency = base_currency.upper() if base_currency else ''
        use_legacy = not has_currency_arg or base_currency == '' or base_currency == 'LEGACY'
        
        if use_legacy:
            params = TRADE_PARAMS
            base_for_price = 'BTC'  # legacy UI чаще по BTC
        else:
            params = state_manager.get_breakeven_params(base_currency)
            base_for_price = base_currency
        
        # Получаем текущую цену из WS
        current_price = 0.0
        try:
            ws_manager = get_websocket_manager()
            if ws_manager and base_for_price:
                pd = ws_manager.get_data(f"{base_for_price}_USDT")
                if pd and pd.get('ticker') and pd['ticker'].get('last'):
                    current_price = float(pd['ticker']['last'])
        except Exception:
            current_price = 0.0
        
        table_data = calculate_breakeven_table(params, current_price=current_price)
        return jsonify({
            "success": True,
            "table": table_data,
            "params": params,
            "currency": base_currency if not use_legacy else 'LEGACY',
            "legacy": use_legacy,
            "current_price": current_price
        })
    except Exception as e:
        import traceback
        print(f"[ERROR] Breakeven table calculation: {e}")
        print(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500
```

**Добавлены legacy эндпоинты для параметров:**

```python
@app.route('/api/trade/params/legacy', methods=['GET'])
def get_trade_params_legacy():
    """Получить глобальные (legacy) параметры торговли для совместимости со старым UI"""
    try:
        return jsonify({"success": True, "params": TRADE_PARAMS, "legacy": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/trade/params/legacy', methods=['POST'])
def save_trade_params_legacy():
    """Сохранить глобальные (legacy) параметры торговли (не влияет на per-currency)"""
    global TRADE_PARAMS
    try:
        data = request.get_json(silent=True) or {}
        updated = TRADE_PARAMS.copy()
        for k, caster in (
            ('steps', int), ('start_volume', float), ('start_price', float),
            ('pprof', float), ('kprof', float), ('target_r', float),
            ('geom_multiplier', float), ('rebuy_mode', str)
        ):
            if k in data and data[k] is not None:
                try:
                    updated[k] = caster(data[k])
                except Exception:
                    pass
        TRADE_PARAMS = updated
        state_manager.set("legacy_trade_params", TRADE_PARAMS)
        print(f"[PARAMS][LEGACY] -> {TRADE_PARAMS}")
        return jsonify({"success": True, "params": TRADE_PARAMS, "legacy": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
```

## Тестирование:

### Переключатель Trade/Copy:
```bash
# GET текущий режим
curl http://localhost:5000/api/mode

# POST переключение на copy
curl -X POST http://localhost:5000/api/mode -H "Content-Type: application/json" -d '{"mode":"copy"}'

# POST переключение на trade
curl -X POST http://localhost:5000/api/mode -H "Content-Type: application/json" -d '{"mode":"trade"}'
```

### Таблица безубыточности:
```bash
# Legacy режим (без указания валюты)
curl http://localhost:5000/api/breakeven/table

# Per-currency режим (для BTC)
curl http://localhost:5000/api/breakeven/table?base_currency=BTC

# Per-currency режим (для ETH)
curl http://localhost:5000/api/breakeven/table?base_currency=ETH
```

### Legacy параметры:
```bash
# GET legacy параметры
curl http://localhost:5000/api/trade/params/legacy

# POST legacy параметры
curl -X POST http://localhost:5000/api/trade/params/legacy -H "Content-Type: application/json" -d '{"steps":20,"start_volume":5.0}'
```

## Результат:

✅ **Trade/Copy переключатель работает**
- Режим сохраняется в state_manager
- Применяется ко всем активным движкам
- Синхронизируется при старте сервера

✅ **Таблица безубыточности работает**
- Поддержка legacy режима (старый UI)
- Поддержка per-currency режима (новый UI)
- Корректная передача текущей цены из WebSocket
- Fallback на дефолтное значение если цена недоступна

✅ **Обратная совместимость**
- Старый UI продолжает работать с legacy эндпоинтами
- Новый UI использует per-currency эндпоинты
- Нет breaking changes

## Файлы изменены:
- `mTrade.py` - основные исправления переключателя и таблицы

## Связанные файлы (не изменены, работают корректно):
- `breakeven_calculator.py` - расчет таблицы безубыточности
- `state_manager.py` - сохранение/загрузка состояния
- `trading_engine.py` - движок торговли с режимами normal/copy
- `autotrader.py` - per-currency автотрейдер
