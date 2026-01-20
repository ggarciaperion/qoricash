"""Agregar la columna password que falta en la tabla clients"""
from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    try:
        print('🔄 Agregando columna password a la tabla clients...')

        # Verificar si la columna ya existe
        result = db.session.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='clients' AND column_name='password'
        """)).fetchone()

        if result:
            print('⚠️  La columna password ya existe')
        else:
            # Agregar la columna password
            db.session.execute(text("""
                ALTER TABLE clients
                ADD COLUMN password VARCHAR(255)
            """))
            db.session.commit()
            print('✅ Columna password agregada exitosamente')

    except Exception as e:
        print(f'❌ Error: {str(e)}')
        db.session.rollback()
