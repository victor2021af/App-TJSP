@echo off
setlocal
cd /d "%~dp0backend"
if not exist .venv\Scripts\python.exe echo Rode instalar.bat primeiro. & exit /b 1
if not exist ..\frontend\dist\index.html echo Interface nao compilada. Rode instalar.bat. & exit /b 1
if not exist ..\certs\cert.pem echo Certificado nao encontrado. Rode gerar-certificado.bat primeiro. & exit /b 1
echo.
echo ATENCAO: este modo libera o app para outros aparelhos da SUA rede Wi-Fi.
if /i "%TJSP_AUTH%"=="on" (echo Login: LIGADO - sera pedido usuario e senha.) else (echo Login: DESLIGADO - quem estiver na sua rede e abrir o endereco acessa e altera seus dados.)
echo.
echo - Use apenas na rede da sua casa, nunca em Wi-Fi publico, de trabalho ou hotspot de terceiros.
echo - Quando o Windows perguntar sobre o Firewall, permita somente redes PRIVADAS.
echo - Nao faca redirecionamento de porta no roteador: isso exporia o app a internet.
echo - Para exigir senha, use iniciar-rede-com-senha.bat em vez deste.
echo.
echo No celular, abra: https://IP-DESTE-COMPUTADOR:8443  (o IP aparece em Ajustes)
echo Feche esta janela para encerrar.
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8443 --ssl-keyfile ..\certs\key.pem --ssl-certfile ..\certs\cert.pem
