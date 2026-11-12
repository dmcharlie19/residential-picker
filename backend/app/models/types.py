from decimal import Decimal
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

def ruble_check(column, integer_digits):
    # Canonical decimal text: SQLite REAL cannot preserve large ruble amounts to a kopeck.
    return (
        f"{column} IS NULL OR (typeof({column}) = 'text' "
        f"AND length(substr({column},1,instr({column},'.')-1)) BETWEEN 1 AND {integer_digits} "
        f"AND length({column})-instr({column},'.')=2 "
        f"AND replace({column},'.','') NOT GLOB '*[^0-9]*' "
        f"AND CAST({column} AS NUMERIC)>0)"
    )

class DecimalRubles(TypeDecorator):
    """Exact ruble values as canonical decimal text, with no unit scaling."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        number = Decimal(str(value))
        if not number.is_finite() or number * 100 != (number * 100).to_integral_value():
            raise ValueError("Expected a finite ruble amount with at most two fractional digits")
        return format(number, '.2f')

    def process_result_value(self, value, dialect):
        return None if value is None else Decimal(value)
