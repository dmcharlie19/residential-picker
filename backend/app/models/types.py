from decimal import Decimal
from sqlalchemy import Integer
from sqlalchemy.types import TypeDecorator

class ScaledDecimal(TypeDecorator):
    """Store cents / hundredths of m² as exact 64-bit SQLite integers."""
    impl = Integer
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        number = Decimal(str(value))
        scaled = number * 100
        if not number.is_finite() or scaled != scaled.to_integral_value():
            raise ValueError("Expected a finite decimal with at most two fractional digits")
        return int(scaled)

    def process_result_value(self, value, dialect):
        return None if value is None else Decimal(value) / 100
