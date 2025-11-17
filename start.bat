@echo off
REM Script para iniciar todos os serviços do sistema
REM Windows - ProjetoRefatorado

echo ========================================
echo   Sistema de Naturalizacao - v2.0
echo ========================================
echo.

REM Verificar se Redis está rodando
echo [1/3] Verificando Redis...
redis-cli ping >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERRO] Redis nao esta rodando!
    echo.
    echo Execute um dos comandos:
    echo   1. Docker: docker run -d -p 6379:6379 --name redis redis:alpine
    echo   2. WSL:    wsl sudo service redis-server start
    echo.
    pause
    exit /b 1
)
echo [OK] Redis conectado
echo.

REM Iniciar Flask
echo [2/3] Iniciando Flask...
start "Flask Server" cmd /k "python run.py"
timeout /t 3 >nul
echo [OK] Flask iniciado em http://localhost:5000
echo.

REM Iniciar Celery Worker
echo [3/3] Iniciando Celery Worker...
start "Celery Worker" cmd /k "celery -A celery_app worker --loglevel=info --pool=solo"
timeout /t 3 >nul
echo [OK] Celery Worker iniciado
echo.

echo ========================================
echo   Servicos iniciados com sucesso!
echo ========================================
echo.
echo URLs importantes:
echo   - App:     http://localhost:5000
echo   - Swagger: http://localhost:5000/api/v2/doc
echo.
echo Pressione Ctrl+C nas janelas para parar os servicos.
echo.
pause
