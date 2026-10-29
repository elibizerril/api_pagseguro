"""Erros da integração PagBank.

Separar erros de configuração de erros da API ajuda a distinguir:
- "esqueci o token" (problema local);
- "o PagBank recusou o payload" (problema de contrato);
- "a rede caiu" (problema de transporte).
"""

from __future__ import annotations

from typing import Any


class PagBankError(Exception):
    """Erro ao conversar com a Orders API."""

    def __init__(
        self,
        mensagem: str,
        *,
        status_code: int | None = None,
        detalhes: Any = None,
    ) -> None:
        super().__init__(mensagem)
        self.status_code = status_code
        self.detalhes = detalhes


class ConfigError(PagBankError):
    """Erro de configuração local, como token ausente."""
