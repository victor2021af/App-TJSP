@echo off
setlocal
cd /d "%~dp0"
echo === TJSP Aprovacao: instalacao ===
where py >nul 2>nul
if errorlevel 1 echo Python nao encontrado. Instale o Python 3.11 ou superior em python.org e rode de novo. & exit /b 1
where npm >nul 2>nul
if errorlevel 1 echo Node.js nao encontrado. Instale a versao LTS em nodejs.org e rode de novo. & exit /b 1

if not exist backend\.venv\Scripts\python.exe py -3 -m venv backend\.venv
if errorlevel 1 echo Falha ao criar o ambiente Python. & exit /b 1

backend\.venv\Scripts\python.exe -m pip install --upgrade pip
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
if errorlevel 1 echo Falha ao instalar as dependencias Python. & exit /b 1

pushd frontend
call npm install
if errorlevel 1 popd & echo Falha no npm install. & exit /b 1
call npm run build
if errorlevel 1 popd & echo Falha ao compilar a interface. & exit /b 1
popd

echo.
echo Instalacao concluida. Para usar no computador: iniciar.bat
