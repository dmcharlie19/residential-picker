"""Environment configuration shared by HTTP and import commands."""
import os
from dataclasses import dataclass
from decimal import Decimal
from sqlalchemy.engine import make_url


@dataclass
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "mysql+pymysql://picker@127.0.0.1:13306/residential_picker")
    demo_mode: bool = os.getenv("DEMO_MODE", "false").lower() in ("true", "1")
    area_tolerance_ratio: Decimal = Decimal(os.getenv("AREA_TOLERANCE_RATIO", "0.10"))
    price_max_age_days: int = int(os.getenv("PRICE_MAX_AGE_DAYS", "30"))

    def __post_init__(self):
        url = make_url(self.database_url)
        if url.drivername != "mysql+pymysql":
            raise ValueError("DATABASE_URL must use mysql+pymysql")
        demo_databases = {"residential_picker_demo", "residential_picker_test_demo"}
        if self.demo_mode != (url.database in demo_databases):
            raise ValueError("DEMO_MODE and the database name must agree; use a separate demo database")
        if not self.area_tolerance_ratio.is_finite() or not Decimal("0") <= self.area_tolerance_ratio <= Decimal("1"):
            raise ValueError("AREA_TOLERANCE_RATIO must be between 0 and 1")
        if not 1 <= self.price_max_age_days <= 365:
            raise ValueError("PRICE_MAX_AGE_DAYS must be between 1 and 365")


settings = Settings()
