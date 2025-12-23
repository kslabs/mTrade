# Интеграция двухпроцессного автотрейдера

## ✅ Что уже сделано

1. **Создан модуль `dual_process_autotrader.py`** с архитектурой:
   - **Процесс-циклер**: перебирает валюты по кругу
   - **Процесс-реактор**: реагирует на WebSocket обновления
   - **Общая память**: `Manager().dict()` для флагов и очередей
   - **Debounce**: защита от всплесков (100ms по умолчанию)
   - **Приоритетная очередь**: срочные задачи обрабатываются первыми

2. **Импорт добавлен в `mTrade.py`**

3. **Обновлена инициализация** в блоке `if __name__ == '__main__'`

## 🔧 Что нужно доделать вручную

### 1. Замените эндпоинт `/api/autotrade/start`

Найдите в `mTrade.py` (примерно строка 1215):

```python
@app.route('/api/autotrade/start', methods=['POST'])
def start_autotrade():
    """Включить автоторговлю (запустить поток per-currency)"""
    global AUTO_TRADE_GLOBAL_ENABLED, AUTO_TRADER
    try:
        AUTO_TRADE_GLOBAL_ENABLED = True
        state_manager.set_auto_trade_enabled(True)

        if AUTO_TRADER is None:
            def _api_client_provider():
                if not account_manager.active_account:
                    return None
                acc = account_manager.get_account(account_manager.active_account)
                if not acc:
                    return None
                from gate_api_client import GateAPIClient
                return GateAPIClient(acc['api_key'], acc['api_secret'], CURRENT_NETWORK_MODE)

            AUTO_TRADER = AutoTrader(_api_client_provider, get_websocket_manager(), state_manager)

        if not AUTO_TRADER.running:
            AUTO_TRADER.start()
```

**Замените на:**

```python
@app.route('/api/autotrade/start', methods=['POST'])
def start_autotrade():
    """Включить автоторговлю (запустить двухпроцессный автотрейдер)"""
    global AUTO_TRADE_GLOBAL_ENABLED, AUTO_TRADER
    try:
        AUTO_TRADE_GLOBAL_ENABLED = True
        state_manager.set_auto_trade_enabled(True)

        if AUTO_TRADER is None:
            def _api_client_provider():
                if not account_manager.active_account:
                    return None
                acc = account_manager.get_account(account_manager.active_account)
                if not acc:
                    return None
                from gate_api_client import GateAPIClient
                return GateAPIClient(acc['api_key'], acc['api_secret'], CURRENT_NETWORK_MODE)
            
            ws_manager = get_websocket_manager()
            currencies = Config.load_currencies()
            
            AUTO_TRADER = DualProcessAutoTrader(
                api_client_provider=_api_client_provider,
                ws_manager=ws_manager,
                state_manager=state_manager,
                currencies=[c['base'] for c in currencies if c.get('enabled', True)],
                debounce_seconds=0.1,
                max_urgent_per_cycle=5
            )

        if not AUTO_TRADER.running.value:  # ← Изменено с .running на .running.value
            AUTO_TRADER.start()

        print("[AUTOTRADE] ✅ Двухпроцессный автотрейдер включен")
        return jsonify({
            "success": True,
            "enabled": True,
            "running": AUTO_TRADER.running.value if AUTO_TRADER else False,
            "message": "Двухпроцессный автотрейдер включен"
        })
    except Exception as e:
        import traceback
        print(f"[ERROR] Start autotrade: {e}\n{traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500
```

### 2. Замените эндпоинт `/api/autotrade/stop`

```python
@app.route('/api/autotrade/stop', methods=['POST'])
def stop_autotrade():
    """Выключить автоторговлю (остановить двухпроцессный автотрейдер)"""
    global AUTO_TRADE_GLOBAL_ENABLED, AUTO_TRADER
    try:
        AUTO_TRADE_GLOBAL_ENABLED = False
        state_manager.set_auto_trade_enabled(False)
        if AUTO_TRADER and AUTO_TRADER.running.value:  # ← Изменено
            AUTO_TRADER.stop()
        print("[AUTOTRADE] ✅ Двухпроцессный автотрейдер выключен")
        return jsonify({
            "success": True,
            "enabled": False,
            "running": AUTO_TRADER.running.value if AUTO_TRADER else False,  # ← Изменено
            "message": "Двухпроцессный автотрейдер выключен"
        })
    except Exception as e:
        import traceback
        print(f"[ERROR] Stop autotrade: {e}\n{traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500
```

