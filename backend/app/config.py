"""File-backed SQLite configuration for HTTP and import commands."""
import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from sqlalchemy.engine import make_url

DEFAULT_DATABASE = Path(__file__).resolve().parents[2] / "data" / "residential-picker.sqlite3"

@dataclass
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///" + DEFAULT_DATABASE.as_posix())
    demo_mode: bool = os.getenv("DEMO_MODE", "false").lower() in ("true", "1")
    area_tolerance_ratio: Decimal = Decimal(os.getenv("AREA_TOLERANCE_RATIO", "0.10"))
    price_max_age_days: int = int(os.getenv("PRICE_MAX_AGE_DAYS", "30"))

    def __post_init__(self):
        url = make_url(self.database_url)
        if url.drivername not in {"sqlite", "sqlite+pysqlite"} or not url.database or url.database == ":memory:" or url.query or url.host:
            raise ValueError("DATABASE_URL must point to a SQLite file")
        is_demo_file = Path(url.database).stem.endswith("-demo")
        if self.demo_mode != is_demo_file:
            raise ValueError("DEMO_MODE requires a separate SQLite file ending in -demo.sqlite3")
        if not self.area_tolerance_ratio.is_finite() or not Decimal("0") <= self.area_tolerance_ratio <= Decimal("1"):
            raise ValueError("AREA_TOLERANCE_RATIO must be between 0 and 1")
        if not 1 <= self.price_max_age_days <= 365:
            raise ValueError("PRICE_MAX_AGE_DAYS must be between 1 and 365")

settings = Settings()
