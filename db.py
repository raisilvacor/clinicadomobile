"""
Módulo de gerenciamento do banco de dados PostgreSQL
Compatível com Python 3.13 usando psycopg (psycopg3)
"""
import os
import json
from contextlib import contextmanager

# Usar psycopg (psycopg3) que é compatível com Python 3.13
USE_DATABASE = True
CONFIG_FILE = 'config.json'  # Definir sempre para fallback

try:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.pool import ConnectionPool
    PSYCOPG_VERSION = 3
    print("✅ psycopg importado com sucesso!")
except ImportError as e:
    USE_DATABASE = False
    print(f"⚠️  psycopg não encontrado ({e}), usando config.json como fallback")
    print("⚠️  ATENÇÃO: Dados serão perdidos após deploy! Instale psycopg[binary]>=3.1.0")

# URL do banco de dados do Render
# Priorizar variável de ambiente, senão usar fallback
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    # Fallback para URL hardcoded (não recomendado, mas necessário se env var não estiver configurada)
    DATABASE_URL = 'postgresql://rai:nk1HAfaFPhbOvg34lqWl7YC5LfPNmNS3@dpg-d57kenggjchc739lcorg-a.virginia-postgres.render.com/mobiledb_p0w2'
    print("⚠️  DATABASE_URL não encontrada em variáveis de ambiente, usando fallback")

if DATABASE_URL:
    print(f"✅ DATABASE_URL configurada: {DATABASE_URL[:40]}...")
else:
    print("❌ DATABASE_URL não configurada!")

# Pool de conexões
pool = None

def _load_config_file():
    """Carrega config.json como fallback"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def _save_config_file(config):
    """Salva config.json como fallback"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def init_db():
    """Inicializa o pool de conexões"""
    if not USE_DATABASE:
        print("⚠️  Banco de dados desabilitado - usando config.json")
        return None
    global pool
    if pool is None:
        try:
            print(f"🔌 Conectando ao banco de dados PostgreSQL...")
            print(f"🔌 DATABASE_URL: {DATABASE_URL[:30]}...")  # Mostrar apenas início por segurança
            pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=20)
            print("✅ Pool de conexões criado com sucesso!")
            # Testar conexão criando uma conexão direta primeiro
            test_conn = pool.getconn()
            try:
                test_cur = test_conn.cursor()
                test_cur.execute("SELECT 1")
                test_cur.fetchone()
                print("✅ Conexão com banco de dados estabelecida!")
            except Exception as e:
                print(f"⚠️  Falha ao testar conexão: {e}")
            finally:
                pool.putconn(test_conn)
        except Exception as e:
            print(f"❌ Erro ao criar pool de conexões: {e}")
            USE_DATABASE = False
            return None
    return pool

@contextmanager
def get_db_connection():
    """Context manager para obter conexão do pool"""
    if not USE_DATABASE:
        yield None
        return
    
    # Garantir que o pool está inicializado
    global pool
    if pool is None:
        init_db()
        if pool is None:
            yield None
            return
    
    conn = None
    try:
        conn = pool.getconn()
        yield conn
        if conn:
            conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"⚠️  Erro na transação: {e}")
        raise
    finally:
        if conn:
            pool.putconn(conn)

def _get_cursor(conn, dict_cursor=False):
    """Helper para obter cursor"""
    if not conn:
        return None
    if dict_cursor:
        return conn.cursor(row_factory=dict_row)
    else:
        return conn.cursor()

