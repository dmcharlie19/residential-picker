from alembic import context
from app.sqlite import make_engine
from app.config import settings
from app.models import Base

config = context.config
target_metadata = Base.metadata


def run():
    if context.is_offline_mode():
        context.configure(url=settings.database_url, target_metadata=target_metadata, literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
    else:
        engine = make_engine(settings.database_url)
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
            with context.begin_transaction():
                context.run_migrations()
        engine.dispose()


run()
