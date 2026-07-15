#!/bin/bash

# Script para fazer push do Sentinel Arbitrage para GitHub
# Execute no seu computador local onde tem credenciais configuradas

set -e

echo "🚀 PUSH SENTINEL ARBITRAGE PARA GITHUB"
echo "======================================"
echo ""

# Validar se está no diretório correto
if [ ! -f "bot/main.py" ]; then
    echo "❌ Erro: Execute este script dentro da pasta 'sentinel-arbitrage'"
    echo "   cd sentinel-arbitrage && bash push-github.sh"
    exit 1
fi

echo "📍 Diretório: $(pwd)"
echo ""

# Verificar git
if ! command -v git &> /dev/null; then
    echo "❌ Git não está instalado"
    exit 1
fi

echo "✓ Git encontrado"
echo ""

# Verificar se já tem repositório git
if [ ! -d .git ]; then
    echo "🔄 Inicializando Git..."
    git init
    git config user.name "Sentinel Arbitrage"
    git config user.email "sentinel@arbitrage.bot"
fi

echo "✓ Git configurado"
echo ""

# Adicionar arquivos
echo "📦 Adicionando arquivos..."
git add .
echo "✓ Arquivos adicionados"
echo ""

# Criar commit se não tiver
if [ -z "$(git log --oneline 2>/dev/null | head -1)" ]; then
    echo "✍️  Criando commit inicial..."
    git commit -m "🚀 Initial commit: Sentinel Arbitrage Bot

- Smart Contract Solidity: Flash Loans + Aave V3
- Python Bot: Multi-source sentiment analysis
- Dashboard: Real-time Flask API with Chart.js
- Database: SQLite with operation history
- Documentation: Complete setup guide
- Ready for production

Version: 1.0.0"
    echo "✓ Commit criado"
else
    echo "✓ Commits já existem"
fi

echo ""

# Verificar remote
if ! git remote | grep -q origin; then
    echo "🔗 Adicionando remote..."
    git remote add origin https://github.com/victorhf220/flashtrader.git
    echo "✓ Remote adicionado"
else
    echo "✓ Remote já existe"
fi

echo ""

# Renomear branch se necessário
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" != "main" ]; then
    echo "🔄 Renomeando branch para 'main'..."
    git branch -M main
    echo "✓ Branch 'main' configurado"
fi

echo ""
echo "======================================"
echo "🚀 FAZENDO PUSH PARA GITHUB..."
echo "======================================"
echo ""
echo "Se pedir login, use:"
echo "  - Username: seu usuario do GitHub (ou email)"
echo "  - Password: seu personal access token"
echo ""
echo "Para gerar token:"
echo "  https://github.com/settings/tokens/new"
echo "  Selecione: 'repo' (full control)"
echo ""

# Fazer push
if git push -u origin main; then
    echo ""
    echo "======================================"
    echo "✅ SUCESSO!"
    echo "======================================"
    echo ""
    echo "Seu repositório está em:"
    echo "  https://github.com/victorhf220/flashtrader"
    echo ""
    echo "Para clonar em outra máquina:"
    echo "  git clone https://github.com/victorhf220/flashtrader.git"
else
    echo ""
    echo "❌ Erro ao fazer push"
    echo ""
    echo "Possíveis soluções:"
    echo "1. Verifique sua conexão com internet"
    echo "2. Gere um Personal Access Token (https://github.com/settings/tokens/new)"
    echo "3. Configure SSH: https://docs.github.com/en/authentication/connecting-to-github-with-ssh"
    exit 1
fi
