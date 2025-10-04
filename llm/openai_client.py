"""
Cliente centralizado para interações com OpenAI via LangChain.

Este módulo fornece uma abstração reutilizável para configurar e usar
a API da OpenAI em diferentes partes do projeto. Centraliza configurações,
validações e facilita manutenção e testes.

Uso:
    >>> from llm.openai_client import OpenAIClient
    >>> client = OpenAIClient()
    >>> llm = client.get_llm()
    >>> # Use o LLM em suas chains do LangChain
"""

import os
from typing import Optional
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# Carrega variáveis de ambiente
load_dotenv()


class OpenAIClient:
    """
    Wrapper centralizado para gerenciar a configuração e instância do LLM da OpenAI.
    
    Esta classe encapsula toda a lógica de configuração da OpenAI API,
    incluindo validação de credenciais, seleção de modelo e parâmetros.
    Facilita reutilização em diferentes agentes (extractor, analyzer, etc).
    
    Attributes:
        api_key (str): Chave de API da OpenAI.
        default_model (str): Modelo padrão (ex: gpt-4o, gpt-4-turbo).
        default_temperature (float): Temperature padrão para geração.
        default_timeout (float): Timeout padrão em segundos.
    
    Example:
        >>> # Uso básico
        >>> client = OpenAIClient()
        >>> llm = client.get_llm()
        
        >>> # Com configurações customizadas
        >>> llm_criativo = client.get_llm(temperature=0.7)
        >>> llm_rapido = client.get_llm(model="gpt-3.5-turbo")
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
        default_temperature: float = 0.0,
        default_timeout: float = 30.0
    ):
        """
        Inicializa o cliente OpenAI com configurações padrão.
        
        Args:
            api_key (Optional[str]): Chave de API. Se None, lê de OPENAI_API_KEY env var.
            default_model (Optional[str]): Modelo padrão. Se None, lê de OPENAI_MODEL env var.
            default_temperature (float): Temperature padrão (0.0 = determinístico).
            default_timeout (float): Timeout padrão em segundos.
        
        Raises:
            ValueError: Se OPENAI_API_KEY não estiver configurada.
        """
        # Obtém API key (prioridade: parâmetro > env var)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OPENAI_API_KEY não configurada. "
                "Configure a variável de ambiente ou passe como parâmetro."
            )
        
        # Obtém modelo padrão (prioridade: parâmetro > env var > fallback)
        self.default_model = default_model or os.getenv("OPENAI_MODEL", "gpt-4o")
        
        # Armazena configurações padrão
        self.default_temperature = default_temperature
        self.default_timeout = default_timeout
        
        # Cache da instância LLM padrão (criada sob demanda)
        self._default_llm: Optional[ChatOpenAI] = None
    
    def get_llm(
        self,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        timeout: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> ChatOpenAI:
        """
        Retorna uma instância configurada do ChatOpenAI.
        
        Este método cria ou reutiliza uma instância do LLM com as configurações
        especificadas. Se todos os parâmetros forem None, retorna uma instância
        cacheada com configurações padrão (para melhor performance).
        
        Args:
            model (Optional[str]): Modelo a usar. Se None, usa default_model.
            temperature (Optional[float]): Temperature (0.0-2.0). Se None, usa default.
            timeout (Optional[float]): Timeout em segundos. Se None, usa default.
            max_tokens (Optional[int]): Máximo de tokens na resposta. Se None, sem limite.
            **kwargs: Outros parâmetros do ChatOpenAI.
        
        Returns:
            ChatOpenAI: Instância configurada do modelo de linguagem.
        
        Example:
            >>> client = OpenAIClient()
            
            >>> # LLM padrão (determinístico, gpt-4o)
            >>> llm = client.get_llm()
            
            >>> # LLM para análise criativa
            >>> llm_criativo = client.get_llm(temperature=0.7)
            
            >>> # LLM rápido e barato
            >>> llm_rapido = client.get_llm(model="gpt-3.5-turbo", timeout=10.0)
            
            >>> # LLM com limite de tokens (para controle de custo)
            >>> llm_controlado = client.get_llm(max_tokens=500)
        """
        # Se todos os parâmetros opcionais são None, reutiliza instância cacheada
        if all(p is None for p in [model, temperature, timeout, max_tokens]) and not kwargs:
            if self._default_llm is None:
                self._default_llm = self._create_llm()
            return self._default_llm
        
        # Cria nova instância com configurações customizadas
        return self._create_llm(
            model=model,
            temperature=temperature,
            timeout=timeout,
            max_tokens=max_tokens,
            **kwargs
        )
    
    def _create_llm(
        self,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        timeout: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
        ) -> ChatOpenAI:
        """
        Cria uma nova instância do ChatOpenAI (método interno).
        
        Args:
            model (Optional[str]): Modelo a usar.
            temperature (Optional[float]): Temperature de geração.
            timeout (Optional[float]): Timeout em segundos.
            max_tokens (Optional[int]): Máximo de tokens na resposta.
            **kwargs: Outros parâmetros do ChatOpenAI.
        
        Returns:
            ChatOpenAI: Nova instância configurada.
        """
        # Usa valores passados ou fallback para defaults
        final_model = model if model is not None else self.default_model
        final_temperature = temperature if temperature is not None else self.default_temperature
        final_timeout = timeout if timeout is not None else self.default_timeout
        
        # Prepara kwargs para ChatOpenAI
        llm_kwargs = {
            "model": final_model,
            "temperature": final_temperature,
            "timeout": final_timeout,
            "api_key": self.api_key,
            **kwargs
        }
        
        # Adiciona max_tokens apenas se especificado
        if max_tokens is not None:
            llm_kwargs["max_tokens"] = max_tokens
        
        return ChatOpenAI(**llm_kwargs)
    
    def get_model_info(self) -> dict:
        """
        Retorna informações sobre a configuração atual.
        
        Útil para debugging e logging de configuração.
        
        Returns:
            dict: Dicionário com informações de configuração.
        
        Example:
            >>> client = OpenAIClient()
            >>> print(client.get_model_info())
            {
                'default_model': 'gpt-4o',
                'default_temperature': 0.0,
                'default_timeout': 30.0,
                'api_key_configured': True
            }
        """
        return {
            "default_model": self.default_model,
            "default_temperature": self.default_temperature,
            "default_timeout": self.default_timeout,
            "api_key_configured": bool(self.api_key),
            "api_key_prefix": self.api_key[:10] + "..." if self.api_key else None
        }


# ============================================================================
# INSTÂNCIA GLOBAL PADRÃO (para conveniência)
# ============================================================================

# Instância global singleton para uso simples
# Você pode importar diretamente: from llm.openai_client import default_client
try:
    default_client = OpenAIClient()
except ValueError:
    # Se não houver API key, default_client será None
    default_client = None

