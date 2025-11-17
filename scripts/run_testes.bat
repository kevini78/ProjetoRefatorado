@echo off
:: ============================================================================
:: Script de Execução de Testes de Documentos Específicos
:: ============================================================================
:: 
:: Este script executa testes automatizados para validação de documentos:
::   - Documento do representante legal
::   - Carteira de Registro Nacional Migratorio
::   - Comprovante de tempo de residência
::   - Documento de viagem internacional
::
:: Uso:
::   run_testes.bat                 - Testa processo padrão (743961)
::   run_testes.bat 743961 784408   - Testa múltiplos processos
::
:: ============================================================================

echo.
echo ================================================================================
echo TESTES DE DOCUMENTOS ESPECIFICOS - NATURALIZACAO
echo ================================================================================
echo.

:: Verificar se Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado! Instale Python 3.8+ e tente novamente.
    pause
    exit /b 1
)

:: Mudar para o diretório do projeto
cd /d "%~dp0\.."

:: Verificar se o arquivo .env existe
if not exist ".env" (
    echo [AVISO] Arquivo .env nao encontrado!
    echo Certifique-se de configurar as credenciais antes de executar os testes.
    echo.
    pause
)

:: Executar testes com geração de relatórios
echo [INFO] Iniciando testes...
echo [INFO] Diretorio: %CD%
echo [INFO] Script: scripts\run_testes_documentos.py
echo.

if "%~1"=="" (
    echo [INFO] Testando processo padrao: 743961
    echo.
    python scripts\run_testes_documentos.py
) else (
    echo [INFO] Testando processos: %*
    echo.
    python scripts\run_testes_documentos.py %*
)

:: Verificar resultado
if errorlevel 1 (
    echo.
    echo ================================================================================
    echo [ERRO] Alguns testes falharam!
    echo ================================================================================
    echo.
    echo Verifique os relatorios gerados para mais detalhes.
    echo.
    pause
    exit /b 1
) else (
    echo.
    echo ================================================================================
    echo [SUCESSO] Todos os testes passaram!
    echo ================================================================================
    echo.
    echo Relatorios gerados com sucesso.
    echo.
    pause
    exit /b 0
)
