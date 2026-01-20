"""Listar todos los archivos de migración"""
import os

migrations_dir = 'migrations/versions'
print('📁 Archivos de migración en migrations/versions:\n')

if os.path.exists(migrations_dir):
    files = sorted(os.listdir(migrations_dir))
    for f in files:
        if f.endswith('.py') and not f.startswith('__'):
            print(f'   {f}')
    print(f'\n📊 Total: {len([f for f in files if f.endswith(".py") and not f.startswith("__")])} archivos')
else:
    print('❌ Directorio migrations/versions no existe')
