# Gerador de APK para Clínica CELL App

Este diretório contém os arquivos necessários para gerar um APK do app PWA.

## Opção 1: Usar PWA Builder (Recomendado - Mais Fácil)

1. Acesse: https://www.pwabuilder.com/
2. Digite a URL do seu app: `https://clinicacel.onrender.com/mobile_app/`
3. Clique em "Build My PWA"
4. Selecione "Android" e baixe o APK

## Opção 2: Usar Bubblewrap (Google)

1. Instale Node.js
2. Execute:
```bash
npm install -g @bubblewrap/cli
bubblewrap init --manifest https://clinicacel.onrender.com/mobile_app/manifest.json
bubblewrap build
```

## Opção 3: Usar Android Studio (Avançado)

Veja os arquivos neste diretório para criar um projeto Android básico.

