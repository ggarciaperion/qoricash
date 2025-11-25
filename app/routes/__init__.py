"""
Blueprints (rutas) de la aplicación QoriCash Trading V2
"""
from app.routes.auth import auth_bp
from app.routes.dashboard import dashboard_bp
from app.routes.users import users_bp
from app.routes.clients import clients_bp
from app.routes.operations import operations_bp
from app.routes.position import position_bp

__all__ = ['auth_bp', 'dashboard_bp', 'users_bp', 'clients_bp', 'operations_bp', 'position_bp']
