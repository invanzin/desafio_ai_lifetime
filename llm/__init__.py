"""
Módulo LLM: Cliente centralizado para interações com OpenAI.

Este módulo fornece abstrações para trabalhar com a API da OpenAI
via LangChain, facilitando reutilização e manutenção.
"""

from llm.openai_client import OpenAIClient, default_client

__all__ = ["OpenAIClient", "default_client"]

