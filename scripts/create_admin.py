from app import create_app, db
from app.models.user import User
from app.utils.formatters import now_peru

app = create_app()

with app.app_context():
    # Verificar si ya existe
    existing = User.query.filter_by(username='admin').first()
    if existing:
        print("❌ Usuario admin ya existe")
    else:
        # Crear usuario Master
        admin = User(
            username='admin',
            email='admin@qoricash.com',
            dni='12345678',
            role='Master',
            status='Activo',
            created_at=now_peru()
        )
        admin.set_password('admin123')  # Cambiar en producción
        
        db.session.add(admin)
        db.session.commit()
        
        print("✅ Usuario admin creado")
        print("   Username: admin")
        print("   Password: admin123")
        print("   ⚠️  CAMBIAR CONTRASEÑA EN PRODUCCIÓN")