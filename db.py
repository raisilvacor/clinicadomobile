"""
Módulo de gerenciamento do banco de dados PostgreSQL
Compatível com Python 3.13 usando psycopg (psycopg3)
"""
import os
import json
from contextlib import contextmanager

# Usar psycopg (psycopg3) que é compatível com Python 3.13
CONFIG_FILE = 'config.json'  # Definir sempre para fallback
USE_DATABASE = True
ConnectionPool = None
dict_row = None

try:
    import psycopg
    from psycopg.rows import dict_row
    
    # Tentar diferentes formas de importar ConnectionPool
    ConnectionPool = None
    import_error_msg = None
    
    # Tentativa 1: psycopg_pool (pacote separado)
    try:
        from psycopg_pool import ConnectionPool
        print("✅ psycopg_pool.ConnectionPool importado com sucesso!")
    except ImportError as e1:
        import_error_msg = str(e1)
        # Tentativa 2: psycopg.pool
        try:
            from psycopg.pool import ConnectionPool
            print("✅ psycopg.pool.ConnectionPool importado com sucesso!")
        except ImportError as e2:
            # Tentativa 3: psycopg import pool
            try:
                import psycopg.pool as pool_module
                ConnectionPool = pool_module.ConnectionPool
                print("✅ psycopg.pool.ConnectionPool importado via módulo!")
            except (ImportError, AttributeError) as e3:
                # Tentativa 4: verificar se está no psycopg diretamente
                if hasattr(psycopg, 'pool'):
                    ConnectionPool = getattr(psycopg.pool, 'ConnectionPool', None)
                    if ConnectionPool:
                        print("✅ ConnectionPool encontrado em psycopg.pool!")
                    else:
                        raise ImportError(f"ConnectionPool não encontrado. Erros: {e1}, {e2}, {e3}")
                else:
                    raise ImportError(f"ConnectionPool não encontrado. Erros: {e1}, {e2}, {e3}")
    
    if ConnectionPool is None:
        raise ImportError("ConnectionPool não pôde ser importado")
    
    PSYCOPG_VERSION = 3
    print("✅ psycopg e ConnectionPool importados com sucesso!")
