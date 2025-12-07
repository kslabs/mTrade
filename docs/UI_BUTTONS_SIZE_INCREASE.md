# Увеличение размера кнопок включения/выключения торговли

## Описание изменений
Увеличены круглые кнопки включения/выключения торговли для валют на веб-странице в 2 раза.

## Внесённые изменения

### Файл: `static/style.css`

#### 1. Основной стиль `.perm-indicator` (строка 320)
**Было:**
```css
.perm-indicator {width:10px;height:10px;border-radius:50%;position:absolute;top:4px;right:4px;box-shadow:0 0 0 1px #222,inset 0 0 4px rgba(0,0,0,.6);cursor:pointer}
```

**Стало:**
```css
.perm-indicator {width:20px;height:20px;border-radius:50%;position:absolute;top:4px;right:4px;box-shadow:0 0 0 2px #222,inset 0 0 6px rgba(0,0,0,.6);cursor:pointer;transition:transform .2s,box-shadow .2s}
```

**Изменения:**
- Размер увеличен с 10px × 10px до 20px × 20px (в 2 раза)
- Толщина внешней тени увеличена с 1px до 2px
- Размытие внутренней тени увеличено с 4px до 6px
- Добавлен transition для плавной анимации при наведении

#### 2. Добавлены hover-эффекты
**Новые стили:**
```css
.perm-indicator:hover {transform:scale(1.15);box-shadow:0 0 0 2px #4CAF50,inset 0 0 8px rgba(0,0,0,.4)}
.perm-indicator.off:hover {box-shadow:0 0 0 2px #f44336,inset 0 0 8px rgba(0,0,0,.4)}
```

**Эффект:**
- При наведении курсора кнопка увеличивается на 15% (scale(1.15))
- Внешняя тень меняет цвет: зелёный (#4CAF50) для включённых, красный (#f44336) для выключенных
- Плавная анимация благодаря transition

#### 3. Обновлены специфичные стили для табов (строки 373-374)
**Было:**
```css
.base-currency-tabs .tab-item .perm-indicator {border:1px solid #111}
.base-currency-tabs .tab-item.active .perm-indicator.on {box-shadow:0 0 0 1px #0d3,inset 0 0 4px rgba(0,0,0,.4)}
```

**Стало:**
```css
.base-currency-tabs .tab-item .perm-indicator {border:2px solid #111}
.base-currency-tabs .tab-item.active .perm-indicator.on {box-shadow:0 0 0 2px #0d3,inset 0 0 6px rgba(0,0,0,.4)}
```

**Изменения:**
- Толщина границы увеличена с 1px до 2px
- Толщина внешней тени увеличена с 1px до 2px
- Размытие внутренней тени увеличено с 4px до 6px

## Результат
✅ Круглые кнопки включения/выключения торговли увеличены в 2 раза (с 10px до 20px)
✅ Добавлена интерактивность: кнопки увеличиваются и подсвечиваются при наведении курсора
✅ Все тени и границы пропорционально скорректированы
✅ Изменения применяются немедленно после перезагрузки страницы (Ctrl+F5)

## Тестирование
Для проверки изменений:
1. Убедитесь, что сервер запущен
2. Откройте веб-интерфейс в браузере
3. Нажмите Ctrl+F5 для принудительной перезагрузки страницы (очистка кеша CSS)
4. Проверьте размер круглых кнопок в табах валют
5. Наведите курсор на кнопку — она должна увеличиться и подсветиться

## Дата изменений
2025-01-XX

## Автор
GitHub Copilot (AI Assistant)
