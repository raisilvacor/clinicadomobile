"""
Módulo de gerenciamento do banco de dados PostgreSQL
Compatível com Python 3.13 usando psycopg (psycopg3)
"""
import os
import json
from contextlib import contextmanager
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

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

def _get_database_url():
    url = os.environ.get('DATABASE_URL')
    if url:
        return url

    host = os.environ.get('PGHOST')
    user = os.environ.get('PGUSER')
    password = os.environ.get('PGPASSWORD')
    database = os.environ.get('PGDATABASE')
    port = os.environ.get('PGPORT') or '5432'

    if host and user and password and database:
        return f'postgresql://{user}:{password}@{host}:{port}/{database}'

    return None

def _redact_database_url(database_url):
    try:
        parts = urlsplit(database_url)
        netloc = parts.netloc
        if '@' in netloc:
            creds, host = netloc.rsplit('@', 1)
            if ':' in creds:
                username, _ = creds.split(':', 1)
                netloc = f'{username}:***@{host}'
            else:
                netloc = f'{creds}@{host}'
        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    except Exception:
        return '***'

DATABASE_URL = _get_database_url()
if DATABASE_URL:
    redacted = _redact_database_url(DATABASE_URL)
    try:
        host = urlsplit(DATABASE_URL).hostname or ''
        if host and '.' not in host:
            print(f"⚠️  DATABASE_URL parece inválida (host sem domínio): {host}")
            print("⚠️  Use a URL completa do Postgres (ex: ...render.com) nas variáveis de ambiente.")
    except Exception:
        pass
    print(f"✅ DATABASE_URL configurada: {redacted}")
