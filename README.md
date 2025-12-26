# Assistência Técnica de Celulares - TechCell

Página web profissional para assistência técnica de celulares Android e iPhone com painel administrativo completo.

## Características

- Design moderno e profissional
- Cores: Preto (fundo) e Laranja (destaque)
- Totalmente responsivo
- Interface intuitiva e atraente
- **Painel administrativo completo** para gerenciar todo o conteúdo do site

## Como executar

### 1. Instalar dependências

```bash
pip install -r requirements.txt
```

### 2. Executar a aplicação

```bash
python app.py
```

### 3. Acessar no navegador

**Site público:**
- Abra o navegador e acesse: `http://localhost:5000`

**Painel administrativo:**
- Acesse: `http://localhost:5000/admin/login`
- Senha padrão: `admin123`

## Estrutura do Projeto

```
.
├── app.py              # Aplicação Flask principal
├── config.json         # Arquivo de configuração (conteúdo do site)
├── requirements.txt    # Dependências do projeto
├── templates/          # Templates HTML
│   ├── index.html     # Página principal
│   └── admin/         # Templates do painel administrativo
│       ├── base.html
│       ├── login.html
│       ├── dashboard.html
│       ├── hero.html
│       ├── services.html
│       ├── about.html
│       ├── devices.html
│       ├── laboratory.html
│       ├── contact.html
│       └── password.html
├── static/            # Arquivos estáticos
│   ├── images/       # Imagens
│   └── videos/       # Vídeos
└── README.md         # Este arquivo
```

## Painel Administrativo

O painel administrativo permite gerenciar completamente o conteúdo do site:

### Funcionalidades:

1. **Hero Section** - Editar título, subtítulo, botão e imagem de fundo
2. **Serviços** - Adicionar, editar e remover serviços
3. **Sobre** - Editar informações sobre a empresa e características
4. **Dispositivos** - Gerenciar módulos Android, iPhone e MAC
5. **Laboratório** - Gerenciar imagens da galeria
6. **Contato** - Editar telefones, e-mails, endereço e horários
7. **Senha** - Alterar senha de acesso ao painel

### Segurança:

- **IMPORTANTE:** Altere a senha padrão imediatamente após a primeira instalação
- A senha está armazenada em `config.json`
- Em produção, use um sistema de autenticação mais robusto

## Tecnologias Utilizadas

- Python 3.x
- Flask (Framework web)
- HTML5
- CSS3
- JavaScript
- JSON (armazenamento de dados)

## Personalização

Tudo pode ser personalizado através do painel administrativo. Não é necessário editar código manualmente!

Se preferir editar diretamente, o conteúdo está armazenado em `config.json`.
