"""add manual restrictive list fields

Revision ID: 20251212_145550
Revises:
Create Date: 2025-12-12 14:55:50

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'l4m5n6o7p8q9'
down_revision = 'k4l5m6n7o8p9'
branch_labels = None
depends_on = None


def upgrade():
    # Agregar campos para búsqueda manual a la tabla restrictive_list_checks
    op.add_column('restrictive_list_checks', sa.Column('is_manual', sa.Boolean(), nullable=True, server_default='0'))

    # Verificaciones manuales específicas - PEP
    op.add_column('restrictive_list_checks', sa.Column('pep_checked', sa.Boolean(), nullable=True, server_default='0'))
    op.add_column('restrictive_list_checks', sa.Column('pep_result', sa.String(length=50), nullable=True))
    op.add_column('restrictive_list_checks', sa.Column('pep_details', sa.Text(), nullable=True))

    # OFAC
    op.add_column('restrictive_list_checks', sa.Column('ofac_checked', sa.Boolean(), nullable=True, server_default='0'))
    op.add_column('restrictive_list_checks', sa.Column('ofac_result', sa.String(length=50), nullable=True))
    op.add_column('restrictive_list_checks', sa.Column('ofac_details', sa.Text(), nullable=True))

    # ONU
    op.add_column('restrictive_list_checks', sa.Column('onu_checked', sa.Boolean(), nullable=True, server_default='0'))
    op.add_column('restrictive_list_checks', sa.Column('onu_result', sa.String(length=50), nullable=True))
    op.add_column('restrictive_list_checks', sa.Column('onu_details', sa.Text(), nullable=True))

    # UIF
    op.add_column('restrictive_list_checks', sa.Column('uif_checked', sa.Boolean(), nullable=True, server_default='0'))
    op.add_column('restrictive_list_checks', sa.Column('uif_result', sa.String(length=50), nullable=True))
    op.add_column('restrictive_list_checks', sa.Column('uif_details', sa.Text(), nullable=True))

    # INTERPOL
    op.add_column('restrictive_list_checks', sa.Column('interpol_checked', sa.Boolean(), nullable=True, server_default='0'))
    op.add_column('restrictive_list_checks', sa.Column('interpol_result', sa.String(length=50), nullable=True))
    op.add_column('restrictive_list_checks', sa.Column('interpol_details', sa.Text(), nullable=True))

    # Denuncias
    op.add_column('restrictive_list_checks', sa.Column('denuncias_checked', sa.Boolean(), nullable=True, server_default='0'))
    op.add_column('restrictive_list_checks', sa.Column('denuncias_result', sa.String(length=50), nullable=True))
    op.add_column('restrictive_list_checks', sa.Column('denuncias_details', sa.Text(), nullable=True))

    # Otras listas
    op.add_column('restrictive_list_checks', sa.Column('otras_listas_checked', sa.Boolean(), nullable=True, server_default='0'))
    op.add_column('restrictive_list_checks', sa.Column('otras_listas_result', sa.String(length=50), nullable=True))
    op.add_column('restrictive_list_checks', sa.Column('otras_listas_details', sa.Text(), nullable=True))

    # Observaciones generales y archivos adjuntos
    op.add_column('restrictive_list_checks', sa.Column('observations', sa.Text(), nullable=True))
    op.add_column('restrictive_list_checks', sa.Column('attachments', sa.Text(), nullable=True))


def downgrade():
    # Eliminar las columnas agregadas
    op.drop_column('restrictive_list_checks', 'attachments')
    op.drop_column('restrictive_list_checks', 'observations')

    op.drop_column('restrictive_list_checks', 'otras_listas_details')
    op.drop_column('restrictive_list_checks', 'otras_listas_result')
    op.drop_column('restrictive_list_checks', 'otras_listas_checked')

    op.drop_column('restrictive_list_checks', 'denuncias_details')
    op.drop_column('restrictive_list_checks', 'denuncias_result')
    op.drop_column('restrictive_list_checks', 'denuncias_checked')

    op.drop_column('restrictive_list_checks', 'interpol_details')
    op.drop_column('restrictive_list_checks', 'interpol_result')
    op.drop_column('restrictive_list_checks', 'interpol_checked')

    op.drop_column('restrictive_list_checks', 'uif_details')
    op.drop_column('restrictive_list_checks', 'uif_result')
    op.drop_column('restrictive_list_checks', 'uif_checked')

    op.drop_column('restrictive_list_checks', 'onu_details')
    op.drop_column('restrictive_list_checks', 'onu_result')
    op.drop_column('restrictive_list_checks', 'onu_checked')

    op.drop_column('restrictive_list_checks', 'ofac_details')
    op.drop_column('restrictive_list_checks', 'ofac_result')
    op.drop_column('restrictive_list_checks', 'ofac_checked')

    op.drop_column('restrictive_list_checks', 'pep_details')
    op.drop_column('restrictive_list_checks', 'pep_result')
    op.drop_column('restrictive_list_checks', 'pep_checked')

    op.drop_column('restrictive_list_checks', 'is_manual')
