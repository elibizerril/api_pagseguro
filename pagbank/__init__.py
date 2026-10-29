"""Integração didática com a Orders API do PagBank (antigo PagSeguro)."""

from .client import PagBankClient
from .errors import ConfigError, PagBankError
from .payloads import (
    Cartao,
    Cliente,
    Item,
    montar_pedido_credito,
    montar_pedido_pix,
    pedido_para_exibicao,
)

__all__ = [
    "Cartao",
    "Cliente",
    "ConfigError",
    "Item",
    "PagBankClient",
    "PagBankError",
    "montar_pedido_credito",
    "montar_pedido_pix",
    "pedido_para_exibicao",
]
