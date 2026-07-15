@echo off
REM Script para fazer push do Sentinel Arbitrage para GitHub (Windows)

echo 🚀 PUSH SENTINEL ARBITRAGE PARA GITHUB
echo ======================================
echo.

REM Validar diretório
if not exist "bot\main.py" (
    echo ❌ Erro: Execute este script dentro da pasta 'sentinel-arbitrage'
    echo    cd sentinel-arbitrage && push-github.bat
    pause
    exit /b 1
)

echo 📍 Diretório: %CD%
echo.

REM Verificar git
where git >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Git não está instalado
    echo    Baixe em: https://git-scm.com/download/win
    pause
    exit /b 1
)

echo ✓ Git encontrado
echo.

REM Verificar se tem git
if not exist .git (
    echo 🔄 Inicializando Git...
    git init
    git config user.name "Sentinel Arbitrage"
    git config user.email "sentinel@arbitrage.bot"
)

echo ✓ Git configurado
echo.

REM Adicionar arquivos
echo 📦 Adicionando arquivos...
git add .
echo ✓ Arquivos adicionados
echo.

REM Criar commit
git log --oneline >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ✍️  Criando commit inicial...
    git commit -m "🚀 Initial commit: Sentinel Arbitrage Bot - Smart Contract, Python Bot, Dashboard, Documentation. Version 1.0.0 - Ready for production"
    echo ✓ Commit criado
) else (
    echo ✓ Commits já existem
)

echo.

REM Verificar remote
git remote | findstr origin >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo 🔗 Adicionando remote...
    git remote add origin https://github.com/victorhf220/flashtrader.git
    echo ✓ Remote adicionado
) else (
    echo ✓ Remote já existe
)

echo.

REM Renomear branch
for /f "tokens=*" %%i in ('git rev-parse --abbrev-ref HEAD') do set CURRENT_BRANCH=%%i
if not "%CURRENT_BRANCH%"=="main" (
    echo 🔄 Renomeando branch para 'main'...
    git branch -M main
    echo ✓ Branch 'main' configurado
)

echo.
echo ======================================
echo 🚀 FAZENDO PUSH PARA GITHUB...
echo ======================================
echo.
echo Se pedir login, use:
echo   - Username: seu usuario do GitHub (ou email)
echo   - Password: seu personal access token
echo.
echo Para gerar token:
echo   https://github.com/settings/tokens/new
echo   Selecione: 'repo' (full control)
echo.

REM Fazer push
git push -u origin main
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ======================================
    echo ✅ SUCESSO!
    echo ======================================
    echo.
    echo Seu repositório está em:
    echo   https://github.com/victorhf220/flashtrader
    echo.
) else (
    echo.
    echo ❌ Erro ao fazer push
    echo.
    echo Possíveis soluções:
    echo 1. Verifique sua conexão com internet
    echo 2. Gere um Personal Access Token
    echo    https://github.com/settings/tokens/new
    echo 3. Configure SSH
    echo    https://docs.github.com/en/authentication/connecting-to-github-with-ssh
)

pause
