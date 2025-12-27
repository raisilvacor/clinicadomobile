# Configuração do Gunicorn para evitar timeouts
import multiprocessing

# Número de workers
workers = 1  # Render usa 1 worker por padrão

# Timeout aumentado para servir vídeos grandes
timeout = 120  # 2 minutos (aumentado de 30s padrão)

# Keep-alive
keepalive = 5

# Worker class
worker_class = "sync"

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Graceful timeout
graceful_timeout = 30

# Preload app para melhor performance
preload_app = True

