# Инструкция по размещению на хостинге

## Что это за проект

Проект состоит из:

- статических файлов сайта (`index.html`, `styles.css`, `script.js`, `assets/`);
- админ-панели (`admin.html`, `admin.js`);
- Python-сервера (`server.py`);
- SQLite-базы (`data/gazel_express.db`).

Важно: это **не** просто статический сайт. Для работы формы заявок, админ-панели, входа и Excel-выгрузки нужен запущенный Python-процесс.

Поэтому для размещения нужен:

- VPS/VDS;
- или Python-хостинг, где можно держать запущенный Python-процесс;
- или любой Linux-сервер с Python 3.

Обычный статический хостинг без Python-процесса для этого проекта не подходит.

## Минимальные требования

- Python 3.10+;
- доступ по SSH;
- возможность запускать фоновый процесс;
- желательно Nginx для домена и проксирования.

## Быстрый запуск после загрузки архива

1. Загрузить архив на сервер.
2. Распаковать проект.
3. Перейти в папку проекта.
4. Запустить:

```bash
python3 server.py --host 0.0.0.0 --port 8000
```

После этого сайт будет доступен по адресу:

- `http://IP_СЕРВЕРА:8000`
- админ-панель: `http://IP_СЕРВЕРА:8000/admin.html`

Если нужен первый администратор:

```bash
python3 server.py --create-admin admin strongpass123
```

## Рекомендуемый вариант: запуск как сервис

Ниже пример для Ubuntu/Debian.

### 1. Установить Python и Nginx

```bash
sudo apt update
sudo apt install -y python3 nginx
```

### 2. Загрузить и распаковать проект

Пример:

```bash
mkdir -p /var/www
cd /var/www
unzip gazel-express-project.zip -d gazel-express
cd gazel-express
```

Важно: файл `data/gazel_express.db` должен остаться внутри проекта, иначе потеряются заявки и администраторы.

### 3. Проверить ручной запуск

```bash
cd /var/www/gazel-express
python3 server.py --host 127.0.0.1 --port 8000
```

Если всё открылось, остановить процесс и настроить сервис.

### 4. Создать systemd-сервис

Скопировать пример из файла `deploy/gazel-express.service.example` или создать:

```ini
[Unit]
Description=Gazel Express site
After=network.target

[Service]
Type=simple
WorkingDirectory=/var/www/gazel-express
ExecStart=/usr/bin/python3 /var/www/gazel-express/server.py --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3
User=www-data
Group=www-data

[Install]
WantedBy=multi-user.target
```

Сохранить как:

```bash
/etc/systemd/system/gazel-express.service
```

После этого:

```bash
sudo chown -R www-data:www-data /var/www/gazel-express
sudo systemctl daemon-reload
sudo systemctl enable gazel-express
sudo systemctl start gazel-express
sudo systemctl status gazel-express
```

## Подключение домена через Nginx

Скопировать пример из `deploy/nginx.gazel-express.conf.example` или создать конфиг:

```nginx
server {
    listen 80;
    server_name example.com www.example.com;

    client_max_body_size 20m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Сохранить как:

```bash
/etc/nginx/sites-available/gazel-express
```

Дальше:

```bash
sudo ln -s /etc/nginx/sites-available/gazel-express /etc/nginx/sites-enabled/gazel-express
sudo nginx -t
sudo systemctl reload nginx
```

## HTTPS через Let's Encrypt

Если домен уже направлен на сервер:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d example.com -d www.example.com
```

## Обновление проекта

При обновлении:

1. Сделать резервную копию `data/gazel_express.db`.
2. Заменить файлы проекта.
3. Не удалять базу, если нужно сохранить текущие заявки и администраторов.
4. Перезапустить сервис:

```bash
sudo systemctl restart gazel-express
```

## Резервная копия базы

Главный файл с данными:

- `data/gazel_express.db`

Для бэкапа достаточно скопировать этот файл:

```bash
cp /var/www/gazel-express/data/gazel_express.db /var/www/gazel_express.db.backup
```

## Если хостинг обычный shared hosting

Если хостинг позволяет только заливать HTML-файлы в папку сайта, то проект в текущем виде не заработает полностью, потому что ему нужен постоянно работающий `python3 server.py`.

В таком случае нужны:

- либо VPS/VDS;
- либо перенос проекта на WSGI/ASGI-стек под конкретный Python-хостинг;
- либо переработка проекта под чисто статический сайт без админки и базы.
