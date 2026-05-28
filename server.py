import argparse
import os
import datetime as dt
import hashlib
import html
import io
import json
import secrets
import sqlite3
import uuid
import zipfile
from contextlib import contextmanager
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "gazel_express.db"
SESSION_COOKIE = "gazel_admin_session"
ORDER_STATUS_NEW = "new"
ORDER_STATUS_IN_PROGRESS = "in_progress"
ORDER_STATUS_COMPLETED = "completed"
ORDER_STATUS_ALIASES = {
    "new": ORDER_STATUS_NEW,
    "новая": ORDER_STATUS_NEW,
    "новый": ORDER_STATUS_NEW,
    "in_progress": ORDER_STATUS_IN_PROGRESS,
    "in progress": ORDER_STATUS_IN_PROGRESS,
    "processing": ORDER_STATUS_IN_PROGRESS,
    "в процессе": ORDER_STATUS_IN_PROGRESS,
    "completed": ORDER_STATUS_COMPLETED,
    "done": ORDER_STATUS_COMPLETED,
    "finished": ORDER_STATUS_COMPLETED,
    "выполнено": ORDER_STATUS_COMPLETED,
    "выполнен": ORDER_STATUS_COMPLETED,
    "архив": ORDER_STATUS_COMPLETED,
    "archived": ORDER_STATUS_COMPLETED,
    "в архиве": ORDER_STATUS_COMPLETED,
}
ORDER_STATUS_LABELS = {
    ORDER_STATUS_NEW: "Новая",
    ORDER_STATUS_IN_PROGRESS: "В процессе",
    ORDER_STATUS_COMPLETED: "Выполнено",
}


def now_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def normalize_login(value):
    return str(value or "").strip().lower()


def trim_value(value):
    return str(value or "").strip()


def normalize_order_status(value, default=None):
    normalized = trim_value(value).lower().replace("-", "_")
    return ORDER_STATUS_ALIASES.get(normalized, default)


def order_status_label(value):
    status = normalize_order_status(value, ORDER_STATUS_NEW)
    return ORDER_STATUS_LABELS.get(status, ORDER_STATUS_LABELS[ORDER_STATUS_NEW])


def is_archived_order(value):
    return normalize_order_status(value, ORDER_STATUS_NEW) == ORDER_STATUS_COMPLETED


def sha256_hash(value):
    return hashlib.sha256(trim_value(value).encode("utf-8")).hexdigest()


def fallback_hash(value):
    total = 0

    for char in trim_value(value):
        total = ((total << 5) - total + ord(char)) & 0xFFFFFFFF

        if total >= 0x80000000:
            total -= 0x100000000

    return f"fallback-{abs(total)}"


def verify_password(password, stored_hash):
    return stored_hash in {sha256_hash(password), fallback_hash(password)}


def connect_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def db_session():
    connection = connect_db()

    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db():
    with db_session() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS admins (
                login TEXT PRIMARY KEY,
                display_login TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                customer TEXT NOT NULL,
                phone TEXT NOT NULL,
                truck_type TEXT NOT NULL,
                date_time TEXT,
                cargo TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'new',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                admin_login TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (admin_login) REFERENCES admins(login) ON DELETE CASCADE
            );
            """
        )


def serialize_admin(row):
    if not row:
        return None

    return {
        "login": row["login"],
        "displayLogin": row["display_login"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def serialize_order(row):
    status = normalize_order_status(row["status"], ORDER_STATUS_NEW)

    return {
        "id": row["id"],
        "customer": row["customer"],
        "phone": row["phone"],
        "truckType": row["truck_type"],
        "dateTime": row["date_time"],
        "cargo": row["cargo"],
        "status": status,
        "statusLabel": order_status_label(status),
        "archived": is_archived_order(status),
        "createdAt": row["created_at"],
    }


def xml_escape(value):
    return html.escape(str(value or ""), quote=False)


def column_name(index):
    result = ""

    while index > 0:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result

    return result


def build_sheet_xml(rows):
    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>',
    ]

    for row_index, row in enumerate(rows, start=1):
        parts.append(f'<row r="{row_index}">')

        for col_index, value in enumerate(row, start=1):
            if value is None:
                continue

            cell_ref = f"{column_name(col_index)}{row_index}"
            text = xml_escape(value)
            parts.append(
                f'<c r="{cell_ref}" t="inlineStr"><is><t>{text}</t></is></c>'
            )

        parts.append("</row>")

    parts.append("</sheetData></worksheet>")
    return "".join(parts).encode("utf-8")


def build_workbook_bytes(sheets):
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
              <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
              <Default Extension="xml" ContentType="application/xml"/>
              <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
              <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
              <Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
              <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
              <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
            </Types>""",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
              <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
              <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
              <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
            </Relationships>""",
        )
        archive.writestr(
            "docProps/core.xml",
            f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
                xmlns:dc="http://purl.org/dc/elements/1.1/"
                xmlns:dcterms="http://purl.org/dc/terms/"
                xmlns:dcmitype="http://purl.org/dc/dcmitype/"
                xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
              <dc:title>Газель Экспресс</dc:title>
              <dc:creator>Codex</dc:creator>
              <cp:lastModifiedBy>Codex</cp:lastModifiedBy>
              <dcterms:created xsi:type="dcterms:W3CDTF">{now_iso()}</dcterms:created>
              <dcterms:modified xsi:type="dcterms:W3CDTF">{now_iso()}</dcterms:modified>
            </cp:coreProperties>""",
        )
        archive.writestr(
            "docProps/app.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
                xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
              <Application>Газель Экспресс</Application>
            </Properties>""",
        )
        archive.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
                xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
              <sheets>
                <sheet name="Заявки" sheetId="1" r:id="rId1"/>
                <sheet name="Админы" sheetId="2" r:id="rId2"/>
              </sheets>
            </workbook>""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
              <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
              <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>
            </Relationships>""",
        )
        archive.writestr("xl/worksheets/sheet1.xml", build_sheet_xml(sheets[0]))
        archive.writestr("xl/worksheets/sheet2.xml", build_sheet_xml(sheets[1]))

    return buffer.getvalue()


