# Migração para PostgreSQL - Instruções

## Status da Migração

✅ **Concluído:**
- Módulo `db.py` criado com todas as funções de banco de dados
- Script de migração `migrate_to_db.py` criado
- Rotas de conteúdo do site (hero, services, about, devices, laboratory, contact) migradas
- Rota de login e senha migrada
- Rotas de checklist parcialmente migradas

⚠️ **Pendente:**
- Atualizar todas as rotas de repairs para usar o banco
- Atualizar todas as rotas de orders para usar o banco
- Atualizar rotas públicas (status, approve_budget, etc.)

## Como Completar a Migração

### 1. Executar o Script de Migração

```bash
python migrate_to_db.py
```

Este script irá:
- Criar todas as tabelas no banco de dados
- Migrar dados do `config.json` para o PostgreSQL

### 2. Variável de Ambiente

Certifique-se de que a variável `DATABASE_URL` está configurada no Render:
- Vá em Settings > Environment Variables
- Adicione: `DATABASE_URL` = `postgresql://rai:nk1HAfaFPhbOvg34lqWl7YC5LfPNmNS3@dpg-d57kenggjchc739lcorg-a.virginia-postgres.render.com/mobiledb_p0w2`

### 3. Substituições Restantes

Todas as referências a `load_config()` e `save_config()` precisam ser substituídas:

**Para Repairs:**
- `config.get('repairs', [])` → `get_all_repairs()`
- `repair = [buscar em lista]` → `repair = db_get_repair(repair_id)`
- `save_config(config)` → `save_repair(repair_id, repair_data)`

**Para Checklists:**
- `config.get('checklists', [])` → `get_all_checklists()`
- `checklist = [buscar em lista]` → `checklist = db_get_checklist(checklist_id)`
- `save_config(config)` → `save_checklist(checklist_id, checklist_data)`

**Para Orders:**
- `config.get('orders', [])` → `get_all_orders()`
- `order = [buscar em lista]` → `order = db_get_order(order_id)`
- `save_config(config)` → `save_order(order_id, repair_id, order_data)`

## Estrutura do Banco de Dados

### Tabelas Criadas:
1. **site_content** - Conteúdo do site (hero, serviços, sobre, etc.)
2. **admin_settings** - Configurações do admin (senha)
3. **repairs** - Reparos
4. **checklists** - Checklists antifraude
5. **orders** - Ordens de retirada (OR)

### Índices:
- `idx_repairs_repair_id` - Performance em buscas de reparos
- `idx_checklists_id` - Performance em buscas de checklists
- `idx_orders_repair_id` - Performance em buscas de orders por reparo
- `idx_orders_id` - Performance em buscas de orders

## Notas Importantes

⚠️ **IMPORTANTE:** 
- Faça backup do `config.json` antes de remover
- O sistema ainda funciona com `config.json` como fallback
- Após migração completa, você pode manter `config.json` como backup

## Funções Disponíveis no db.py

### Site Content:
- `get_site_content()` - Obtém todo o conteúdo
- `save_site_content_section(section, data)` - Salva uma seção
- `get_site_content_section(section)` - Obtém uma seção específica

### Admin:
- `get_admin_password()` - Obtém senha
- `save_admin_password(password)` - Salva senha

### Repairs:
- `get_all_repairs()` - Lista todos
- `get_repair(repair_id)` - Obtém um específico
- `save_repair(repair_id, repair_data)` - Salva/atualiza
- `delete_repair(repair_id)` - Deleta

### Checklists:
- `get_all_checklists()` - Lista todos
- `get_checklist(checklist_id)` - Obtém um específico
- `get_checklists_by_repair(repair_id)` - Lista por reparo
- `save_checklist(checklist_id, checklist_data)` - Salva/atualiza
- `delete_checklist(checklist_id)` - Deleta

### Orders:
- `get_all_orders()` - Lista todas
- `get_order(order_id)` - Obtém uma específica
- `get_order_by_repair(repair_id)` - Obtém por reparo
- `save_order(order_id, repair_id, order_data)` - Salva/atualiza
- `delete_order(order_id)` - Deleta

