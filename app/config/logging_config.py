"""
Configuração centralizada de logging para a aplicação.

Este módulo configura logging estruturado com:
- Rotação automática de arquivos
- Níveis separados (INFO geral + ERROR específico)
- Formato padronizado com timestamp
- Output para console (dev) e arquivo (prod)

Uso:
    >>> from app.config.logging_config import setup_logging
    >>> setup_logging()
    >>> logger = logging.getLogger(__name__)
"""

import logging
import logging.handlers
import os
from pathlib import Path


def setup_logging(
    log_level: str = "INFO",
    log_dir: str = "logs",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    console_output: bool = True
):
    """
    Configura o sistema de logging da aplicação.
    
    Cria dois handlers:
    1. **app.log** - Logs gerais (INFO+)
    2. **error.log** - Apenas erros (WARNING+)
    
    Recursos:
    - Rotação automática quando arquivo atinge max_bytes
    - Mantém backup_count arquivos antigos
    - Formato: [TIMESTAMP] [LEVEL] [MODULE] Message
    - Thread-safe (RotatingFileHandler)
    
    Args:
        log_level (str): Nível mínimo de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir (str): Diretório para salvar logs
        max_bytes (int): Tamanho máximo do arquivo antes de rotacionar (padrão: 10MB)
        backup_count (int): Número de backups a manter (padrão: 5)
        console_output (bool): Se True, também imprime logs no console
    
    Example:
        >>> setup_logging(log_level="DEBUG", console_output=True)
        >>> logger = logging.getLogger(__name__)
        >>> logger.info("Aplicação iniciada")
    """
    
    # Cria diretório de logs se não existir
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # Formato de log padronizado
    log_format = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Formato mais detalhado para erros
    error_format = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Obtém logger raiz
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove handlers existentes (evita duplicação)
    root_logger.handlers.clear()
    
    # ========================================================================
    # HANDLER 1: Arquivo de logs gerais (app.log)
    # ========================================================================
    app_log_handler = logging.handlers.RotatingFileHandler(
        filename=log_path / "app.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    app_log_handler.setLevel(logging.INFO)
    app_log_handler.setFormatter(log_format)
    root_logger.addHandler(app_log_handler)
    
    # ========================================================================
    # HANDLER 2: Arquivo de erros (error.log)
    # ========================================================================
    error_log_handler = logging.handlers.RotatingFileHandler(
        filename=log_path / "error.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    error_log_handler.setLevel(logging.WARNING)
    error_log_handler.setFormatter(error_format)
    root_logger.addHandler(error_log_handler)
    
    # ========================================================================
    # HANDLER 3: Console (opcional, útil para desenvolvimento)
    # ========================================================================
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(log_format)
        root_logger.addHandler(console_handler)
    
    # Log inicial confirmando configuração
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configurado - Nível: {log_level}, Diretório: {log_path.absolute()}")
    logger.info(f"Rotação: {max_bytes / 1024 / 1024:.1f}MB por arquivo, {backup_count} backups")


def get_logger(name: str) -> logging.Logger:
    """
    Retorna um logger configurado para o módulo especificado.
    
    Args:
        name (str): Nome do módulo (use __name__)
    
    Returns:
        logging.Logger: Logger configurado
    
    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Mensagem de log")
    """
    return logging.getLogger(name)

