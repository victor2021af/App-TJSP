@echo off
setlocal
cd /d "%~dp0backend"
if "%~1"=="" (
  echo Uso: importar-provas.bat "C:\caminho\da\pasta com os PDFs"
  exit /b 1
)
.venv\Scripts\python -m app.importar_pastas "%~1"
pause
