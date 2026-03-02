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
    DATABASE_URL = 'postgresql://rai:nk1HAfaFPhbOvg34lqWl7YC5LfPNnNS3@dpg-d57kenggjchc739lcorg-a.virginia-postgres.render.com/mobiledb_p0w2'
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
        print(f"⚠️  Erro ao ler do banco, usando config.json: {e}")
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

# ========== FUNÇÕES DE CUSTOMER PASSWORDS ==========

def get_customer_password_hash(cpf):
    """Obtém o hash da senha de um cliente pelo CPF"""
    if not USE_DATABASE:
        return None
    try:
        with get_db_connection() as conn:
            if not conn: return None
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT password_hash FROM customer_passwords WHERE cpf = %s", (cpf,))
            row = cur.fetchone()
            return row['password_hash'] if row else None
    except Exception as e:
        print(f"⚠️  Erro ao obter hash de senha do cliente: {e}")
        return None

def set_customer_password_hash(cpf, password_hash):
    """Define ou atualiza o hash da senha de um cliente"""
    if not USE_DATABASE:
        return False
    try:
        with get_db_connection() as conn:
            if not conn: return False
            cur = _get_cursor(conn)
            cur.execute("""
                INSERT INTO customer_passwords (cpf, password_hash, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (cpf) 
                DO UPDATE SET password_hash = %s, updated_at = CURRENT_TIMESTAMP
            """, (cpf, password_hash, password_hash))
            return True
    except Exception as e:
        print(f"⚠️  Erro ao definir hash de senha do cliente: {e}")
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

# ========== FUNÇÕES DE PUSH NOTIFICATIONS ==========

def save_push_token(cpf, token, device_info=None):
    """Salva um token de notificação push para um CPF"""
    if not USE_DATABASE:
        return False
    try:
        with get_db_connection() as conn:
            if not conn: return False
            cur = _get_cursor(conn)
            device_info_json = json.dumps(device_info) if device_info else None
            cur.execute("""
                INSERT INTO push_tokens (cpf, token, device_info, updated_at)
                VALUES (%s, %s, %s::jsonb, CURRENT_TIMESTAMP)
                ON CONFLICT (cpf, token) 
                DO UPDATE SET device_info = %s::jsonb, updated_at = CURRENT_TIMESTAMP
            """, (cpf, token, device_info_json, device_info_json))
            return True
    except Exception as e:
        print(f"⚠️  Erro ao salvar token push: {e}")
        return False

def get_push_tokens_by_cpf(cpf):
    """Obtém todos os tokens de notificação push para um CPF"""
    if not USE_DATABASE:
        return []
    try:
        with get_db_connection() as conn:
            if not conn: return []
            cur = _get_cursor(conn, dict_cursor=True)
            cur.execute("SELECT token FROM push_tokens WHERE cpf = %s", (cpf,))
            tokens = cur.fetchall()
            return [t['token'] for t in tokens]
    except Exception as e:
        print(f"⚠️  Erro ao obter tokens push por CPF: {e}")
        return []

def delete_push_token(token):
    """Deleta um token de notificação push"""
    if not USE_DATABASE:
        return False
    try:
        with get_db_connection() as conn:
            if not conn: return False
            cur = _get_cursor(conn)
            cur.execute("DELETE FROM push_tokens WHERE token = %s", (token,))
            return True
    except Exception as e:
        print(f"⚠️  Erro ao deletar token push: {e}")
        return False

def delete_push_tokens_by_cpf(cpf):
    """Deleta todos os tokens de notificação push para um CPF"""
    if not USE_DATABASE:
        return False
    try:
        with get_db_connection() as conn:
            if not conn: return False
            cur = _get_cursor(conn)
            cur.execute("DELETE FROM push_tokens WHERE cpf = %s", (cpf,))
            return True
    except Exception as e:
        print(f"⚠️  Erro ao deletar tokens push por CPF: {e}")
        return False
