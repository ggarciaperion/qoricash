"""Add content_batches and content_proposals tables

Revision ID: c1o2n3t4e5n6
Revises: 34bb9704ef8c, f7a8b9c0d1e2, w2a3m4s5g6c7
Create Date: 2026-10-24

Merges current three heads and adds content module tables.
"""
from alembic import op
import sqlalchemy as sa

revision = 'c1o2n3t4e5n6'
down_revision = ('34bb9704ef8c', 'f7a8b9c0d1e2', 'w2a3m4s5g6c7')
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'content_batches',
        sa.Column('id',            sa.Integer(),    nullable=False),
        sa.Column('created_at',    sa.DateTime(),   nullable=True),
        sa.Column('created_by',    sa.Integer(),    sa.ForeignKey('users.id'), nullable=True),
        sa.Column('count',         sa.Integer(),    nullable=True, default=0),
        sa.Column('model_used',    sa.String(80),   nullable=True),
        sa.Column('input_tokens',  sa.Integer(),    nullable=True, default=0),
        sa.Column('output_tokens', sa.Integer(),    nullable=True, default=0),
        sa.Column('notes',         sa.Text(),       nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'content_proposals',
        sa.Column('id',               sa.Integer(),    nullable=False),
        sa.Column('batch_id',         sa.Integer(),    sa.ForeignKey('content_batches.id'), nullable=True),
        sa.Column('created_at',       sa.DateTime(),   nullable=True),
        sa.Column('updated_at',       sa.DateTime(),   nullable=True),
        # Clasificación
        sa.Column('network',          sa.String(30),   nullable=False),
        sa.Column('topic',            sa.String(200),  nullable=True),
        sa.Column('objective',        sa.String(200),  nullable=True),
        sa.Column('audience',         sa.String(200),  nullable=True),
        sa.Column('tag',              sa.String(60),   nullable=True),
        # Contenido
        sa.Column('text_body',        sa.Text(),       nullable=True),
        sa.Column('visual_idea',      sa.Text(),       nullable=True),
        sa.Column('cta',              sa.String(300),  nullable=True),
        sa.Column('hashtags',         sa.String(500),  nullable=True),
        sa.Column('sources',          sa.Text(),       nullable=True),
        # Video
        sa.Column('script_scenes',    sa.Text(),       nullable=True),
        sa.Column('flow_prompt',      sa.Text(),       nullable=True),
        # Imagen
        sa.Column('image_path',       sa.String(500),  nullable=True),
        sa.Column('image_format',     sa.String(20),   nullable=True),
        # Estado
        sa.Column('status',           sa.String(30),   nullable=True, default='borrador'),
        sa.Column('rejection_reason', sa.Text(),       nullable=True),
        sa.Column('scheduled_at',     sa.DateTime(),   nullable=True),
        sa.Column('platform_id',      sa.String(200),  nullable=True),
        sa.Column('published_url',    sa.String(500),  nullable=True),
        sa.Column('published_at',     sa.DateTime(),   nullable=True),
        # Ediciones
        sa.Column('user_edits',           sa.Text(), nullable=True),
        sa.Column('adjustment_request',   sa.Text(), nullable=True),
        sa.Column('adjustment_result',    sa.Text(), nullable=True),
        sa.Column('error_msg',            sa.Text(), nullable=True),
        sa.Column('is_demo',          sa.Boolean(),    nullable=True, default=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('content_proposals')
    op.drop_table('content_batches')
