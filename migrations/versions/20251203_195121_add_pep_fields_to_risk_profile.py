"""Add PEP fields to ClientRiskProfile

Revision ID: pep_fields_20251203_195121
Revises: j2k3l4m5n6o7
Create Date: 2025-12-03 19:51:21

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'pep_fields_20251203_195121'
down_revision = 'j2k3l4m5n6o7'
branch_labels = None
depends_on = None


def upgrade():
    # Agregar columnas PEP a client_risk_profiles
    with op.batch_alter_table('client_risk_profiles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pep_type', sa.String(50), nullable=True))
        batch_op.add_column(sa.Column('pep_position', sa.String(200), nullable=True))
        batch_op.add_column(sa.Column('pep_entity', sa.String(200), nullable=True))
        batch_op.add_column(sa.Column('pep_designation_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('pep_end_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('pep_notes', sa.Text(), nullable=True))


def downgrade():
    # Eliminar columnas PEP
    with op.batch_alter_table('client_risk_profiles', schema=None) as batch_op:
        batch_op.drop_column('pep_notes')
        batch_op.drop_column('pep_end_date')
        batch_op.drop_column('pep_designation_date')
        batch_op.drop_column('pep_entity')
        batch_op.drop_column('pep_position')
        batch_op.drop_column('pep_type')
