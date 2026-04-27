from __future__ import annotations

import os
import secrets
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
LAUNCHER_URL_PATH = BASE_DIR / "desktop_launcher" / "launcher-url.txt"


def read_existing_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if not ENV_PATH.exists():
        return values

    for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def prompt(label: str, default: str) -> str:
    shown_default = f" [{default}]" if default else ""
    value = input(f"{label}{shown_default}: ").strip()
    return value or default


def prompt_port(default: str) -> str:
    while True:
        value = prompt("Server port", default)
        try:
            port = int(value)
        except ValueError:
            print("Enter a number between 1 and 65535.")
            continue
        if 1 <= port <= 65535:
            return str(port)
        print("Enter a number between 1 and 65535.")


def prompt_timezone(default: str) -> str:
    while True:
        value = prompt("Timezone", default)
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError:
            print("Enter a valid timezone, for example Europe/London.")
            continue
        return value


def prompt_bool(label: str, default: bool) -> str:
    default_text = "yes" if default else "no"
    while True:
        value = prompt(label, default_text).lower()
        if value in {"y", "yes", "true", "1", "on"}:
            return "true"
        if value in {"n", "no", "false", "0", "off"}:
            return "false"
        print("Enter yes or no.")


def resolve_database_path(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = BASE_DIR / path
    return path.resolve()


def write_env(values: dict[str, str]) -> None:
    lines = [
        "# First Responders Checking System deployment settings",
        "# Created by deploy_config.py. Keep this file private on the server.",
        f"FIRST_RESPONDERS_DATABASE={values['FIRST_RESPONDERS_DATABASE']}",
        f"FIRST_RESPONDERS_HOST={values['FIRST_RESPONDERS_HOST']}",
        f"FIRST_RESPONDERS_PORT={values['FIRST_RESPONDERS_PORT']}",
        f"FIRST_RESPONDERS_TIMEZONE={values['FIRST_RESPONDERS_TIMEZONE']}",
        f"FIRST_RESPONDERS_ADMIN_PASSWORD={values['FIRST_RESPONDERS_ADMIN_PASSWORD']}",
        f"FIRST_RESPONDERS_SECRET_KEY={values['FIRST_RESPONDERS_SECRET_KEY']}",
        f"FIRST_RESPONDERS_DEBUG={values['FIRST_RESPONDERS_DEBUG']}",
        "",
    ]
    ENV_PATH.write_text("\n".join(lines), encoding="utf-8")


def configure_launcher(values: dict[str, str]) -> None:
    server_name = os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "127.0.0.1"
    default_url = f"http://{server_name}:{values['FIRST_RESPONDERS_PORT']}"
    current_url = ""
    if LAUNCHER_URL_PATH.exists():
        current_url = LAUNCHER_URL_PATH.read_text(encoding="utf-8").strip()

    launcher_url = prompt("Launcher URL", current_url or default_url)
    LAUNCHER_URL_PATH.write_text(launcher_url + "\n", encoding="utf-8")


def initialize_database() -> None:
    import app

    app.init_db()


def main() -> None:
    existing = read_existing_env()
    print("First Responders Checking System deployment setup")
    print("Press Enter to accept the default shown in brackets.")
    print()

    default_db = existing.get("FIRST_RESPONDERS_DATABASE", str(BASE_DIR / "data" / "checkin.db"))
    database_path = resolve_database_path(prompt("SQLite database path", default_db))

    values = {
        "FIRST_RESPONDERS_DATABASE": str(database_path),
        "FIRST_RESPONDERS_HOST": prompt("Server host", existing.get("FIRST_RESPONDERS_HOST", "0.0.0.0")),
        "FIRST_RESPONDERS_PORT": prompt_port(existing.get("FIRST_RESPONDERS_PORT", "17000")),
        "FIRST_RESPONDERS_TIMEZONE": prompt_timezone(
            existing.get("FIRST_RESPONDERS_TIMEZONE", "Europe/London")
        ),
        "FIRST_RESPONDERS_ADMIN_PASSWORD": prompt(
            "Admin password", existing.get("FIRST_RESPONDERS_ADMIN_PASSWORD", "SafetyFirst")
        ),
        "FIRST_RESPONDERS_SECRET_KEY": existing.get(
            "FIRST_RESPONDERS_SECRET_KEY", secrets.token_hex(32)
        ),
        "FIRST_RESPONDERS_DEBUG": prompt_bool(
            "Enable Flask debug mode", existing.get("FIRST_RESPONDERS_DEBUG", "false").lower() == "true"
        ),
    }

    database_path.parent.mkdir(parents=True, exist_ok=True)
    write_env(values)
    configure_launcher(values)

    for key, value in values.items():
        os.environ[key] = value
    initialize_database()

    print()
    print(f"Wrote {ENV_PATH}")
    print(f"Initialized database at {database_path}")
    print(f"Updated launcher URL at {LAUNCHER_URL_PATH}")
    print(f"Run with: python app.py")


if __name__ == "__main__":
    main()
