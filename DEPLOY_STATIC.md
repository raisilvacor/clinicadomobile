# Como Fazer o Deploy do Site Estático (Render.com)

Este projeto foi convertido para um **Site Estático** (HTML/CSS/JS) e não requer mais um backend Python.
Todos os dados são salvos no navegador do usuário (LocalStorage).

## Passo a Passo para Deploy no Render

1. **Acesse o Render.com** e vá em "New +".
2. Escolha **"Static Site"**.
3. Conecte seu repositório do GitHub/GitLab.
4. Preencha os campos:
   - **Name**: `techcell-sistema` (ou outro nome)
   - **Branch**: `main` (ou a branch que você está usando)
   - **Root Directory**: Deixe em branco (ou `.`)
   - **Build Command**: Deixe em branco (não precisa compilar nada)
   - **Publish Directory**: `public`  <-- **MUITO IMPORTANTE**
5. Clique em **"Create Static Site"**.

## Solução de Problemas

- **Se aparecer apenas a página de Reparos (Dashboard):**
  - Verifique se você não está acessando `admin.html` diretamente.
  - A página inicial (`index.html`) é a Landing Page (Site Institucional).
  - Para acessar o sistema, clique em "Área do Técnico" no menu.

- **Se as páginas derem erro 404:**
  - Certifique-se de que o **Publish Directory** está configurado exatamente como `public`.

## Estrutura de Arquivos

- `public/index.html` -> Site Institucional (Página Inicial)
- `public/admin.html` -> Dashboard de Reparos (Área do Técnico)
- `public/novo_reparo.html` -> Formulário de Novo Reparo
- `public/emitir_or.html` -> Emissão de Ordem de Retirada
- `public/js/app.js` -> Lógica do Sistema (Banco de Dados Local)
