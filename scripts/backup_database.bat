@echo off
REM Script de backup para Windows
REM Ejecutar diariamente con Programador de Tareas de Windows

SET TIMESTAMP=%date:~-4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%%time:~6,2%
SET TIMESTAMP=%TIMESTAMP: =0%
SET BACKUP_DIR=C:\Backups\QoriCash\Database
SET BACKUP_FILE=%BACKUP_DIR%\qoricash_backup_%TIMESTAMP%.sql

REM Crear directorio si no existe
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

REM Hacer backup usando pg_dump
echo Iniciando backup de base de datos...
pg_dump %DATABASE_URL% > "%BACKUP_FILE%"

if %errorlevel% equ 0 (
    echo Backup exitoso: %BACKUP_FILE%

    REM Comprimir con 7zip (si está instalado)
    if exist "C:\Program Files\7-Zip\7z.exe" (
        "C:\Program Files\7-Zip\7z.exe" a -tgzip "%BACKUP_FILE%.gz" "%BACKUP_FILE%"
        del "%BACKUP_FILE%"
        echo Archivo comprimido: %BACKUP_FILE%.gz
    )
) else (
    echo ERROR: Fallo el backup
)

REM Opcional: Copiar a Google Drive / Dropbox
REM xcopy "%BACKUP_FILE%.gz" "C:\Users\TuUsuario\Google Drive\Backups\" /Y

pause
