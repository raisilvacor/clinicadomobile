"""
Script de migração de config.json para PostgreSQL
Execute este script uma vez para migrar os dados existentes
"""
import json
import os
from db import (
    create_tables, 
    save_admin_password, 
    save_site_content_section,
    save_repair,
    save_checklist,
    save_order
)

def migrate_from_config():
    """Migra dados do config.json para o banco de dados"""
    CONFIG_FILE = 'config.json'
    
    if not os.path.exists(CONFIG_FILE):
        print("Arquivo config.json não encontrado. Nada para migrar.")
        return
    
    print("Criando tabelas no banco de dados...")
    create_tables()
    
    print("Lendo config.json...")
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Migrar senha do admin
    if 'admin_password' in config:
        print("Migrando senha do admin...")
        save_admin_password(config['admin_password'])
    
    # Migrar conteúdo do site
    if 'site_content' in config:
        print("Migrando conteúdo do site...")
        site_content = config['site_content']
        for section, data in site_content.items():
            print(f"  - Migrando seção: {section}")
            save_site_content_section(section, data)
    
    # Migrar reparos
    if 'repairs' in config:
        print(f"Migrando {len(config['repairs'])} reparos...")
        for repair in config['repairs']:
            repair_id = repair.get('id')
            if repair_id:
                print(f"  - Migrando reparo: {repair_id}")
                save_repair(repair_id, repair)
    
    # Migrar checklists
    if 'checklists' in config:
        print(f"Migrando {len(config['checklists'])} checklists...")
        for checklist in config['checklists']:
            checklist_id = checklist.get('id')
            if checklist_id:
                print(f"  - Migrando checklist: {checklist_id}")
                save_checklist(checklist_id, checklist)
    
    # Migrar ordens
    if 'orders' in config:
        print(f"Migrando {len(config['orders'])} ordens de retirada...")
        for order in config['orders']:
            order_id = order.get('id')
            repair_id = order.get('repair_id')
            if order_id and repair_id:
                print(f"  - Migrando ordem: {order_id}")
                save_order(order_id, repair_id, order)
    
    print("\n✅ Migração concluída com sucesso!")
    print("⚠️  IMPORTANTE: Faça backup do config.json antes de removê-lo.")
    print("   Você pode manter o config.json como backup, mas o sistema agora usa o banco de dados.")

if __name__ == '__main__':
    migrate_from_config()

