"""Add media_local_path to wa_messages for persistent KYC document storage

Revision ID: d1o2c3s4t5r6
Revises: s1e2s3i4o5n6
Create Date: 2026-09-23

Contexto:
    El proxy /crm/api/media/<media_id> obtenía el archivo directamente de Meta
    en cada solicitud. Los media de WhatsApp tienen una vida útil limitada en
    los servidores de Meta (~30 días para mensajes recibidos). Después de ese
    período el proxy devuelve 404, haciendo irrecuperable el documento KYC.

    Esta migración añade media_local_path (VARCHAR 512) para almacenar la URL
    de Cloudinary después de que el B7 handler descarga y sube el archivo en
    background (eventlet.spawn_n → _download_wa_media_to_cloudinary).
    El proxy verifica este campo primero; si está vacío, sigue al fallback de Meta.
"""
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = 'd1o2c3s4t5r6'
down_revision = 's1e2s3i4o5n6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('wa_messages', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('media_local_path', sa.String(512), nullable=True, server_default='')
        )


def downgrade():
    with op.batch_alter_table('wa_messages', schema=None) as batch_op:
        batch_op.drop_column('media_local_path')
