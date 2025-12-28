# Como Gerar o APK do App Clínica CEL

## Método 1: PWA Builder (Mais Fácil - Recomendado) ⭐

1. Acesse: **https://www.pwabuilder.com/**
2. Cole a URL: `https://clinicacel.onrender.com/mobile_app/`
3. Clique em **"Start"**
4. Aguarde a análise
5. Clique em **"Build My PWA"**
6. Selecione **"Android"**
7. Clique em **"Generate Package"**
8. Baixe o APK gerado

## Método 2: Bubblewrap (Linha de Comando)

### Pré-requisitos:
- Node.js instalado (https://nodejs.org/)

### Passos:

```bash
# 1. Instalar Bubblewrap
npm install -g @bubblewrap/cli

# 2. Inicializar projeto
bubblewrap init --manifest https://clinicacel.onrender.com/mobile_app/manifest.json

# 3. Gerar APK
bubblewrap build
```

O APK estará em: `./app-release.apk`

## Método 3: Android Studio (Avançado)

1. Abra Android Studio
2. Crie um novo projeto "Empty Activity"
3. Substitua os arquivos pelos arquivos deste diretório
4. Build > Generate Signed Bundle / APK
5. Selecione APK
6. Siga o assistente

## Método 4: Usar Site Online (Mais Rápido)

1. Acesse: **https://appsgeyser.com/** ou **https://www.appypie.com/**
2. Escolha "Web App"
3. Cole a URL: `https://clinicacel.onrender.com/mobile_app/`
4. Configure nome: "Clínica CEL"
5. Gere e baixe o APK

## Recomendação

**Use o Método 1 (PWA Builder)** - É o mais fácil, rápido e gera um APK de qualidade profissional.

