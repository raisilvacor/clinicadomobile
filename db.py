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
    global USE_DATABASE, pool, ConnectionPool, DATABASE_URL
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
            
            # Garantir SSL na string de conexão
            if 'sslmode' not in DATABASE_URL:
                if '?' in DATABASE_URL:
                    DATABASE_URL += '&sslmode=require'
                else:
                    DATABASE_URL += '?sslmode=require'
                    
            print(f"🔌 DATABASE_URL: {DATABASE_URL[:40]}...")  # Mostrar apenas início por segurança
            
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
    
    # Usar conexão direta para garantir que as tabelas sejam criadas
    conn = None
    try:
        print("📋 Criando tabelas no banco de dados...")
        
        # Obter DATABASE_URL
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            print("⚠️  create_tables: DATABASE_URL não configurada")
            return
        
        # Criar conexão direta (não do pool) para criação de tabelas
        import psycopg
        conn = psycopg.connect(database_url, autocommit=True)
        cur = conn.cursor()
        
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
        
        # Tabela para transações financeiras (Fluxo de Caixa)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id VARCHAR(50) PRIMARY KEY,
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
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS customer_passwords (
                cpf VARCHAR(11) PRIMARY KEY,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS budget_requests (
                id VARCHAR(50) PRIMARY KEY,
                data JSONB NOT NULL,
                status VARCHAR(20) DEFAULT 'pendente',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
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
        
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_repairs_repair_id ON repairs(id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_checklists_id ON checklists(id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_repair_id ON orders(repair_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_id ON orders(id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_suppliers_id ON suppliers(id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_customer_passwords_cpf ON customer_passwords(cpf)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_budget_requests_status ON budget_requests(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_push_tokens_cpf ON push_tokens(cpf)")
        
            
        # Tabela para usuários do admin
        try:
            print("📋 Criando tabela admin_users...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS admin_users (
                    id VARCHAR(50) PRIMARY KEY,
                    username VARCHAR(100) UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    name VARCHAR(200) NOT NULL,
                    email VARCHAR(200),
                    phone VARCHAR(20),
                    permissions JSONB DEFAULT '{}',
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("✅ Tabela admin_users criada/verificada")
        except Exception as e:
            print(f"⚠️  Erro ao criar tabela admin_users: {e}")
            import traceback
            traceback.print_exc()
        
        # Tabela para técnicos
        try:
            print("📋 Criando tabela technicians...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS technicians (
                    id VARCHAR(50) PRIMARY KEY,
                    name VARCHAR(200) NOT NULL,
                    cpf VARCHAR(11) UNIQUE,
                    email VARCHAR(200),
                    phone VARCHAR(20),
                    address TEXT,
                    specialties JSONB DEFAULT '[]',
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("✅ Tabela technicians criada/verificada")
        except Exception as e:
            print(f"⚠️  Erro ao criar tabela technicians: {e}")
            import traceback
            traceback.print_exc()
        
        # Índices
        try:
            print("📋 Criando índices para admin_users e technicians...")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_admin_users_username ON admin_users(username)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_admin_users_active ON admin_users(is_active)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_technicians_cpf ON technicians(cpf)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_technicians_active ON technicians(is_active)")
            print("✅ Índices criados/verificados")
        except Exception as e:
            print(f"⚠️  Erro ao criar índices: {e}")
            import traceback
            traceback.print_exc()
        
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
        
        # Com autocommit=True, as tabelas já foram criadas automaticamente
        # Verificar se as tabelas foram criadas
        try:
            cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'admin_users')")
            admin_users_exists = cur.fetchone()[0]
            cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'technicians')")
            technicians_exists = cur.fetchone()[0]
            print(f"✅ Verificação: admin_users existe = {admin_users_exists}, technicians existe = {technicians_exists}")
            
            if not admin_users_exists:
                print("⚠️  ATENÇÃO: admin_users não existe! Criando novamente...")
                cur.execute("""
                    CREATE TABLE admin_users (
                        id VARCHAR(50) PRIMARY KEY,
                        username VARCHAR(100) UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        name VARCHAR(200) NOT NULL,
                        email VARCHAR(200),
                        phone VARCHAR(20),
                        permissions JSONB DEFAULT '{}',
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                print("✅ Tabela admin_users criada!")
            
            if not technicians_exists:
                print("⚠️  ATENÇÃO: technicians não existe! Criando novamente...")
                cur.execute("""
                    CREATE TABLE technicians (
                        id VARCHAR(50) PRIMARY KEY,
                        name VARCHAR(200) NOT NULL,
                        cpf VARCHAR(11) UNIQUE,
                        email VARCHAR(200),
                        phone VARCHAR(20),
                        address TEXT,
                        specialties JSONB DEFAULT '[]',
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                print("✅ Tabela technicians criada!")
            
            # Verificar novamente
            cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'admin_users')")
            admin_users_exists = cur.fetchone()[0]
            cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'technicians')")
            technicians_exists = cur.fetchone()[0]
            print(f"✅ Verificação final: admin_users existe = {admin_users_exists}, technicians existe = {technicians_exists}")
            
        except Exception as e:
            print(f"⚠️  Erro ao verificar/criar tabelas: {e}")
            import traceback
            traceback.print_exc()
        
        print("✅ Tabelas criadas/verificadas com sucesso!")
        
        # Fechar cursor
        cur.close()
        
    except Exception as e:
        print(f"❌ Erro ao criar tabelas: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Fechar conexão direta
        if conn:
            try:
                conn.close()
                print("✅ Conexão fechada")
            except Exception as e:
                print(f"⚠️  Erro ao fechar conexão: {e}")

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

def save_nfse_config(nfse_config):
    """Salva a configuração NFS-e"""
    if not USE_DATABASE:
        config = _load_config_file()
        config['nfse_config'] = nfse_config
        _save_config_file(config)
        return
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                config['nfse_config'] = nfse_config
                _save_config_file(config)
                return
            cur = _get_cursor(conn)
            data_json = json.dumps(nfse_config)
            cur.execute("""
                INSERT INTO site_content (section, data, updated_at)
                VALUES ('nfse_config', %s::jsonb, CURRENT_TIMESTAMP)
                ON CONFLICT (section) 
                DO UPDATE SET data = %s::jsonb, updated_at = CURRENT_TIMESTAMP
            """, (data_json, data_json))
            conn.commit()
            print("✅ Configuração NFS-e salva com sucesso!")
    except Exception as e:
        print(f"⚠️  Erro ao salvar configuração NFS-e no banco: {e}")
        config = _load_config_file()
        config['nfse_config'] = nfse_config
        _save_config_file(config)

def get_nfse_config():
    """Obtém a configuração NFS-e"""
    if not USE_DATABASE:
        config = _load_config_file()
        return config.get('nfse_config', {})
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                return config.get('nfse_config', {})
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT data FROM site_content WHERE section = 'nfse_config'")
            row = cur.fetchone()
            if row:
                return row['data']
            return {}
    except Exception as e:
        print(f"⚠️  Erro ao ler configuração NFS-e do banco: {e}")
        config = _load_config_file()
        return config.get('nfse_config', {})

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

# ========== FUNÇÕES DE HORÁRIOS DE FUNCIONAMENTO ==========

def get_business_hours():
    """Obtém os horários de funcionamento"""
    if not USE_DATABASE:
        config = _load_config_file()
        return config.get('business_hours', {
            'monday': {'open': '09:00', 'close': '18:00', 'enabled': True},
            'tuesday': {'open': '09:00', 'close': '18:00', 'enabled': True},
            'wednesday': {'open': '09:00', 'close': '18:00', 'enabled': True},
            'thursday': {'open': '09:00', 'close': '18:00', 'enabled': True},
            'friday': {'open': '09:00', 'close': '18:00', 'enabled': True},
            'saturday': {'open': '09:00', 'close': '18:00', 'enabled': True},
            'sunday': {'open': '09:00', 'close': '18:00', 'enabled': False}
        })
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                return config.get('business_hours', {
                    'monday': {'open': '09:00', 'close': '18:00', 'enabled': True},
                    'tuesday': {'open': '09:00', 'close': '18:00', 'enabled': True},
                    'wednesday': {'open': '09:00', 'close': '18:00', 'enabled': True},
                    'thursday': {'open': '09:00', 'close': '18:00', 'enabled': True},
                    'friday': {'open': '09:00', 'close': '18:00', 'enabled': True},
                    'saturday': {'open': '09:00', 'close': '18:00', 'enabled': True},
                    'sunday': {'open': '09:00', 'close': '18:00', 'enabled': False}
                })
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT value FROM admin_settings WHERE key = 'business_hours'")
            row = cur.fetchone()
            if row:
                import json
                return json.loads(row['value'])
            else:
                # Retornar padrão
                return {
                    'monday': {'open': '09:00', 'close': '18:00', 'enabled': True},
                    'tuesday': {'open': '09:00', 'close': '18:00', 'enabled': True},
                    'wednesday': {'open': '09:00', 'close': '18:00', 'enabled': True},
                    'thursday': {'open': '09:00', 'close': '18:00', 'enabled': True},
                    'friday': {'open': '09:00', 'close': '18:00', 'enabled': True},
                    'saturday': {'open': '09:00', 'close': '18:00', 'enabled': True},
                    'sunday': {'open': '09:00', 'close': '18:00', 'enabled': False}
                }
    except Exception as e:
        print(f"⚠️  Erro ao ler horários do banco: {e}")
        config = _load_config_file()
        return config.get('business_hours', {
            'monday': {'open': '09:00', 'close': '18:00', 'enabled': True},
            'tuesday': {'open': '09:00', 'close': '18:00', 'enabled': True},
            'wednesday': {'open': '09:00', 'close': '18:00', 'enabled': True},
            'thursday': {'open': '09:00', 'close': '18:00', 'enabled': True},
            'friday': {'open': '09:00', 'close': '18:00', 'enabled': True},
            'saturday': {'open': '09:00', 'close': '18:00', 'enabled': True},
            'sunday': {'open': '09:00', 'close': '18:00', 'enabled': False}
        })

def save_business_hours(business_hours):
    """Salva os horários de funcionamento"""
    if not USE_DATABASE:
        config = _load_config_file()
        config['business_hours'] = business_hours
        _save_config_file(config)
        return
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                config['business_hours'] = business_hours
                _save_config_file(config)
                return
            cur = _get_cursor(conn)
            import json
            hours_json = json.dumps(business_hours)
            cur.execute("""
                INSERT INTO admin_settings (key, value, updated_at)
                VALUES ('business_hours', %s, CURRENT_TIMESTAMP)
                ON CONFLICT (key) 
                DO UPDATE SET value = %s, updated_at = CURRENT_TIMESTAMP
            """, (hours_json, hours_json))
            conn.commit()
    except Exception as e:
        print(f"⚠️  Erro ao salvar horários no banco: {e}")
        config = _load_config_file()
        config['business_hours'] = business_hours
        _save_config_file(config)

def is_business_open():
    """Verifica se o estabelecimento está aberto no momento atual"""
    from datetime import datetime, timedelta
    
    try:
        business_hours = get_business_hours()
        
        # Usar timezone do Brasil (UTC-3)
        # Converter UTC para horário de Brasília (UTC-3)
        now_utc = datetime.utcnow()
        now = now_utc - timedelta(hours=3)
        
        # Obter dia da semana atual (0 = segunda, 6 = domingo)
        current_day = now.weekday()
        
        # Mapear número do dia para nome
        days_map = {
            0: 'monday',
            1: 'tuesday',
            2: 'wednesday',
            3: 'thursday',
            4: 'friday',
            5: 'saturday',
            6: 'sunday'
        }
        
        day_name = days_map[current_day]
        day_config = business_hours.get(day_name, {})
        
        # Debug: imprimir informações
        print(f"🔍 Verificando status: Dia={day_name}, Config={day_config}")
        
        # Se o dia está desabilitado, está fechado
        if not day_config.get('enabled', False):
            print(f"❌ Dia {day_name} está desabilitado")
            return False
        
        # Obter horário atual no timezone do Brasil
        current_time = now.strftime('%H:%M')
        
        # Obter horários de abertura e fechamento
        open_time = day_config.get('open', '09:00')
        close_time = day_config.get('close', '18:00')
        
        # Garantir formato correto (HH:MM)
        if len(open_time) == 5 and len(close_time) == 5:
            # Comparar horários (formato HH:MM como string funciona porque é lexicográfico)
            is_open = open_time <= current_time < close_time
            print(f"⏰ Horário atual (Brasil): {current_time}, Abertura: {open_time}, Fechamento: {close_time}, Status: {'ABERTO' if is_open else 'FECHADO'}")
            return is_open
        else:
            print(f"⚠️  Formato de horário inválido: open={open_time}, close={close_time}")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao verificar status: {e}")
        import traceback
        traceback.print_exc()
        return False

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
            result = []
            for row in rows:
                try:
                    request_data = {
                        'id': row['id'],
                        'status': row['status'],
                        'created_at': row['created_at'].isoformat() if row['created_at'] else None
                    }
                    # Adicionar dados do JSON se existir
                    if row.get('data') and isinstance(row['data'], dict):
                        request_data.update(row['data'])
                    result.append(request_data)
                except Exception as e:
                    print(f"Erro ao processar solicitação {row.get('id', 'N/A')}: {e}")
                    # Adicionar mesmo com erro, com dados básicos
                    result.append({
                        'id': row.get('id', 'N/A'),
                        'status': row.get('status', 'pendente'),
                        'created_at': row['created_at'].isoformat() if row.get('created_at') else None
                    })
            return result
    except Exception as e:
        print(f"⚠️  Erro ao ler solicitações do banco: {e}")
        config = _load_config_file()
        return config.get('budget_requests', [])

def save_budget_request(request_id, request_data, status='pendente'):
    """Salva ou atualiza uma solicitação de orçamento"""
    if not USE_DATABASE:
        config = _load_config_file()
        if 'budget_requests' not in config:
            config['budget_requests'] = []
        
        # Verificar se já existe e atualizar
        existing = next((r for r in config['budget_requests'] if r['id'] == request_id), None)
        if existing:
            existing.update(request_data)
            existing['status'] = status
        else:
            config['budget_requests'].append({'id': request_id, 'status': status, **request_data})
            
        _save_config_file(config)
        return
    
    try:
        with get_db_connection() as conn:
            if not conn:
                # Fallback para arquivo se conexão falhar
                config = _load_config_file()
                if 'budget_requests' not in config:
                    config['budget_requests'] = []
                existing = next((r for r in config['budget_requests'] if r['id'] == request_id), None)
                if existing:
                    existing.update(request_data)
                    existing['status'] = status
                else:
                    config['budget_requests'].append({'id': request_id, 'status': status, **request_data})
                _save_config_file(config)
                return

            cur = _get_cursor(conn)
            data_json = json.dumps(request_data)
            
            # Upsert (Insert ou Update)
            cur.execute("""
                INSERT INTO budget_requests (id, data, status, updated_at)
                VALUES (%s, %s::jsonb, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (id) 
                DO UPDATE SET 
                    data = EXCLUDED.data,
                    status = EXCLUDED.status,
                    updated_at = CURRENT_TIMESTAMP
            """, (request_id, data_json, status))
            conn.commit()
    except Exception as e:
        print(f"⚠️  Erro ao salvar solicitação no banco: {e}")
        # Fallback
        config = _load_config_file()
        if 'budget_requests' not in config:
            config['budget_requests'] = []
        existing = next((r for r in config['budget_requests'] if r['id'] == request_id), None)
        if existing:
            existing.update(request_data)
            existing['status'] = status
        else:
            config['budget_requests'].append({'id': request_id, 'status': status, **request_data})
        _save_config_file(config)

def update_budget_request_status(request_id, new_status, admin_notes=None):
    """Atualiza apenas o status e notas de uma solicitação"""
    if not USE_DATABASE:
        config = _load_config_file()
        if 'budget_requests' in config:
            req = next((r for r in config['budget_requests'] if r['id'] == request_id), None)
            if req:
                req['status'] = new_status
                if admin_notes:
                    req['admin_notes'] = admin_notes
                _save_config_file(config)
        return

    try:
        with get_db_connection() as conn:
            if not conn:
                # Fallback
                config = _load_config_file()
                if 'budget_requests' in config:
                    req = next((r for r in config['budget_requests'] if r['id'] == request_id), None)
                    if req:
                        req['status'] = new_status
                        if admin_notes:
                            req['admin_notes'] = admin_notes
                        _save_config_file(config)
                return

            cur = _get_cursor(conn)
            
            # Se tiver notas, precisamos atualizar o JSON data também
            if admin_notes:
                cur.execute("""
                    UPDATE budget_requests 
                    SET status = %s, 
                        updated_at = CURRENT_TIMESTAMP,
                        data = jsonb_set(data, '{admin_notes}', %s::jsonb)
                    WHERE id = %s
                """, (new_status, json.dumps(admin_notes), request_id))
            else:
                cur.execute("""
                    UPDATE budget_requests 
                    SET status = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (new_status, request_id))
            conn.commit()
    except Exception as e:
        print(f"⚠️  Erro ao atualizar status no banco: {e}")
        # Fallback
        config = _load_config_file()
        if 'budget_requests' in config:
            req = next((r for r in config['budget_requests'] if r['id'] == request_id), None)
            if req:
                req['status'] = new_status
                if admin_notes:
                    req['admin_notes'] = admin_notes
                _save_config_file(config)

def delete_budget_request(request_id):
    """Exclui uma solicitação de orçamento"""
    if not USE_DATABASE:
        config = _load_config_file()
        if 'budget_requests' in config:
            config['budget_requests'] = [r for r in config['budget_requests'] if r.get('id') != request_id]
            _save_config_file(config)
        return True
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                if 'budget_requests' in config:
                    config['budget_requests'] = [r for r in config['budget_requests'] if r.get('id') != request_id]
                    _save_config_file(config)
                return True
            cur = _get_cursor(conn)
            cur.execute("DELETE FROM budget_requests WHERE id = %s", (request_id,))
            conn.commit()
            return True
    except Exception as e:
        print(f"⚠️  Erro ao excluir solicitação do banco: {e}")
        config = _load_config_file()
        if 'budget_requests' in config:
            config['budget_requests'] = [r for r in config['budget_requests'] if r.get('id') != request_id]
            _save_config_file(config)
        return True

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

 


# ========== BUDGET CONFIG (ORÇAMENTO) ==========

def get_budget_config():
    """Lê a configuração de orçamentos (Marcas, Modelos, Preços)"""
    try:
        if os.path.exists('budget_config.json'):
            with open('budget_config.json', 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Erro ao ler budget_config.json: {e}")
    return []

def save_budget_config(data):
    """Salva a configuração de orçamentos"""
    try:
        with open('budget_config.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Erro ao salvar budget_config.json: {e}")
        return False

def transform_budget_config_to_raw(config):
    """Converte o formato amigável para o formato raw usado pelo frontend"""
    # Raw format: { "Brand": { "Model": [price_tela, price_vidro, ...] } }
    # Map order: Tela, Vidro, Bateria, Conector, Tampa, Lente, Face ID
    services_map = {
        "Troca de Tela": 0,
        "Troca de Vidro": 1,
        "Troca de Bateria": 2,
        "Troca de Conector": 3,
        "Troca de Tampa": 4,
        "Troca de Lente": 5,
        "Reparo de Face ID": 6
    }
    
    raw_data = {}
    
    for brand_obj in config:
        brand_name = brand_obj['brand']
        brand_data = {}
        
        for model in brand_obj.get('models', []):
            model_name = model['name']
            # Initialize array with 7 nulls
            prices = [None] * 7
            
            for service in model.get('services', []):
                s_name = service.get('service')
                s_price = service.get('price')
                
                if s_name in services_map:
                    idx = services_map[s_name]
                    prices[idx] = s_price
            
            brand_data[model_name] = prices
            
        raw_data[brand_name] = brand_data
        
    return raw_data


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
    
    # Salvar configuração NFS-e
    if 'nfse_config' in config:
        save_nfse_config(config['nfse_config'])
    
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

# ========== FUNÇÕES DE GESTÃO FINANCEIRA ==========

def get_financial_data(start_date=None, end_date=None):
    """Obtém dados financeiros dos reparos"""
    from datetime import datetime, timedelta
    
    repairs = get_all_repairs()
    
    # Se não houver datas, usar últimos 30 dias
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).isoformat()
    if not end_date:
        end_date = datetime.now().isoformat()
    
    # Converter para datetime para comparação
    try:
        # Se a data vem no formato YYYY-MM-DD (do formulário), adicionar hora 00:00:00
        if isinstance(start_date, str) and len(start_date) == 10 and '-' in start_date:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        else:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00') if 'Z' in start_date else start_date)
        
        if isinstance(end_date, str) and len(end_date) == 10 and '-' in end_date:
            # Para end_date, usar fim do dia (23:59:59)
            end_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        else:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00') if 'Z' in end_date else end_date)
    except Exception as e:
        print(f"Erro ao converter datas: {e}")
        start_dt = datetime.now() - timedelta(days=30)
        end_dt = datetime.now()
    
    # Faturamento por período
    total_billing = 0.0
    billing_by_month = {}
    billing_by_status = {}
    
    # Serviços mais vendidos
    services_count = {}
    
    # Valor perdido por abandono
    abandoned_value = 0.0
    abandoned_repairs = []
    
    # Serviços em garantia
    warranty_repairs = []
    
    # Dados para custos (se disponíveis no orçamento)
    total_cost = 0.0
    costs_by_month = {}
    
    for repair in repairs:
        status = repair.get('status', '').lower()  # Normalizar para lowercase
        completed_at = repair.get('completed_at')
        order = get_order_by_repair(repair.get('id'))
        budget = repair.get('budget')
        budget_amount = 0.0
        cost_amount = 0.0
        
        if budget and isinstance(budget, dict) and budget.get('status') == 'approved':
            try:
                # Helper para converter valores monetários com segurança
                def safe_money(val):
                    if not val: return 0.0
                    if isinstance(val, (int, float)): return float(val)
                    if isinstance(val, str):
                        return float(val.replace('R$', '').replace(' ', '').replace(',', '.'))
                    return 0.0

                budget_amount = safe_money(budget.get('amount', 0))
                # Tentar obter custo (se existir campo 'cost' ou 'parts_cost')
                cost_amount = safe_money(budget.get('cost', 0)) or safe_money(budget.get('parts_cost', 0))
            except Exception as e:
                print(f"Erro ao processar valores do orçamento: {e}")
                budget_amount = 0.0
                cost_amount = 0.0
            
            # Se está concluído OU tem OR, conta como faturado
            # IMPORTANTE: Reparos concluídos devem ser contados mesmo sem OR
            if status == 'concluido' or order:
                # Verificar se está no período
                repair_date = None
                
                # Prioridade: data de conclusão > data de emissão da OR > data de criação
                if completed_at:
                    try:
                        repair_date = datetime.fromisoformat(completed_at.replace('Z', '+00:00') if 'Z' in completed_at else completed_at)
                    except:
                        try:
                            # Tentar formato alternativo
                            repair_date = datetime.strptime(completed_at[:10], '%Y-%m-%d')
                        except:
                            pass
                elif order and order.get('emitted_at'):
                    try:
                        repair_date = datetime.fromisoformat(order.get('emitted_at').replace('Z', '+00:00') if 'Z' in order.get('emitted_at') else order.get('emitted_at'))
                    except:
                        try:
                            # Tentar formato alternativo
                            repair_date = datetime.strptime(order.get('emitted_at')[:10], '%Y-%m-%d')
                        except:
                            pass
                elif repair.get('created_at'):
                    try:
                        repair_date = datetime.fromisoformat(repair.get('created_at').replace('Z', '+00:00') if 'Z' in repair.get('created_at') else repair.get('created_at'))
                    except:
                        try:
                            # Tentar formato alternativo
                            repair_date = datetime.strptime(repair.get('created_at')[:10], '%Y-%m-%d')
                        except:
                            pass
                
                # Se encontrou uma data válida e está no período
                if repair_date:
                    # Comparar apenas as datas (ignorar hora)
                    repair_date_only = repair_date.date()
                    start_date_only = start_dt.date()
                    end_date_only = end_dt.date()
                    
                    if start_date_only <= repair_date_only <= end_date_only:
                        total_billing += budget_amount
                        total_cost += cost_amount
                        
                        # Por mês
                        month_key = repair_date.strftime('%Y-%m')
                        billing_by_month[month_key] = billing_by_month.get(month_key, 0) + budget_amount
                        costs_by_month[month_key] = costs_by_month.get(month_key, 0) + cost_amount
                        
                        # Por status
                        billing_by_status[status] = billing_by_status.get(status, 0) + budget_amount
                elif status == 'concluido':
                    # Se está concluído mas não tem data válida, usar data de criação como fallback
                    # Isso garante que reparos concluídos sejam sempre contados
                    created_at = repair.get('created_at')
                    if created_at:
                        try:
                            repair_date = datetime.fromisoformat(created_at.replace('Z', '+00:00') if 'Z' in created_at else created_at)
                            repair_date_only = repair_date.date()
                            start_date_only = start_dt.date()
                            end_date_only = end_dt.date()
                            
                            if start_date_only <= repair_date_only <= end_date_only:
                                total_billing += budget_amount
                                total_cost += cost_amount
                                
                                # Por mês
                                month_key = repair_date.strftime('%Y-%m')
                                billing_by_month[month_key] = billing_by_month.get(month_key, 0) + budget_amount
                                costs_by_month[month_key] = costs_by_month.get(month_key, 0) + cost_amount
                                
                                # Por status
                                billing_by_status[status] = billing_by_status.get(status, 0) + budget_amount
                        except:
                            pass
            
            # Serviços mais vendidos (por tipo de dispositivo ou problema)
            device_name = repair.get('device_name', 'Outros')
            problem = repair.get('problem_description', '')
            service_key = f"{device_name}"
            if problem:
                # Pegar primeira palavra do problema como tipo de serviço
                problem_words = problem.split()
                if problem_words:
                    service_key = f"{device_name} - {problem_words[0]}"
            
            services_count[service_key] = services_count.get(service_key, 0) + 1
        
        # Valor perdido por abandono (concluído há mais de 90 dias sem OR)
        if status == 'concluido' and not order and completed_at:
            try:
                completed_dt = datetime.fromisoformat(completed_at.replace('Z', '+00:00') if 'Z' in completed_at else completed_at)
                days_abandoned = (datetime.now() - completed_dt).days
                
                if days_abandoned > 90:
                    abandoned_value += budget_amount if budget and isinstance(budget, dict) else 0
                    abandoned_repairs.append({
                        'id': repair.get('id'),
                        'customer_name': repair.get('customer_name', 'N/A'),
                        'device_name': repair.get('device_name', 'N/A'),
                        'completed_at': completed_at,
                        'days_abandoned': days_abandoned,
                        'value': budget_amount if budget and isinstance(budget, dict) else 0
                    })
            except:
                pass
        
        # Serviços em garantia
        warranty = repair.get('warranty')
        if warranty and isinstance(warranty, dict):
            valid_until = warranty.get('valid_until')
            if valid_until:
                try:
                    valid_until_dt = datetime.fromisoformat(valid_until.replace('Z', '+00:00') if 'Z' in valid_until else valid_until)
                    if valid_until_dt > datetime.now():
                        warranty_repairs.append({
                            'id': repair.get('id'),
                            'customer_name': repair.get('customer_name', 'N/A'),
                            'device_name': repair.get('device_name', 'N/A'),
                            'completed_at': repair.get('completed_at', ''),
                            'valid_until': valid_until,
                            'period': warranty.get('period', 'N/A')
                        })
                except:
                    pass
    
    # Ordenar serviços mais vendidos
    services_sorted = sorted(services_count.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Preparar dados para o dashboard financeiro (Últimos 12 meses)
    today = datetime.now()
    chart_months = []
    
    # Gerar chaves dos últimos 12 meses (inclusive o atual)
    for i in range(11, -1, -1):
        # Para garantir mês correto, subtraímos do primeiro dia do mês atual
        first_day_current = today.replace(day=1)
        # Subtrair meses aproximadamente
        # Maneira segura de subtrair meses
        month_target = first_day_current.month - i
        year_target = first_day_current.year
        while month_target <= 0:
            month_target += 12
            year_target -= 1
        
        key = f"{year_target}-{month_target:02d}"
        chart_months.append(key)
    
    # Dados para os gráficos
    chart_labels = []
    chart_revenue = []
    chart_cost = []
    chart_profit = []
    
    current_month_key = today.strftime('%Y-%m')
    last_month_key = (today.replace(day=1) - timedelta(days=1)).strftime('%Y-%m')
    
    current_revenue = 0
    last_revenue = 0
    
    for key in chart_months:
        revenue = billing_by_month.get(key, 0)
        cost = costs_by_month.get(key, 0)
        profit = revenue - cost
        
        # Formatar label (Ex: "Out/2023")
        try:
            dt = datetime.strptime(key, '%Y-%m')
            # Traduzir mês manualmente para evitar dependência de locale
            months_pt = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
            label = f"{months_pt[dt.month-1]}/{dt.year}"
        except:
            label = key
        
        chart_labels.append(label)
        chart_revenue.append(revenue)
        chart_cost.append(cost)
        chart_profit.append(profit)
        
        if key == current_month_key:
            current_revenue = revenue
        elif key == last_month_key:
            last_revenue = revenue

    # Crescimento
    growth_rate = 0
    growth_type = 'neutral' # positive, negative, neutral
    if last_revenue > 0:
        growth_rate = ((current_revenue - last_revenue) / last_revenue) * 100
        if growth_rate > 0:
            growth_type = 'positive'
        elif growth_rate < 0:
            growth_type = 'negative'
    elif current_revenue > 0:
        growth_rate = 100 # Se mês passado foi 0 e este tem receita, crescimento de 100% (ou infinito)
        growth_type = 'positive'
        
    # Meta Automática (Média dos últimos 3 meses anteriores + 20%)
    last_3_months_revenue = 0
    count_3_months = 0
    
    # Pegar índices dos meses anteriores ao atual
    try:
        current_idx = chart_months.index(current_month_key)
        start_idx = max(0, current_idx - 3)
        for i in range(start_idx, current_idx):
            last_3_months_revenue += chart_revenue[i]
            count_3_months += 1
    except:
        pass
        
    average_revenue = last_3_months_revenue / count_3_months if count_3_months > 0 else 0
    revenue_goal = average_revenue * 1.2 # Meta: 20% acima da média
    if revenue_goal == 0 and current_revenue > 0:
        revenue_goal = current_revenue * 1.2 # Se não tem histórico, meta é 20% acima do atual
    
    goal_progress = (current_revenue / revenue_goal * 100) if revenue_goal > 0 else 0
    
    return {
        'total_billing': total_billing,
        'total_cost': total_cost,
        'total_profit': total_billing - total_cost,
        'billing_by_month': billing_by_month,
        'billing_by_status': billing_by_status,
        'top_services': services_sorted,
        'abandoned_value': abandoned_value,
        'abandoned_repairs': abandoned_repairs,
        'warranty_repairs': warranty_repairs,
        'period': {
            'start': start_date,
            'end': end_date
        },
        'dashboard': {
            'labels': chart_labels,
            'revenue': chart_revenue,
            'cost': chart_cost,
            'profit': chart_profit,
            'growth': {
                'rate': round(growth_rate, 1),
                'type': growth_type,
                'current': current_revenue,
                'last': last_revenue
            },
            'goal': {
                'target': round(revenue_goal, 2),
                'progress': round(goal_progress, 1),
                'current': current_revenue
            }
        }
    }

# ========== FUNÇÕES DE SCORE DE RISCO DO CLIENTE ==========

def calculate_customer_risk_score(cpf):
    """Calcula o score de risco do cliente baseado no histórico"""
    from datetime import datetime, timedelta
    
    try:
        if not cpf:
            return {
                'score': 0,
                'level': 'low',
                'label': '🟢 Baixo risco',
                'details': {
                    'total_repairs': 0,
                    'warranty_claims': 0,
                    'abandoned_devices': 0,
                    'value_disputes': 0,
                    'cancelled_after_analysis': 0,
                    'open_repairs': 0,
                    'message': 'CPF não informado'
                }
            }
        
        # Normalizar CPF
        cpf_clean = str(cpf).replace('.', '').replace('-', '').replace(' ', '')
        
        # Buscar todos os reparos do cliente
        repairs = get_repairs_by_cpf(cpf_clean)
        
        if not repairs:
            return {
                'score': 0,
                'level': 'low',
                'label': '🟢 Baixo risco',
                'details': {
                    'total_repairs': 0,
                    'warranty_claims': 0,
                    'abandoned_devices': 0,
                    'value_disputes': 0,
                    'cancelled_after_analysis': 0,
                    'open_repairs': 0,
                    'message': 'Cliente novo, sem histórico'
                }
            }
        
        # Critérios de risco
        score = 0
        details = {
            'total_repairs': len(repairs),
            'warranty_claims': 0,
            'abandoned_devices': 0,
            'value_disputes': 0,
            'cancelled_after_analysis': 0,
            'open_repairs': 0
        }
        
        # Verificar cada reparo
        for repair in repairs:
            status = repair.get('status', '').lower()
            
            # OS abertas simultâneas (não concluídas)
            if status not in ['concluido', 'cancelado']:
                details['open_repairs'] += 1
            
            # Verificar se acionou garantia (reparo concluído com garantia e depois teve novo problema)
            warranty = repair.get('warranty')
            if warranty and isinstance(warranty, dict):
                # Se tem garantia e o reparo foi concluído, verificar se houve retorno
                if status == 'concluido':
                    # Verificar histórico por mensagens de garantia
                    messages = repair.get('messages', [])
                    for msg in messages:
                        if isinstance(msg, dict):
                            content = msg.get('content', '').lower()
                            if 'garantia' in content or 'garant' in content:
                                details['warranty_claims'] += 1
                                break
            
            # Verificar se abandonou aparelho (concluído há mais de 90 dias sem OR)
            if status == 'concluido':
                completed_at = repair.get('completed_at')
                if completed_at:
                    try:
                        completed_dt = datetime.fromisoformat(completed_at.replace('Z', '+00:00') if 'Z' in completed_at else completed_at)
                        days_abandoned = (datetime.now() - completed_dt).days
                        
                        # Verificar se tem OR
                        try:
                            order = get_order_by_repair(repair.get('id'))
                            if not order and days_abandoned > 90:
                                details['abandoned_devices'] += 1
                        except Exception as e:
                            # Se não conseguir buscar OR, considerar abandonado se passar de 90 dias
                            if days_abandoned > 90:
                                details['abandoned_devices'] += 1
                    except Exception as e:
                        pass
            
            # Verificar se discutiu valor (mensagens com palavras-chave)
            messages = repair.get('messages', [])
            for msg in messages:
                if isinstance(msg, dict):
                    content = msg.get('content', '').lower()
                    dispute_keywords = ['caro', 'caro demais', 'muito caro', 'preço', 'valor', 'barato', 'desconto', 'negociar']
                    if any(keyword in content for keyword in dispute_keywords):
                        details['value_disputes'] += 1
                        break
            
            # Verificar se cancelou após análise (status cancelado após ter orçamento)
            if status == 'cancelado':
                budget = repair.get('budget')
                if budget and isinstance(budget, dict):
                    # Se tinha orçamento e cancelou, conta como cancelamento após análise
                    details['cancelled_after_analysis'] += 1
        
        # Calcular score baseado nos critérios
        # Cada critério adiciona pontos:
        # - Acionou garantia: +3 pontos por ocorrência
        # - Abandonou aparelho: +5 pontos por ocorrência
        # - Discutiu valor: +2 pontos por ocorrência
        # - Cancelou após análise: +4 pontos por ocorrência
        # - OS abertas simultâneas: +1 ponto por OS (máximo 3 pontos)
        
        score += details['warranty_claims'] * 3
        score += details['abandoned_devices'] * 5
        score += details['value_disputes'] * 2
        score += details['cancelled_after_analysis'] * 4
        score += min(details['open_repairs'], 3)  # Máximo 3 pontos para OS abertas
        
        # Determinar nível de risco
        if score >= 10:
            level = 'high'
            label = '🔴 Alto risco'
        elif score >= 5:
            level = 'medium'
            label = '🟡 Médio risco'
        else:
            level = 'low'
            label = '🟢 Baixo risco'
        
        return {
            'score': score,
            'level': level,
            'label': label,
            'details': details
        }
    except Exception as e:
        print(f"Erro ao calcular score de risco para CPF {cpf}: {e}")
        import traceback
        traceback.print_exc()
        # Retornar score padrão em caso de erro
        return {
            'score': 0,
            'level': 'low',
            'label': '🟢 Baixo risco',
            'details': {
                'total_repairs': 0,
                'warranty_claims': 0,
                'abandoned_devices': 0,
                'value_disputes': 0,
                'cancelled_after_analysis': 0,
                'open_repairs': 0,
                'error': str(e)
            }
        }

# ========== FUNÇÕES DE SCORE DE QUALIDADE DO TÉCNICO ==========

def calculate_technician_quality_score(technician_id):
    """Calcula o score de qualidade do técnico baseado nas métricas"""
    from datetime import datetime, timedelta
    
    try:
        if not technician_id:
            return {
                'score': 0,
                'level': 'unknown',
                'label': '⚪ Sem dados',
                'metrics': {
                    'warranty_return_rate': 0,
                    'average_repair_time': 0,
                    'error_rate': 0,
                    'reopened_os': 0,
                    'total_repairs': 0,
                    'completed_repairs': 0,
                    'warranty_returns': 0,
                    'total_repair_time': 0,
                    'errors': 0,
                    'reopened': 0
                }
            }
        
        # Buscar todos os reparos
        repairs = get_all_repairs()
        
        # Filtrar reparos do técnico
        technician_repairs = []
        for repair in repairs:
            # Verificar se o reparo tem técnico associado
            # Pode ser technician_id, technician_name, assigned_to, etc.
            repair_technician = repair.get('technician_id') or repair.get('technician_name') or repair.get('assigned_to')
            if repair_technician == technician_id or (isinstance(repair_technician, str) and technician_id in repair_technician):
                technician_repairs.append(repair)
        
        if not technician_repairs:
            return {
                'score': 0,
                'level': 'unknown',
                'label': '⚪ Sem dados',
                'metrics': {
                    'warranty_return_rate': 0,
                    'average_repair_time': 0,
                    'error_rate': 0,
                    'reopened_os': 0,
                    'total_repairs': 0,
                    'completed_repairs': 0,
                    'warranty_returns': 0,
                    'total_repair_time': 0,
                    'errors': 0,
                    'reopened': 0
                }
            }
        
        # Métricas
        total_repairs = len(technician_repairs)
        completed_repairs = 0
        warranty_returns = 0
        total_repair_time = 0  # em dias
        errors = 0
        reopened = 0
        
        now = datetime.now()
        
        for repair in technician_repairs:
            status = repair.get('status', '').lower()
            repair_type = repair.get('repair_type', 'novo').lower()
            
            # Contar reparos completados
            if status == 'concluido':
                completed_repairs += 1
                
                # Calcular tempo do reparo
                created_at = repair.get('created_at')
                completed_at = repair.get('completed_at') or repair.get('updated_at')
                
                if created_at and completed_at:
                    try:
                        created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        completed_date = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                        if created_date.tzinfo:
                            created_date = created_date.replace(tzinfo=None)
                        if completed_date.tzinfo:
                            completed_date = completed_date.replace(tzinfo=None)
                        repair_time = (completed_date - created_date).days
                        if repair_time > 0:
                            total_repair_time += repair_time
                    except:
                        pass
                
                # Verificar se é retorno em garantia
                if repair_type == 'retorno':
                    warranty_returns += 1
                    errors += 1  # Retorno em garantia conta como erro
            
            # Verificar reabertura de OS
            history = repair.get('history', [])
            status_changes = [h.get('status', '').lower() for h in history if isinstance(h, dict)]
            if status_changes.count('concluido') > 1:
                reopened += 1
        
        # Calcular métricas
        warranty_return_rate = (warranty_returns / completed_repairs * 100) if completed_repairs > 0 else 0
        average_repair_time = (total_repair_time / completed_repairs) if completed_repairs > 0 else 0
        error_rate = (errors / completed_repairs * 100) if completed_repairs > 0 else 0
        reopened_os = reopened
        
        # Calcular score (0-100, onde 100 é perfeito)
        # Penalidades:
        # - Retorno em garantia: -10 pontos por %
        # - Tempo médio alto (>7 dias): -5 pontos por dia acima de 7
        # - Taxa de erro: -5 pontos por %
        # - Reabertura: -15 pontos por OS
        
        score = 100
        score -= min(warranty_return_rate * 10, 50)  # Máximo 50 pontos de penalidade
        if average_repair_time > 7:
            score -= min((average_repair_time - 7) * 5, 30)  # Máximo 30 pontos de penalidade
        score -= min(error_rate * 5, 30)  # Máximo 30 pontos de penalidade
        score -= min(reopened_os * 15, 50)  # Máximo 50 pontos de penalidade
        
        score = max(0, min(100, score))  # Garantir entre 0 e 100
        
        # Determinar nível de qualidade
        if score >= 80:
            level = 'excellent'
            label = '🟢 Excelente'
        elif score >= 60:
            level = 'good'
            label = '🟡 Bom'
        elif score >= 40:
            level = 'regular'
            label = '🟠 Regular'
        else:
            level = 'poor'
            label = '🔴 Precisa Melhorar'
        
        return {
            'score': round(score, 2),
            'level': level,
            'label': label,
            'metrics': {
                'warranty_return_rate': round(warranty_return_rate, 2),
                'average_repair_time': round(average_repair_time, 2),
                'error_rate': round(error_rate, 2),
                'reopened_os': reopened_os,
                'total_repairs': total_repairs,
                'completed_repairs': completed_repairs,
                'warranty_returns': warranty_returns,
                'total_repair_time': total_repair_time,
                'errors': errors,
                'reopened': reopened
            }
        }
    except Exception as e:
        print(f"Erro ao calcular score de qualidade para técnico {technician_id}: {e}")
        import traceback
        traceback.print_exc()
        return {
            'score': 0,
            'level': 'unknown',
            'label': '⚪ Erro no cálculo',
            'metrics': {
                'warranty_return_rate': 0,
                'average_repair_time': 0,
                'error_rate': 0,
                'reopened_os': 0,
                'total_repairs': 0,
                'completed_repairs': 0,
                'warranty_returns': 0,
                'total_repair_time': 0,
                'errors': 0,
                'reopened': 0,
                'error': str(e)
            }
        }

def get_all_technician_quality_scores():
    """Obtém scores de qualidade de todos os técnicos"""
    technicians = get_all_technicians()
    scores = []
    
    for tech in technicians:
        if tech.get('is_active', True):
            quality_score = calculate_technician_quality_score(tech.get('id'))
            scores.append({
                'technician': tech,
                'quality_score': quality_score
            })
    
    # Ordenar por score (maior primeiro)
    scores.sort(key=lambda x: x['quality_score']['score'], reverse=True)
    
    return scores

# ========== FUNÇÕES DE USUÁRIOS DO ADMIN ==========

def get_all_admin_users():
    """Obtém todos os usuários do admin"""
    if not USE_DATABASE:
        config = _load_config_file()
        return config.get('admin_users', [])
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                return config.get('admin_users', [])
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT * FROM admin_users ORDER BY created_at DESC")
            rows = cur.fetchall()
            users = []
            for row in rows:
                user = dict(row)
                # Garantir que permissions seja um dict
                if isinstance(user.get('permissions'), str):
                    import json
                    try:
                        user['permissions'] = json.loads(user['permissions'])
                    except:
                        user['permissions'] = {}
                elif not user.get('permissions'):
                    user['permissions'] = {}
                users.append(user)
            return users
    except Exception as e:
        print(f"⚠️  Erro ao ler usuários do admin: {e}")
        config = _load_config_file()
        return config.get('admin_users', [])

def get_admin_user(user_id):
    """Obtém um usuário do admin específico"""
    if not USE_DATABASE:
        config = _load_config_file()
        users = config.get('admin_users', [])
        user = next((u for u in users if u.get('id') == user_id), None)
        if user and not user.get('permissions'):
            user['permissions'] = {}
        return user
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                users = config.get('admin_users', [])
                user = next((u for u in users if u.get('id') == user_id), None)
                if user and not user.get('permissions'):
                    user['permissions'] = {}
                return user
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT * FROM admin_users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            if row:
                user = dict(row)
                # Garantir que permissions seja um dict
                if isinstance(user.get('permissions'), str):
                    import json
                    try:
                        user['permissions'] = json.loads(user['permissions'])
                    except:
                        user['permissions'] = {}
                elif not user.get('permissions'):
                    user['permissions'] = {}
                return user
            return None
    except Exception as e:
        print(f"⚠️  Erro ao ler usuário do admin: {e}")
        config = _load_config_file()
        users = config.get('admin_users', [])
        user = next((u for u in users if u.get('id') == user_id), None)
        if user and not user.get('permissions'):
            user['permissions'] = {}
        return user

def save_admin_user(user_id, user_data):
    """Salva ou atualiza um usuário do admin"""
    import json
    import hashlib
    
    # Se tiver senha, fazer hash
    if 'password' in user_data and user_data['password']:
        password = user_data.pop('password')
        user_data['password_hash'] = hashlib.sha256(password.encode()).hexdigest()
    
    if not USE_DATABASE:
        config = _load_config_file()
        if 'admin_users' not in config:
            config['admin_users'] = []
        users = config.get('admin_users', [])
        found = False
        for i, u in enumerate(users):
            if u.get('id') == user_id:
                users[i] = {**u, **user_data, 'id': user_id}
                found = True
                break
        if not found:
            users.append({**user_data, 'id': user_id})
        config['admin_users'] = users
        _save_config_file(config)
        return
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                if 'admin_users' not in config:
                    config['admin_users'] = []
                users = config.get('admin_users', [])
                found = False
                for i, u in enumerate(users):
                    if u.get('id') == user_id:
                        users[i] = {**u, **user_data, 'id': user_id}
                        found = True
                        break
                if not found:
                    users.append({**user_data, 'id': user_id})
                config['admin_users'] = users
                _save_config_file(config)
                return
            cur = _get_cursor(conn)
            
            # Preparar dados para JSONB
            permissions_json = json.dumps(user_data.get('permissions', {}))
            
            cur.execute("""
                INSERT INTO admin_users (id, username, password_hash, name, email, phone, permissions, is_active, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (id) 
                DO UPDATE SET 
                    username = EXCLUDED.username,
                    password_hash = COALESCE(EXCLUDED.password_hash, admin_users.password_hash),
                    name = EXCLUDED.name,
                    email = EXCLUDED.email,
                    phone = EXCLUDED.phone,
                    permissions = EXCLUDED.permissions,
                    is_active = EXCLUDED.is_active,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                user_id,
                user_data.get('username', ''),
                user_data.get('password_hash', ''),
                user_data.get('name', ''),
                user_data.get('email', ''),
                user_data.get('phone', ''),
                permissions_json,
                user_data.get('is_active', True)
            ))
            conn.commit()
    except Exception as e:
        print(f"⚠️  Erro ao salvar usuário do admin: {e}")
        config = _load_config_file()
        if 'admin_users' not in config:
            config['admin_users'] = []
        users = config.get('admin_users', [])
        found = False
        for i, u in enumerate(users):
            if u.get('id') == user_id:
                users[i] = {**u, **user_data, 'id': user_id}
                found = True
                break
        if not found:
            users.append({**user_data, 'id': user_id})
        config['admin_users'] = users
        _save_config_file(config)

def delete_admin_user(user_id):
    """Exclui um usuário do admin"""
    if not USE_DATABASE:
        config = _load_config_file()
        if 'admin_users' in config:
            config['admin_users'] = [u for u in config['admin_users'] if u.get('id') != user_id]
            _save_config_file(config)
        return
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                if 'admin_users' in config:
                    config['admin_users'] = [u for u in config['admin_users'] if u.get('id') != user_id]
                    _save_config_file(config)
                return
            cur = _get_cursor(conn)
            cur.execute("DELETE FROM admin_users WHERE id = %s", (user_id,))
            conn.commit()
    except Exception as e:
        print(f"⚠️  Erro ao excluir usuário do admin: {e}")
        config = _load_config_file()
        if 'admin_users' in config:
            config['admin_users'] = [u for u in config['admin_users'] if u.get('id') != user_id]
            _save_config_file(config)

# ========== FUNÇÕES DE TÉCNICOS ==========

def get_all_technicians():
    """Obtém todos os técnicos"""
    if not USE_DATABASE:
        config = _load_config_file()
        return config.get('technicians', [])
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                return config.get('technicians', [])
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT * FROM technicians ORDER BY created_at DESC")
            rows = cur.fetchall()
            technicians = []
            for row in rows:
                tech = dict(row)
                # Garantir que specialties seja uma lista
                if isinstance(tech.get('specialties'), str):
                    import json
                    try:
                        tech['specialties'] = json.loads(tech['specialties'])
                    except:
                        tech['specialties'] = []
                elif not tech.get('specialties'):
                    tech['specialties'] = []
                technicians.append(tech)
            return technicians
    except Exception as e:
        print(f"⚠️  Erro ao ler técnicos: {e}")
        config = _load_config_file()
        return config.get('technicians', [])

def get_technician(technician_id):
    """Obtém um técnico específico"""
    if not USE_DATABASE:
        config = _load_config_file()
        technicians = config.get('technicians', [])
        tech = next((t for t in technicians if t.get('id') == technician_id), None)
        if tech and not tech.get('specialties'):
            tech['specialties'] = []
        return tech
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                technicians = config.get('technicians', [])
                tech = next((t for t in technicians if t.get('id') == technician_id), None)
                if tech and not tech.get('specialties'):
                    tech['specialties'] = []
                return tech
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT * FROM technicians WHERE id = %s", (technician_id,))
            row = cur.fetchone()
            if row:
                tech = dict(row)
                # Garantir que specialties seja uma lista
                if isinstance(tech.get('specialties'), str):
                    import json
                    try:
                        tech['specialties'] = json.loads(tech['specialties'])
                    except:
                        tech['specialties'] = []
                elif not tech.get('specialties'):
                    tech['specialties'] = []
                return tech
            return None
    except Exception as e:
        print(f"⚠️  Erro ao ler técnico: {e}")
        config = _load_config_file()
        technicians = config.get('technicians', [])
        tech = next((t for t in technicians if t.get('id') == technician_id), None)
        if tech and not tech.get('specialties'):
            tech['specialties'] = []
        return tech

def save_technician(technician_id, technician_data):
    """Salva ou atualiza um técnico"""
    import json
    
    if not USE_DATABASE:
        config = _load_config_file()
        if 'technicians' not in config:
            config['technicians'] = []
        technicians = config.get('technicians', [])
        found = False
        for i, t in enumerate(technicians):
            if t.get('id') == technician_id:
                technicians[i] = {**t, **technician_data, 'id': technician_id}
                found = True
                break
        if not found:
            technicians.append({**technician_data, 'id': technician_id})
        config['technicians'] = technicians
        _save_config_file(config)
        return
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                if 'technicians' not in config:
                    config['technicians'] = []
                technicians = config.get('technicians', [])
                found = False
                for i, t in enumerate(technicians):
                    if t.get('id') == technician_id:
                        technicians[i] = {**t, **technician_data, 'id': technician_id}
                        found = True
                        break
                if not found:
                    technicians.append({**technician_data, 'id': technician_id})
                config['technicians'] = technicians
                _save_config_file(config)
                return
            cur = _get_cursor(conn)
            
            # Preparar especialidades para JSONB
            specialties_json = json.dumps(technician_data.get('specialties', []))
            
            cur.execute("""
                INSERT INTO technicians (id, name, cpf, email, phone, address, specialties, is_active, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (id) 
                DO UPDATE SET 
                    name = EXCLUDED.name,
                    cpf = EXCLUDED.cpf,
                    email = EXCLUDED.email,
                    phone = EXCLUDED.phone,
                    address = EXCLUDED.address,
                    specialties = EXCLUDED.specialties,
                    is_active = EXCLUDED.is_active,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                technician_id,
                technician_data.get('name', ''),
                technician_data.get('cpf', ''),
                technician_data.get('email', ''),
                technician_data.get('phone', ''),
                technician_data.get('address', ''),
                specialties_json,
                technician_data.get('is_active', True)
            ))
            conn.commit()
    except Exception as e:
        print(f"⚠️  Erro ao salvar técnico: {e}")
        config = _load_config_file()
        if 'technicians' not in config:
            config['technicians'] = []
        technicians = config.get('technicians', [])
        found = False
        for i, t in enumerate(technicians):
            if t.get('id') == technician_id:
                technicians[i] = {**t, **technician_data, 'id': technician_id}
                found = True
                break
        if not found:
            technicians.append({**technician_data, 'id': technician_id})
        config['technicians'] = technicians
        _save_config_file(config)

def delete_technician(technician_id):
    """Exclui um técnico"""
    if not USE_DATABASE:
        config = _load_config_file()
        if 'technicians' in config:
            config['technicians'] = [t for t in config['technicians'] if t.get('id') != technician_id]
            _save_config_file(config)
        return

    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                if 'technicians' in config:
                    config['technicians'] = [t for t in config['technicians'] if t.get('id') != technician_id]
                    _save_config_file(config)
                return
            cur = _get_cursor(conn)
            cur.execute("DELETE FROM technicians WHERE id = %s", (technician_id,))
            conn.commit()
    except Exception as e:
        print(f"⚠️  Erro ao excluir técnico: {e}")
        config = _load_config_file()
        if 'technicians' in config:
            config['technicians'] = [t for t in config['technicians'] if t.get('id') != technician_id]
            _save_config_file(config)


# ========== GESTÃO FINANCEIRA ==========

def get_all_transactions(start_date=None, end_date=None):
    """Obtém todas as transações financeiras"""
    from datetime import datetime
    
    if not USE_DATABASE:
        config = _load_config_file()
        transactions = config.get('transactions', [])
        # Filtrar por data se necessário
        if start_date and end_date:
            try:
                start_dt = datetime.fromisoformat(start_date) if isinstance(start_date, str) else start_date
                end_dt = datetime.fromisoformat(end_date) if isinstance(end_date, str) else end_date
                
                filtered = []
                for t in transactions:
                    date_str = t.get('date') or t.get('created_at')
                    if date_str:
                        t_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        if t_date.tzinfo:
                            t_date = t_date.replace(tzinfo=None)
                        if start_dt <= t_date <= end_dt:
                            filtered.append(t)
                return sorted(filtered, key=lambda x: x.get('date') or x.get('created_at'), reverse=True)
            except:
                return sorted(transactions, key=lambda x: x.get('date') or x.get('created_at'), reverse=True)
        return sorted(transactions, key=lambda x: x.get('date') or x.get('created_at'), reverse=True)
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                return config.get('transactions', [])
            
            cur = _get_cursor(conn, dict_cursor=True)
            
            query = "SELECT data FROM transactions"
            params = []
            
            if start_date and end_date:
                query += " WHERE (data->>'date')::timestamp BETWEEN %s AND %s"
                params.extend([start_date, end_date])
            
            query += " ORDER BY (data->>'date')::timestamp DESC"
            
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            return [row['data'] for row in rows]
    except Exception as e:
        print(f"⚠️  Erro ao ler transações do banco: {e}")
        return []

def get_transaction(transaction_id):
    """Obtém uma transação específica"""
    if not USE_DATABASE:
        config = _load_config_file()
        transactions = config.get('transactions', [])
        for t in transactions:
            if t.get('id') == transaction_id:
                return t
        return None
    
    try:
        with get_db_connection() as conn:
            if not conn:
                return None
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT data FROM transactions WHERE id = %s", (transaction_id,))
            row = cur.fetchone()
            return row['data'] if row else None
    except Exception as e:
        print(f"⚠️  Erro ao ler transação: {e}")
        return None

def save_transaction(transaction_id, transaction_data):
    """Salva ou atualiza uma transação"""
    if not USE_DATABASE:
        config = _load_config_file()
        if 'transactions' not in config:
            config['transactions'] = []
        transactions = config.get('transactions', [])
        found = False
        for i, t in enumerate(transactions):
            if t.get('id') == transaction_id:
                transactions[i] = transaction_data
                found = True
                break
        if not found:
            transactions.append(transaction_data)
        config['transactions'] = transactions
        _save_config_file(config)
        return
    
    try:
        with get_db_connection() as conn:
            if not conn:
                # Fallback
                config = _load_config_file()
                if 'transactions' not in config:
                    config['transactions'] = []
                transactions = config.get('transactions', [])
                found = False
                for i, t in enumerate(transactions):
                    if t.get('id') == transaction_id:
                        transactions[i] = transaction_data
                        found = True
                        break
                if not found:
                    transactions.append(transaction_data)
                config['transactions'] = transactions
                _save_config_file(config)
                return

            cur = _get_cursor(conn)
            data_json = json.dumps(transaction_data)
            
            cur.execute("""
                INSERT INTO transactions (id, data, updated_at)
                VALUES (%s, %s::jsonb, CURRENT_TIMESTAMP)
                ON CONFLICT (id) 
                DO UPDATE SET data = %s::jsonb, updated_at = CURRENT_TIMESTAMP
            """, (transaction_id, data_json, data_json))
            conn.commit()
    except Exception as e:
        print(f"⚠️  Erro ao salvar transação: {e}")

def delete_transaction(transaction_id):
    """Remove uma transação"""
    if not USE_DATABASE:
        config = _load_config_file()
        if 'transactions' in config:
            config['transactions'] = [t for t in config['transactions'] if t.get('id') != transaction_id]
            _save_config_file(config)
        return

    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                if 'transactions' in config:
                    config['transactions'] = [t for t in config['transactions'] if t.get('id') != transaction_id]
                    _save_config_file(config)
                return
            
            cur = _get_cursor(conn)
            cur.execute("DELETE FROM transactions WHERE id = %s", (transaction_id,))
            conn.commit()
    except Exception as e:
        print(f"⚠️  Erro ao excluir transação: {e}")

def get_financial_summary(start_date=None, end_date=None):
    """
    Retorna resumo financeiro consolidado (Reparos + Transações Manuais)
    """
    from datetime import datetime, timedelta
    
    # Se não informar datas, assume mês atual
    if not start_date or not end_date:
        now = datetime.now()
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if now.month == 12:
            end_date = now.replace(year=now.year+1, month=1, day=1) - timedelta(seconds=1)
        else:
            end_date = now.replace(month=now.month+1, day=1) - timedelta(seconds=1)
    
    # 1. Dados de Reparos (Automático)
    repair_data = get_financial_data(start_date, end_date)
    
    # 2. Dados de Transações Manuais
    transactions = get_all_transactions(start_date, end_date)
    
    manual_income = 0.0
    manual_expense = 0.0
    
    category_totals = {}
    
    # Somar transações manuais
    for t in transactions:
        amount = float(t.get('amount', 0))
        t_type = t.get('type') # 'income' ou 'expense'
        category = t.get('category', 'Outros')
        
        if t_type == 'income':
            manual_income += amount
            # Categorias de entrada
            cat_key = f"in_{category}"
            category_totals[cat_key] = category_totals.get(cat_key, 0) + amount
        elif t_type == 'expense':
            manual_expense += amount
            # Categorias de saída
            cat_key = f"out_{category}"
            category_totals[cat_key] = category_totals.get(cat_key, 0) + amount
    
    # Adicionar dados de reparos às categorias
    repair_revenue = repair_data.get('total_billing', 0)
    repair_cost = repair_data.get('total_cost', 0)
    
    category_totals['in_Serviços'] = category_totals.get('in_Serviços', 0) + repair_revenue
    category_totals['out_Peças'] = category_totals.get('out_Peças', 0) + repair_cost
    
    # Totais consolidados
    total_income = repair_revenue + manual_income
    total_expense = repair_cost + manual_expense
    net_profit = total_income - total_expense
    
    # Preparar dados para gráficos
    # Agrupar por categoria para o gráfico
    expense_categories = {k.replace('out_', ''): v for k, v in category_totals.items() if k.startswith('out_')}
    income_categories = {k.replace('in_', ''): v for k, v in category_totals.items() if k.startswith('in_')}
    
    # Base do retorno é os dados de reparo (para manter compatibilidade com dashboard existente)
    result = repair_data.copy()
    
    # Atualizar/Adicionar novos dados
    result.update({
        'period': {
            'start': start_date,
            'end': end_date
        },
        'summary': {
            'total_income': total_income,
            'total_expense': total_expense,
            'net_profit': net_profit,
            'repair_revenue': repair_revenue,
            'repair_cost': repair_cost,
            'manual_income': manual_income,
            'manual_expense': manual_expense
        },
        'categories': {
            'income': income_categories,
            'expense': expense_categories
        },
        'transactions': transactions # Lista para exibir na tabela
    })
    
    return result