### 3. Обновите `/api/autotrade/status`

```python
@app.route('/api/autotrade/status', methods=['GET'])
def get_autotrade_status():
    """Получить статус автоторговли + краткую статистику"""
    try:
        enabled = state_manager.get_auto_trade_enabled()
        stats = AUTO_TRADER.get_stats() if AUTO_TRADER and AUTO_TRADER.running.value else {}  # ← Изменено
        return jsonify({
            "success": True,
            "enabled": enabled,
            "running": AUTO_TRADER.running.value if AUTO_TRADER else False,  # ← Изменено
            "stats": stats
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
```

### 4. Интегрируйте реальную торговую логику

В файле `dual_process_autotrader.py` найдите метод `_execute_trading_logic` (строка ~250):

```python
def _execute_trading_logic(self, currency: str):
    """
    ТОРГОВАЯ ЛОГИКА (заглушка, будет заменена реальным кодом).
    """
```

Замените заглушку на вызов вашего существующего кода из `autotrader.py`. Например:

```python
def _execute_trading_logic(self, currency: str):
    """ТОРГОВАЯ ЛОГИКА"""
    # Импортировать функции из autotrader.py
    from autotrader import process_currency_trade
    
    # Вызвать обработку
    process_currency_trade(
        currency=currency,
        api_client=self.api_client_provider(),
        ws_manager=self.ws_manager,
        state_manager=self.state_manager,
        cycles=self.cycles
    )
```

## 📊 Мониторинг

После запуска проверьте логи:

```
[DUAL-AT] Инициализация двухпроцессного автотрейдера
[DUAL-AT] Валюты: 10
[DUAL-AT] Debounce: 0.1s
[DUAL-AT] Max urgent/cycle: 5
[DUAL-AT] ✅ Процесс-циклер запущен (PID: 12345)
[DUAL-AT] ✅ Процесс-реактор запущен (PID: 12346)
[DUAL-AT] 🚀 Двухпроцессный автотрейдер активен
```

Статистика доступна через `/api/autotrade/status`:
- `cycler_iterations` - сколько итераций сделал циклер
- `cycler_processed` - сколько валют обработано циклером
- `reactor_queued` - сколько задач поставил реактор
- `urgent_processed` - сколько срочных задач выполнено
- `reactor_debounced` - сколько обновлений пропущено из-за debounce

## 🎯 Преимущества

1. **Быстрая реакция**: реактор ставит задачи мгновенно при изменении цены
2. **Нет блокировок**: два независимых процесса работают параллельно
3. **Защита от перегрузок**: debounce и лимиты срочных задач
4. **Наблюдаемость**: детальная статистика и логирование
5. **Масштабируемость**: легко добавить больше валют

## ⚙️ Настройка параметров

При создании `DualProcessAutoTrader` можно настроить:

```python
AUTO_TRADER = DualProcessAutoTrader(
    debounce_seconds=0.1,       # Минимальный интервал между обработками (сек)
    urgent_queue_max_size=100,  # Максимальный размер очереди срочных задач
    max_urgent_per_cycle=5      # Максимум срочных задач за один цикл
)
```

Рекомендуемые значения:
- **debounce_seconds**: 0.05-0.2 (быстрая реакция, но не перегрузка)
- **max_urgent_per_cycle**: 3-10 (баланс между срочными и обычными задачами)

## 🐛 Отладка

Если что-то не работает:

1. Проверьте, что оба процесса запустились (PID в логах)
2. Проверьте статистику через `/api/autotrade/status`
3. Убедитесь, что `TRADING_PERMISSIONS` включены для валют
4. Проверьте, что WebSocket manager работает и получает данные

## 🔄 Откат на старую версию

Если нужно вернуться к одно процессному варианту, просто закомментируйте строки с `DualProcessAutoTrader` и раскомментируйте `AutoTrader`.
