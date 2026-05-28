from app import create_app
from app.extensions import db

app = create_app()
with app.app_context():
    # Limpiar competidores eliminados
    for slug in ('instakash', 'metafxperu'):
        db.session.execute(db.text(f"DELETE FROM fx_change_events WHERE competitor_id=(SELECT id FROM fx_competitors WHERE slug='{slug}')"))
        db.session.execute(db.text(f"DELETE FROM fx_rate_history WHERE competitor_id=(SELECT id FROM fx_competitors WHERE slug='{slug}')"))
        db.session.execute(db.text(f"DELETE FROM fx_rate_current WHERE competitor_id=(SELECT id FROM fx_competitors WHERE slug='{slug}')"))
        db.session.execute(db.text(f"DELETE FROM fx_competitors WHERE slug='{slug}'"))
        print(f'Competidor {slug} eliminado')

    # Ampliar columna role a 50 chars
    db.session.execute(db.text("ALTER TABLE users ALTER COLUMN role TYPE VARCHAR(50)"))
    print('Columna role ampliada a VARCHAR(50)')

    # Reemplazar check constraint para incluir 'Presidente de Negocios'
    db.session.execute(db.text("ALTER TABLE users DROP CONSTRAINT IF EXISTS check_user_role"))
    db.session.execute(db.text("""
        ALTER TABLE users ADD CONSTRAINT check_user_role CHECK (
            role IN ('Master','Trader','Operador','Middle Office','App','Web','Presidente de Negocios')
        )
    """))
    print('Constraint check_user_role actualizado')

    # Cambiar rol de Gian Pierre a Presidente de Negocios
    result = db.session.execute(db.text(
        "UPDATE users SET role='Presidente de Negocios' WHERE dni='73085751'"
    ))
    print(f'Rol actualizado: {result.rowcount} fila(s)')

    db.session.commit()

    # Verificar
    row = db.session.execute(db.text(
        "SELECT username, dni, role FROM users WHERE dni='73085751'"
    )).fetchone()
    if row:
        print(f'Usuario: {row[0]} | DNI: {row[1]} | Rol: {row[2]}')
    print('Listo.')
