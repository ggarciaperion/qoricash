#!/usr/bin/env python
"""
Script para aplicar migraciones pendientes en Render
Ejecutar: python run_migrations.py
"""
import os
import sys
from flask import Flask
from flask_migrate import upgrade

# Configurar variable de entorno
os.environ['FLASK_APP'] = 'run.py'

# Importar la aplicación
from run import app

def apply_migrations():
    """Aplicar todas las migraciones pendientes"""
    with app.app_context():
        try:
            print("=" * 50)
            print("APLICANDO MIGRACIONES DE BASE DE DATOS")
            print("=" * 50)

            # Aplicar migraciones
            from flask_migrate import upgrade as flask_upgrade
            flask_upgrade()

            print("\n✅ Migraciones aplicadas exitosamente")
            print("=" * 50)
            return True

        except Exception as e:
            print(f"\n❌ Error al aplicar migraciones: {str(e)}")
            print("=" * 50)
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    success = apply_migrations()
    sys.exit(0 if success else 1)
