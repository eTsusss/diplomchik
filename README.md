# Газель Экспресс

Локальный сайт грузоперевозок с формой заявки, админ-панелью, SQLite-базой и выгрузкой в Excel.

## Как запустить

```bash
python3 server.py
```

После запуска сайт будет доступен по адресу:

- `http://localhost:8000`
- админ-панель: `http://localhost:8000/admin.html`

## Как запустить через Docker

```bash
docker compose up --build
```

После запуска через Docker сайт будет доступен по адресу:

- `http://localhost:4000`
- админ-панель: `http://localhost:4000/admin.html`

База данных проброшена как локальная папка `data`, поэтому заявки и администраторы сохраняются между перезапусками контейнера.

Создать первого администратора через Docker можно командой:

```bash
docker compose run --rm gazel-express python3 server.py --create-admin admin secret123
```

## Как запустить на сервере из Git

На сервере должны быть установлены Git, Docker и Docker Compose.

```bash
git clone URL_РЕПОЗИТОРИЯ gazel-express
cd gazel-express
docker compose up -d --build
```

После запуска сайт будет доступен на порту `4000`:

- `http://IP_СЕРВЕРА:4000`
- админ-панель: `http://IP_СЕРВЕРА:4000/admin.html`

Если на сервере ещё нет администратора:

```bash
docker compose run --rm gazel-express python3 server.py --create-admin admin strongpass123
```

Папка `data` создаётся на сервере автоматически и хранит SQLite-базу. Файл базы не хранится в Git, чтобы случайно не публиковать заявки и пароли администраторов.

## Как выложить на сервер через npm

На сервере должны быть установлены Docker и Docker Compose. Деплой выполняется по SSH:

```bash
DEPLOY_HOST=IP_СЕРВЕРА DEPLOY_USER=root npm run deploy
```

По умолчанию проект загружается в `/var/www/gazel-express`. Другой путь можно указать так:

```bash
DEPLOY_HOST=IP_СЕРВЕРА DEPLOY_USER=root DEPLOY_PATH=/var/www/site npm run deploy
```

Если SSH работает не на 22 порту:

```bash
DEPLOY_HOST=IP_СЕРВЕРА DEPLOY_USER=root DEPLOY_PORT=2222 npm run deploy
```

По умолчанию папка `data` не загружается на сервер повторно, чтобы не затереть заявки и администраторов. Если нужно один раз перенести текущую локальную базу на сервер:

```bash
DEPLOY_HOST=IP_СЕРВЕРА DEPLOY_USER=root DEPLOY_INCLUDE_DATA=1 npm run deploy
```

После деплоя сайт будет работать на сервере на порту `4000`:

- `http://IP_СЕРВЕРА:4000`
- админ-панель: `http://IP_СЕРВЕРА:4000/admin.html`

## Где хранятся данные

Файловая база данных проекта:

- `data/gazel_express.db`

Именно этот файл нужно передавать вместе с проектом, если вы хотите сохранить:

- аккаунты администраторов;
- заявки с сайта;
- текущую структуру базы.

## Первый администратор

Если в базе ещё нет админов, создать первого можно командой:

```bash
python3 server.py --create-admin LOGIN PASSWORD
```

Пример:

```bash
python3 server.py --create-admin admin secret123
```

Если аккаунт был создан в старой версии сайта и хранился в браузере, откройте проект через `server.py` на этом же компьютере: сайт автоматически перенесёт старые данные в SQLite.

## Выгрузка в Excel

После входа в админ-панель используйте кнопку `Выгрузить Excel`.

Файл выгружается в формате `.xlsx` и содержит:

- лист с заявками;
- лист с администраторами.
