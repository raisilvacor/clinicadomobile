@echo off
echo Iniciando aplicacao...
echo Verificando dependencias...
py -m pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo Erro ao instalar dependencias.
    pause
    exit /b %ERRORLEVEL%
)
echo Executando app.py...
py app.py
if %ERRORLEVEL% NEQ 0 (
    echo Erro ao executar a aplicacao.
    pause
    exit /b %ERRORLEVEL%
)
pause