else:
    print("⚠️  DATABASE_URL não configurada - usando config.json como fallback")
    USE_DATABASE = False

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
            if DATABASE_URL:
                parts = urlsplit(DATABASE_URL)
                query = dict(parse_qsl(parts.query, keep_blank_values=True))
                query.setdefault('sslmode', 'require')
                DATABASE_URL = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
                    
            if DATABASE_URL:
                print(f"🔌 DATABASE_URL: {_redact_database_url(DATABASE_URL)}")
            
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

        cur.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id VARCHAR(50) PRIMARY KEY,
                doc_type VARCHAR(10) NOT NULL,
                doc_number VARCHAR(14) UNIQUE NOT NULL,
                data JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS equipments (
                id VARCHAR(50) PRIMARY KEY,
                customer_id VARCHAR(50) NOT NULL,
                data JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS service_orders (
                id VARCHAR(50) PRIMARY KEY,
                os_number SERIAL UNIQUE,
                customer_id VARCHAR(50) NOT NULL,
                technician_id VARCHAR(50),
                equipment_id VARCHAR(50),
                status VARCHAR(30) NOT NULL,
                labor_value NUMERIC(12,2) DEFAULT 0,
                parts_value NUMERIC(12,2) DEFAULT 0,
                total_value NUMERIC(12,2) DEFAULT 0,
                budget_date DATE,
                authorized BOOLEAN DEFAULT FALSE,
                opened_at DATE,
                concluded_at DATE,
                delivered_at DATE,
                data JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS service_order_parts (
                id SERIAL PRIMARY KEY,
                service_order_id VARCHAR(50) NOT NULL,
                part VARCHAR(300) NOT NULL,
                quantity INTEGER NOT NULL,
                value NUMERIC(12,2) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS service_order_history (
                id SERIAL PRIMARY KEY,
                service_order_id VARCHAR(50) NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tabela para produtos da loja
        cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id VARCHAR(50) PRIMARY KEY,
                data JSONB NOT NULL,
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
        
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_repairs_repair_id ON repairs(id)")

        cur.execute("CREATE INDEX IF NOT EXISTS idx_suppliers_id ON suppliers(id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_budget_requests_status ON budget_requests(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_customers_doc_number ON customers(doc_number)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_customers_created_at ON customers(created_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_equipments_customer_id ON equipments(customer_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_service_orders_customer_id ON service_orders(customer_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_service_orders_status ON service_orders(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_service_orders_public_token ON service_orders ((data->>'public_token'))")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_service_order_parts_os_id ON service_order_parts(service_order_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_service_order_history_os_id ON service_order_history(service_order_id)")
        
            
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
            conn.commit()
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
                config = _load_config_file()
                repairs = config.get('repairs', [])
                config['repairs'] = [r for r in repairs if r.get('id') != repair_id]
                _save_config_file(config)
                return
            cur = _get_cursor(conn)
            cur.execute("DELETE FROM repairs WHERE id = %s", (repair_id,))
    except Exception as e:
        print(f"⚠️  Erro ao deletar do banco, usando config.json: {e}")
        config = _load_config_file()
        repairs = config.get('repairs', [])
        config['repairs'] = [r for r in repairs if r.get('id') != repair_id]
        _save_config_file(config)

# ========== FUNÇÕES DE TRANSAÇÕES (FLUXO DE CAIXA) ==========

def get_all_transactions():
    """Obtém todas as transações"""
    if not USE_DATABASE:
        config = _load_config_file()
        return config.get('transactions', [])
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                return config.get('transactions', [])
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT data FROM transactions ORDER BY created_at DESC")
            rows = cur.fetchall()
            return [row['data'] for row in rows]
    except Exception as e:
        print(f"⚠️  Erro ao ler do banco, usando config.json: {e}")
        config = _load_config_file()
        return config.get('transactions', [])

def get_transaction(transaction_id):
    """Obtém uma transação específica"""
    if not USE_DATABASE:
        config = _load_config_file()
        transactions = config.get('transactions', [])
        for transaction in transactions:
            if transaction.get('id') == transaction_id:
                return transaction
        return None
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                return config.get('transactions', [])
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT data FROM transactions WHERE id = %s", (transaction_id,))
            row = cur.fetchone()
            return row['data'] if row else None
    except Exception as e:
        print(f"⚠️  Erro ao ler do banco, usando config.json: {e}")
        config = _load_config_file()
        transactions = config.get('transactions', [])
        for transaction in transactions:
            if transaction.get('id') == transaction_id:
                return transaction
        return None

def save_transaction(transaction_id, transaction_data):
    """Salva ou atualiza uma transação"""
    if not USE_DATABASE:
        config = _load_config_file()
        if 'transactions' not in config:
            config['transactions'] = []
        transactions = config.get('transactions', [])
        # Atualizar ou adicionar
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
                config = _load_config_file()
                if 'transactions' not in config:
                    config['transactions'] = []
                transactions = config.get('transactions', [])
                # Atualizar ou adicionar
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
    except Exception as e:
        print(f"⚠️  Erro ao salvar no banco, usando config.json: {e}")
        config = _load_config_file()
        if 'transactions' not in config:
            config['transactions'] = []
        transactions = config.get('transactions', [])
        # Atualizar ou adicionar
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

def delete_transaction(transaction_id):
    """Deleta uma transação"""
    if not USE_DATABASE:
        config = _load_config_file()
        transactions = config.get('transactions', [])
        config['transactions'] = [t for t in transactions if t.get('id') != transaction_id]
        _save_config_file(config)
        return
    
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                transactions = config.get('transactions', [])
                config['transactions'] = [t for t in transactions if t.get('id') != transaction_id]
                _save_config_file(config)
                return
            cur = _get_cursor(conn)
            cur.execute("DELETE FROM transactions WHERE id = %s", (transaction_id,))
    except Exception as e:
        print(f"⚠️  Erro ao deletar do banco, usando config.json: {e}")
        config = _load_config_file()
        transactions = config.get('transactions', [])
        config['transactions'] = [t for t in transactions if t.get('id') != transaction_id]
        _save_config_file(config)

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
            return row['data'] if row else None
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
            cur = _get_cursor(conn)
            data_json = json.dumps(supplier_data)
            cur.execute("""
                INSERT INTO suppliers (id, data, updated_at)
                VALUES (%s, %s::jsonb, CURRENT_TIMESTAMP)
                ON CONFLICT (id) 
                DO UPDATE SET data = %s::jsonb, updated_at = CURRENT_TIMESTAMP
            """, (supplier_id, data_json, data_json))
    except Exception as e:
        print(f"⚠️  Erro ao salvar no banco, usando config.json: {e}")
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
                config = _load_config_file()
                suppliers = config.get('suppliers', [])
                config['suppliers'] = [s for s in suppliers if s.get('id') != supplier_id]
                _save_config_file(config)
                return
            cur = _get_cursor(conn)
            cur.execute("DELETE FROM suppliers WHERE id = %s", (supplier_id,))
    except Exception as e:
        print(f"⚠️  Erro ao deletar do banco, usando config.json: {e}")
        config = _load_config_file()
        suppliers = config.get('suppliers', [])
        config['suppliers'] = [s for s in suppliers if s.get('id') != supplier_id]
        _save_config_file(config)

# ========== FUNÇÕES DE CLIENTES ==========

def get_all_customers():
    """Obtém todos os clientes"""
    if not USE_DATABASE:
        config = _load_config_file()
        return config.get('customers', [])
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                return config.get('customers', [])
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT id, doc_type, doc_number, data, created_at, updated_at FROM customers ORDER BY created_at DESC")
            rows = cur.fetchall()
            customers = []
            for row in rows:
                data = row['data'] if row and row.get('data') else {}
                data['id'] = row['id']
                data['doc_type'] = row['doc_type']
                data['doc_number'] = row['doc_number']
                data['created_at'] = row['created_at']
                data['updated_at'] = row['updated_at']
                customers.append(data)
            return customers
    except Exception as e:
        print(f"⚠️  Erro ao obter clientes: {e}")
        config = _load_config_file()
        return config.get('customers', [])

def get_customer(customer_id):
    """Obtém um cliente específico"""
    if not USE_DATABASE:
        config = _load_config_file()
        customers = config.get('customers', [])
        for c in customers:
            if c.get('id') == customer_id:
                return c
        return None
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                customers = config.get('customers', [])
                for c in customers:
                    if c.get('id') == customer_id:
                        return c
                return None
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT id, doc_type, doc_number, data, created_at, updated_at FROM customers WHERE id = %s", (customer_id,))
            row = cur.fetchone()
            if not row:
                return None
            data = row['data'] if row.get('data') else {}
            data['id'] = row['id']
            data['doc_type'] = row['doc_type']
            data['doc_number'] = row['doc_number']
            data['created_at'] = row['created_at']
            data['updated_at'] = row['updated_at']
            return data
    except Exception as e:
        print(f"⚠️  Erro ao obter cliente: {e}")
        return None

def get_customer_by_doc(doc_number):
    """Obtém um cliente pelo CPF/CNPJ (somente dígitos)"""
    doc_number = (doc_number or '').strip()
    if not doc_number:
        return None
    if not USE_DATABASE:
        config = _load_config_file()
        customers = config.get('customers', [])
        for c in customers:
            if c.get('doc_number') == doc_number:
                return c
        return None
    try:
        with get_db_connection() as conn:
            if not conn:
                return None
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT id, doc_type, doc_number, data, created_at, updated_at FROM customers WHERE doc_number = %s", (doc_number,))
            row = cur.fetchone()
            if not row:
                return None
            data = row['data'] if row.get('data') else {}
            data['id'] = row['id']
            data['doc_type'] = row['doc_type']
            data['doc_number'] = row['doc_number']
            data['created_at'] = row['created_at']
            data['updated_at'] = row['updated_at']
            return data
    except Exception as e:
        print(f"⚠️  Erro ao obter cliente por doc: {e}")
        return None

def save_customer(customer_id, customer_data):
    """Salva ou atualiza um cliente"""
    if not customer_data:
        return
    if not USE_DATABASE:
        config = _load_config_file()
        if 'customers' not in config:
            config['customers'] = []
        customers = config.get('customers', [])
        found = False
        for i, c in enumerate(customers):
            if c.get('id') == customer_id:
                customers[i] = customer_data
                found = True
                break
        if not found:
            customers.append(customer_data)
        config['customers'] = customers
        _save_config_file(config)
        return
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                if 'customers' not in config:
                    config['customers'] = []
                customers = config.get('customers', [])
                found = False
                for i, c in enumerate(customers):
                    if c.get('id') == customer_id:
                        customers[i] = customer_data
                        found = True
                        break
                if not found:
                    customers.append(customer_data)
                config['customers'] = customers
                _save_config_file(config)
                return
            doc_type = (customer_data.get('doc_type') or '').strip()
            doc_number = (customer_data.get('doc_number') or '').strip()
            data_json = json.dumps(customer_data)
            cur = _get_cursor(conn)
            cur.execute("""
                INSERT INTO customers (id, doc_type, doc_number, data, updated_at)
                VALUES (%s, %s, %s, %s::jsonb, CURRENT_TIMESTAMP)
                ON CONFLICT (id)
                DO UPDATE SET doc_type = %s, doc_number = %s, data = %s::jsonb, updated_at = CURRENT_TIMESTAMP
            """, (customer_id, doc_type, doc_number, data_json, doc_type, doc_number, data_json))
    except Exception as e:
        print(f"⚠️  Erro ao salvar cliente: {e}")
        raise

def delete_customer(customer_id):
    """Deleta um cliente"""
    if not USE_DATABASE:
        config = _load_config_file()
        customers = config.get('customers', [])
        config['customers'] = [c for c in customers if c.get('id') != customer_id]
        _save_config_file(config)
        return
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                customers = config.get('customers', [])
                config['customers'] = [c for c in customers if c.get('id') != customer_id]
                _save_config_file(config)
                return
            cur = _get_cursor(conn)
            cur.execute("DELETE FROM customers WHERE id = %s", (customer_id,))
    except Exception as e:
        print(f"⚠️  Erro ao deletar cliente: {e}")
        raise

def get_all_equipments_by_customer(customer_id):
    if not USE_DATABASE:
        config = _load_config_file()
        equipments = config.get('equipments', [])
        return [e for e in equipments if e.get('customer_id') == customer_id]
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                equipments = config.get('equipments', [])
                return [e for e in equipments if e.get('customer_id') == customer_id]
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT id, customer_id, data, created_at, updated_at FROM equipments WHERE customer_id = %s ORDER BY created_at DESC", (customer_id,))
            rows = cur.fetchall()
            result = []
            for row in rows:
                data = row['data'] if row and row.get('data') else {}
                data['id'] = row['id']
                data['customer_id'] = row['customer_id']
                data['created_at'] = row['created_at']
                data['updated_at'] = row['updated_at']
                result.append(data)
            return result
    except Exception as e:
        print(f"⚠️  Erro ao obter equipamentos: {e}")
        config = _load_config_file()
        equipments = config.get('equipments', [])
        return [e for e in equipments if e.get('customer_id') == customer_id]

def get_equipment(equipment_id):
    if not USE_DATABASE:
        config = _load_config_file()
        equipments = config.get('equipments', [])
        for e in equipments:
            if e.get('id') == equipment_id:
                return e
        return None
    try:
        with get_db_connection() as conn:
            if not conn:
                return None
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT id, customer_id, data, created_at, updated_at FROM equipments WHERE id = %s", (equipment_id,))
            row = cur.fetchone()
            if not row:
                return None
            data = row['data'] if row.get('data') else {}
            data['id'] = row['id']
            data['customer_id'] = row['customer_id']
            data['created_at'] = row['created_at']
            data['updated_at'] = row['updated_at']
            return data
    except Exception as e:
        print(f"⚠️  Erro ao obter equipamento: {e}")
        return None

def save_equipment(equipment_id, customer_id, equipment_data):
    if not equipment_data:
        return
    if not USE_DATABASE:
        config = _load_config_file()
        if 'equipments' not in config:
            config['equipments'] = []
        equipments = config.get('equipments', [])
        payload = equipment_data.copy()
        payload['id'] = equipment_id
        payload['customer_id'] = customer_id
        found = False
        for i, e in enumerate(equipments):
            if e.get('id') == equipment_id:
                equipments[i] = payload
                found = True
                break
        if not found:
            equipments.append(payload)
        config['equipments'] = equipments
        _save_config_file(config)
        return
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                if 'equipments' not in config:
                    config['equipments'] = []
                equipments = config.get('equipments', [])
                payload = equipment_data.copy()
                payload['id'] = equipment_id
                payload['customer_id'] = customer_id
                found = False
                for i, e in enumerate(equipments):
                    if e.get('id') == equipment_id:
                        equipments[i] = payload
                        found = True
                        break
                if not found:
                    equipments.append(payload)
                config['equipments'] = equipments
                _save_config_file(config)
                return
            cur = _get_cursor(conn)
            data_json = json.dumps(equipment_data)
            cur.execute("""
                INSERT INTO equipments (id, customer_id, data, updated_at)
                VALUES (%s, %s, %s::jsonb, CURRENT_TIMESTAMP)
                ON CONFLICT (id)
                DO UPDATE SET customer_id = %s, data = %s::jsonb, updated_at = CURRENT_TIMESTAMP
            """, (equipment_id, customer_id, data_json, customer_id, data_json))
    except Exception as e:
        print(f"⚠️  Erro ao salvar equipamento: {e}")
        raise

def delete_equipment(equipment_id):
    if not USE_DATABASE:
        config = _load_config_file()
        equipments = config.get('equipments', [])
        config['equipments'] = [e for e in equipments if e.get('id') != equipment_id]
        _save_config_file(config)
        return
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                equipments = config.get('equipments', [])
                config['equipments'] = [e for e in equipments if e.get('id') != equipment_id]
                _save_config_file(config)
                return
            cur = _get_cursor(conn)
            cur.execute("DELETE FROM equipments WHERE id = %s", (equipment_id,))
    except Exception as e:
        print(f"⚠️  Erro ao deletar equipamento: {e}")
        raise

def get_all_service_orders():
    if not USE_DATABASE:
        config = _load_config_file()
        return config.get('service_orders', [])
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                return config.get('service_orders', [])
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("""
                SELECT 
                    so.id,
                    so.os_number,
                    so.customer_id,
                    so.technician_id,
                    so.equipment_id,
                    so.status,
                    so.labor_value,
                    so.parts_value,
                    so.total_value,
                    so.opened_at,
                    so.concluded_at,
                    so.delivered_at,
                    so.created_at,
                    so.updated_at,
                    c.data->>'full_name' AS customer_name,
                    c.doc_number AS customer_doc,
                    t.name AS technician_name
                FROM service_orders so
                LEFT JOIN customers c ON c.id = so.customer_id
                LEFT JOIN technicians t ON t.id = so.technician_id
                ORDER BY so.os_number DESC
            """)
            rows = cur.fetchall()
            result = []
            for row in rows:
                result.append(row)
            return result
    except Exception as e:
        print(f"⚠️  Erro ao obter OS: {e}")
        config = _load_config_file()
        return config.get('service_orders', [])

def get_service_order(service_order_id):
    if not USE_DATABASE:
        config = _load_config_file()
        orders = config.get('service_orders', [])
        for o in orders:
            if o.get('id') == service_order_id:
                return o
        return None
    try:
        with get_db_connection() as conn:
            if not conn:
                return None
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("""
                SELECT 
                    id,
                    os_number,
                    customer_id,
                    technician_id,
                    equipment_id,
                    status,
                    labor_value,
                    parts_value,
                    total_value,
                    budget_date,
                    authorized,
                    opened_at,
                    concluded_at,
                    delivered_at,
                    data,
                    created_at,
                    updated_at
                FROM service_orders
                WHERE id = %s
            """, (service_order_id,))
            row = cur.fetchone()
            if not row:
                return None
            data = row['data'] if row.get('data') else {}
            data['id'] = row['id']
            data['os_number'] = row['os_number']
            data['customer_id'] = row['customer_id']
            data['technician_id'] = row['technician_id']
            data['equipment_id'] = row['equipment_id']
            data['status'] = row['status']
            data['labor_value'] = float(row['labor_value'] or 0)
            data['parts_value'] = float(row['parts_value'] or 0)
            data['total_value'] = float(row['total_value'] or 0)
            data['budget_date'] = row['budget_date']
            data['authorized'] = row['authorized']
            data['opened_at'] = row['opened_at']
            data['concluded_at'] = row['concluded_at']
            data['delivered_at'] = row['delivered_at']
            data['created_at'] = row['created_at']
            data['updated_at'] = row['updated_at']

            cur.execute("SELECT id, customer_id, doc_type, doc_number, data FROM customers WHERE id = %s", (row['customer_id'],))
            customer_row = cur.fetchone()
            if customer_row:
                customer_data = customer_row['data'] if customer_row.get('data') else {}
                customer_data['id'] = customer_row['id']
                customer_data['doc_type'] = customer_row['doc_type']
                customer_data['doc_number'] = customer_row['doc_number']
                data['customer'] = customer_data

            if row['technician_id']:
                cur.execute("SELECT id, name, cpf, email, phone, address, specialties, is_active FROM technicians WHERE id = %s", (row['technician_id'],))
                tech_row = cur.fetchone()
                if tech_row:
                    data['technician'] = tech_row

            if row['equipment_id']:
                cur.execute("SELECT id, customer_id, data FROM equipments WHERE id = %s", (row['equipment_id'],))
                eq_row = cur.fetchone()
                if eq_row:
                    eq_data = eq_row['data'] if eq_row.get('data') else {}
                    eq_data['id'] = eq_row['id']
                    eq_data['customer_id'] = eq_row['customer_id']
                    data['equipment'] = eq_data

            cur.execute("SELECT part, quantity, value FROM service_order_parts WHERE service_order_id = %s ORDER BY id ASC", (service_order_id,))
            data['parts'] = cur.fetchall() or []

            cur.execute("SELECT message, created_at FROM service_order_history WHERE service_order_id = %s ORDER BY created_at ASC", (service_order_id,))
            data['history'] = cur.fetchall() or []

            return data
    except Exception as e:
        print(f"⚠️  Erro ao obter OS: {e}")
        return None

def get_service_order_by_public_token(public_token):
    public_token = (public_token or '').strip()
    if not public_token:
        return None

    if not USE_DATABASE:
        config = _load_config_file()
        orders = config.get('service_orders', [])
        for o in orders:
            if isinstance(o, dict) and (o.get('public_token') or '') == public_token:
                return o
        return None

    try:
        with get_db_connection() as conn:
            if not conn:
                return None
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT id FROM service_orders WHERE data->>'public_token' = %s LIMIT 1", (public_token,))
            row = cur.fetchone()
            if not row:
                return None
            return get_service_order(row['id'])
    except Exception as e:
        print(f"⚠️  Erro ao obter OS por token: {e}")
        return None

def save_service_order(service_order_id, payload, parts, history_message=None, create_new=False):
    if not payload:
        return None
    from datetime import datetime
    if not USE_DATABASE:
        config = _load_config_file()
        if 'service_orders' not in config:
            config['service_orders'] = []
        orders = config.get('service_orders', [])
        if create_new:
            max_number = 0
            for o in orders:
                try:
                    max_number = max(max_number, int(o.get('os_number') or 0))
                except Exception:
                    continue
            payload['os_number'] = max_number + 1
        payload['id'] = service_order_id
        if parts is not None:
            payload['parts'] = parts
        if history_message:
            history = payload.get('history') or []
            history.append({'message': history_message, 'created_at': datetime.now().isoformat()})
            payload['history'] = history
        found = False
        for i, o in enumerate(orders):
            if o.get('id') == service_order_id:
                orders[i] = payload
                found = True
                break
        if not found:
            orders.append(payload)
        config['service_orders'] = orders
        _save_config_file(config)
        return payload.get('os_number')

    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                if 'service_orders' not in config:
                    config['service_orders'] = []
                orders = config.get('service_orders', [])
                if create_new:
                    max_number = 0
                    for o in orders:
                        try:
                            max_number = max(max_number, int(o.get('os_number') or 0))
                        except Exception:
                            continue
                    payload['os_number'] = max_number + 1
                payload['id'] = service_order_id
                if parts is not None:
                    payload['parts'] = parts
                if history_message:
                    history = payload.get('history') or []
                    history.append({'message': history_message, 'created_at': datetime.now().isoformat()})
                    payload['history'] = history
                found = False
                for i, o in enumerate(orders):
                    if o.get('id') == service_order_id:
                        orders[i] = payload
                        found = True
                        break
                if not found:
                    orders.append(payload)
                config['service_orders'] = orders
                _save_config_file(config)
                return payload.get('os_number')

            cur = _get_cursor(conn)
            data_json = json.dumps(payload)
            customer_id = payload.get('customer_id')
            technician_id = payload.get('technician_id')
            equipment_id = payload.get('equipment_id')
            status = payload.get('status')
            labor_value = payload.get('labor_value') or 0
            parts_value = payload.get('parts_value') or 0
            total_value = payload.get('total_value') or 0
            budget_date = payload.get('budget_date') or None
            authorized = payload.get('authorized') is True
            opened_at = payload.get('opened_at') or None
            concluded_at = payload.get('concluded_at') or None
            delivered_at = payload.get('delivered_at') or None

            if create_new:
                cur.execute("""
                    INSERT INTO service_orders (
                        id, customer_id, technician_id, equipment_id, status,
                        labor_value, parts_value, total_value, budget_date, authorized,
                        opened_at, concluded_at, delivered_at, data, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, CURRENT_TIMESTAMP)
                    RETURNING os_number
                """, (
                    service_order_id, customer_id, technician_id, equipment_id, status,
                    labor_value, parts_value, total_value, budget_date, authorized,
                    opened_at, concluded_at, delivered_at, data_json
                ))
                row = cur.fetchone()
                os_number = row[0] if row else None
            else:
                cur.execute("""
                    UPDATE service_orders
                    SET customer_id = %s, technician_id = %s, equipment_id = %s, status = %s,
                        labor_value = %s, parts_value = %s, total_value = %s, budget_date = %s, authorized = %s,
                        opened_at = %s, concluded_at = %s, delivered_at = %s, data = %s::jsonb, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (
                    customer_id, technician_id, equipment_id, status,
                    labor_value, parts_value, total_value, budget_date, authorized,
                    opened_at, concluded_at, delivered_at, data_json, service_order_id
                ))
                cur.execute("SELECT os_number FROM service_orders WHERE id = %s", (service_order_id,))
                row = cur.fetchone()
                os_number = row[0] if row else None

            if parts is not None:
                cur.execute("DELETE FROM service_order_parts WHERE service_order_id = %s", (service_order_id,))
                for p in parts:
                    part_name = (p.get('part') or '').strip()
                    quantity = int(p.get('quantity') or 0)
                    value = float(p.get('value') or 0)
                    if part_name and quantity > 0 and value >= 0:
                        cur.execute(
                            "INSERT INTO service_order_parts (service_order_id, part, quantity, value) VALUES (%s, %s, %s, %s)",
                            (service_order_id, part_name, quantity, value),
                        )

            if history_message:
                cur.execute(
                    "INSERT INTO service_order_history (service_order_id, message) VALUES (%s, %s)",
                    (service_order_id, history_message),
                )

            return os_number
    except Exception as e:
        print(f"⚠️  Erro ao salvar OS: {e}")
        raise

def delete_service_order(service_order_id):
    if not USE_DATABASE:
        config = _load_config_file()
        orders = config.get('service_orders', [])
        config['service_orders'] = [o for o in orders if o.get('id') != service_order_id]
        _save_config_file(config)
        return
    try:
        with get_db_connection() as conn:
            if not conn:
                config = _load_config_file()
                orders = config.get('service_orders', [])
                config['service_orders'] = [o for o in orders if o.get('id') != service_order_id]
                _save_config_file(config)
                return
            cur = _get_cursor(conn)
            cur.execute("DELETE FROM service_order_parts WHERE service_order_id = %s", (service_order_id,))
            cur.execute("DELETE FROM service_order_history WHERE service_order_id = %s", (service_order_id,))
            cur.execute("DELETE FROM service_orders WHERE id = %s", (service_order_id,))
    except Exception as e:
        print(f"⚠️  Erro ao deletar OS: {e}")
        raise

# ========== FUNÇÕES DE PRODUTOS ==========

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
        print(f"⚠️  Erro ao ler do banco, usando config.json: {e}")
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
        print(f"⚠️  Erro ao ler do banco, usando config.json: {e}")
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
        # Atualizar ou adicionar
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
                # Atualizar ou adicionar
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
    except Exception as e:
        print(f"⚠️  Erro ao salvar no banco, usando config.json: {e}")
        config = _load_config_file()
        if 'products' not in config:
            config['products'] = []
        products = config.get('products', [])
        # Atualizar ou adicionar
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
                config = _load_config_file()
                products = config.get('products', [])
                config['products'] = [p for p in products if p.get('id') != product_id]
                _save_config_file(config)
                return
            cur = _get_cursor(conn)
            cur.execute("DELETE FROM products WHERE id = %s", (product_id,))
    except Exception as e:
        print(f"⚠️  Erro ao deletar do banco, usando config.json: {e}")
        config = _load_config_file()
        products = config.get('products', [])
        config['products'] = [p for p in products if p.get('id') != product_id]
        _save_config_file(config)

# ========== FUNÇÕES DE MARCAS ==========

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
            cur.execute("SELECT data FROM brands ORDER BY created_at DESC")
            rows = cur.fetchall()
            return [row['data'] for row in rows]
    except Exception as e:
        print(f"⚠️  Erro ao ler do banco, usando config.json: {e}")
        config = _load_config_file()
        return config.get('brands', [])

def save_brand(brand_id, brand_data):
    """Salva ou atualiza uma marca"""
    if not USE_DATABASE:
        config = _load_config_file()
        if 'brands' not in config:
            config['brands'] = []
        brands = config.get('brands', [])
        # Atualizar ou adicionar
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
                # Atualizar ou adicionar
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
    except Exception as e:
        print(f"⚠️  Erro ao salvar no banco, usando config.json: {e}")
        config = _load_config_file()
        if 'brands' not in config:
            config['brands'] = []
        brands = config.get('brands', [])
        # Atualizar ou adicionar
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
                config = _load_config_file()
                brands = config.get('brands', [])
                config['brands'] = [b for b in brands if b.get('id') != brand_id]
                _save_config_file(config)
                return
            cur = _get_cursor(conn)
            cur.execute("DELETE FROM brands WHERE id = %s", (brand_id,))
    except Exception as e:
        print(f"⚠️  Erro ao deletar do banco, usando config.json: {e}")
        config = _load_config_file()
        brands = config.get('brands', [])
        config['brands'] = [b for b in brands if b.get('id') != brand_id]
        _save_config_file(config)

# ========== FUNÇÕES DE USUÁRIOS ADMIN ==========

def get_admin_user(user_id):
    """Obtém um usuário admin pelo ID"""
    if not USE_DATABASE:
        return None # Admin users should always be in DB
    try:
        with get_db_connection() as conn:
            if not conn: return None
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT id, username, password_hash, name, email, phone, permissions, is_active FROM admin_users WHERE id = %s", (user_id,))
            user = cur.fetchone()
            return user
    except Exception as e:
        print(f"⚠️  Erro ao obter usuário admin: {e}")
        return None

def get_admin_user_by_username(username):
    """Obtém um usuário admin pelo username"""
    if not USE_DATABASE:
        return None # Admin users should always be in DB
    try:
        with get_db_connection() as conn:
            if not conn: return None
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT id, username, password_hash, name, email, phone, permissions, is_active FROM admin_users WHERE username = %s", (username,))
            user = cur.fetchone()
            return user
    except Exception as e:
        print(f"⚠️  Erro ao obter usuário admin por username: {e}")
        return None

def get_all_admin_users():
    """Obtém todos os usuários admin"""
    if not USE_DATABASE:
        return []
    try:
        with get_db_connection() as conn:
            if not conn: return []
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT id, username, name, email, phone, permissions, is_active, created_at, updated_at FROM admin_users ORDER BY created_at DESC")
            users = cur.fetchall()
            return users
    except Exception as e:
        print(f"⚠️  Erro ao obter todos os usuários admin: {e}")
        return []

def save_admin_user(user_id, username, password_hash, name, email, phone, permissions, is_active):
    """Salva ou atualiza um usuário admin"""
    if not USE_DATABASE:
        return False
    try:
        with get_db_connection() as conn:
            if not conn: return False
            cur = _get_cursor(conn)
            permissions_json = json.dumps(permissions)
            cur.execute("""
                INSERT INTO admin_users (id, username, password_hash, name, email, phone, permissions, is_active, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (id) 
                DO UPDATE SET username = %s, password_hash = %s, name = %s, email = %s, phone = %s, permissions = %s::jsonb, is_active = %s, updated_at = CURRENT_TIMESTAMP
            """, (user_id, username, password_hash, name, email, phone, permissions_json, is_active,
                  username, password_hash, name, email, phone, permissions_json, is_active))
            return True
    except Exception as e:
        print(f"⚠️  Erro ao salvar usuário admin: {e}")
        return False

def delete_admin_user(user_id):
    """Deleta um usuário admin"""
    if not USE_DATABASE:
        return False
    try:
        with get_db_connection() as conn:
            if not conn: return False
            cur = _get_cursor(conn)
            cur.execute("DELETE FROM admin_users WHERE id = %s", (user_id,))
            return True
    except Exception as e:
        print(f"⚠️  Erro ao deletar usuário admin: {e}")
        return False

# ========== FUNÇÕES DE TÉCNICOS ==========

def get_technician(tech_id):
    """Obtém um técnico pelo ID"""
    if not USE_DATABASE:
        return None
    try:
        with get_db_connection() as conn:
            if not conn: return None
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT id, name, cpf, email, phone, address, specialties, is_active FROM technicians WHERE id = %s", (tech_id,))
            tech = cur.fetchone()
            return tech
    except Exception as e:
        print(f"⚠️  Erro ao obter técnico: {e}")
        return None

def get_all_technicians():
    """Obtém todos os técnicos"""
    if not USE_DATABASE:
        return []
    try:
        with get_db_connection() as conn:
            if not conn: return []
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT id, name, cpf, email, phone, address, specialties, is_active, created_at, updated_at FROM technicians ORDER BY created_at DESC")
            techs = cur.fetchall()
            return techs
    except Exception as e:
        print(f"⚠️  Erro ao obter todos os técnicos: {e}")
        return []

def save_technician(tech_id, name, cpf, email, phone, address, specialties, is_active):
    """Salva ou atualiza um técnico"""
    if not USE_DATABASE:
        return False
    try:
        with get_db_connection() as conn:
            if not conn: return False
            cur = _get_cursor(conn)
            specialties_json = json.dumps(specialties)
            cur.execute("""
                INSERT INTO technicians (id, name, cpf, email, phone, address, specialties, is_active, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (id) 
                DO UPDATE SET name = %s, cpf = %s, email = %s, phone = %s, address = %s, specialties = %s::jsonb, is_active = %s, updated_at = CURRENT_TIMESTAMP
            """, (tech_id, name, cpf, email, phone, address, specialties_json, is_active,
                  name, cpf, email, phone, address, specialties_json, is_active))
            return True
    except Exception as e:
        print(f"⚠️  Erro ao salvar técnico: {e}")
        return False

def delete_technician(tech_id):
    """Deleta um técnico"""
    if not USE_DATABASE:
        return False
    try:
        with get_db_connection() as conn:
            if not conn: return False
            cur = _get_cursor(conn)
            cur.execute("DELETE FROM technicians WHERE id = %s", (tech_id,))
            return True
    except Exception as e:
        print(f"⚠️  Erro ao deletar técnico: {e}")
        return False

# ========== FUNÇÕES DE BUDGET REQUESTS ==========

def get_all_budget_requests():
    """Obtém todas as solicitações de orçamento"""
    if not USE_DATABASE:
        return []
    try:
        with get_db_connection() as conn:
            if not conn: return []
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT id, data, status, created_at, updated_at FROM budget_requests ORDER BY created_at DESC")
            requests = cur.fetchall()
            return requests
    except Exception as e:
        print(f"⚠️  Erro ao obter solicitações de orçamento: {e}")
        return []

def get_budget_request(request_id):
    """Obtém uma solicitação de orçamento específica"""
    if not USE_DATABASE:
        return None
    try:
        with get_db_connection() as conn:
            if not conn: return None
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT id, data, status, created_at, updated_at FROM budget_requests WHERE id = %s", (request_id,))
            req = cur.fetchone()
            return req
    except Exception as e:
        print(f"⚠️  Erro ao obter solicitação de orçamento: {e}")
        return None

def save_budget_request(request_id, data, status='pendente'):
    """Salva ou atualiza uma solicitação de orçamento"""
    if not USE_DATABASE:
        return False
    try:
        with get_db_connection() as conn:
            if not conn: return False
            cur = _get_cursor(conn)
            data_json = json.dumps(data)
            cur.execute("""
                INSERT INTO budget_requests (id, data, status, updated_at)
                VALUES (%s, %s::jsonb, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (id) 
                DO UPDATE SET data = %s::jsonb, status = %s, updated_at = CURRENT_TIMESTAMP
            """, (request_id, data_json, status, data_json, status))
            return True
    except Exception as e:
        print(f"⚠️  Erro ao salvar solicitação de orçamento: {e}")
        return False

def update_budget_request_status(request_id, status, admin_notes=None):
    """Atualiza o status e notas de uma solicitação de orçamento"""
    if not USE_DATABASE:
        return False
    try:
        with get_db_connection() as conn:
            if not conn: return False
            cur = _get_cursor(conn, dict_cursor=True)
            # Obter dados atuais para atualizar as notas dentro do JSON data
            cur.execute("SELECT data FROM budget_requests WHERE id = %s", (request_id,))
            row = cur.fetchone()
            if not row:
                return False
            
            data = row['data']
            if admin_notes is not None:
                data['admin_notes'] = admin_notes
            
            data_json = json.dumps(data)
            cur.execute("""
                UPDATE budget_requests 
                SET status = %s, data = %s::jsonb, updated_at = CURRENT_TIMESTAMP 
                WHERE id = %s
            """, (status, data_json, request_id))
            return True
    except Exception as e:
        print(f"⚠️  Erro ao atualizar status da solicitação de orçamento: {e}")
        return False

def delete_budget_request(request_id):
    """Deleta uma solicitação de orçamento"""
    if not USE_DATABASE:
        return False
    try:
        with get_db_connection() as conn:
            if not conn: return False
            cur = _get_cursor(conn)
            cur.execute("DELETE FROM budget_requests WHERE id = %s", (request_id,))
            return True
    except Exception as e:
        print(f"⚠️  Erro ao deletar solicitação de orçamento: {e}")
        return False

# ========== FUNÇÕES DE CONFIGURAÇÃO DE ORÇAMENTO ==========

def get_budget_config():
    """Obtém a configuração do formulário de orçamento"""
    BUDGET_CONFIG_FILE = 'budget_config.json'
    
    def load_from_json():
        if os.path.exists(BUDGET_CONFIG_FILE):
            try:
                with open(BUDGET_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []

    if not USE_DATABASE:
        return load_from_json()
    
    try:
        with get_db_connection() as conn:
            if not conn:
                return load_from_json()
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT value FROM admin_settings WHERE key = 'budget_config'")
            row = cur.fetchone()
            if row:
                config = json.loads(row['value'])
                # Garantir que retorna uma lista
                if isinstance(config, dict) and 'brands' in config:
                    return config['brands']
                return config if isinstance(config, list) else []
            
            # Se não encontrar no banco, tentar carregar do JSON
            config = load_from_json()
            if config:
                # Salvar no banco para futuras consultas
                save_budget_config(config)
            return config
    except Exception as e:
        print(f"⚠️  Erro ao ler configuração de orçamento: {e}")
        return load_from_json()

def save_budget_config(config_data):
    """Salva a configuração do formulário de orçamento"""
    BUDGET_CONFIG_FILE = 'budget_config.json'
    
    # Salvar sempre no JSON como backup
    try:
        with open(BUDGET_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️  Erro ao salvar backup de orçamento em JSON: {e}")

    if not USE_DATABASE:
        return
    
    try:
        with get_db_connection() as conn:
            if not conn:
                return
            cur = _get_cursor(conn)
            config_json = json.dumps(config_data)
            cur.execute("""
                INSERT INTO admin_settings (key, value, updated_at)
                VALUES ('budget_config', %s, CURRENT_TIMESTAMP)
                ON CONFLICT (key) 
                DO UPDATE SET value = %s, updated_at = CURRENT_TIMESTAMP
            """, (config_json, config_json))
    except Exception as e:
        print(f"⚠️  Erro ao salvar configuração de orçamento no banco: {e}")

def transform_budget_config_to_raw(config):
    """Transforma a configuração estruturada em um formato simples para o orçamentador"""
    raw = {}
    if not config:
        return raw
        
    # Se for uma lista (formato do admin_budget_config)
    if isinstance(config, list):
        for brand_data in config:
            brand_name = brand_data.get('brand')
            if brand_name:
                raw[brand_name] = [m.get('name') for m in brand_data.get('models', [])]
        return raw

    # Se for um dicionário (formato antigo/legado)
    if isinstance(config, dict):
        brands_data = config.get('brands', [])
        for brand in brands_data:
            brand_name = brand.get('name')
            if brand_name:
                raw[brand_name] = [m.get('name') for m in brand.get('models', [])]
        raw['defeitos'] = [d.get('name') for d in config.get('defects', [])]
    
    return raw

# ========== FUNÇÕES DE QUALIDADE DE TÉCNICOS ==========

def calculate_technician_quality_score(tech_id):
    """Calcula o score de qualidade de um técnico baseado em seus reparos"""
    repairs = get_all_repairs()
    tech_repairs = [r for r in repairs if r.get('technician_id') == tech_id]
    
    if not tech_repairs:
        return {
            'score': 0,
            'total_repairs': 0,
            'completed_repairs': 0,
            'return_rate': 0,
            'level': 'Iniciante'
        }
    
    total = len(tech_repairs)
    completed = len([r for r in tech_repairs if r.get('status') == 'concluido'])
    returns = len([r for r in tech_repairs if r.get('repair_type') == 'retorno'])
    
    # Cálculo simples de score (0-100)
    # 70% peso para conclusão, 30% peso inverso para retornos
    completion_rate = (completed / total) * 100 if total > 0 else 0
    return_rate = (returns / total) * 100 if total > 0 else 0
    
    score = (completion_rate * 0.7) + ((100 - return_rate) * 0.3)
    
    level = 'Iniciante'
    if score >= 90: level = 'Mestre'
    elif score >= 75: level = 'Avançado'
    elif score >= 50: level = 'Intermediário'
    
    return {
        'score': round(score, 1),
        'total_repairs': total,
        'completed_repairs': completed,
        'return_rate': round(return_rate, 1),
        'level': level
    }

def get_all_technician_quality_scores():
    """Obtém os scores de qualidade de todos os técnicos ativos"""
    techs = get_all_technicians()
    scores = []
    for tech in techs:
        if tech.get('is_active'):
            quality = calculate_technician_quality_score(tech.get('id'))
            scores.append({
                'technician': tech,
                'quality_score': quality
            })
    return scores

# ========== FIM DO ARQUIVO ==========
