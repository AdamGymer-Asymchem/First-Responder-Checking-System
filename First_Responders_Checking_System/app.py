from __future__ import annotations
import csv
import os
import secrets

import sqlite3
from contextlib import closing
from datetime import datetime
from io import StringIO
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, flash, g, make_response, redirect, render_template, request, session, url_for


BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"


def load_env_file(path: Path = ENV_PATH) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def resolve_path(value: str | None, default: Path) -> Path:
    if not value:
        return default

    path = Path(value).expanduser()
    if not path.is_absolute():
        path = BASE_DIR / path
    return path.resolve()


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


load_env_file()

DEFAULT_DATABASE_PATH = BASE_DIR / "data" / "checkin.db"
DATABASE_PATH = resolve_path(os.environ.get("FIRST_RESPONDERS_DATABASE"), DEFAULT_DATABASE_PATH)
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
APP_TIMEZONE = ZoneInfo(os.environ.get("FIRST_RESPONDERS_TIMEZONE", "Europe/London"))
APP_HOST = os.environ.get("FIRST_RESPONDERS_HOST", "127.0.0.1")
APP_PORT = int(os.environ.get("FIRST_RESPONDERS_PORT", "17000"))
APP_DEBUG = env_bool("FIRST_RESPONDERS_DEBUG", True)


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FIRST_RESPONDERS_SECRET_KEY") or secrets.token_hex(32)
app.config["DATABASE"] = DATABASE_PATH
app.config["ADMIN_PASSWORD"] = os.environ.get("FIRST_RESPONDERS_ADMIN_PASSWORD", "SafetyFirst")


def connect_db() -> sqlite3.Connection:
    connection = sqlite3.connect(app.config["DATABASE"])
    connection.row_factory = sqlite3.Row
    # Avoid file-backed journal files in a synced directory for this prototype.
    connection.execute("PRAGMA journal_mode=MEMORY")
    connection.execute("PRAGMA synchronous=NORMAL")
    return connection


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = connect_db()
    return g.db


