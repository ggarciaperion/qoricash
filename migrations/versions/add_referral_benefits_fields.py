"""add_referral_benefits_fields

Agrega campos para sistema de beneficios por referidos:
- referral_pips_earned: Total de pips ganados por referidos
- referral_pips_available: Pips disponibles para usar
- referral_completed_uses: Cantidad de usos válidos (operaciones completadas)

Revision ID: ref_benefits_001
Revises: j2k3l4m5n6o7
Create Date: 2026-01-20 19:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ref_benefits_001'
down_revision = 'j2k3l4m5n6o7'
branch_labels = None
depends_on = None


def upgrade():
    # Agregar columnas para beneficios por referidos
    op.add_column('clients', sa.Column('referral_pips_earned', sa.Float(), nullable=True))
    op.add_column('clients', sa.Column('referral_pips_available', sa.Float(), nullable=True))
    op.add_column('clients', sa.Column('referral_completed_uses', sa.Integer(), nullable=True))

    # Establecer valores por defecto para registros existentes
    op.execute("UPDATE clients SET referral_pips_earned = 0.0 WHERE referral_pips_earned IS NULL")
    op.execute("UPDATE clients SET referral_pips_available = 0.0 WHERE referral_pips_available IS NULL")
    op.execute("UPDATE clients SET referral_completed_uses = 0 WHERE referral_completed_uses IS NULL")

    # Hacer las columnas NOT NULL después de establecer los defaults
    op.alter_column('clients', 'referral_pips_earned', nullable=False)
    op.alter_column('clients', 'referral_pips_available', nullable=False)
    op.alter_column('clients', 'referral_completed_uses', nullable=False)


def downgrade():
    # Eliminar columnas en caso de rollback
    op.drop_column('clients', 'referral_completed_uses')
    op.drop_column('clients', 'referral_pips_available')
    op.drop_column('clients', 'referral_pips_earned')