except ImportError as e:
    USE_DATABASE = False
    ConnectionPool = None
    dict_row = None
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
    global USE_DATABASE, pool, ConnectionPool
    if not USE_DATABASE:
        print("⚠️  Banco de dados desabilitado - usando config.json")
        return None
    if ConnectionPool is None:
        print("❌ ConnectionPool não disponível - usando config.json")
        USE_DATABASE = False
        return None
    if pool is None:
        try:
            print(f"🔌 Conectando ao banco de dados PostgreSQL...")
            print(f"🔌 DATABASE_URL: {DATABASE_URL[:30]}...")  # Mostrar apenas início por segurança
            # Configurar pool com timeout maior e parâmetros otimizados
            # psycopg_pool ConnectionPool aceita: min_size, max_size, timeout, max_waiting, max_idle, reconnect_timeout
            try:
                pool = ConnectionPool(
                    DATABASE_URL,
                    min_size=1,
                    max_size=10,  # Reduzir max_size para evitar esgotamento
                    timeout=60,  # Aumentar timeout para 60 segundos
                    max_waiting=10,  # Limitar número de requisições esperando
                    max_idle=300,  # Fechar conexões idle após 5 minutos
                    reconnect_timeout=10  # Timeout para reconexão
                )
            except TypeError:
                # Se alguns parâmetros não forem suportados, usar apenas os básicos
                print("⚠️  Usando configuração básica do pool (alguns parâmetros não suportados)")
                pool = ConnectionPool(
                    DATABASE_URL,
                    min_size=1,
                    max_size=10,
                    timeout=60
                )
            print("✅ Pool de conexões criado com sucesso!")
            # Testar conexão criando uma conexão direta primeiro
            test_conn = pool.getconn(timeout=10)  # Timeout de 10s para teste
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
    """Context manager para obter conexão do pool com retry automático"""
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
    max_retries = 2
    for attempt in range(max_retries):
        try:
            # Obter conexão com timeout reduzido
            try:
                conn = pool.getconn(timeout=10)  # Timeout de 10s para obter conexão
            except Exception as getconn_error:
                error_msg = str(getconn_error).lower()
                if 'timeout' in error_msg or "couldn't get a connection" in error_msg:
                    print(f"⚠️  Timeout ao obter conexão do pool (tentativa {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        # Tentar reinicializar o pool
                        try:
                            if pool:
                                pool.close()
                        except:
                            pass
                        pool = None
                        init_db()
                        if pool is None:
                            yield None
                            return
                        continue
                    else:
                        raise
                else:
                    raise
            
            # Verificar se a conexão está válida
            try:
                test_cur = conn.cursor()
                test_cur.execute("SELECT 1")
                test_cur.fetchone()
                test_cur.close()
            except Exception as conn_check_error:
                # Conexão inválida, descartar e tentar novamente
                if conn:
                    try:
                        pool.putconn(conn, close=True)  # Fechar conexão inválida
                    except:
                        pass
                conn = None
                if attempt < max_retries - 1:
                    print(f"⚠️  Conexão inválida detectada, tentando reconectar... (tentativa {attempt + 1}/{max_retries})")
                    continue
                else:
                    raise
            
            # Conexão válida, usar normalmente
            yield conn
            if conn:
                conn.commit()
            break  # Sucesso, sair do loop
        except Exception as e:
            error_msg = str(e).lower()
            # Verificar se é erro de conexão perdida
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
                try:
                    # Tentar retornar conexão ao pool, mas fechar se estiver ruim
                    if 'connection is lost' in error_msg or 'connection' in error_msg and 'lost' in error_msg:
                        pool.putconn(conn, close=True)
                    else:
                        pool.putconn(conn)
                except:
                    pass
                conn = None
            
            # Se for erro de conexão e ainda temos tentativas, tentar reconectar
            if ('connection' in error_msg and ('lost' in error_msg or 'closed' in error_msg or 'timeout' in error_msg)) and attempt < max_retries - 1:
                print(f"⚠️  Erro de conexão detectado: {e}, tentando reconectar... (tentativa {attempt + 1}/{max_retries})")
                # Tentar reinicializar o pool se necessário
                try:
                    if pool:
                        pool.close()
                except:
                    pass
                pool = None
                init_db()
                if pool is None:
                    yield None
                    return
                continue
            else:
                print(f"⚠️  Erro na transação: {e}")
                if attempt == max_retries - 1:
                    raise
        finally:
            if conn and attempt == max_retries - 1:
                try:
                    pool.putconn(conn)
                except:
                    pass

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
    global USE_DATABASE, pool
    if not USE_DATABASE:
        print("⚠️  create_tables: Banco desabilitado, pulando criação de tabelas")
        return
    
    # Garantir que o pool está inicializado
    if pool is None:
        init_db()
        if pool is None:
            print("⚠️  create_tables: Pool não disponível")
            return
    
    try:
        print("📋 Criando tabelas no banco de dados...")
        with get_db_connection() as conn:
            if not conn:
                print("⚠️  create_tables: Sem conexão disponível")
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
            
            # Tabela para produtos da loja
            cur.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id VARCHAR(50) PRIMARY KEY,
                    data JSONB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS brands (
                    id VARCHAR(50) PRIMARY KEY,
                    data JSONB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tabela para senhas de clientes (associadas ao CPF)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS customer_passwords (
                    cpf VARCHAR(11) PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tabela para solicitações de orçamento
            cur.execute("""
                CREATE TABLE IF NOT EXISTS budget_requests (
                    id VARCHAR(50) PRIMARY KEY,
                    data JSONB NOT NULL,
                    status VARCHAR(20) DEFAULT 'pendente',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tabela para tokens de notificação push (FCM)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS push_tokens (
                    id SERIAL PRIMARY KEY,
                    cpf VARCHAR(11) NOT NULL,
                    token TEXT NOT NULL,
                    device_info JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(cpf, token)
                )
            """)
            
            # Índices para melhor performance
            cur.execute("CREATE INDEX IF NOT EXISTS idx_repairs_repair_id ON repairs(id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_checklists_id ON checklists(id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_repair_id ON orders(repair_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_id ON orders(id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_suppliers_id ON suppliers(id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_customer_passwords_cpf ON customer_passwords(cpf)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_budget_requests_status ON budget_requests(status)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_push_tokens_cpf ON push_tokens(cpf)")
            # Criar índices para pending_notifications se a tabela existir
            try:
                # Verificar se o índice já existe antes de criar
                cur.execute("""
                    SELECT 1 FROM pg_indexes 
                    WHERE indexname = 'idx_pending_notifications_cpf'
                """)
                if not cur.fetchone():
                    cur.execute("CREATE INDEX idx_pending_notifications_cpf ON pending_notifications(cpf)")
                
                cur.execute("""
                    SELECT 1 FROM pg_indexes 
                    WHERE indexname = 'idx_pending_notifications_created'
                """)
                if not cur.fetchone():
                    cur.execute("CREATE INDEX idx_pending_notifications_created ON pending_notifications(created_at)")
            except Exception as e:
                print(f"⚠️  Erro ao criar índices de notificações: {e}")
            
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

# ========== FUNÇÕES DE PRODUTOS (LOJA) ==========

def get_all_products():
    """Obtém todos os produtos"""
    if not USE_DATABASE:
        config = _load_config_file()
        return config.get('products', [])
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                return config.get('products', [])
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT data FROM products ORDER BY created_at DESC")
            rows = cur.fetchall()
            return [row['data'] for row in rows]
    except Exception as e:
        print(f"⚠️  Erro ao ler produtos do banco, usando config.json: {e}")
        config = _load_config_file()
        return config.get('products', [])

def get_product(product_id):
    """Obtém um produto específico"""
    if not USE_DATABASE:
        config = _load_config_file()
        products = config.get('products', [])
        for product in products:
            if product.get('id') == product_id:
                return product
        return None
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                products = config.get('products', [])
                for product in products:
                    if product.get('id') == product_id:
                        return product
                return None
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT data FROM products WHERE id = %s", (product_id,))
            row = cur.fetchone()
            return row['data'] if row else None
    except Exception as e:
        print(f"⚠️  Erro ao ler produto do banco, usando config.json: {e}")
        config = _load_config_file()
        products = config.get('products', [])
        for product in products:
            if product.get('id') == product_id:
                return product
        return None

def save_product(product_id, product_data):
    """Salva ou atualiza um produto"""
    if not USE_DATABASE:
        config = _load_config_file()
        if 'products' not in config:
            config['products'] = []
        products = config.get('products', [])
        found = False
        for i, p in enumerate(products):
            if p.get('id') == product_id:
                products[i] = product_data
                found = True
                break
        if not found:
            products.append(product_data)
        config['products'] = products
        _save_config_file(config)
        return
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                if 'products' not in config:
                    config['products'] = []
                products = config.get('products', [])
                found = False
                for i, p in enumerate(products):
                    if p.get('id') == product_id:
                        products[i] = product_data
                        found = True
                        break
                if not found:
                    products.append(product_data)
                config['products'] = products
                _save_config_file(config)
                return
            cur = _get_cursor(conn)
            data_json = json.dumps(product_data)
            cur.execute("""
                INSERT INTO products (id, data, updated_at)
                VALUES (%s, %s::jsonb, CURRENT_TIMESTAMP)
                ON CONFLICT (id) 
                DO UPDATE SET data = %s::jsonb, updated_at = CURRENT_TIMESTAMP
            """, (product_id, data_json, data_json))
            conn.commit()
    except Exception as e:
        print(f"⚠️  Erro ao salvar produto no banco, salvando em config.json: {e}")
        config = _load_config_file()
        if 'products' not in config:
            config['products'] = []
        products = config.get('products', [])
        found = False
        for i, p in enumerate(products):
            if p.get('id') == product_id:
                products[i] = product_data
                found = True
                break
        if not found:
            products.append(product_data)
        config['products'] = products
        _save_config_file(config)

def delete_product(product_id):
    """Deleta um produto"""
    if not USE_DATABASE:
        config = _load_config_file()
        products = config.get('products', [])
        config['products'] = [p for p in products if p.get('id') != product_id]
        _save_config_file(config)
        return
    
    try:
        with get_db_connection() as conn:
            if not conn:
                return
            cur = _get_cursor(conn)
            cur.execute("DELETE FROM products WHERE id = %s", (product_id,))
            conn.commit()
    except Exception as e:
        print(f"⚠️  Erro ao deletar produto do banco: {e}")

# ========== FUNÇÕES DE BRANDS ==========

def get_all_brands():
    """Obtém todas as marcas"""
    if not USE_DATABASE:
        config = _load_config_file()
        return config.get('brands', [])
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                return config.get('brands', [])
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT data FROM brands ORDER BY created_at ASC")
            rows = cur.fetchall()
            return [row['data'] for row in rows]
    except Exception as e:
        print(f"⚠️  Erro ao ler marcas do banco, usando config.json: {e}")
        config = _load_config_file()
        return config.get('brands', [])

def get_brand(brand_id):
    """Obtém uma marca específica"""
    if not USE_DATABASE:
        config = _load_config_file()
        brands = config.get('brands', [])
        for brand in brands:
            if brand.get('id') == brand_id:
                return brand
        return None
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                brands = config.get('brands', [])
                for brand in brands:
                    if brand.get('id') == brand_id:
                        return brand
                return None
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT data FROM brands WHERE id = %s", (brand_id,))
            row = cur.fetchone()
            return row['data'] if row else None
    except Exception as e:
        print(f"⚠️  Erro ao ler marca do banco, usando config.json: {e}")
        config = _load_config_file()
        brands = config.get('brands', [])
        for brand in brands:
            if brand.get('id') == brand_id:
                return brand
        return None

def save_brand(brand_id, brand_data):
    """Salva ou atualiza uma marca"""
    if not USE_DATABASE:
        config = _load_config_file()
        if 'brands' not in config:
            config['brands'] = []
        brands = config.get('brands', [])
        found = False
        for i, b in enumerate(brands):
            if b.get('id') == brand_id:
                brands[i] = brand_data
                found = True
                break
        if not found:
            brands.append(brand_data)
        config['brands'] = brands
        _save_config_file(config)
        return
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                if 'brands' not in config:
                    config['brands'] = []
                brands = config.get('brands', [])
                found = False
                for i, b in enumerate(brands):
                    if b.get('id') == brand_id:
                        brands[i] = brand_data
                        found = True
                        break
                if not found:
                    brands.append(brand_data)
                config['brands'] = brands
                _save_config_file(config)
                return
            cur = _get_cursor(conn)
            data_json = json.dumps(brand_data)
            cur.execute("""
                INSERT INTO brands (id, data, updated_at)
                VALUES (%s, %s::jsonb, CURRENT_TIMESTAMP)
                ON CONFLICT (id) 
                DO UPDATE SET data = %s::jsonb, updated_at = CURRENT_TIMESTAMP
            """, (brand_id, data_json, data_json))
            conn.commit()
    except Exception as e:
        print(f"⚠️  Erro ao salvar marca no banco, salvando em config.json: {e}")
        config = _load_config_file()
        if 'brands' not in config:
            config['brands'] = []
        brands = config.get('brands', [])
        found = False
        for i, b in enumerate(brands):
            if b.get('id') == brand_id:
                brands[i] = brand_data
                found = True
                break
        if not found:
            brands.append(brand_data)
        config['brands'] = brands
        _save_config_file(config)

def delete_brand(brand_id):
    """Deleta uma marca"""
    if not USE_DATABASE:
        config = _load_config_file()
        brands = config.get('brands', [])
        config['brands'] = [b for b in brands if b.get('id') != brand_id]
        _save_config_file(config)
        return
    
    try:
        with get_db_connection() as conn:
            if not conn:
                return
            cur = _get_cursor(conn)
            cur.execute("DELETE FROM brands WHERE id = %s", (brand_id,))
            conn.commit()
    except Exception as e:
        print(f"⚠️  Erro ao deletar marca do banco: {e}")

# ========== FUNÇÕES DE SENHAS DE CLIENTES ==========

def get_customer_password_hash(cpf):
    """Obtém o hash da senha de um cliente pelo CPF"""
    if not USE_DATABASE:
        config = _load_config_file()
        customer_passwords = config.get('customer_passwords', {})
        return customer_passwords.get(cpf)
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                customer_passwords = config.get('customer_passwords', {})
                return customer_passwords.get(cpf)
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT password_hash FROM customer_passwords WHERE cpf = %s", (cpf,))
            row = cur.fetchone()
            return row['password_hash'] if row else None
    except Exception as e:
        print(f"⚠️  Erro ao ler senha do banco: {e}")
        config = _load_config_file()
        customer_passwords = config.get('customer_passwords', {})
        return customer_passwords.get(cpf)

def save_customer_password(cpf, password_hash):
    """Salva ou atualiza a senha de um cliente"""
    if not USE_DATABASE:
        config = _load_config_file()
        if 'customer_passwords' not in config:
            config['customer_passwords'] = {}
        config['customer_passwords'][cpf] = password_hash
        _save_config_file(config)
        return
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                if 'customer_passwords' not in config:
                    config['customer_passwords'] = {}
                config['customer_passwords'][cpf] = password_hash
                _save_config_file(config)
                return
            cur = _get_cursor(conn)
            cur.execute("""
                INSERT INTO customer_passwords (cpf, password_hash, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (cpf) 
                DO UPDATE SET password_hash = %s, updated_at = CURRENT_TIMESTAMP
            """, (cpf, password_hash, password_hash))
            conn.commit()
    except Exception as e:
        print(f"⚠️  Erro ao salvar senha no banco: {e}")
        config = _load_config_file()
        if 'customer_passwords' not in config:
            config['customer_passwords'] = {}
        config['customer_passwords'][cpf] = password_hash
        _save_config_file(config)

def get_repairs_by_cpf(cpf):
    """Obtém todos os reparos de um cliente pelo CPF"""
    repairs = get_all_repairs()
    cpf_clean = cpf.replace('.', '').replace('-', '').replace(' ', '')
    return [r for r in repairs if r.get('customer_cpf', '').replace('.', '').replace('-', '').replace(' ', '') == cpf_clean]

# ========== FUNÇÕES DE SOLICITAÇÕES DE ORÇAMENTO ==========

def get_all_budget_requests():
    """Obtém todas as solicitações de orçamento"""
    if not USE_DATABASE:
        config = _load_config_file()
        return config.get('budget_requests', [])
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                return config.get('budget_requests', [])
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT id, data, status, created_at FROM budget_requests ORDER BY created_at DESC")
            rows = cur.fetchall()
            return [{'id': row['id'], 'status': row['status'], 'created_at': row['created_at'].isoformat() if row['created_at'] else None, **row['data']} for row in rows]
    except Exception as e:
        print(f"⚠️  Erro ao ler solicitações do banco: {e}")
        config = _load_config_file()
        return config.get('budget_requests', [])

def save_budget_request(request_id, request_data):
    """Salva uma solicitação de orçamento"""
    if not USE_DATABASE:
        config = _load_config_file()
        if 'budget_requests' not in config:
            config['budget_requests'] = []
        config['budget_requests'].append({'id': request_id, **request_data})
        _save_config_file(config)
        return
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                if 'budget_requests' not in config:
                    config['budget_requests'] = []
                config['budget_requests'].append({'id': request_id, **request_data})
                _save_config_file(config)
                return
            cur = _get_cursor(conn)
            data_json = json.dumps(request_data)
            cur.execute("""
                INSERT INTO budget_requests (id, data, status, updated_at)
                VALUES (%s, %s::jsonb, 'pendente', CURRENT_TIMESTAMP)
            """, (request_id, data_json))
            conn.commit()
    except Exception as e:
        print(f"⚠️  Erro ao salvar solicitação no banco: {e}")
        config = _load_config_file()
        if 'budget_requests' not in config:
            config['budget_requests'] = []
        config['budget_requests'].append({'id': request_id, **request_data})
        _save_config_file(config)

# ========== FUNÇÕES DE PUSH TOKENS ==========

def save_push_token(cpf, subscription, device_info=None):
    """Salva ou atualiza subscription de notificação push"""
    if not USE_DATABASE:
        return
    
    try:
        with get_db_connection() as conn:
            if not conn:
                return
            cur = _get_cursor(conn)
            
            # Converter subscription para JSON se for dict
            if isinstance(subscription, dict):
                subscription_json = json.dumps(subscription)
            else:
                subscription_json = subscription
            
            # Criar objeto com subscription e device_info
            token_data = {
                'subscription': subscription_json if isinstance(subscription_json, str) else json.dumps(subscription_json),
                'device_info': device_info or {}
            }
            token_json = json.dumps(token_data)
            
            device_json = json.dumps(device_info) if device_info else None
            cur.execute("""
                INSERT INTO push_tokens (cpf, token, device_info, updated_at)
                VALUES (%s, %s, %s::jsonb, CURRENT_TIMESTAMP)
                ON CONFLICT (cpf) 
                DO UPDATE SET token = EXCLUDED.token, device_info = EXCLUDED.device_info, updated_at = CURRENT_TIMESTAMP
            """, (cpf, token_json, device_json))
            conn.commit()
    except Exception as e:
        print(f"⚠️  Erro ao salvar subscription push: {e}")

def get_push_tokens_by_cpf(cpf):
    """Obtém todas as subscriptions de push de um cliente"""
    if not USE_DATABASE:
        return []
    
    try:
        with get_db_connection() as conn:
            if not conn:
                return []
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT token FROM push_tokens WHERE cpf = %s", (cpf,))
            rows = cur.fetchall()
            tokens = []
            for row in rows:
                try:
                    token_data = json.loads(row['token']) if isinstance(row['token'], str) else row['token']
                    tokens.append(token_data)
                except:
                    # Fallback para formato antigo
                    tokens.append({'subscription': row['token']})
            return tokens
    except Exception as e:
        print(f"⚠️  Erro ao ler subscriptions push: {e}")
        return []

# ========== FUNÇÕES DE NOTIFICAÇÕES PENDENTES ==========

def save_pending_notification(cpf, repair_id, notification_type, title, body, data=None):
    """Salva uma notificação pendente para ser enviada ao cliente"""
    if not USE_DATABASE:
        return
    
    try:
        with get_db_connection() as conn:
            if not conn:
                return
            cur = _get_cursor(conn)
            data_json = json.dumps(data) if data else None
            cur.execute("""
                INSERT INTO pending_notifications (cpf, repair_id, notification_type, title, body, data, created_at)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, CURRENT_TIMESTAMP)
            """, (cpf, repair_id, notification_type, title, body, data_json))
            conn.commit()
            print(f"✅ Notificação pendente salva para CPF {cpf}: {title}")
    except Exception as e:
        print(f"⚠️  Erro ao salvar notificação pendente: {e}")

def get_pending_notifications(cpf, since_timestamp=None):
    """Obtém notificações pendentes para um CPF desde um timestamp"""
    if not USE_DATABASE:
        return []
    
    try:
        with get_db_connection() as conn:
            if not conn:
                return []
            cur = _get_cursor(conn, dict_cursor=True)
            if since_timestamp:
                cur.execute("""
                    SELECT id, repair_id, notification_type, title, body, data, created_at
                    FROM pending_notifications
                    WHERE cpf = %s AND created_at > %s AND sent_at IS NULL
                    ORDER BY created_at ASC
                """, (cpf, since_timestamp))
            else:
                cur.execute("""
                    SELECT id, repair_id, notification_type, title, body, data, created_at
                    FROM pending_notifications
                    WHERE cpf = %s AND sent_at IS NULL
                    ORDER BY created_at ASC
                """, (cpf,))
            rows = cur.fetchall()
            notifications = []
            for row in rows:
                try:
                    notification = {
                        'id': row['id'],
                        'repair_id': row['repair_id'],
                        'type': row['notification_type'],
                        'title': row['title'],
                        'body': row['body'],
                        'data': json.loads(row['data']) if row['data'] else {},
                        'timestamp': row['created_at'].isoformat() if hasattr(row['created_at'], 'isoformat') else str(row['created_at'])
                    }
                    notifications.append(notification)
                except Exception as e:
                    print(f"⚠️  Erro ao processar notificação: {e}")
            return notifications
    except Exception as e:
        print(f"⚠️  Erro ao ler notificações pendentes: {e}")
        return []

def mark_notification_sent(notification_id):
    """Marca uma notificação como enviada"""
    if not USE_DATABASE:
        return
    
    try:
        with get_db_connection() as conn:
            if not conn:
                return
            cur = _get_cursor(conn)
            cur.execute("""
                UPDATE pending_notifications
                SET sent_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (notification_id,))
            conn.commit()
    except Exception as e:
        print(f"⚠️  Erro ao marcar notificação como enviada: {e}")

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