@app.teardown_appcontext
def close_db(_exception: BaseException | None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    schema = """
    CREATE TABLE IF NOT EXISTS people (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        radio_number TEXT NOT NULL UNIQUE,
        is_on_site INTEGER NOT NULL DEFAULT 0,
        last_action_at TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS check_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        person_id INTEGER NOT NULL,
        event_type TEXT NOT NULL,
        event_time TEXT NOT NULL,
        event_date TEXT NOT NULL,
        comments TEXT,
        FOREIGN KEY (person_id) REFERENCES people (id)
    );

    CREATE TABLE IF NOT EXISTS app_state (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """
    with closing(connect_db()) as connection:
        connection.executescript(schema)
        connection.commit()


def current_time() -> datetime:
    return datetime.now(APP_TIMEZONE)


def current_date_iso() -> str:
    return current_time().date().isoformat()


def is_person_effectively_on_site(person: sqlite3.Row | dict) -> bool:
    if not person["is_on_site"]:
        return False

    last_action_at = person["last_action_at"]
    if not last_action_at:
        return False

    try:
        action_date = datetime.fromisoformat(last_action_at).date().isoformat()
    except ValueError:
        return False

    return action_date == current_date_iso()


def get_state(key: str) -> str | None:
    row = get_db().execute(
        "SELECT value FROM app_state WHERE key = ?",
        (key,),
    ).fetchone()
    return row["value"] if row else None


def set_state(key: str, value: str) -> None:
    get_db().execute(
        """
        INSERT INTO app_state (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )


def ensure_daily_reset() -> None:
    now = current_time()
    today = current_date_iso()
    last_reset = get_state("last_reset_date")
    if last_reset == today:
        return

    db = get_db()
    active_people = db.execute(
        "SELECT id FROM people WHERE is_on_site = 1"
    ).fetchall()

    for row in active_people:
        db.execute(
            """
            INSERT INTO check_events (person_id, event_type, event_time, event_date, comments)
            VALUES (?, 'auto_reset', ?, ?, ?)
            """,
            (
                row["id"],
                now.isoformat(timespec="seconds"),
                today,
                "Automatic midnight reset cleared previous on-site status.",
            ),
        )

    db.execute(
        """
        UPDATE people
        SET is_on_site = 0,
            last_action_at = ?
        WHERE is_on_site = 1
        """,
        (now.isoformat(timespec="seconds"),),
    )
    set_state("last_reset_date", today)
    db.commit()


@app.before_request
def prepare_request() -> None:
    init_db()
    ensure_daily_reset()


def is_admin_authenticated() -> bool:
    return bool(session.get("is_admin"))


def require_admin():
    if is_admin_authenticated():
        return None
    flash("Admin access required.")
    return redirect(url_for("admin_login"))


@app.route("/")
def index():
    db = get_db()
    people = db.execute(
        """
        SELECT id, name, radio_number, is_on_site, last_action_at
        FROM people
        ORDER BY LOWER(name), LOWER(radio_number)
        """
    ).fetchall()
    decorated_people = []
    for person in people:
        person_data = dict(person)
        person_data["effective_on_site"] = is_person_effectively_on_site(person)
        decorated_people.append(person_data)

    on_site_count = sum(person["effective_on_site"] for person in decorated_people)
    signed_in_people = [person for person in decorated_people if person["effective_on_site"]]

    return render_template(
        "index.html",
        now=current_time(),
        people=decorated_people,
        on_site_count=on_site_count,
        signed_in_people=signed_in_people,
        current_date=current_date_iso(),
    )


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == app.config["ADMIN_PASSWORD"]:
            session["is_admin"] = True
            return redirect(url_for("admin"))
        flash("Incorrect password.")
        return redirect(url_for("admin_login"))

    return render_template("admin_login.html")


@app.post("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    flash("Signed out of admin.")
    return redirect(url_for("index"))


@app.route("/admin")
def admin():
    guard = require_admin()
    if guard is not None:
        return guard

    db = get_db()
    people = db.execute(
        """
        SELECT id, name, radio_number, is_on_site, last_action_at
        FROM people
        ORDER BY LOWER(name), LOWER(radio_number)
        """
    ).fetchall()
    recent_events = db.execute(
        """
        SELECT e.event_type, e.event_time, e.comments, p.name, p.radio_number
        FROM check_events e
        JOIN people p ON p.id = e.person_id
        ORDER BY e.event_time DESC
        LIMIT 15
        """
    ).fetchall()
    decorated_people = []
    for person in people:
        person_data = dict(person)
        person_data["effective_on_site"] = is_person_effectively_on_site(person)
        decorated_people.append(person_data)

    return render_template(
        "admin.html",
        now=current_time(),
        people=decorated_people,
        recent_events=recent_events,
        database_path=DATABASE_PATH,
        current_date=current_date_iso(),
    )


@app.post("/people")
def create_person():
    guard = require_admin()
    if guard is not None:
        return guard

    name = request.form.get("name", "").strip()
    radio_number = request.form.get("radio_number", "").strip()

    if not name or not radio_number:
        flash("Name and radio number are required.")
        return redirect(url_for("index"))

    try:
        get_db().execute(
            """
            INSERT INTO people (name, radio_number, created_at)
            VALUES (?, ?, ?)
            """,
            (name, radio_number, current_time().isoformat(timespec="seconds")),
        )
        get_db().commit()
        flash(f"Added {name}.")
    except sqlite3.IntegrityError:
        flash("That radio number is already registered.")

    return redirect(url_for("admin"))


@app.post("/people/<int:person_id>/delete")
def delete_person(person_id: int):
    guard = require_admin()
    if guard is not None:
        return guard

    db = get_db()
    person = db.execute(
        "SELECT id, name FROM people WHERE id = ?",
        (person_id,),
    ).fetchone()

    if person is None:
        flash("Person not found.")
        return redirect(url_for("admin"))

    db.execute("DELETE FROM check_events WHERE person_id = ?", (person_id,))
    db.execute("DELETE FROM people WHERE id = ?", (person_id,))
    db.commit()

    flash(f"Deleted {person['name']}.")
    return redirect(url_for("admin"))


@app.post("/people/<int:person_id>/action")
def record_action(person_id: int):
    action = request.form.get("action", "").strip()
    comments = request.form.get("comments", "").strip() or None

    if action not in {"check_in", "check_out"}:
        flash("Invalid action.")
        return redirect(url_for("index"))

    db = get_db()
    person = db.execute(
        "SELECT id, is_on_site, name FROM people WHERE id = ?",
        (person_id,),
    ).fetchone()

    if person is None:
        flash("Person not found.")
        return redirect(url_for("index"))

    desired_status = 1 if action == "check_in" else 0
    now = current_time().isoformat(timespec="seconds")
    today = current_date_iso()

    db.execute(
        """
        UPDATE people
        SET is_on_site = ?, last_action_at = ?
        WHERE id = ?
        """,
        (desired_status, now, person_id),
    )
    db.execute(
        """
        INSERT INTO check_events (person_id, event_type, event_time, event_date, comments)
        VALUES (?, ?, ?, ?, ?)
        """,
        (person_id, action, now, today, comments),
    )
    db.commit()

    action_label = "checked in" if action == "check_in" else "checked out"
    flash(f"{person['name']} {action_label}.")
    return redirect(url_for("index"))


@app.route("/history")
def history():
    guard = require_admin()
    if guard is not None:
        return guard

    rows = get_db().execute(
        """
        SELECT e.event_type, e.event_time, e.event_date, e.comments, p.name, p.radio_number
        FROM check_events e
        JOIN people p ON p.id = e.person_id
        ORDER BY e.event_time DESC
        LIMIT 500
        """
    ).fetchall()
    return render_template("history.html", events=rows)


@app.route("/history/export.csv")
def export_history_csv():
    guard = require_admin()
    if guard is not None:
        return guard

    rows = get_db().execute(
        """
        SELECT e.event_time, e.event_date, p.name, p.radio_number, e.event_type, e.comments
        FROM check_events e
        JOIN people p ON p.id = e.person_id
        ORDER BY e.event_time DESC
        """
    ).fetchall()

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["event_time", "event_date", "name", "radio_number", "event_type", "comments"])
    for row in rows:
        writer.writerow(
            [
                row["event_time"],
                row["event_date"],
                row["name"],
                row["radio_number"],
                row["event_type"],
                row["comments"] or "",
            ]
        )

    response = make_response(buffer.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = (
        f"attachment; filename=history-export-{current_time().date().isoformat()}.csv"
    )
    return response


if __name__ == "__main__":
    init_db()
    app.run(host=APP_HOST, port=APP_PORT, debug=APP_DEBUG)
