"""Create the residential catalog and apartment lots."""
from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "residential_complexes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("developer", sa.String(255), nullable=False),
        sa.Column("district", sa.String(255), nullable=False),
        sa.Column("housing_class", sa.String(32), nullable=False),
        sa.Column("min_price_m2", sa.Integer(), nullable=True),
        sa.Column("price_source_url", sa.Text(), nullable=True),
        sa.Column("price_observed_on", sa.Date(), nullable=True),
        sa.Column("price_checked_on", sa.Date(), nullable=True),
        sa.Column("completion_status", sa.String(32), nullable=False),
        sa.Column("completion_description", sa.Text(), nullable=False),
        sa.Column("completion_source_url", sa.Text(), nullable=False),
        sa.Column("completion_checked_on", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("min_price_m2 IS NULL OR (typeof(min_price_m2) = 'integer' AND min_price_m2 BETWEEN 1 AND 99999999999999)", name="ck_complex_price"),
        sa.CheckConstraint("completion_status IN ('completed','under_construction','mixed','needs_verification')", name="ck_completion_status"),
    )
    op.create_index("ix_complex_city_price", "residential_complexes", ["city","min_price_m2"])
    op.create_table(
        "apartment_lots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("complex_id", sa.Integer(), sa.ForeignKey("residential_complexes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("external_id", sa.String(150), nullable=False),
        sa.Column("rooms", sa.Integer(), nullable=False),
        sa.Column("area_m2", sa.Integer(), nullable=False),
        sa.Column("starting_price_rub", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("building", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("imported_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("complex_id", "external_id", name="uq_lot_external"),
        sa.CheckConstraint("rooms BETWEEN 0 AND 20", name="ck_lot_rooms"),
        sa.CheckConstraint("typeof(area_m2) = 'integer' AND area_m2 BETWEEN 1 AND 99999999", name="ck_lot_area"),
        sa.CheckConstraint("typeof(starting_price_rub) = 'integer' AND starting_price_rub BETWEEN 1 AND 9999999999999999", name="ck_lot_price"),
    )
    op.create_index("ix_lot_search","apartment_lots",["complex_id","is_active","is_demo","area_m2","starting_price_rub"])


def downgrade():
    op.drop_table("apartment_lots")
    op.drop_table("residential_complexes")
