"""update clients table with new fields

Revision ID: update_clients_table
Revises: add_assigned_operator
Create Date: 2025-11-27

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'update_clients_table'
down_revision = 'add_assigned_operator'
branch_labels = None
depends_on = None


def upgrade():
    """Actualizar tabla clients con nuevos campos"""
    with op.batch_alter_table('clients', schema=None) as batch_op:
        # Tipo de documento
        batch_op.add_column(sa.Column('document_type', sa.String(length=10), nullable=True))
        
        # Información personal (DNI/CE)
        batch_op.add_column(sa.Column('apellido_paterno', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('apellido_materno', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('nombres', sa.String(length=100), nullable=True))
        
        # Información empresa (RUC)
        batch_op.add_column(sa.Column('razon_social', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('persona_contacto', sa.String(length=200), nullable=True))
        
        # Documentos adicionales RUC
        batch_op.add_column(sa.Column('dni_representante_front_url', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('dni_representante_back_url', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('ficha_ruc_url', sa.String(length=500), nullable=True))
        
        # Validación OC
        batch_op.add_column(sa.Column('validation_oc_url', sa.String(length=500), nullable=True))
        
        # Dirección
        batch_op.add_column(sa.Column('direccion', sa.String(length=300), nullable=True))
        batch_op.add_column(sa.Column('distrito', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('provincia', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('departamento', sa.String(length=100), nullable=True))
        
        # Cuentas bancarias JSON
        batch_op.add_column(sa.Column('bank_accounts_json', sa.Text(), nullable=True))
        
        # Campos bancarios adicionales
        batch_op.add_column(sa.Column('account_type', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('currency', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('bank_account_number', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('origen', sa.String(length=20), nullable=True))
        
        # Auditoría
        batch_op.add_column(sa.Column('created_by', sa.Integer(), nullable=True))
        
        # Aumentar tamaño phone de 20 a 100
        batch_op.alter_column('phone',
                    existing_type=sa.String(20),
                    type_=sa.String(100),
                    existing_nullable=True)
        
        # Eliminar columna name si existe (reemplazada por apellido_paterno/materno/nombres)
        try:
            batch_op.drop_column('name')
        except:
            pass
    
    # Agregar foreign key para created_by
    try:
        op.create_foreign_key('fk_clients_created_by', 'clients', 'users', ['created_by'], ['id'])
    except:
        pass
    
    # Establecer document_type='DNI' por defecto para registros existentes
    op.execute("UPDATE clients SET document_type = 'DNI' WHERE document_type IS NULL")
    
    # Ahora hacer document_type NOT NULL
    with op.batch_alter_table('clients', schema=None) as batch_op:
        batch_op.alter_column('document_type',
                    existing_type=sa.String(10),
                    nullable=False)


def downgrade():
    """Revertir cambios"""
    with op.batch_alter_table('clients', schema=None) as batch_op:
        batch_op.drop_constraint('fk_clients_created_by', type_='foreignkey')
        batch_op.drop_column('created_by')
        batch_op.drop_column('origen')
        batch_op.drop_column('bank_account_number')
        batch_op.drop_column('currency')
        batch_op.drop_column('account_type')
        batch_op.drop_column('bank_accounts_json')
        batch_op.drop_column('departamento')
        batch_op.drop_column('provincia')
        batch_op.drop_column('distrito')
        batch_op.drop_column('direccion')
        batch_op.drop_column('validation_oc_url')
        batch_op.drop_column('ficha_ruc_url')
        batch_op.drop_column('dni_representante_back_url')
        batch_op.drop_column('dni_representante_front_url')
        batch_op.drop_column('persona_contacto')
        batch_op.drop_column('razon_social')
        batch_op.drop_column('nombres')
        batch_op.drop_column('apellido_materno')
        batch_op.drop_column('apellido_paterno')
        batch_op.drop_column('document_type')
        
        batch_op.alter_column('phone',
                    existing_type=sa.String(100),
                    type_=sa.String(20),
                    existing_nullable=True)
        
        batch_op.add_column(sa.Column('name', sa.String(200), nullable=False))
