"""Store areas in square metres and money in rubles rather than scaled units."""
from alembic import op
import sqlalchemy as sa

revision = '0002_explicit_units'
down_revision = '0001_initial'
branch_labels = None
depends_on = None

def ruble_check(column, digits):
    return (f"{column} IS NULL OR (typeof({column}) = 'text' "
            f"AND length(substr({column},1,instr({column},'.')-1)) BETWEEN 1 AND {digits} "
            f"AND length({column})-instr({column},'.')=2 "
            f"AND replace({column},'.','') NOT GLOB '*[^0-9]*' "
            f"AND CAST({column} AS NUMERIC)>0)")

def tables(scaled):
    money = sa.Integer if scaled else sa.Text
    price_check = "min_price_m2 IS NULL OR (typeof(min_price_m2) = 'integer' AND min_price_m2 BETWEEN 1 AND 99999999999999)" if scaled else ruble_check('min_price_m2',12)
    area_check = "typeof(area_m2) = 'integer' AND area_m2 BETWEEN 1 AND 99999999" if scaled else "typeof(area_m2) IN ('integer','real') AND area_m2 > 0 AND area_m2 <= 999999.99"
    lot_check = "typeof(starting_price_rub) = 'integer' AND starting_price_rub BETWEEN 1 AND 9999999999999999" if scaled else ruble_check('starting_price_rub',14)
    op.create_table('residential_complexes_new',
        sa.Column('id',sa.Integer(),primary_key=True),sa.Column('slug',sa.String(100),nullable=False,unique=True),
        sa.Column('city',sa.String(100),nullable=False),sa.Column('name',sa.String(200),nullable=False),
        sa.Column('developer',sa.String(255),nullable=False),sa.Column('district',sa.String(255),nullable=False),
        sa.Column('housing_class',sa.String(32),nullable=False),sa.Column('min_price_m2',money(),nullable=True),
        sa.Column('price_source_url',sa.Text(),nullable=True),sa.Column('price_observed_on',sa.Date(),nullable=True),
        sa.Column('price_checked_on',sa.Date(),nullable=True),sa.Column('completion_status',sa.String(32),nullable=False),
        sa.Column('completion_description',sa.Text(),nullable=False),sa.Column('completion_source_url',sa.Text(),nullable=False),
        sa.Column('completion_checked_on',sa.Date(),nullable=False),sa.Column('notes',sa.Text(),nullable=True),
        sa.Column('created_at',sa.DateTime(),nullable=False),sa.Column('updated_at',sa.DateTime(),nullable=False),
        sa.CheckConstraint(price_check,name='ck_complex_price'),
        sa.CheckConstraint("completion_status IN ('completed','under_construction','mixed','needs_verification')",name='ck_completion_status'))
    op.create_table('apartment_lots_new',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('complex_id',sa.Integer(),sa.ForeignKey('residential_complexes_new.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('external_id',sa.String(150),nullable=False),sa.Column('rooms',sa.Integer(),nullable=False),
        sa.Column('area_m2',sa.Integer() if scaled else sa.Numeric(8,2),nullable=False),
        sa.Column('starting_price_rub',money(),nullable=False),sa.Column('updated_at',sa.DateTime(),nullable=False),
        sa.Column('source_url',sa.Text(),nullable=True),sa.Column('building',sa.String(100),nullable=True),
        sa.Column('is_active',sa.Boolean(),nullable=False,server_default=sa.true()),
        sa.Column('is_demo',sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column('imported_at',sa.DateTime(),nullable=False),
        sa.UniqueConstraint('complex_id','external_id',name='uq_lot_external'),
        sa.CheckConstraint('rooms BETWEEN 0 AND 20',name='ck_lot_rooms'),
        sa.CheckConstraint(area_check,name='ck_lot_area'),sa.CheckConstraint(lot_check,name='ck_lot_price'))

def rebuild(scaled):
    tables(scaled)
    def money(column):
        if scaled:
            return f"CAST(replace({column},'.','') AS INTEGER)"
        # Integer division and remainder preserve even the maximum amount exactly.
        return f"CASE WHEN {column} IS NULL THEN NULL ELSE CAST({column}/100 AS TEXT) || '.' || printf('%02d',{column}%100) END"
    parent=['id','slug','city','name','developer','district','housing_class','min_price_m2','price_source_url','price_observed_on','price_checked_on','completion_status','completion_description','completion_source_url','completion_checked_on','notes','created_at','updated_at']
    child=['id','complex_id','external_id','rooms','area_m2','starting_price_rub','updated_at','source_url','building','is_active','is_demo','imported_at']
    pselect=[money(c) if c=='min_price_m2' else c for c in parent]
    area='CAST(round(area_m2*100,0) AS INTEGER)' if scaled else 'area_m2/100.0'
    lselect=[money(c) if c=='starting_price_rub' else area if c=='area_m2' else c for c in child]
    op.execute(f"INSERT INTO residential_complexes_new ({','.join(parent)}) SELECT {','.join(pselect)} FROM residential_complexes")
    op.execute(f"INSERT INTO apartment_lots_new ({','.join(child)}) SELECT {','.join(lselect)} FROM apartment_lots")
    op.drop_table('apartment_lots')
    op.drop_table('residential_complexes')
    op.rename_table('residential_complexes_new','residential_complexes')
    op.rename_table('apartment_lots_new','apartment_lots')
    op.create_index('ix_complex_city_price','residential_complexes',['city','min_price_m2'])
    op.create_index('ix_lot_search','apartment_lots',['complex_id','is_active','is_demo','area_m2','starting_price_rub'])

def upgrade():
    rebuild(False)

def downgrade():
    rebuild(True)
