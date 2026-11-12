"""SQLite connections and exact fixed-point arithmetic."""
from pathlib import Path
from decimal import Decimal
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url

def decimal_cents(rubles):
    return None if rubles is None else int(Decimal(str(rubles)) * 100)

def estimate_cents(price_rubles, area_hundredths):
    price_cents = decimal_cents(price_rubles)
    if price_cents is None:
        return None
    # Positive integers: ROUND_HALF_UP without floating point or overflow.
    return min((price_cents * area_hundredths + 50) // 100, 9223372036854775807)

def make_engine(url):
    parsed = make_url(url)
    if parsed.drivername not in {"sqlite", "sqlite+pysqlite"} or not parsed.database or parsed.database == ":memory:" or parsed.query:
        raise ValueError("A file-backed SQLite database is required")
    Path(parsed.database).resolve().parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 15}, pool_pre_ping=True)

    @event.listens_for(engine, "connect")
    def configure(connection, record):
        connection.isolation_level = None
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=15000")
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.create_function("decimal_cents", 1, decimal_cents, deterministic=True)
        connection.create_function("estimate_cents", 2, estimate_cents, deterministic=True)
    @event.listens_for(engine, "begin")
    def begin(connection):
        connection.exec_driver_sql("BEGIN")
    return engine
