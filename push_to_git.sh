#!/bin/bash
echo "🚀 Iniciando push para o repositório Git..."

if [ ! -d ".git" ]; then
    git init
    git config user.name "odl-user-1808301"
    git config user.email "odl_user_1808301@sandboxailabs1007.onmicrosoft.com"
fi

if [ ! -f "index.html" ]; then
    echo "❌ Erro: Arquivo index.html não encontrado."
    exit 1
fi

git add index.html
git commit -m "feat: Add generated HTML application - $(date '+%Y-%m-%d %H:%M:%S')"

if git remote get-url origin >/dev/null 2>&1; then
    git push origin main 2>/dev/null || git push origin master 2>/dev/null || {
        echo "⚠️  Push falhou. Arquivo commitado localmente."
    }
else
    echo "⚠️  Nenhum repositório remoto configurado."
    echo "Configure com: git remote add origin <URL_DO_SEU_REPOSITORIO>"
fi

echo "✅ Processo concluído!"
