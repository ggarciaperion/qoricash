"""Verificar TODAS las columnas relacionadas con password en la tabla clients"""
from app import create_app
from app.extensions import db
from sqlalchemy import inspect, text

app = create_app()
with app.app_context():
    inspector = inspect(db.engine)
    columns = inspector.get_columns('clients')

    print('\n🔍 Columnas relacionadas con password en tabla clients:\n')

    password_cols = [col for col in columns if 'password' in col['name'].lower()]

    if password_cols:
        for col in password_cols:
            print(f'  ✓ {col["name"]}:')
            print(f'     - Tipo: {col["type"]}')
            print(f'     - Nullable: {col["nullable"]}')
            print(f'     - Default: {col.get("default", "None")}')
            print()
    else:
        print('  ❌ No se encontraron columnas relacionadas con password\n')

    # Verificar también en la base de datos directamente
    print('📊 Verificación directa en PostgreSQL:\n')
    result = db.session.execute(text("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name='clients' AND column_name LIKE '%password%'
        ORDER BY column_name
    """)).fetchall()

    if result:
        for row in result:
            print(f'  ✓ {row[0]}:')
            print(f'     - Tipo: {row[1]}')
            print(f'     - Nullable: {row[2]}')
            print(f'     - Default: {row[3]}')
            print()
    else:
        print('  ❌ No se encontraron columnas con "password" en el nombre\n')
