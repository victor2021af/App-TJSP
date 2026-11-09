@echo off
setlocal
cd /d "%~dp0backend"
if not exist .venv\Scripts\python.exe echo Rode instalar.bat primeiro. & exit /b 1
.venv\Scripts\python.exe -c "from app.services import backup; print('Backup criado:', backup.criar_backup())"
