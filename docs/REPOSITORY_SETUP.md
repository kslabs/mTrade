# 📦 Руководство по подготовке репозитория



Пошаговое руководство по подготовке проекта для публикации на GitHub/GitLab/Bitbucket.



## 📋 Содержание



- [Предварительная подготовка](#предварительная-подготовка)

- [Создание репозитория](#создание-репозитория)

- [Первая публикация](#первая-публикация)

- [Работа с ветками](#работа-с-ветками)

- [GitHub Actions (CI/CD)](#github-actions-cicd)



## ✅ Предварительная подготовка



### 1. Проверка файлов



Убедитесь, что следующие файлы созданы и настроены:



```bash

# Обязательные файлы

✅ README.md              # Основная документация

✅ LICENSE                # Лицензия проекта (MIT)

✅ .gitignore             # Исключения для Git

✅ .gitattributes         # Настройки Git

✅ requirements.txt       # Python зависимости

✅ CONTRIBUTING.md        # Руководство для контрибьюторов

✅ CHANGELOG.md           # История изменений



# Примеры конфигурации

✅ config.json.example

✅ accounts.json.example

✅ config/secrets.example.json



# Документация

✅ docs/README.md

✅ UI_STATE_GUIDE.md

✅ QUICKSTART.md

```



### 2. Очистка чувствительных данных



**ВАЖНО!** Перед публикацией удалите все чувствительные данные:



```bash

# Убедитесь, что эти файлы в .gitignore:

config.json              # ❌ НЕ коммитить!

accounts.json            # ❌ НЕ коммитить!

config/secrets.json      # ❌ НЕ коммитить!

*.log                    # ❌ НЕ коммитить!

*.pid                    # ❌ НЕ коммитить!

```



### 3. Проверка кода



```bash

# Запустить тесты

python test_test_mode.py

python test_websocket.py



# Проверить Python код (опционально)

pip install flake8 pylint

flake8 mTrade.py --max-line-length=120

pylint mTrade.py

```



## 🌐 Создание репозитория



### GitHub



1. **Создать репозиторий:**

   - Перейти на https://github.com/new

   - Название: `bGate.mTrade`

   - Описание: `Professional Gate.io trading platform with web interface`

   - Visibility: `Public` или `Private`

   - НЕ добавлять README, .gitignore, лицензию (уже есть локально)



2. **Настроить репозиторий:**

   - Settings → General → Features:

     - ✅ Issues

     - ✅ Projects

     - ✅ Wiki

   - Settings → Topics: добавить теги

     - `gateio`, `trading`, `crypto`, `python`, `flask`, `websocket`



### GitLab



1. **Создать проект:**

   - Перейти на https://gitlab.com/projects/new

   - Project name: `bGate.mTrade`

   - Visibility Level: `Public` или `Private`

   - Initialize repository with a README: `No`



### Bitbucket



1. **Создать репозиторий:**

   - Перейти в Repositories → Create repository

   - Repository name: `bGate.mTrade`

   - Access level: `Public` или `Private`

   - Include a README?: `No`



## 🚀 Первая публикация



### Инициализация локального репозитория



```bash

# Перейти в директорию проекта

cd c:\Users\Администратор\Documents\bGate.mTrade



# Инициализировать Git (если еще не сделано)

git init



# Добавить все файлы

git add .



# Проверить статус

git status



# Убедиться, что чувствительные файлы НЕ добавлены

# (должны быть в .gitignore)



# Создать первый коммит

git commit -m "Initial commit: Gate.io Multi-Trading Platform v1.4"

```



### Подключение к удаленному репозиторию



#### GitHub:

```bash

git remote add origin https://github.com/yourusername/bGate.mTrade.git

git branch -M main

git push -u origin main

```



#### GitLab:

```bash

git remote add origin https://gitlab.com/yourusername/bGate.mTrade.git

git branch -M main

git push -u origin main

```



#### Bitbucket:

```bash

git remote add origin https://bitbucket.org/yourusername/bGate.mTrade.git

git branch -M main

git push -u origin main

```



### SSH вместо HTTPS (рекомендуется)



```bash

# Создать SSH ключ (если нет)

ssh-keygen -t ed25519 -C "your_email@example.com"



# Скопировать публичный ключ

cat ~/.ssh/id_ed25519.pub



# Добавить SSH ключ в GitHub/GitLab/Bitbucket:

# GitHub: Settings → SSH and GPG keys → New SSH key

# GitLab: Preferences → SSH Keys → Add key

# Bitbucket: Personal settings → SSH keys → Add key



# Использовать SSH URL:

git remote set-url origin git@github.com:yourusername/bGate.mTrade.git

```



## 🌿 Работа с ветками



### Структура веток



```

main (production)

  ├── develop (development)

  │   ├── feature/auto-trading

  │   ├── feature/stop-loss

  │   └── fix/websocket-reconnect

  └── hotfix/critical-bug

```



### Создание веток



```bash

# Создать ветку develop

git checkout -b develop

git push -u origin develop



# Создать feature ветку

git checkout develop

git checkout -b feature/auto-trading

git push -u origin feature/auto-trading



# Работать в ветке

git add .

git commit -m "feat(autotrade): добавить базовую логику автотрейдинга"

git push

```



### Merge в main



```bash

# Переключиться на develop

git checkout develop



# Влить изменения из feature

git merge feature/auto-trading



# Переключиться на main

git checkout main



# Влить изменения из develop

git merge develop



# Отправить на сервер

git push

```



### Защита веток (GitHub)



Settings → Branches → Branch protection rules:



Для ветки `main`:

- ✅ Require pull request reviews before merging

- ✅ Require status checks to pass before merging

- ✅ Require branches to be up to date before merging

- ✅ Include administrators



## 🤖 GitHub Actions (CI/CD)



Создать файл `.github/workflows/python-tests.yml`:



```yaml

name: Python Tests



on:

  push:

    branches: [ main, develop ]

  pull_request:

    branches: [ main, develop ]



jobs:

  test:

    runs-on: ubuntu-latest

    

    strategy:

      matrix:

        python-version: [3.8, 3.9, 3.10, 3.11]

    

    steps:

    - uses: actions/checkout@v3

    

    - name: Set up Python ${{ matrix.python-version }}

      uses: actions/setup-python@v4

      with:

        python-version: ${{ matrix.python-version }}

    

    - name: Install dependencies

      run: |

        python -m pip install --upgrade pip

        pip install -r requirements.txt

        pip install pytest pytest-cov flake8

    

    - name: Lint with flake8

      run: |

        # Остановить сборку если есть синтаксические ошибки

        flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

        # Проверить остальные правила (предупреждения)

        flake8 . --count --exit-zero --max-complexity=10 --max-line-length=120 --statistics

    

    - name: Run tests

      run: |

        python test_test_mode.py

        python test_websocket.py

    

    - name: Test coverage

      run: |

        pytest --cov=. --cov-report=xml

    

    - name: Upload coverage to Codecov

      uses: codecov/codecov-action@v3

      with:

        file: ./coverage.xml

        flags: unittests

        name: codecov-umbrella

```



## 🏷️ Создание релизов



### Semantic Versioning (SemVer)



```

MAJOR.MINOR.PATCH



1.4.0 → 1.4.1 (patch: исправления)

1.4.1 → 1.5.0 (minor: новые функции)

1.5.0 → 2.0.0 (major: breaking changes)

```



### Создание тега



```bash

# Создать тег

git tag -a v1.4.0 -m "Release v1.4.0: Currency Management"



# Отправить тег на сервер

git push origin v1.4.0



# Отправить все теги

git push --tags

```



### Создание релиза на GitHub



1. Перейти: Releases → Draft a new release

2. Choose a tag: `v1.4.0`

3. Release title: `v1.4.0 - Currency Management`

4. Описание: скопировать из CHANGELOG.md

5. Attach binaries: (опционально)

6. Publish release



## 📊 GitHub дополнительные настройки



### README бейджи



Добавить в начало README.md:



```markdown

# Gate.io Multi-Trading Platform



![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)

![License](https://img.shields.io/badge/license-MIT-green)

![Version](https://img.shields.io/badge/version-1.4.0-orange)

![Tests](https://github.com/yourusername/bGate.mTrade/workflows/Python%20Tests/badge.svg)

[![codecov](https://codecov.io/gh/yourusername/bGate.mTrade/branch/main/graph/badge.svg)](https://codecov.io/gh/yourusername/bGate.mTrade)

```



### GitHub Templates



**`.github/ISSUE_TEMPLATE/bug_report.md`:**

```markdown

---

name: Bug report

about: Создать отчет об ошибке

title: '[BUG] '

labels: bug

assignees: ''

---



**Описание ошибки**

Четкое описание проблемы.



**Шаги для воспроизведения**

1. Перейти в '...'

2. Нажать на '...'

3. Появляется ошибка



**Ожидаемое поведение**

Что должно было произойти.



**Скриншоты**

Если применимо, добавьте скриншоты.



**Окружение:**

 - ОС: [например, Windows 10]

 - Python версия: [например, 3.11]

 - Версия проекта: [например, v1.4]

```



**`.github/PULL_REQUEST_TEMPLATE.md`:**

```markdown

## Описание

Краткое описание изменений.



## Тип изменений

- [ ] Исправление бага (fix)

- [ ] Новая функция (feature)

- [ ] Критическое изменение (breaking change)

- [ ] Документация (docs)



## Чеклист

- [ ] Код соответствует стандартам проекта

- [ ] Добавлены тесты

- [ ] Все тесты проходят

- [ ] Обновлена документация

- [ ] Обновлен CHANGELOG.md

```



## 🔄 Синхронизация форков



Для контрибьюторов:



```bash

# Добавить upstream

git remote add upstream https://github.com/original/bGate.mTrade.git



# Получить изменения

git fetch upstream



# Влить в локальную main

git checkout main

git merge upstream/main



# Отправить в свой форк

git push origin main

```



## 📝 Чеклист перед публикацией



- [ ] Все чувствительные данные удалены

- [ ] .gitignore настроен правильно

- [ ] README.md актуален

- [ ] CHANGELOG.md заполнен

- [ ] Тесты проходят

- [ ] Код отформатирован

- [ ] Лицензия добавлена

- [ ] Примеры конфигов созданы

- [ ] Документация полная

- [ ] Коммиты осмысленные



## ❓ Полезные команды



```bash

# Показать статус

git status



# Показать историю

git log --oneline --graph --all



# Показать изменения

git diff



# Отменить изменения в файле

git checkout -- filename



# Отменить последний коммит (сохранить изменения)

git reset --soft HEAD~1



# Показать удаленные репозитории

git remote -v



# Обновить с сервера

git pull



# Отправить на сервер

git push



# Клонировать репозиторий

git clone https://github.com/yourusername/bGate.mTrade.git

```



## 🔗 Ссылки



- [Git документация](https://git-scm.com/doc)

- [GitHub Docs](https://docs.github.com)

- [GitLab Docs](https://docs.gitlab.com)

- [Bitbucket Docs](https://support.atlassian.com/bitbucket-cloud/)



---



**Готово! Проект подготовлен к публикации! 🎉**

