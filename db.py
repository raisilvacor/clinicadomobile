"""
Módulo de gerenciamento do banco de dados PostgreSQL
"""
import os
import json
from contextlib import contextmanager

# Tentar importar psycopg3 primeiro, depois psycopg2 como fallback
try:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.pool import ConnectionPool
    PSYCOPG_VERSION = 3
    dict_row_available = True
except ImportError:
    dict_row = None
    dict_row_available = False
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor, Json
        from psycopg2.pool import SimpleConnectionPool
        PSYCOPG_VERSION = 2
    except ImportError:
        raise ImportError("É necessário instalar psycopg[binary] ou psycopg2-binary")

# URL do banco de dados do Render
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://rai:nk1HAfaFPhbOvg34lqWl7YC5LfPNmNS3@dpg-d57kenggjchc739lcorg-a.virginia-postgres.render.com/mobiledb_p0w2')

# Pool de conexões
pool = None

def init_db():
    """Inicializa o pool de conexões"""
    global pool
    if pool is None:
        if PSYCOPG_VERSION == 3:
            pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=20)
        else:
            pool = SimpleConnectionPool(1, 20, DATABASE_URL)
    return pool

@contextmanager
def get_db_connection():
    """Context manager para obter conexão do pool"""
    pool = init_db()
    if PSYCOPG_VERSION == 3:
        conn = pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            pool.putconn(conn)
    else:
        conn = pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            pool.putconn(conn)

def _get_cursor(conn, dict_cursor=False):
    """Helper para obter cursor compatível com psycopg2 e psycopg3"""
    if dict_cursor:
        if PSYCOPG_VERSION == 3:
            return conn.cursor(row_factory=dict_row)
        else:
            return conn.cursor(cursor_factory=RealDictCursor)
    else:
        return conn.cursor()

def create_tables():
    """Cria as tabelas necessárias no banco de dados"""
    with get_db_connection() as conn:
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
        
        # Índices para melhor performance
        cur.execute("CREATE INDEX IF NOT EXISTS idx_repairs_repair_id ON repairs(id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_checklists_id ON checklists(id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_repair_id ON orders(repair_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_id ON orders(id)")
        
        conn.commit()

# ========== FUNÇÕES DE SITE CONTENT ==========

def get_site_content():
    """Obtém todo o conteúdo do site"""
    with get_db_connection() as conn:
        cur = _get_cursor(conn, dict_cursor=True)
        cur.execute("SELECT section, data FROM site_content")
        rows = cur.fetchall()
        
        content = {}
        for row in rows:
            content[row['section']] = row['data']
        
        return content

def save_site_content_section(section, data):
    """Salva uma seção do conteúdo do site"""
    with get_db_connection() as conn:
        cur = _get_cursor(conn)
        if PSYCOPG_VERSION == 3:
            import json as json_module
            data_json = json_module.dumps(data)
            cur.execute("""
                INSERT INTO site_content (section, data, updated_at)
                VALUES (%s, %s::jsonb, CURRENT_TIMESTAMP)
                ON CONFLICT (section) 
                DO UPDATE SET data = %s::jsonb, updated_at = CURRENT_TIMESTAMP
            """, (section, data_json, data_json))
        else:
            cur.execute("""
                INSERT INTO site_content (section, data, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (section) 
                DO UPDATE SET data = %s, updated_at = CURRENT_TIMESTAMP
            """, (section, Json(data), Json(data)))

def get_site_content_section(section):
    """Obtém uma seção específica do conteúdo do site"""
    with get_db_connection() as conn:
        cur = _get_cursor(conn, dict_cursor=True)
        cur.execute("SELECT data FROM site_content WHERE section = %s", (section,))
        row = cur.fetchone()
        return row['data'] if row else None

# ========== FUNÇÕES DE ADMIN SETTINGS ==========

def get_admin_password():
    """Obtém a senha do admin"""
    with get_db_connection() as conn:
        cur = _get_cursor(conn, dict_cursor=True)
        cur.execute("SELECT value FROM admin_settings WHERE key = 'password'")
        row = cur.fetchone()
        return row['value'] if row else 'admin123'  # Default

def save_admin_password(password):
    """Salva a senha do admin"""
    with get_db_connection() as conn:
        cur = _get_cursor(conn)
        cur.execute("""
            INSERT INTO admin_settings (key, value, updated_at)
            VALUES ('password', %s, CURRENT_TIMESTAMP)
            ON CONFLICT (key) 
            DO UPDATE SET value = %s, updated_at = CURRENT_TIMESTAMP
        """, (password, password))
        conn.commit()

# ========== FUNÇÕES DE REPAIRS ==========

def get_all_repairs():
    """Obtém todos os reparos"""
    with get_db_connection() as conn:
        cur = _get_cursor(conn, dict_cursor=True)
        cur.execute("SELECT data FROM repairs ORDER BY created_at DESC")
        rows = cur.fetchall()
        return [row['data'] for row in rows]

def get_repair(repair_id):
    """Obtém um reparo específico"""
    with get_db_connection() as conn:
        cur = _get_cursor(conn, dict_cursor=True)
        cur.execute("SELECT data FROM repairs WHERE id = %s", (repair_id,))
        row = cur.fetchone()
        return row['data'] if row else None

