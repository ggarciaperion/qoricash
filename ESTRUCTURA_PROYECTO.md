# 📁 ESTRUCTURA DEL NUEVO PROYECTO QORICASH

```
qoricash-trading-v2/
│
├── app/
│   ├── __init__.py                 # Factory de la aplicación Flask
│   │
│   ├── models/                     # Modelos SQLAlchemy (ORM)
│   │   ├── __init__.py
│   │   ├── user.py                 # Modelo User
│   │   ├── client.py               # Modelo Client
│   │   ├── operation.py            # Modelo Operation
│   │   └── audit_log.py            # Modelo AuditLog
│   │
│   ├── services/                   # Lógica de negocio
│   │   ├── __init__.py
│   │   ├── auth_service.py         # Servicio de autenticación
│   │   ├── user_service.py         # Servicio de usuarios
│   │   ├── client_service.py       # Servicio de clientes
│   │   ├── operation_service.py    # Servicio de operaciones
│   │   ├── file_service.py         # Servicio de archivos (Cloudinary)
│   │   └── notification_service.py # Servicio de notificaciones
│   │
│   ├── routes/                     # Blueprints (rutas)
│   │   ├── __init__.py
│   │   ├── auth.py                 # Rutas de autenticación
│   │   ├── dashboard.py            # Rutas de dashboards
│   │   ├── users.py                # Rutas de usuarios
│   │   ├── clients.py              # Rutas de clientes
│   │   └── operations.py           # Rutas de operaciones
│   │
│   ├── schemas/                    # Validación de datos
│   │   ├── __init__.py
│   │   ├── user_schema.py
│   │   ├── client_schema.py
│   │   └── operation_schema.py
│   │
│   ├── utils/                      # Utilidades
│   │   ├── __init__.py
│   │   ├── decorators.py           # Decoradores custom (@require_role)
│   │   ├── validators.py           # Validadores
│   │   ├── formatters.py           # Formateadores
│   │   └── constants.py            # Constantes
│   │
│   ├── templates/                  # Templates Jinja2
│   │   ├── base.html
│   │   ├── auth/
│   │   │   └── login.html
│   │   ├── dashboard/
│   │   │   ├── master.html
│   │   │   └── trader.html
│   │   ├── users/
│   │   │   └── manage.html
│   │   ├── clients/
│   │   │   └── list.html
│   │   └── operations/
│   │       ├── list.html
│   │       └── create.html
│   │
│   ├── static/                     # Archivos estáticos
│   │   ├── css/
│   │   │   └── main.css
│   │   ├── js/
│   │   │   ├── common.js
│   │   │   └── dashboard.js
│   │   └── images/
│   │       └── logo.png
│   │
│   ├── extensions.py               # Extensiones Flask
│   └── config.py                   # Configuración
│
├── migrations/                     # Migraciones Alembic
│   └── versions/
│
├── tests/                          # Tests
│   ├── __init__.py
│   ├── test_auth.py
│   ├── test_users.py
│   └── test_operations.py
│
├── scripts/                        # Scripts de utilidad
│   ├── init_db.py                  # Inicializar base de datos
│   └── create_admin.py             # Crear usuario admin
│
├── .env.example                    # Ejemplo de variables de entorno
├── .gitignore                      # Git ignore
├── requirements.txt                # Dependencias Python
├── Procfile                        # Configuración Render
├── gunicorn_config.py              # Configuración Gunicorn
├── run.py                          # Entry point desarrollo
└── README.md                       # Documentación
```

## 🎯 CARACTERÍSTICAS CLAVE

✅ **Separación clara de responsabilidades**
- Models: Solo estructura de datos
- Services: Solo lógica de negocio
- Routes: Solo manejo de HTTP
- Schemas: Solo validación

✅ **Escalable y mantenible**
- Cada módulo es independiente
- Fácil agregar nuevas funcionalidades
- Código reutilizable

✅ **Profesional**
- Patrones de diseño estándar
- Clean Architecture
- Best practices de Flask

✅ **Listo para producción**
- Manejo de errores robusto
- Logging profesional
- Configuración por entornos
- Migraciones de base de datos
