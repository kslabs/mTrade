# 🚀 Команды для публикации (копировать и выполнять)



## 1️⃣ Инициализация Git



```bash

cd c:\Users\Администратор\Documents\bGate.mTrade

git init

git add .

git status

```



## 2️⃣ Первый коммит



```bash

git commit -m "Initial commit: Gate.io Multi-Trading Platform v1.4



Features:

- Обычный и копитрейдинг режимы

- Автотрейдинг с настраиваемыми параметрами  

- WebSocket для real-time данных

- Управление валютными парами

- Сохранение состояния UI

- Полная русская локализация



Technical:

- Python 3.8+ with Flask

- WebSocket real-time updates

- RESTful API

- Server-side state management

- Comprehensive documentation in Russian"

```



## 3️⃣ Подключение к GitHub (замените yourusername!)



```bash

git remote add origin https://github.com/yourusername/bGate.mTrade.git

git branch -M main

git push -u origin main

```



## 4️⃣ Создание тега v1.4.0



```bash

git tag -a v1.4.0 -m "Release v1.4.0: Currency Management & UI State



New Features:

- Currency management interface with add/edit/delete

- Server-side UI state persistence

- Auto-save for all settings

- Improved auto-trading state management



Improvements:

- Enhanced WebSocket stability

- Better error handling

- Comprehensive Russian documentation

- GitHub Actions CI/CD setup



Documentation:

- Added CONTRIBUTING.md

- Added REPOSITORY_SETUP.md

- Added UI_STATE_GUIDE.md

- Updated README.md with badges

- Created GitHub templates"



git push origin v1.4.0

```



## 5️⃣ Создание ветки develop



```bash

git checkout -b develop

git push -u origin develop

git checkout main

```



## 🔑 SSH ключ (для удобства)



### Создать ключ:

```bash

ssh-keygen -t ed25519 -C "your_email@example.com"

```



### Windows - показать публичный ключ:

```powershell

type %USERPROFILE%\.ssh\id_ed25519.pub

```



### Linux/Mac - показать публичный ключ:

```bash

cat ~/.ssh/id_ed25519.pub

```



### Добавить на GitHub:

1. GitHub → Settings → SSH and GPG keys → New SSH key

2. Вставить скопированный ключ

3. Изменить remote на SSH:



```bash

git remote set-url origin git@github.com:yourusername/bGate.mTrade.git

```



## 📝 Дальнейшая работа



### Создать feature ветку:

```bash

git checkout develop

git checkout -b feature/your-feature-name

# ... работа над feature ...

git add .

git commit -m "feat(scope): краткое описание"

git push -u origin feature/your-feature-name

# Создать Pull Request на GitHub

```



### Обновить локальную ветку:

```bash

git checkout main

git pull origin main

git checkout develop

git pull origin develop

```



### Синхронизировать форк (для контрибьюторов):

```bash

git remote add upstream https://github.com/original/bGate.mTrade.git

git fetch upstream

git checkout main

git merge upstream/main

git push origin main

```



## 🐛 Исправление ошибок



### Забыли файл в .gitignore:

```bash

git rm --cached filename

git commit -m "chore: remove sensitive file from git"

git push

```



### Отменить последний коммит (сохранить изменения):

```bash

git reset --soft HEAD~1

```



### Показать историю:

```bash

git log --oneline --graph --all

```



### Проверить статус:

```bash

git status

```



### Показать изменения:

```bash

git diff

```



## ✅ Быстрая проверка



### Убедиться, что чувствительные файлы не добавлены:

```bash

git status | findstr "config.json accounts.json secrets.json"

```



Если команда что-то нашла - НЕ коммитить!



### Проверить .gitignore:

```bash

type .gitignore

```



### Проверить remote:

```bash

git remote -v

```



## 🎯 Полезные алиасы Git (опционально)



```bash

git config --global alias.st status

git config --global alias.co checkout

git config --global alias.br branch

git config --global alias.ci commit

git config --global alias.unstage 'reset HEAD --'

git config --global alias.last 'log -1 HEAD'

git config --global alias.visual 'log --oneline --graph --all'

```



Теперь можно использовать:

```bash

git st        # вместо git status

git co main   # вместо git checkout main

git ci -m ""  # вместо git commit -m ""

git visual    # красивая история

```



## 📊 GitHub настройки после публикации



### 1. Repository Settings:

- About → Description: `Professional Gate.io trading platform with web interface`

- Topics: `gateio` `trading` `crypto` `python` `flask` `websocket` `cryptocurrency` `trading-bot`

- Website: (если есть)



### 2. Features (Settings → General):

- ✅ Issues

- ✅ Projects

- ✅ Wiki

- ✅ Discussions (опционально)



### 3. Branch Protection (Settings → Branches):

- Branch name pattern: `main`

- ✅ Require pull request reviews before merging

- ✅ Require status checks to pass before merging

- ✅ Require branches to be up to date



### 4. Create Release:

1. Releases → Draft a new release

2. Tag: v1.4.0

3. Title: v1.4.0 - Currency Management & UI State

4. Description: (из CHANGELOG.md)

5. Publish



---



## 🎉 Готово!



Ваш репозиторий:

```

https://github.com/yourusername/bGate.mTrade

```



Не забудьте:

- ⭐ Добавить описание на GitHub

- 📝 Создать Release

- 📊 Добавить теги (topics)

- 🔐 Настроить защиту веток

