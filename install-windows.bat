@echo off
REM ========================================
REM QORICASH TRADING V2 - INSTALADOR WINDOWS
REM ========================================

echo.
echo ========================================
echo  QORICASH TRADING V2 - INSTALADOR
echo ========================================
echo.

REM Verificar Python
echo [1/8] Verificando Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no esta instalado
    echo Descarga Python 3.11 desde: https://www.python.org/downloads/
    pause
    exit /b 1
)
python --version
echo.

REM Crear entorno virtual
echo [2/8] Creando entorno virtual...
if exist venv (
    echo Entorno virtual ya existe, omitiendo...
) else (
    python -m venv venv
    echo Entorno virtual creado
)
echo.

REM Activar entorno virtual
echo [3/8] Activando entorno virtual...
call venv\Scripts\activate.bat
echo Entorno virtual activado
echo.

REM Actualizar pip
echo [4/8] Actualizando pip...
python -m pip install --upgrade pip --quiet
echo pip actualizado
echo.

REM Instalar dependencias
echo [5/8] Instalando dependencias...
echo Esto puede tardar unos minutos...
pip install -r requirements-windows.txt --quiet
if errorlevel 1 (
    echo ERROR: Fallo la instalacion de dependencias
    echo Intentando con requirements.txt alternativo...
    pip install -r requirements.txt --quiet
)
echo Dependencias instaladas
echo.

REM Crear archivo .env
echo [6/8] Configurando variables de entorno...
if exist .env (
    echo Archivo .env ya existe
) else (
    copy .env.example .env >nul
    echo Archivo .env creado
    echo IMPORTANTE: Edita .env con tus valores (DATABASE_URL, CLOUDINARY_URL, etc.)
)
echo.

REM Verificar instalación
echo [7/8] Verificando instalacion...
python -c "import flask; print('Flask OK')" 2>nul
if errorlevel 1 (
    echo ERROR: Flask no se instalo correctamente
    pause
    exit /b 1
)
python -c "from flask_sqlalchemy import SQLAlchemy; print('SQLAlchemy OK')" 2>nul
if errorlevel 1 (
    echo ERROR: SQLAlchemy no se instalo correctamente
    pause
    exit /b 1
)
echo Todas las dependencias verificadas
echo.

REM Instrucciones finales
echo [8/8] Instalacion completada!
echo.
echo ========================================
echo  PROXIMOS PASOS:
echo ========================================
echo.
echo 1. Edita el archivo .env con tus valores:
echo    - DATABASE_URL (PostgreSQL o SQLite)
echo    - SECRET_KEY (genera uno nuevo)
echo    - CLOUDINARY_URL (opcional)
echo.
echo 2. Inicializa la base de datos:
echo    flask db init
echo    flask db migrate -m "Initial migration"
echo    flask db upgrade
echo.
echo 3. Crea el usuario administrador:
echo    python scripts\create_admin.py
echo.
echo 4. Ejecuta el sistema:
echo    python run.py
echo.
echo ========================================
echo  Abre http://localhost:5000 en tu navegador
echo ========================================
echo.

pause