def create_admin_record(connection, login, password):
    display_login = trim_value(login)
    normalized_login = normalize_login(login)
    clean_password = trim_value(password)

    if len(display_login) < 3:
        raise ValueError("Логин должен содержать минимум 3 символа.")

    if len(clean_password) < 6:
        raise ValueError("Пароль должен содержать минимум 6 символов.")

    exists = connection.execute(
        "SELECT 1 FROM admins WHERE login = ?",
        (normalized_login,),
    ).fetchone()

    if exists:
        raise ValueError("Такой аккаунт уже существует.")

    created_at = now_iso()
    connection.execute(
        """
        INSERT INTO admins (login, display_login, password_hash, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (normalized_login, display_login, sha256_hash(clean_password), created_at),
    )


PAGE_ALIASES = {
    "/": "/index.html",
    "/about": "/about.html",
    "/contacts": "/contacts.html",
    "/admin": "/admin.html",
}


def normalize_public_path(path):
    path = unquote(path or "/")

    if not path.startswith("/"):
        path = f"/{path}"

    if path != "/" and path.endswith("/"):
        path = path.rstrip("/") or "/"

    if path in PAGE_ALIASES:
        return PAGE_ALIASES[path]

    if path.startswith("/api/"):
        return path

    if Path(path).name and "." not in Path(path).name:
        candidate = f"{path}.html"
        if (BASE_DIR / candidate.lstrip("/")).is_file():
            return candidate

    return path


class AppHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def list_directory(self, path):
        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
        return None

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/bootstrap":
            self.handle_bootstrap()
            return

        if path == "/api/orders":
            self.handle_get_orders()
            return

        if path == "/api/admins":
            self.handle_get_admins()
            return

        if path == "/api/auth/me":
            self.handle_auth_me()
            return

        if path == "/api/export/orders.xlsx":
            self.handle_export_excel()
            return

        if path.startswith("/api/"):
            self.send_json({"message": "Маршрут не найден."}, HTTPStatus.NOT_FOUND)
            return

        if path == "/favicon.ico":
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()
            return

        path = normalize_public_path(path)
        self.path = f"{path}?{parsed.query}" if parsed.query else path
        super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/api/orders":
            self.handle_create_order()
            return

        if path == "/api/auth/login":
            self.handle_login()
            return

        if path == "/api/auth/logout":
            self.handle_logout()
            return

        if path == "/api/admins":
            self.handle_create_admin()
            return

        if path == "/api/migrate-legacy":
            self.handle_migrate_legacy()
            return

        self.send_json({"message": "Маршрут не найден."}, HTTPStatus.NOT_FOUND)

    def do_PATCH(self):
        path = urlparse(self.path).path

        if path == "/api/admins/password":
            self.handle_change_password()
            return

        if path.startswith("/api/orders/") and path.endswith("/status"):
            parts = path.strip("/").split("/")

            if len(parts) == 4:
                self.handle_update_order_status(unquote(parts[2]))
                return

        self.send_json({"message": "Маршрут не найден."}, HTTPStatus.NOT_FOUND)

    def do_DELETE(self):
        path = urlparse(self.path).path

        if path.startswith("/api/admins/"):
            login = unquote(path.rsplit("/", 1)[-1])
            self.handle_delete_admin(login)
            return

        self.send_json({"message": "Маршрут не найден."}, HTTPStatus.NOT_FOUND)

    def parse_body(self):
        length = int(self.headers.get("Content-Length", "0"))

        if length <= 0:
            return {}

        raw = self.rfile.read(length).decode("utf-8")

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            self.send_json({"message": "Неверный формат JSON."}, HTTPStatus.BAD_REQUEST)
            return None

    def send_json(self, payload, status=HTTPStatus.OK, extra_headers=None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))

        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)

        self.end_headers()
        self.wfile.write(body)

    def parse_cookies(self):
        cookie = SimpleCookie()
        cookie.load(self.headers.get("Cookie", ""))
        return cookie

    def build_cookie_header(self, token="", expires=""):
        cookie = SimpleCookie()
        cookie[SESSION_COOKIE] = token
        cookie[SESSION_COOKIE]["path"] = "/"
        cookie[SESSION_COOKIE]["httponly"] = True
        cookie[SESSION_COOKIE]["samesite"] = "Lax"

        if expires:
            cookie[SESSION_COOKIE]["expires"] = expires

        return cookie.output(header="").strip()

    def get_session_admin(self, connection):
        cookies = self.parse_cookies()
        morsel = cookies.get(SESSION_COOKIE)

        if not morsel:
            return None

        token = morsel.value

        return connection.execute(
            """
            SELECT admins.login, admins.display_login, admins.created_at, admins.updated_at
            FROM sessions
            JOIN admins ON admins.login = sessions.admin_login
            WHERE sessions.token = ?
            """,
            (token,),
        ).fetchone()

    def require_admin(self, connection):
        admin = self.get_session_admin(connection)

        if not admin:
            self.send_json({"message": "Нужен вход в админ-панель."}, HTTPStatus.UNAUTHORIZED)
            return None

        return admin

    def handle_bootstrap(self):
        with db_session() as connection:
            admins_count = connection.execute("SELECT COUNT(*) AS count FROM admins").fetchone()["count"]
            orders_count = connection.execute("SELECT COUNT(*) AS count FROM orders").fetchone()["count"]
            current_admin = self.get_session_admin(connection)

        self.send_json(
            {
                "hasAdmins": admins_count > 0,
                "orderCount": orders_count,
                "currentAdmin": serialize_admin(current_admin),
            }
        )

    def handle_auth_me(self):
        with db_session() as connection:
            admin = self.require_admin(connection)

            if not admin:
                return

        self.send_json({"admin": serialize_admin(admin)})

    def handle_login(self):
        payload = self.parse_body()

        if payload is None:
            return

        login = normalize_login(payload.get("login"))
        password = trim_value(payload.get("password"))

        if not login or not password:
            self.send_json({"message": "Заполните логин и пароль."}, HTTPStatus.BAD_REQUEST)
            return

        with db_session() as connection:
            admin = connection.execute(
                "SELECT * FROM admins WHERE login = ?",
                (login,),
            ).fetchone()

            if not admin or not verify_password(password, admin["password_hash"]):
                self.send_json({"message": "Неверный логин или пароль."}, HTTPStatus.UNAUTHORIZED)
                return

            token = secrets.token_urlsafe(32)
            connection.execute("DELETE FROM sessions WHERE admin_login = ?", (login,))
            connection.execute(
                "INSERT INTO sessions (token, admin_login, created_at) VALUES (?, ?, ?)",
                (token, login, now_iso()),
            )

        self.send_json(
            {"admin": serialize_admin(admin)},
            extra_headers={"Set-Cookie": self.build_cookie_header(token=token)},
        )

    def handle_logout(self):
        with db_session() as connection:
            cookies = self.parse_cookies()
            morsel = cookies.get(SESSION_COOKIE)

            if morsel:
                connection.execute("DELETE FROM sessions WHERE token = ?", (morsel.value,))

        self.send_json(
            {"ok": True},
            extra_headers={
                "Set-Cookie": self.build_cookie_header(token="", expires="Thu, 01 Jan 1970 00:00:00 GMT")
            },
        )

    def handle_create_order(self):
        payload = self.parse_body()

        if payload is None:
            return

        customer = trim_value(payload.get("customer"))
        phone = trim_value(payload.get("phone"))
        truck_type = trim_value(payload.get("truckType"))
        date_time = trim_value(payload.get("dateTime"))
        cargo = trim_value(payload.get("cargo"))

        if not all([customer, phone, truck_type, cargo]):
            self.send_json({"message": "Заполните обязательные поля заявки."}, HTTPStatus.BAD_REQUEST)
            return

        order_id = payload.get("id") or f"order-{uuid.uuid4().hex[:12]}"
        created_at = now_iso()

        with db_session() as connection:
            connection.execute(
                """
                INSERT INTO orders (id, customer, phone, truck_type, date_time, cargo, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (order_id, customer, phone, truck_type, date_time, cargo, ORDER_STATUS_NEW, created_at),
            )

            order = connection.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()

        self.send_json({"order": serialize_order(order)}, HTTPStatus.CREATED)

    def handle_get_orders(self):
        with db_session() as connection:
            admin = self.require_admin(connection)

            if not admin:
                return

            rows = connection.execute(
                "SELECT * FROM orders ORDER BY datetime(created_at) DESC, created_at DESC"
            ).fetchall()

        self.send_json({"orders": [serialize_order(row) for row in rows]})

    def handle_update_order_status(self, order_id):
        payload = self.parse_body()

        if payload is None:
            return

        status = normalize_order_status(payload.get("status"))

        if not status:
            self.send_json({"message": "Передан неверный статус заявки."}, HTTPStatus.BAD_REQUEST)
            return

        with db_session() as connection:
            admin = self.require_admin(connection)

            if not admin:
                return

            cursor = connection.execute(
                "UPDATE orders SET status = ? WHERE id = ?",
                (status, trim_value(order_id)),
            )

            if cursor.rowcount == 0:
                self.send_json({"message": "Заявка не найдена."}, HTTPStatus.NOT_FOUND)
                return

            order = connection.execute(
                "SELECT * FROM orders WHERE id = ?",
                (trim_value(order_id),),
            ).fetchone()

        self.send_json({"order": serialize_order(order)})

    def handle_get_admins(self):
        with db_session() as connection:
            admin = self.require_admin(connection)

            if not admin:
                return

            rows = connection.execute(
                "SELECT login, display_login, created_at, updated_at FROM admins ORDER BY datetime(created_at), created_at"
            ).fetchall()

        self.send_json({"admins": [serialize_admin(row) for row in rows]})

    def handle_create_admin(self):
        payload = self.parse_body()

        if payload is None:
            return

        with db_session() as connection:
            admin = self.require_admin(connection)

            if not admin:
                return

            try:
                create_admin_record(connection, payload.get("login"), payload.get("password"))
                row = connection.execute(
                    "SELECT login, display_login, created_at, updated_at FROM admins WHERE login = ?",
                    (normalize_login(payload.get("login")),),
                ).fetchone()
            except ValueError as error:
                self.send_json({"message": str(error)}, HTTPStatus.BAD_REQUEST)
                return

        self.send_json({"admin": serialize_admin(row)}, HTTPStatus.CREATED)

    def handle_change_password(self):
        payload = self.parse_body()

        if payload is None:
            return

        login = normalize_login(payload.get("login"))
        password = trim_value(payload.get("password"))

        if len(password) < 6:
            self.send_json({"message": "Новый пароль должен содержать минимум 6 символов."}, HTTPStatus.BAD_REQUEST)
            return

        with db_session() as connection:
            admin = self.require_admin(connection)

            if not admin:
                return

            updated_at = now_iso()
            cursor = connection.execute(
                "UPDATE admins SET password_hash = ?, updated_at = ? WHERE login = ?",
                (sha256_hash(password), updated_at, login),
            )

            if cursor.rowcount == 0:
                self.send_json({"message": "Аккаунт не найден."}, HTTPStatus.NOT_FOUND)
                return

        self.send_json({"ok": True})

    def handle_delete_admin(self, login):
        target_login = normalize_login(login)

        with db_session() as connection:
            admin = self.require_admin(connection)

            if not admin:
                return

            if target_login == admin["login"]:
                self.send_json(
                    {"message": "Нельзя удалить текущий аккаунт, под которым выполнен вход."},
                    HTTPStatus.BAD_REQUEST,
                )
                return

            admins_count = connection.execute("SELECT COUNT(*) AS count FROM admins").fetchone()["count"]

            if admins_count <= 1:
                self.send_json(
                    {"message": "Нельзя удалить последний аккаунт администратора."},
                    HTTPStatus.BAD_REQUEST,
                )
                return

            cursor = connection.execute("DELETE FROM admins WHERE login = ?", (target_login,))

            if cursor.rowcount == 0:
                self.send_json({"message": "Аккаунт не найден."}, HTTPStatus.NOT_FOUND)
                return

        self.send_json({"ok": True})

    def handle_migrate_legacy(self):
        payload = self.parse_body()

        if payload is None:
            return

        legacy_accounts = payload.get("accounts") or []
        legacy_orders = payload.get("orders") or []
        migrated_accounts = 0
        migrated_orders = 0

        with db_session() as connection:
            admins_count = connection.execute("SELECT COUNT(*) AS count FROM admins").fetchone()["count"]

            if admins_count == 0:
                for account in legacy_accounts:
                    login = normalize_login(account.get("login"))
                    display_login = trim_value(account.get("displayLogin") or account.get("display_login") or account.get("login"))
                    password_hash = trim_value(account.get("passwordHash"))
                    created_at = trim_value(account.get("createdAt") or account.get("created_at") or now_iso())
                    updated_at = trim_value(account.get("updatedAt") or account.get("updated_at")) or None

                    if not login or not password_hash or len(display_login) < 3:
                        continue

                    connection.execute(
                        """
                        INSERT OR IGNORE INTO admins (login, display_login, password_hash, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (login, display_login, password_hash, created_at, updated_at),
                    )

                migrated_accounts = connection.execute("SELECT COUNT(*) AS count FROM admins").fetchone()["count"]

            for order in legacy_orders:
                order_id = trim_value(order.get("id")) or f"order-{uuid.uuid4().hex[:12]}"
                customer = trim_value(order.get("customer"))
                phone = trim_value(order.get("phone"))
                truck_type = trim_value(order.get("truckType") or order.get("truck_type"))
                date_time = trim_value(order.get("dateTime") or order.get("date_time"))
                cargo = trim_value(order.get("cargo"))
                status = normalize_order_status(order.get("status"), ORDER_STATUS_NEW)
                created_at = trim_value(order.get("createdAt") or order.get("created_at") or now_iso())

                if not all([order_id, customer, phone, truck_type, cargo]):
                    continue

                connection.execute(
                    """
                    INSERT OR IGNORE INTO orders (id, customer, phone, truck_type, date_time, cargo, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (order_id, customer, phone, truck_type, date_time, cargo, status, created_at),
                )

            migrated_orders = connection.execute("SELECT COUNT(*) AS count FROM orders").fetchone()["count"]

        self.send_json(
            {
                "ok": True,
                "migratedAccounts": migrated_accounts,
                "migratedOrders": migrated_orders,
            }
        )

    def handle_export_excel(self):
        with db_session() as connection:
            admin = self.require_admin(connection)

            if not admin:
                return

            orders = connection.execute(
                "SELECT * FROM orders ORDER BY datetime(created_at) DESC, created_at DESC"
            ).fetchall()
            admins = connection.execute(
                "SELECT login, display_login, created_at, updated_at FROM admins ORDER BY datetime(created_at), created_at"
            ).fetchall()

        orders_sheet = [
            ["ID", "Создана", "Заказчик", "Телефон", "Машина", "Дата подачи", "Груз", "Статус"],
        ]
        admins_sheet = [
            ["Логин", "Отображаемое имя", "Создан", "Изменён"],
        ]

        for row in orders:
            orders_sheet.append(
                [
                    row["id"],
                    row["created_at"],
                    row["customer"],
                    row["phone"],
                    row["truck_type"],
                    row["date_time"],
                    row["cargo"],
                    order_status_label(row["status"]),
                ]
            )

        for row in admins:
            admins_sheet.append(
                [
                    row["login"],
                    row["display_login"],
                    row["created_at"],
                    row["updated_at"] or "",
                ]
            )

        workbook = build_workbook_bytes([orders_sheet, admins_sheet])
        filename = f"gazel-express-export-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx"

        self.send_response(HTTPStatus.OK)
        self.send_header(
            "Content-Type",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.send_header("Content-Length", str(len(workbook)))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(workbook)


def main():
    parser = argparse.ArgumentParser(description="Газель Экспресс: локальный сервер с SQLite")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    parser.add_argument("--init-db", action="store_true")
    parser.add_argument("--create-admin", nargs=2, metavar=("LOGIN", "PASSWORD"))
    args = parser.parse_args()

    init_db()

    if args.create_admin:
        login, password = args.create_admin

        with db_session() as connection:
            try:
                create_admin_record(connection, login, password)
            except ValueError as error:
                print(error)
                return

        print(f"Создан администратор: {login}")
        return

    if args.init_db:
        print(DB_PATH)
        return

    server = ThreadingHTTPServer((args.host, args.port), AppHandler)
    print(f"Server started on http://{args.host}:{args.port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
