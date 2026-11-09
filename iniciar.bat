@echo off
setlocal
cd /d "%~dp0backend"
if not exist .venv\Scripts\python.exe echo Rode instalar.bat primeiro. & exit /b 1
if not exist ..\frontend\dist\index.html echo Interface nao compilada. Rode instalar.bat. & exit /b 1
echo TJSP Aprovacao rodando SOMENTE neste computador: http://127.0.0.1:8000
echo Feche esta janela para encerrar. Seus dados ficam em backend\data\
start "" cmd /c "ping -n 4 127.0.0.1 >nul & start http://127.0.0.1:8000"
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