def create_tables():
    """Cria as tabelas necessárias no banco de dados"""
    if not USE_DATABASE:
        return
    try:
        with get_db_connection() as conn:
            if not conn:
                return
            cur = _get_cursor(conn)
            
            # Tabela para conteúdo do site (hero, serviços, sobre, etc.)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS site_content (
                    id SERIAL PRIMARY KEY,
                    section VARCHAR(50) UNIQUE NOT NULL,
                    data JSONB NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tabela para configurações do admin
            cur.execute("""
                CREATE TABLE IF NOT EXISTS admin_settings (
                    key VARCHAR(100) PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tabela para reparos
            cur.execute("""
                CREATE TABLE IF NOT EXISTS repairs (
                    id VARCHAR(50) PRIMARY KEY,
                    data JSONB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tabela para checklists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS checklists (
                    id VARCHAR(50) PRIMARY KEY,
                    data JSONB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tabela para ordens de retirada (OR)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id VARCHAR(50) PRIMARY KEY,
                    repair_id VARCHAR(50) NOT NULL,
                    data JSONB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tabela para fornecedores
            cur.execute("""
                CREATE TABLE IF NOT EXISTS suppliers (
                    id VARCHAR(50) PRIMARY KEY,
                    data JSONB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Índices para melhor performance
            cur.execute("CREATE INDEX IF NOT EXISTS idx_repairs_repair_id ON repairs(id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_checklists_id ON checklists(id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_repair_id ON orders(repair_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_id ON orders(id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_suppliers_id ON suppliers(id)")
            
            conn.commit()
            print("✅ Tabelas criadas/verificadas com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao criar tabelas: {e}")
        import traceback
        traceback.print_exc()
        pass

# ========== FUNÇÕES DE SITE CONTENT ==========

def get_site_content():
    """Obtém todo o conteúdo do site"""
    if not USE_DATABASE:
        config = _load_config_file()
        return config.get('site_content', {})
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                return config.get('site_content', {})
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT section, data FROM site_content")
            rows = cur.fetchall()
            
            content = {}
            for row in rows:
                content[row['section']] = row['data']
            
            return content
    except Exception as e:
        print(f"⚠️  Erro ao ler do banco, usando config.json: {e}")
        config = _load_config_file()
        return config.get('site_content', {})

def save_site_content_section(section, data):
    """Salva uma seção do conteúdo do site"""
    if not USE_DATABASE:
        config = _load_config_file()
        if 'site_content' not in config:
            config['site_content'] = {}
        config['site_content'][section] = data
        _save_config_file(config)
        return
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                if 'site_content' not in config:
                    config['site_content'] = {}
                config['site_content'][section] = data
                _save_config_file(config)
                return
            cur = _get_cursor(conn)
            data_json = json.dumps(data)
            cur.execute("""
                INSERT INTO site_content (section, data, updated_at)
                VALUES (%s, %s::jsonb, CURRENT_TIMESTAMP)
                ON CONFLICT (section) 
                DO UPDATE SET data = %s::jsonb, updated_at = CURRENT_TIMESTAMP
            """, (section, data_json, data_json))
    except Exception as e:
        print(f"⚠️  Erro ao salvar no banco, usando config.json: {e}")
        config = _load_config_file()
        if 'site_content' not in config:
            config['site_content'] = {}
        config['site_content'][section] = data
        _save_config_file(config)

def get_site_content_section(section):
    """Obtém uma seção específica do conteúdo do site"""
    if not USE_DATABASE:
        config = _load_config_file()
        site_content = config.get('site_content', {})
        return site_content.get(section)
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                site_content = config.get('site_content', {})
                return site_content.get(section)
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT data FROM site_content WHERE section = %s", (section,))
            row = cur.fetchone()
            return row['data'] if row else None
    except Exception as e:
        print(f"⚠️  Erro ao ler do banco, usando config.json: {e}")
        config = _load_config_file()
        site_content = config.get('site_content', {})
        return site_content.get(section)

# ========== FUNÇÕES DE ADMIN SETTINGS ==========

def get_admin_password():
    """Obtém a senha do admin"""
    if not USE_DATABASE:
        config = _load_config_file()
        return config.get('admin_password', 'admin123')
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                return config.get('admin_password', 'admin123')
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT value FROM admin_settings WHERE key = 'password'")
            row = cur.fetchone()
            return row['value'] if row else 'admin123'  # Default
    except Exception as e:
        print(f"⚠️  Erro ao ler do banco, usando config.json: {e}")
        config = _load_config_file()
        return config.get('admin_password', 'admin123')

def save_admin_password(password):
    """Salva a senha do admin"""
    if not USE_DATABASE:
        config = _load_config_file()
        config['admin_password'] = password
        _save_config_file(config)
        return
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                config['admin_password'] = password
                _save_config_file(config)
                return
            cur = _get_cursor(conn)
            cur.execute("""
                INSERT INTO admin_settings (key, value, updated_at)
                VALUES ('password', %s, CURRENT_TIMESTAMP)
                ON CONFLICT (key) 
                DO UPDATE SET value = %s, updated_at = CURRENT_TIMESTAMP
            """, (password, password))
            conn.commit()
    except Exception as e:
        print(f"⚠️  Erro ao salvar no banco, usando config.json: {e}")
        config = _load_config_file()
        config['admin_password'] = password
        _save_config_file(config)

# ========== FUNÇÕES DE REPAIRS ==========

def get_all_repairs():
    """Obtém todos os reparos"""
    if not USE_DATABASE:
        config = _load_config_file()
        return config.get('repairs', [])
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                return config.get('repairs', [])
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT data FROM repairs ORDER BY created_at DESC")
            rows = cur.fetchall()
            return [row['data'] for row in rows]
    except Exception as e:
        print(f"⚠️  Erro ao ler do banco, usando config.json: {e}")
        config = _load_config_file()
        return config.get('repairs', [])

def get_repair(repair_id):
    """Obtém um reparo específico"""
    if not USE_DATABASE:
        config = _load_config_file()
        repairs = config.get('repairs', [])
        for repair in repairs:
            if repair.get('id') == repair_id:
                return repair
        return None
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                repairs = config.get('repairs', [])
                for repair in repairs:
                    if repair.get('id') == repair_id:
                        return repair
                return None
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT data FROM repairs WHERE id = %s", (repair_id,))
            row = cur.fetchone()
            return row['data'] if row else None
    except Exception as e:
        print(f"⚠️  Erro ao ler do banco, usando config.json: {e}")
        config = _load_config_file()
        repairs = config.get('repairs', [])
        for repair in repairs:
            if repair.get('id') == repair_id:
                return repair
        return None

def save_repair(repair_id, repair_data):
    """Salva ou atualiza um reparo"""
    if not USE_DATABASE:
        config = _load_config_file()
        if 'repairs' not in config:
            config['repairs'] = []
        repairs = config.get('repairs', [])
        # Atualizar ou adicionar
        found = False
        for i, r in enumerate(repairs):
            if r.get('id') == repair_id:
                repairs[i] = repair_data
                found = True
                break
        if not found:
            repairs.append(repair_data)
        config['repairs'] = repairs
        _save_config_file(config)
        return
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                if 'repairs' not in config:
                    config['repairs'] = []
                repairs = config.get('repairs', [])
                found = False
                for i, r in enumerate(repairs):
                    if r.get('id') == repair_id:
                        repairs[i] = repair_data
                        found = True
                        break
                if not found:
                    repairs.append(repair_data)
                config['repairs'] = repairs
                _save_config_file(config)
                return
            cur = _get_cursor(conn)
            data_json = json.dumps(repair_data)
            cur.execute("""
                INSERT INTO repairs (id, data, updated_at)
                VALUES (%s, %s::jsonb, CURRENT_TIMESTAMP)
                ON CONFLICT (id) 
                DO UPDATE SET data = %s::jsonb, updated_at = CURRENT_TIMESTAMP
            """, (repair_id, data_json, data_json))
    except Exception as e:
        print(f"⚠️  Erro ao salvar no banco, usando config.json: {e}")
        config = _load_config_file()
        if 'repairs' not in config:
            config['repairs'] = []
        repairs = config.get('repairs', [])
        found = False
        for i, r in enumerate(repairs):
            if r.get('id') == repair_id:
                repairs[i] = repair_data
                found = True
                break
        if not found:
            repairs.append(repair_data)
        config['repairs'] = repairs
        _save_config_file(config)

def delete_repair(repair_id):
    """Deleta um reparo"""
    if not USE_DATABASE:
        config = _load_config_file()
        repairs = config.get('repairs', [])
        config['repairs'] = [r for r in repairs if r.get('id') != repair_id]
        _save_config_file(config)
        return
    
    try:
        with get_db_connection() as conn:
            if not conn:
                return
            cur = _get_cursor(conn)
            cur.execute("DELETE FROM repairs WHERE id = %s", (repair_id,))
            conn.commit()
    except Exception as e:
        print(f"⚠️  Erro ao deletar do banco: {e}")

# ========== FUNÇÕES DE CHECKLISTS ==========

def get_all_checklists():
    """Obtém todos os checklists"""
    if not USE_DATABASE:
        config = _load_config_file()
        return config.get('checklists', [])
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                return config.get('checklists', [])
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT data FROM checklists ORDER BY created_at DESC")
            rows = cur.fetchall()
            return [row['data'] for row in rows]
    except Exception as e:
        print(f"⚠️  Erro ao ler do banco, usando config.json: {e}")
        config = _load_config_file()
        return config.get('checklists', [])

def get_checklist(checklist_id):
    """Obtém um checklist específico"""
    if not USE_DATABASE:
        config = _load_config_file()
        checklists = config.get('checklists', [])
        for checklist in checklists:
            if checklist.get('id') == checklist_id:
                return checklist
        return None
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                checklists = config.get('checklists', [])
                for checklist in checklists:
                    if checklist.get('id') == checklist_id:
                        return checklist
                return None
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT data FROM checklists WHERE id = %s", (checklist_id,))
            row = cur.fetchone()
            return row['data'] if row else None
    except Exception as e:
        print(f"⚠️  Erro ao ler do banco, usando config.json: {e}")
        config = _load_config_file()
        checklists = config.get('checklists', [])
        for checklist in checklists:
            if checklist.get('id') == checklist_id:
                return checklist
        return None

def get_checklists_by_repair(repair_id):
    """Obtém todos os checklists de um reparo"""
    if not USE_DATABASE:
        config = _load_config_file()
        checklists = config.get('checklists', [])
        return [c for c in checklists if c.get('repair_id') == repair_id]
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                checklists = config.get('checklists', [])
                return [c for c in checklists if c.get('repair_id') == repair_id]
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT data FROM checklists WHERE data->>'repair_id' = %s", (repair_id,))
            rows = cur.fetchall()
            return [row['data'] for row in rows]
    except Exception as e:
        print(f"⚠️  Erro ao ler do banco, usando config.json: {e}")
        config = _load_config_file()
        checklists = config.get('checklists', [])
        return [c for c in checklists if c.get('repair_id') == repair_id]

def save_checklist(checklist_id, checklist_data):
    """Salva ou atualiza um checklist"""
    if not USE_DATABASE:
        config = _load_config_file()
        if 'checklists' not in config:
            config['checklists'] = []
        checklists = config.get('checklists', [])
        # Atualizar ou adicionar
        found = False
        for i, c in enumerate(checklists):
            if c.get('id') == checklist_id:
                checklists[i] = checklist_data
                found = True
                break
        if not found:
            checklists.append(checklist_data)
        config['checklists'] = checklists
        _save_config_file(config)
        return
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                if 'checklists' not in config:
                    config['checklists'] = []
                checklists = config.get('checklists', [])
                found = False
                for i, c in enumerate(checklists):
                    if c.get('id') == checklist_id:
                        checklists[i] = checklist_data
                        found = True
                        break
                if not found:
                    checklists.append(checklist_data)
                config['checklists'] = checklists
                _save_config_file(config)
                return
            cur = _get_cursor(conn)
            data_json = json.dumps(checklist_data)
            cur.execute("""
                INSERT INTO checklists (id, data, updated_at)
                VALUES (%s, %s::jsonb, CURRENT_TIMESTAMP)
                ON CONFLICT (id) 
                DO UPDATE SET data = %s::jsonb, updated_at = CURRENT_TIMESTAMP
            """, (checklist_id, data_json, data_json))
    except Exception as e:
        print(f"⚠️  Erro ao salvar no banco, usando config.json: {e}")
        config = _load_config_file()
        if 'checklists' not in config:
            config['checklists'] = []
        checklists = config.get('checklists', [])
        found = False
        for i, c in enumerate(checklists):
            if c.get('id') == checklist_id:
                checklists[i] = checklist_data
                found = True
                break
        if not found:
            checklists.append(checklist_data)
        config['checklists'] = checklists
        _save_config_file(config)

def delete_checklist(checklist_id):
    """Deleta um checklist"""
    if not USE_DATABASE:
        config = _load_config_file()
        checklists = config.get('checklists', [])
        config['checklists'] = [c for c in checklists if c.get('id') != checklist_id]
        _save_config_file(config)
        return
    
    try:
        with get_db_connection() as conn:
            if not conn:
                return
            cur = _get_cursor(conn)
            cur.execute("DELETE FROM checklists WHERE id = %s", (checklist_id,))
            conn.commit()
    except Exception as e:
        print(f"⚠️  Erro ao deletar do banco: {e}")

# ========== FUNÇÕES DE ORDERS ==========

def get_all_orders():
    """Obtém todas as ordens de retirada"""
    if not USE_DATABASE:
        config = _load_config_file()
        return config.get('orders', [])
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                return config.get('orders', [])
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT data FROM orders ORDER BY created_at DESC")
            rows = cur.fetchall()
            return [row['data'] for row in rows]
    except Exception as e:
        print(f"⚠️  Erro ao ler do banco, usando config.json: {e}")
        config = _load_config_file()
        return config.get('orders', [])

def get_order(order_id):
    """Obtém uma ordem específica"""
    if not USE_DATABASE:
        config = _load_config_file()
        orders = config.get('orders', [])
        for order in orders:
            if order.get('id') == order_id:
                return order
        return None
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                orders = config.get('orders', [])
                for order in orders:
                    if order.get('id') == order_id:
                        return order
                return None
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT data FROM orders WHERE id = %s", (order_id,))
            row = cur.fetchone()
            return row['data'] if row else None
    except Exception as e:
        print(f"⚠️  Erro ao ler do banco, usando config.json: {e}")
        config = _load_config_file()
        orders = config.get('orders', [])
        for order in orders:
            if order.get('id') == order_id:
                return order
        return None

def get_order_by_repair(repair_id):
    """Obtém a ordem de retirada de um reparo"""
    if not USE_DATABASE:
        config = _load_config_file()
        orders = config.get('orders', [])
        for order in orders:
            if order.get('repair_id') == repair_id:
                return order
        return None
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                orders = config.get('orders', [])
                for order in orders:
                    if order.get('repair_id') == repair_id:
                        return order
                return None
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT data FROM orders WHERE repair_id = %s", (repair_id,))
            row = cur.fetchone()
            return row['data'] if row else None
    except Exception as e:
        print(f"⚠️  Erro ao ler do banco, usando config.json: {e}")
        config = _load_config_file()
        orders = config.get('orders', [])
        for order in orders:
            if order.get('repair_id') == repair_id:
                return order
        return None

def save_order(order_id, repair_id, order_data):
    """Salva ou atualiza uma ordem de retirada"""
    if not USE_DATABASE:
        config = _load_config_file()
        if 'orders' not in config:
            config['orders'] = []
        orders = config.get('orders', [])
        # Atualizar ou adicionar
        found = False
        for i, o in enumerate(orders):
            if o.get('id') == order_id:
                orders[i] = order_data
                found = True
                break
        if not found:
            orders.append(order_data)
        config['orders'] = orders
        _save_config_file(config)
        return
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                if 'orders' not in config:
                    config['orders'] = []
                orders = config.get('orders', [])
                found = False
                for i, o in enumerate(orders):
                    if o.get('id') == order_id:
                        orders[i] = order_data
                        found = True
                        break
                if not found:
                    orders.append(order_data)
                config['orders'] = orders
                _save_config_file(config)
                return
            cur = _get_cursor(conn)
            data_json = json.dumps(order_data)
            cur.execute("""
                INSERT INTO orders (id, repair_id, data, updated_at)
                VALUES (%s, %s, %s::jsonb, CURRENT_TIMESTAMP)
                ON CONFLICT (id) 
                DO UPDATE SET data = %s::jsonb, updated_at = CURRENT_TIMESTAMP
            """, (order_id, repair_id, data_json, data_json))
    except Exception as e:
        print(f"⚠️  Erro ao salvar no banco, usando config.json: {e}")
        config = _load_config_file()
        if 'orders' not in config:
            config['orders'] = []
        orders = config.get('orders', [])
        found = False
        for i, o in enumerate(orders):
            if o.get('id') == order_id:
                orders[i] = order_data
                found = True
                break
        if not found:
            orders.append(order_data)
        config['orders'] = orders
        _save_config_file(config)

def delete_order(order_id):
    """Deleta uma ordem de retirada"""
    if not USE_DATABASE:
        config = _load_config_file()
        orders = config.get('orders', [])
        config['orders'] = [o for o in orders if o.get('id') != order_id]
        _save_config_file(config)
        return
    
    try:
        with get_db_connection() as conn:
            if not conn:
                return
            cur = _get_cursor(conn)
            cur.execute("DELETE FROM orders WHERE id = %s", (order_id,))
            conn.commit()
    except Exception as e:
        print(f"⚠️  Erro ao deletar do banco: {e}")

# ========== FUNÇÕES DE FORNECEDORES ==========

def get_all_suppliers():
    """Obtém todos os fornecedores"""
    if not USE_DATABASE:
        config = _load_config_file()
        return config.get('suppliers', [])
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                return config.get('suppliers', [])
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT data FROM suppliers ORDER BY created_at DESC")
            rows = cur.fetchall()
            return [row['data'] for row in rows]
    except Exception as e:
        print(f"⚠️  Erro ao ler do banco, usando config.json: {e}")
        config = _load_config_file()
        return config.get('suppliers', [])

def get_supplier(supplier_id):
    """Obtém um fornecedor específico"""
    if not USE_DATABASE:
        config = _load_config_file()
        suppliers = config.get('suppliers', [])
        for supplier in suppliers:
            if supplier.get('id') == supplier_id:
                return supplier
        return None
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                suppliers = config.get('suppliers', [])
                for supplier in suppliers:
                    if supplier.get('id') == supplier_id:
                        return supplier
                return None
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT data FROM suppliers WHERE id = %s", (supplier_id,))
            row = cur.fetchone()
            if row:
                return row['data']
            return None
    except Exception as e:
        print(f"⚠️  Erro ao ler do banco, usando config.json: {e}")
        config = _load_config_file()
        suppliers = config.get('suppliers', [])
        for supplier in suppliers:
            if supplier.get('id') == supplier_id:
                return supplier
        return None

def save_supplier(supplier_id, supplier_data):
    """Salva ou atualiza um fornecedor"""
    if not USE_DATABASE:
        config = _load_config_file()
        if 'suppliers' not in config:
            config['suppliers'] = []
        suppliers = config.get('suppliers', [])
        # Atualizar ou adicionar
        found = False
        for i, s in enumerate(suppliers):
            if s.get('id') == supplier_id:
                suppliers[i] = supplier_data
                found = True
                break
        if not found:
            suppliers.append(supplier_data)
        config['suppliers'] = suppliers
        _save_config_file(config)
        return
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                if 'suppliers' not in config:
                    config['suppliers'] = []
                suppliers = config.get('suppliers', [])
                found = False
                for i, s in enumerate(suppliers):
                    if s.get('id') == supplier_id:
                        suppliers[i] = supplier_data
                        found = True
                        break
                if not found:
                    suppliers.append(supplier_data)
                config['suppliers'] = suppliers
                _save_config_file(config)
                return
            cur = _get_cursor(conn)
            data_json = json.dumps(supplier_data)
            cur.execute("""
                INSERT INTO suppliers (id, data, updated_at)
                VALUES (%s, %s::jsonb, CURRENT_TIMESTAMP)
                ON CONFLICT (id) 
                DO UPDATE SET data = %s::jsonb, updated_at = CURRENT_TIMESTAMP
            """, (supplier_id, data_json, data_json))
            conn.commit()
    except Exception as e:
        print(f"⚠️  Erro ao salvar no banco, usando config.json: {e}")
        config = _load_config_file()
        if 'suppliers' not in config:
            config['suppliers'] = []
        suppliers = config.get('suppliers', [])
        found = False
        for i, s in enumerate(suppliers):
            if s.get('id') == supplier_id:
                suppliers[i] = supplier_data
                found = True
                break
        if not found:
            suppliers.append(supplier_data)
        config['suppliers'] = suppliers
        _save_config_file(config)

def delete_supplier(supplier_id):
    """Deleta um fornecedor"""
    if not USE_DATABASE:
        config = _load_config_file()
        suppliers = config.get('suppliers', [])
        config['suppliers'] = [s for s in suppliers if s.get('id') != supplier_id]
        _save_config_file(config)
        return
    
    try:
        with get_db_connection() as conn:
            if not conn:
                return
            cur = _get_cursor(conn)
            cur.execute("DELETE FROM suppliers WHERE id = %s", (supplier_id,))
            conn.commit()
    except Exception as e:
        print(f"⚠️  Erro ao deletar do banco: {e}")

# ========== FUNÇÃO DE COMPATIBILIDADE ==========

def load_config():
    """Função de compatibilidade que retorna um dict similar ao config.json"""
    config = {
        'admin_password': get_admin_password(),
        'site_content': get_site_content(),
        'repairs': get_all_repairs(),
        'checklists': get_all_checklists(),
        'orders': get_all_orders()
    }
    return config

def save_config(config):
    """Função de compatibilidade que salva no banco de dados"""
    # Salvar senha do admin
    if 'admin_password' in config:
        save_admin_password(config['admin_password'])
    
    # Salvar conteúdo do site
    if 'site_content' in config:
        site_content = config['site_content']
        for section, data in site_content.items():
            save_site_content_section(section, data)
    
    # Salvar reparos
    if 'repairs' in config:
        for repair in config['repairs']:
            repair_id = repair.get('id')
            if repair_id:
                save_repair(repair_id, repair)
    
    # Salvar checklists
    if 'checklists' in config:
        for checklist in config['checklists']:
            checklist_id = checklist.get('id')
            if checklist_id:
                save_checklist(checklist_id, checklist)
    
    # Salvar ordens
    if 'orders' in config:
        for order in config['orders']:
            order_id = order.get('id')
            repair_id = order.get('repair_id')
            if order_id and repair_id:
                save_order(order_id, repair_id, order)
