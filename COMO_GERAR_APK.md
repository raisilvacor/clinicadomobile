# 📱 Como Gerar APK do App Clínica CEL

## ⭐ Método Mais Fácil: PWA Builder (Recomendado)

### Passo a Passo:

1. **Acesse o site:** https://www.pwabuilder.com/

2. **Cole a URL do seu app:**
   ```
   https://clinicacel.onrender.com/mobile_app/
   ```
   (Substitua pelo seu domínio se for diferente)

3. **Clique em "Start"** e aguarde a análise

4. **Clique em "Build My PWA"**

5. **Selecione "Android"**

6. **Clique em "Generate Package"**

7. **Baixe o APK** gerado

8. **Instale no seu celular:**
   - Transfira o APK para o celular
   - Ative "Instalar apps de fontes desconhecidas" nas configurações
   - Abra o arquivo APK e instale

---

## 🔧 Método Alternativo: Bubblewrap (Linha de Comando)

### Pré-requisitos:
- Node.js instalado: https://nodejs.org/

### Comandos:

```bash
# 1. Instalar Bubblewrap
npm install -g @bubblewrap/cli

# 2. Inicializar projeto
bubblewrap init --manifest https://clinicacel.onrender.com/mobile_app/manifest.json

# 3. Gerar APK
bubblewrap build
```

O APK estará em: `./app-release.apk`

---

## 🌐 Método Online Rápido: AppsGeyser

1. Acesse: https://appsgeyser.com/
2. Clique em "Create Now"
3. Escolha "Web App"
4. Cole a URL: `https://clinicacel.onrender.com/mobile_app/`
5. Configure:
   - Nome: Clínica CEL
   - Ícone: Use o ícone do app
6. Clique em "Create App"
7. Baixe o APK

---

## 📋 Instruções para Instalar o APK no Android

1. **Ativar instalação de fontes desconhecidas:**
   - Android 8+: Configurações > Apps > Acesso especial > Instalar apps desconhecidos
   - Selecione o navegador usado para baixar e ative

2. **Transferir APK para o celular:**
   - Via USB, email, ou Google Drive

3. **Instalar:**
   - Abra o arquivo APK no celular
   - Toque em "Instalar"
   - Aguarde a instalação

4. **Abrir o app:**
   - O ícone "Clínica CEL" aparecerá na lista de apps

---

## ⚠️ Importante

- O APK gerado funcionará como um navegador que abre o app web
- O app precisa estar online para funcionar
- Notificações push funcionarão normalmente
- Todas as funcionalidades do PWA estarão disponíveis

---

## 🆘 Problemas?

Se tiver problemas ao gerar o APK, me avise e posso ajudar com métodos alternativos.

