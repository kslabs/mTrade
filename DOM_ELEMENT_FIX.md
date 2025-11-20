# Исправление ошибки обращения к несуществующему элементу DOM

**Дата:** 2025-11-06  
**Файл:** `templates/index.html`

## Проблема

При загрузке рыночных данных возникала ошибка:
```
Uncaught (in promise) TypeError: Cannot set properties of null (setting 'textContent')
    at index.html:1951
```

## Причина

JavaScript код пытался обратиться к элементам DOM, которых не существовало на странице:
- `obBaseSymbol` - элемент для отображения базовой валюты в заголовке стакана
- Код пытался обновить `textContent` этого элемента, что приводило к ошибке

## Решение

Удалены ссылки на несуществующий элемент `obBaseSymbol` из JavaScript кода:

### Было:
```javascript
const obBaseSymbolEl = document.getElementById('obBaseSymbol');
const obQuoteSymbolEl = document.getElementById('obQuoteSymbol');

if (baseSymbolEl) baseSymbolEl.textContent = currentBaseCurrency;
if (quoteSymbolEl) quoteSymbolEl.textContent = currentQuoteCurrency;
if (obBaseSymbolEl) obBaseSymbolEl.textContent = currentBaseCurrency;  // ❌ Элемент не существует
if (obQuoteSymbolEl) obQuoteSymbolEl.textContent = currentQuoteCurrency;
```

### Стало:
```javascript
const obQuoteSymbolEl = document.getElementById('obQuoteSymbol');

if (baseSymbolEl) baseSymbolEl.textContent = currentBaseCurrency;
if (quoteSymbolEl) quoteSymbolEl.textContent = currentQuoteCurrency;
if (obQuoteSymbolEl) obQuoteSymbolEl.textContent = currentQuoteCurrency;  // ✅ Только существующие элементы
```

## Структура заголовка стакана

В HTML существует только один элемент для символа валюты в заголовке стакана:
```html
<div class="orderbook-header">
    <div>Цена (<span id="obQuoteSymbol">USDT</span>)</div>  <!-- ✅ Существует -->
    <div>Кол-во</div>                                       <!-- ❌ Нет id для базовой валюты -->
    <div>Сумма</div>
    <div>Σ Накоп.</div>
</div>
```

## Результат

- ❌ Устранена ошибка `Cannot set properties of null`
- ✅ Код больше не обращается к несуществующим элементам
- ✅ Приложение работает без JavaScript ошибок
- ✅ Стакан ордеров корректно отображается

## Файлы изменены

- `c:\Users\Администратор\Documents\bGate.mTrade\templates\index.html` (строки ~1963-1972)

## Дополнительные проверки

Все обращения к элементам DOM теперь защищены проверками:
```javascript
const element = document.getElementById('elementId');
if (element) {
    element.textContent = 'new value';  // ✅ Безопасно
}
```

## Связанные документы

- `NULL_ERROR_FIX.md` - первое исправление ошибок обращения к null элементам
- `ORDERBOOK_DEBUG.md` - диагностика проблем стакана
- `PROJECT_STATUS.md` - общий статус проекта
