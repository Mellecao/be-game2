"""Fixtures compartilhadas para todos os testes.

Garante que variaveis de ambiente minimas estejam definidas antes que
qualquer modulo server.* seja importado e instancie LLMs no nivel de modulo.
"""
import os

import pytest


@pytest.fixture(autouse=True, scope="session")
def set_required_env_vars():
    """Define OPENROUTER_API_KEY fake para todos os testes da sessao.

    Evita que LLM() no nivel de modulo (server/agents.py) levante
    ValidationError por api_key vazia ao ser importado pela primeira vez.
    So define se ainda nao estiver definida (respeita .env real em CI).
    """
    key = "OPENROUTER_API_KEY"
    if not os.environ.get(key):
        os.environ[key] = "fake-key-for-tests"
    yield
