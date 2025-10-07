"""
Configuração centralizada de logging para a aplicação.

Este módulo implementa a "Abordagem Cirúrgica" com 3 arquivos de log distintos:
- debug.log: Logs completos da aplicação (DEBUG+)
- info.log: Apenas logs de marcos de negócio (INFO)
- error.log: Apenas avisos e erros (WARNING+)

Uso:
    >>> from app.config.logging_config import setup_logging
    >>> setup_logging()
    >>> logger = logging.getLogger(__name__)
"""

import logging
import logging.handlers
from pathlib import Path

# PASSO 1: Criar um filtro customizado para isolar um nível de log específico.
class LevelFilter(logging.Filter):
    """
    Filtra logs para permitir apenas um nível específico.
    """
    def __init__(self, level):
        super().__init__()
        self.level = level

    def filter(self, record):
        # Retorna True apenas se o nível do log for exatamente o que queremos.
        return record.levelno == self.level


def setup_logging(
    log_level: str = "DEBUG",  # Padrão agora é DEBUG para capturar tudo
    log_dir: str = "logs",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    console_output: bool = True
):
    """
    Configura o sistema de logging com 3 arquivos de saída + console.
    
    Args:
        log_level (str): Nível mínimo de log para o logger raiz e console.
        log_dir (str): Diretório para salvar logs.
    """
    
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # Formatos
    log_format = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    error_format = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # PASSO 2: Configurar o logger raiz com o nível mais baixo (DEBUG).
    # Ele funcionará como um "portão aberto", deixando todas as mensagens
    # passarem para os handlers, que farão a filtragem final.
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Remove handlers existentes para evitar duplicação
    root_logger.handlers.clear()
    
    # ========================================================================
    # HANDLER 1: Arquivo debug.log (TUDO)
    # ========================================================================
    debug_handler = logging.handlers.RotatingFileHandler(
        filename=log_path / "debug.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    debug_handler.setLevel(logging.DEBUG)  # Captura de DEBUG para cima
    debug_handler.setFormatter(log_format)
    root_logger.addHandler(debug_handler)
    
    # ========================================================================
    # HANDLER 2: Arquivo info.log (APENAS INFO)
    # ========================================================================
    info_handler = logging.handlers.RotatingFileHandler(
        filename=log_path / "info.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    info_handler.setLevel(logging.INFO)  # Nível mínimo é INFO
    # PASSO 3: Aplicar o filtro para permitir APENAS o nível INFO
    info_handler.addFilter(LevelFilter(logging.INFO))
    info_handler.setFormatter(log_format)
    root_logger.addHandler(info_handler)
    
    # ========================================================================
    # HANDLER 3: Arquivo error.log (WARNING E ACIMA)
    # ========================================================================
    error_handler = logging.handlers.RotatingFileHandler(
        filename=log_path / "error.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.WARNING) # Captura de WARNING para cima
    error_handler.setFormatter(error_format)
    root_logger.addHandler(error_handler)
    
    # ========================================================================
    # HANDLER 4: Console (opcional, para desenvolvimento)
    # ========================================================================
    if console_output:
        console_handler = logging.StreamHandler()
        # O console respeitará o nível de log definido na inicialização
        console_handler.setLevel(getattr(logging, log_level.upper()))
        console_handler.setFormatter(log_format)
        root_logger.addHandler(console_handler)
        
    logger = logging.getLogger(__name__)
    logger.info("Logging configurado com sucesso")


def get_logger(name: str) -> logging.Logger:
    """
    Retorna um logger configurado para o módulo especificado.
    
    Args:
        name (str): Nome do módulo (use __name__)
    
    Returns:
        logging.Logger: Logger configurado
    """
    return logging.getLogger(name)