"""Modelos de entrada e montagem dos payloads da Orders API.

Fluxo didático:

    dados do CLI
        ↓
    Cliente / Item / Cartao   (DTO de entrada, validado)
        ↓
    montar_pedido_*()          (payload no contrato do PagBank)
        ↓
    PagBankClient.criar_pedido()

O template/CLI nunca deve montar JSON solto. Assim conseguimos testar o
contrato sem fazer uma requisição real.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .validacao import (
    mascarar_cpf,
    mascarar_numero_cartao,
    normalizar_soft_descriptor,
    somente_digitos,
    validar_cpf,
    validar_luhn,
    validar_validade,
)

EMAIL_SIMPLES = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TIPOS_TELEFONE = {"MOBILE", "HOME", "BUSINESS"}


@dataclass(frozen=True)
class Cliente:
    """Dados mínimos do comprador exigidos pela Orders API."""

    nome: str
    email: str
    cpf: str
    ddd: str = "11"
    telefone: str = "999999999"
    tipo_telefone: str = "MOBILE"

    def __post_init__(self) -> None:
        if len(self.nome.strip().split()) < 2:
            raise ValueError("Informe nome e sobrenome do cliente.")
        if len(self.nome.strip()) > 120:
            raise ValueError("O nome do cliente deve ter no máximo 120 caracteres.")
        if not EMAIL_SIMPLES.match(self.email.strip()):
            raise ValueError("E-mail do cliente inválido.")
        if not validar_cpf(self.cpf):
            raise ValueError("CPF do cliente inválido.")
        if not (self.ddd.isdigit() and len(self.ddd) == 2):
            raise ValueError("DDD deve ter 2 dígitos.")
        if len(somente_digitos(self.telefone)) not in (8, 9):
            raise ValueError("Telefone deve ter 8 ou 9 dígitos.")
        if self.tipo_telefone not in TIPOS_TELEFONE:
            raise ValueError("Tipo de telefone inválido.")


@dataclass(frozen=True)
class Item:
    """Item do pedido. O valor é sempre em centavos."""

    nome: str
    valor_centavos: int
    quantidade: int = 1

    def __post_init__(self) -> None:
        if not self.nome.strip():
            raise ValueError("Informe a descrição do item.")
        if len(self.nome.strip()) > 200:
            raise ValueError("A descrição do item deve ter no máximo 200 caracteres.")
        if self.valor_centavos < 100:
            raise ValueError("O valor mínimo do item é R$ 1,00 (100 centavos).")
        if self.quantidade < 1:
            raise ValueError("A quantidade deve ser pelo menos 1.")


@dataclass(frozen=True)
class Cartao:
    """Dados de cartão usados somente no fluxo de crédito desta etapa."""

    numero: str
    mes: int
    ano: int
    cvv: str
    portador_nome: str
    portador_cpf: str

    def __post_init__(self) -> None:
        if not validar_luhn(self.numero):
            raise ValueError("Número de cartão inválido (falhou no algoritmo de Luhn).")
        try:
            mes = int(self.mes)
            ano = int(self.ano)
        except (TypeError, ValueError) as exc:
            raise ValueError("Validade do cartão inválida.") from exc
        validar_validade(mes, ano)
        if not re.fullmatch(r"\d{3,4}", str(self.cvv)):
            raise ValueError("CVV deve ter 3 ou 4 dígitos.")
        if len(self.portador_nome.strip().split()) < 2:
            raise ValueError("Informe nome e sobrenome do portador.")
        if len(self.portador_nome.strip()) > 30:
            raise ValueError("O nome do portador deve ter no máximo 30 caracteres.")
        if not validar_cpf(self.portador_cpf):
            raise ValueError("CPF do portador inválido.")


def _validar_referencia(referencia: str) -> str:
    referencia = referencia.strip()
    if not referencia:
        raise ValueError("Informe uma referência para o pedido.")
    if len(referencia) > 50:
        raise ValueError("A referência deve ter no máximo 50 caracteres.")
    return referencia


def _cliente_payload(cliente: Cliente) -> dict[str, Any]:
    return {
        "name": cliente.nome.strip(),
        "email": cliente.email.strip(),
        "tax_id": somente_digitos(cliente.cpf),
        "phones": [
            {
                "country": "55",
                "area": somente_digitos(cliente.ddd),
                "number": somente_digitos(cliente.telefone),
                "type": cliente.tipo_telefone,
            }
        ],
    }


def _item_payload(item: Item, referencia: str) -> dict[str, Any]:
    return {
        "reference_id": f"{referencia}-ITEM",
        "name": item.nome.strip(),
        "quantity": item.quantidade,
        "unit_amount": item.valor_centavos,
    }


def _expiracao_padrao() -> str:
    """QR Code válido por 24 horas, em UTC (formato ISO 8601)."""
    return (datetime.now(timezone.utc) + timedelta(hours=24)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def montar_pedido_pix(
    *,
    cliente: Cliente,
    item: Item,
    referencia: str,
    expiracao: str | None = None,
) -> dict[str, Any]:
    """Monta um pedido com cobrança PIX no formato atual da Orders API.

    O formato antigo usava o array de topo `qr_codes`. O formato atual
    cria a cobrança dentro de `charges` com `payment_method.type = PIX`.
    """
    referencia = _validar_referencia(referencia)
    total = item.valor_centavos * item.quantidade

    return {
        "reference_id": referencia,
        "customer": _cliente_payload(cliente),
        "items": [_item_payload(item, referencia)],
        "charges": [
            {
                "reference_id": f"{referencia}-PIX",
                "description": item.nome.strip()[:100],
                "amount": {"value": total, "currency": "BRL"},
                "payment_method": {
                    "type": "PIX",
                    "pix": {"expiration_date": expiracao or _expiracao_padrao()},
                },
            }
        ],
    }


def montar_pedido_credito(
    *,
    cliente: Cliente,
    item: Item,
    referencia: str,
    cartao: Cartao,
    parcelas: int = 1,
    soft_descriptor: str,
) -> dict[str, Any]:
    """Monta um pedido com cobrança de cartão de crédito.

    `soft_descriptor` é o nome que o portador vê na fatura do cartão. É
    exigido pelo PagBank em cobranças de crédito e fica dentro de
    `payment_method`, junto de `type`/`installments`/`capture`.
    """
    referencia = _validar_referencia(referencia)
    fatura = normalizar_soft_descriptor(soft_descriptor)

    if not 1 <= parcelas <= 12:
        raise ValueError("Parcelas devem estar entre 1 e 12.")

    total = item.valor_centavos * item.quantidade

    return {
        "reference_id": referencia,
        "customer": _cliente_payload(cliente),
        "items": [_item_payload(item, referencia)],
        "charges": [
            {
                "reference_id": f"{referencia}-CREDITO",
                "description": item.nome.strip()[:100],
                "amount": {"value": total, "currency": "BRL"},
                "payment_method": {
                    "type": "CREDIT_CARD",
                    "installments": parcelas,
                    "capture": True,
                    "soft_descriptor": fatura,
                    "card": {
                        "number": somente_digitos(cartao.numero),
                        "exp_month": int(cartao.mes),
                        "exp_year": int(cartao.ano)
                        if int(cartao.ano) >= 100
                        else 2000 + int(cartao.ano),
                        "security_code": str(cartao.cvv),
                        "holder": {
                            "name": cartao.portador_nome.strip(),
                            "tax_id": somente_digitos(cartao.portador_cpf),
                        },
                    },
                },
            }
        ],
    }


def pedido_para_exibicao(pedido: dict[str, Any]) -> dict[str, Any]:
    """Cópia segura para imprimir em dry-run/log, com dados mascarados."""
    copia = copy.deepcopy(pedido)

    cliente = copia.get("customer")
    if isinstance(cliente, dict) and cliente.get("tax_id"):
        cliente["tax_id"] = mascarar_cpf(cliente["tax_id"])

    for charge in copia.get("charges", []):
        card = charge.get("payment_method", {}).get("card")
        if not isinstance(card, dict):
            continue

        card["number"] = mascarar_numero_cartao(card.get("number", ""))
        card["security_code"] = "***"

        holder = card.get("holder")
        if isinstance(holder, dict) and holder.get("tax_id"):
            holder["tax_id"] = mascarar_cpf(holder["tax_id"])

    return copia
