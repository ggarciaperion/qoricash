"""Create Estudio Creativo pipeline tables

Revision ID: e1s2t3u4d5i6
Revises: d1a2r3i4o5d6
Create Date: 2026-10-25

Creates the four tables required by the Estudio Creativo module
that have SQLAlchemy models but no prior migration:
  - content_pipelines: workflow coordinator across agents
  - pipeline_stages:   individual agent execution stages
  - content_sources:   news/data sources gathered by Investigador
  - brand_configs:     editable brand config (verified benefits, prohibited claims)

All four are new tables that do not exist in production before this deploy.
No DB-level foreign keys are added post-creation; relationships are managed
at the ORM level (consistent with how d1a2r3i4o5d6 handled pipeline_id columns).
"""
from alembic import op
import sqlalchemy as sa

revision = 'e1s2t3u4d5i6'
down_revision = 'd1a2r3i4o5d6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'content_pipelines',
        sa.Column('id',                sa.Integer(),    nullable=False),
        sa.Column('created_at',        sa.DateTime(),   nullable=True),
        sa.Column('updated_at',        sa.DateTime(),   nullable=True),
        sa.Column('created_by',        sa.Integer(),    nullable=True),
        sa.Column('type',              sa.String(20),   nullable=False),
        sa.Column('title',             sa.String(200),  nullable=True),
        sa.Column('status',            sa.String(30),   nullable=True, server_default='running'),
        sa.Column('current_stage_seq', sa.Integer(),    nullable=True, server_default='1'),
        sa.Column('notes',             sa.Text(),       nullable=True),
        sa.Column('error_msg',         sa.Text(),       nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'pipeline_stages',
        sa.Column('id',               sa.Integer(),    nullable=False),
        sa.Column('pipeline_id',      sa.Integer(),    nullable=False),
        sa.Column('seq',              sa.Integer(),    nullable=False),
        sa.Column('agent_role',       sa.String(40),   nullable=False),
        sa.Column('status',           sa.String(30),   nullable=True, server_default='pending'),
        sa.Column('input_data',       sa.Text(),       nullable=True),
        sa.Column('output_data',      sa.Text(),       nullable=True),
        sa.Column('version',          sa.Integer(),    nullable=True, server_default='1'),
        sa.Column('started_at',       sa.DateTime(),   nullable=True),
        sa.Column('completed_at',     sa.DateTime(),   nullable=True),
        sa.Column('error_msg',        sa.Text(),       nullable=True),
        sa.Column('user_instruction', sa.Text(),       nullable=True),
        sa.Column('review_notes',     sa.Text(),       nullable=True),
        sa.Column('approved_by',      sa.Integer(),    nullable=True),
        sa.Column('approved_at',      sa.DateTime(),   nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'content_sources',
        sa.Column('id',               sa.Integer(),    nullable=False),
        sa.Column('pipeline_id',      sa.Integer(),    nullable=True),
        sa.Column('stage_id',         sa.Integer(),    nullable=True),
        sa.Column('fetched_at',       sa.DateTime(),   nullable=True),
        sa.Column('url',              sa.String(2000), nullable=True),
        sa.Column('title',            sa.String(500),  nullable=True),
        sa.Column('excerpt',          sa.Text(),       nullable=True),
        sa.Column('published_at',     sa.String(30),   nullable=True),
        sa.Column('source_name',      sa.String(200),  nullable=True),
        sa.Column('source_type',      sa.String(30),   nullable=True),
        sa.Column('is_verified',      sa.Boolean(),    nullable=True, server_default='false'),
        sa.Column('used_in_analysis', sa.Boolean(),    nullable=True, server_default='false'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'brand_configs',
        sa.Column('id',                sa.Integer(),   nullable=False),
        sa.Column('updated_at',        sa.DateTime(),  nullable=True),
        sa.Column('updated_by',        sa.Integer(),   nullable=True),
        sa.Column('verified_benefits', sa.Text(),      nullable=True, server_default='[]'),
        sa.Column('prohibited_claims', sa.Text(),      nullable=True, server_default='[]'),
        sa.Column('tone_guide',        sa.Text(),      nullable=True, server_default=''),
        sa.Column('hashtag_sets',      sa.Text(),      nullable=True, server_default='{}'),
        sa.Column('approved_channels', sa.String(200), nullable=True,
                  server_default='linkedin,instagram,facebook,reel'),
        sa.Column('enabled_sources',   sa.String(500), nullable=True,
                  server_default='bcrp,sbs,el_comercio,gestion,peru21'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('brand_configs')
    op.drop_table('content_sources')
    op.drop_table('pipeline_stages')
    op.drop_table('content_pipelines')
