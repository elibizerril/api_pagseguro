"""Traduz erros conhecidos do PagBank em uma próxima ação concreta.

Regra de ouro: a dica **complementa** o erro, nunca o substitui. O CLI continua
imprimindo status HTTP, `code`, `description` e `parameter_name` — a dica é só
um atalho para quem já viu aquele código antes.

Só entram aqui códigos que observamos de verdade. Inventar dica para erro que
nunca vimos seria adivinhação disfarçada de conhecimento.
"""

from __future__ import annotations

from typing import Any

DICA_PIX_KEY = (
    "O vendedor dono do token não tem chave PIX utilizável. Confira em "
    "Pix > Minhas chaves se a chave está ATIVA (prefira chave aleatória) e "
    "aguarde a propagação (~15-60 min) antes de repetir. A chave é da conta, "
    "não do payload."
)

DICA_SOFT_DESCRIPTOR = (
    "A cobrança de crédito exige soft_descriptor (nome na fatura, 1-22 "
    "caracteres, sem acento/símbolo). Use --soft-descriptor."
)

DICA_TOKEN = (
    "O token foi recusado. Confira PAGBANK_TOKEN no .env e se ele é do "
    "ambiente certo (sandbox x produção). Lembre: variável de ambiente do "
    "shell ganha do .env."
)

DICA_PEDIDO = (
    "Não existe pedido com esse ID nesta conta/ambiente. Copie o ORDE_..."
    " inteiro e confirme se ele nasceu no mesmo ambiente (sandbox x produção)."
)


def dica_para(detalhes: Any) -> str | None:
    """Devolve uma dica para o primeiro erro conhecido do corpo, se houver."""
    if not isinstance(detalhes, dict):
        return None

    erros = detalhes.get("error_messages") or detalhes.get("errors") or []
    if not isinstance(erros, list):
        return None

    for erro in erros:
        if not isinstance(erro, dict):
            continue

        codigo = str(erro.get("code") or "").upper()
        parametro = str(erro.get("parameter_name") or "")

        if codigo == "40010":
            return DICA_PIX_KEY
        if codigo == "40002" and "soft_descriptor" in parametro:
            return DICA_SOFT_DESCRIPTOR
        if codigo == "UNAUTHORIZED":
            return DICA_TOKEN
        if codigo == "NOT_FOUND":
            return DICA_PEDIDO

    return None