def save_repair(repair_id, repair_data):
    """Salva ou atualiza um reparo"""
    with get_db_connection() as conn:
        cur = _get_cursor(conn)
        if PSYCOPG_VERSION == 3:
            import json as json_module
            data_json = json_module.dumps(repair_data)
            cur.execute("""
                INSERT INTO repairs (id, data, updated_at)
                VALUES (%s, %s::jsonb, CURRENT_TIMESTAMP)
                ON CONFLICT (id) 
                DO UPDATE SET data = %s::jsonb, updated_at = CURRENT_TIMESTAMP
            """, (repair_id, data_json, data_json))
        else:
            cur.execute("""
                INSERT INTO repairs (id, data, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (id) 
                DO UPDATE SET data = %s, updated_at = CURRENT_TIMESTAMP
            """, (repair_id, Json(repair_data), Json(repair_data)))

def delete_repair(repair_id):
    """Deleta um reparo"""
    with get_db_connection() as conn:
        cur = _get_cursor(conn)
        cur.execute("DELETE FROM repairs WHERE id = %s", (repair_id,))
        conn.commit()

# ========== FUNÇÕES DE CHECKLISTS ==========

def get_all_checklists():
    """Obtém todos os checklists"""
    with get_db_connection() as conn:
        cur = _get_cursor(conn, dict_cursor=True)
        cur.execute("SELECT data FROM checklists ORDER BY created_at DESC")
        rows = cur.fetchall()
        return [row['data'] for row in rows]

def get_checklist(checklist_id):
    """Obtém um checklist específico"""
    with get_db_connection() as conn:
        cur = _get_cursor(conn, dict_cursor=True)
        cur.execute("SELECT data FROM checklists WHERE id = %s", (checklist_id,))
        row = cur.fetchone()
        return row['data'] if row else None

def get_checklists_by_repair(repair_id):
    """Obtém todos os checklists de um reparo"""
    with get_db_connection() as conn:
        cur = _get_cursor(conn, dict_cursor=True)
        cur.execute("SELECT data FROM checklists WHERE data->>'repair_id' = %s", (repair_id,))
        rows = cur.fetchall()
        return [row['data'] for row in rows]

def save_checklist(checklist_id, checklist_data):
    """Salva ou atualiza um checklist"""
    with get_db_connection() as conn:
        cur = _get_cursor(conn)
        if PSYCOPG_VERSION == 3:
            import json as json_module
            data_json = json_module.dumps(checklist_data)
            cur.execute("""
                INSERT INTO checklists (id, data, updated_at)
                VALUES (%s, %s::jsonb, CURRENT_TIMESTAMP)
                ON CONFLICT (id) 
                DO UPDATE SET data = %s::jsonb, updated_at = CURRENT_TIMESTAMP
            """, (checklist_id, data_json, data_json))
        else:
            cur.execute("""
                INSERT INTO checklists (id, data, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (id) 
                DO UPDATE SET data = %s, updated_at = CURRENT_TIMESTAMP
            """, (checklist_id, Json(checklist_data), Json(checklist_data)))

def delete_checklist(checklist_id):
    """Deleta um checklist"""
    with get_db_connection() as conn:
        cur = _get_cursor(conn)
        cur.execute("DELETE FROM checklists WHERE id = %s", (checklist_id,))
        conn.commit()

# ========== FUNÇÕES DE ORDERS ==========

def get_all_orders():
    """Obtém todas as ordens de retirada"""
    with get_db_connection() as conn:
        cur = _get_cursor(conn, dict_cursor=True)
        cur.execute("SELECT data FROM orders ORDER BY created_at DESC")
        rows = cur.fetchall()
        return [row['data'] for row in rows]

def get_order(order_id):
    """Obtém uma ordem específica"""
    with get_db_connection() as conn:
        cur = _get_cursor(conn, dict_cursor=True)
        cur.execute("SELECT data FROM orders WHERE id = %s", (order_id,))
        row = cur.fetchone()
        return row['data'] if row else None

def get_order_by_repair(repair_id):
    """Obtém a ordem de retirada de um reparo"""
    with get_db_connection() as conn:
        cur = _get_cursor(conn, dict_cursor=True)
        cur.execute("SELECT data FROM orders WHERE repair_id = %s", (repair_id,))
        row = cur.fetchone()
        return row['data'] if row else None

def save_order(order_id, repair_id, order_data):
    """Salva ou atualiza uma ordem de retirada"""
    with get_db_connection() as conn:
        cur = _get_cursor(conn)
        if PSYCOPG_VERSION == 3:
            import json as json_module
            data_json = json_module.dumps(order_data)
            cur.execute("""
                INSERT INTO orders (id, repair_id, data, updated_at)
                VALUES (%s, %s, %s::jsonb, CURRENT_TIMESTAMP)
                ON CONFLICT (id) 
                DO UPDATE SET data = %s::jsonb, updated_at = CURRENT_TIMESTAMP
            """, (order_id, repair_id, data_json, data_json))
        else:
            cur.execute("""
                INSERT INTO orders (id, repair_id, data, updated_at)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (id) 
                DO UPDATE SET data = %s, updated_at = CURRENT_TIMESTAMP
            """, (order_id, repair_id, Json(order_data), Json(order_data)))

def delete_order(order_id):
    """Deleta uma ordem de retirada"""
    with get_db_connection() as conn:
        cur = _get_cursor(conn)
        cur.execute("DELETE FROM orders WHERE id = %s", (order_id,))
        conn.commit()

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

