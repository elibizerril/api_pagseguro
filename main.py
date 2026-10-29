"""CLI didática de pagamentos PIX e cartão de crédito (PagBank sandbox).

Exemplos:

    python main.py pix --valor 49.90 --descricao "Curso" \
        --nome "Joao da Silva" --email "joao@example.com" --cpf 12345678909 \
        --dry-run

    python main.py credito --valor 49.90 --descricao "Curso" \
        --nome "Joao da Silva" --email "joao@example.com" --cpf 12345678909 \
        --cartao 4539620659922097 --validade 12/2026 --cvv 123 \
        --portador "Joao da Silva" --cpf-portador 12345678909 \
        --dry-run
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import secrets
import sys
from datetime import datetime
from typing import Any, Sequence

from dotenv import load_dotenv

from pagbank import (
    Cartao,
    Cliente,
    ConfigError,
    Item,
    PagBankClient,
    PagBankError,
    montar_pedido_credito,
    montar_pedido_pix,
    pedido_para_exibicao,
)
from pagbank.diagnostico import dica_para
from pagbank.validacao import (
    formatar_brl,
    normalizar_soft_descriptor,
    valor_em_centavos,
)

STATUS_LEGIVEL = {
    "PAID": "pago",
    "AUTHORIZED": "pré-autorizado",
    "IN_ANALYSIS": "em análise",
    "DECLINED": "recusado",
    "CANCELED": "cancelado",
    "WAITING": "aguardando pagamento",
}


def criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Pagamentos PIX e crédito no sandbox do PagBank/PagSeguro."
    )

    comum = argparse.ArgumentParser(add_help=False)
    comum.add_argument("--valor", required=True, help="Valor do pedido, ex.: 49.90")
    comum.add_argument("--descricao", default="Pedido de teste")
    comum.add_argument("--quantidade", type=int, default=1)
    comum.add_argument("--nome", required=True, help="Nome completo do cliente")
    comum.add_argument("--email", required=True)
    comum.add_argument("--cpf", required=True, help="CPF do cliente (somente números)")
    comum.add_argument("--ddd", default="11")
    comum.add_argument("--telefone", default="999999999")
    comum.add_argument("--referencia", help="ID próprio do pedido (opcional)")
    comum.add_argument(
        "--dry-run",
        action="store_true",
        help="Monta e imprime o payload sem chamar a API",
    )
    comum.add_argument(
        "--json",
        action="store_true",
        dest="saida_json",
        help="Imprime a resposta bruta da API em JSON",
    )

    subcomandos = parser.add_subparsers(dest="comando", required=True)

    subcomandos.add_parser(
        "pix",
        parents=[comum],
        help="Cria um pedido com cobrança PIX",
    )

    credito = subcomandos.add_parser(
        "credito",
        parents=[comum],
        help="Cria um pedido com cobrança de cartão de crédito",
    )
    credito.add_argument("--cartao", help="Número do cartão (somente sandbox)")
    credito.add_argument("--validade", help="Validade no formato MM/AAAA")
    credito.add_argument("--cvv", help="Código de segurança")
    credito.add_argument("--portador", help="Nome do portador (padrão: nome do cliente)")
    credito.add_argument(
        "--cpf-portador",
        dest="cpf_portador",
        help="CPF do portador (padrão: CPF do cliente)",
    )
    credito.add_argument("--parcelas", type=int, default=1)
    credito.add_argument(
        "--soft-descriptor",
        dest="soft_descriptor",
        help=(
            "Nome exibido na fatura do portador (1-22 caracteres). "
            "Obrigatório na API; aqui o padrão é derivado da descrição."
        ),
    )

    consulta = subcomandos.add_parser(
        "consultar",
        help="Consulta o estado de um pedido pelo ID",
    )
    consulta.add_argument("--pedido", required=True, help="ID retornado pela API (ORDE_...)")
    consulta.add_argument(
        "--json",
        action="store_true",
        dest="saida_json",
        help="Imprime a resposta bruta da API em JSON",
    )

    return parser


def _montar_cliente(args: argparse.Namespace) -> Cliente:
    return Cliente(
        nome=args.nome,
        email=args.email,
        cpf=args.cpf,
        ddd=args.ddd,
        telefone=args.telefone,
    )


def _montar_item(args: argparse.Namespace) -> Item:
    return Item(
        nome=args.descricao,
        valor_centavos=valor_em_centavos(args.valor),
        quantidade=args.quantidade,
    )


def _gerar_referencia(prefixo: str) -> str:
    agora = datetime.now().strftime("%Y%m%d%H%M%S")
    aleatorio = secrets.token_hex(2).upper()
    return f"PED-{prefixo}-{agora}-{aleatorio}"


def _referencia(args: argparse.Namespace, prefixo: str) -> str:
    return args.referencia or _gerar_referencia(prefixo)


def _parse_validade(texto: str) -> tuple[int, int]:
    partes = re.split(r"[/\-\s]+", texto.strip())
    if len(partes) != 2 or not all(parte.isdigit() for parte in partes):
        raise ValueError("Validade inválida. Use o formato MM/AAAA.")
    mes, ano = int(partes[0]), int(partes[1])
    if ano < 100:
        ano += 2000
    return mes, ano


def _coletar_cartao(args: argparse.Namespace, cliente: Cliente) -> Cartao:
    numero = (args.cartao or input("Número do cartão (sandbox): ")).strip()
    validade = (args.validade or input("Validade (MM/AAAA): ")).strip()
    cvv = (args.cvv or getpass.getpass("CVV (não será exibido): ")).strip()

    mes, ano = _parse_validade(validade)

    return Cartao(
        numero=numero,
        mes=mes,
        ano=ano,
        cvv=cvv,
        portador_nome=(args.portador or cliente.nome).strip(),
        portador_cpf=(args.cpf_portador or cliente.cpf).strip(),
    )


def _carregar_configuracao() -> tuple[str, bool, int]:
    token = os.getenv("PAGBANK_TOKEN", "")
    if not token:
        raise ConfigError(
            "Token ausente. Copie .env.example para .env e preencha "
            "PAGBANK_TOKEN com o token do sandbox."
        )

    sandbox = os.getenv("PAGBANK_SANDBOX", "true").strip().lower() != "false"

    try:
        timeout = int(os.getenv("PAGBANK_TIMEOUT", "30"))
    except ValueError as exc:
        raise ConfigError("PAGBANK_TIMEOUT deve ser um número inteiro.") from exc

    if not sandbox:
        print(
            "[ATENÇÃO] PAGBANK_SANDBOX=false: usando o ambiente de PRODUÇÃO.",
            file=sys.stderr,
        )
        print(
            "[ATENÇÃO] Esta demo não foi homologada para produção.",
            file=sys.stderr,
        )

    return token, sandbox, timeout


def _imprimir_dry_run(pedido: dict[str, Any]) -> None:
    print("\n[DRY-RUN] Nenhuma requisição foi enviada.")
    print("Payload que seria enviado (dados sensíveis mascarados):\n")
    print(json.dumps(pedido_para_exibicao(pedido), ensure_ascii=False, indent=2))


def _extrair_qr_code(resposta: dict[str, Any]) -> tuple[str | None, str | None]:
    """Aceita o formato atual (charges[].qr_code) e o antigo (qr_codes[])."""
    cargas = resposta.get("charges") or []
    if cargas:
        carga = cargas[0]
        qr = carga.get("qr_code") or {}
        texto = qr.get("text")
        link = _link_qr(carga)
        if texto or link:
            return texto, link

    qr_codes = resposta.get("qr_codes") or []
    if qr_codes:
        qr = qr_codes[0]
        return qr.get("text"), _link_qr(qr)

    return None, None


def _link_qr(origem: dict[str, Any]) -> str | None:
    for link in origem.get("links") or []:
        if link.get("rel") == "QRCODE.PNG":
            return link.get("href")
    return None


def _imprimir_resultado_pix(resposta: dict[str, Any], item: Item) -> None:
    order_id = resposta.get("id", "(sem id)")
    cargas = resposta.get("charges") or []
    status = cargas[0].get("status") if cargas else resposta.get("status")
    texto, link = _extrair_qr_code(resposta)

    print("\n✅ Pedido PIX criado")
    print(f"Order ID: {order_id}")
    print(f"Status: {status or 'desconhecido'}")
    print(f"Valor: {formatar_brl(item.valor_centavos * item.quantidade)}")

    if texto:
        print("\nPIX copia e cola:")
        print(texto)
    else:
        print("\n[AVISO] A resposta não trouxe o texto copia e cola.")

    if link:
        print(f"\nQR Code (PNG): {link}")

    if status == "WAITING":
        print("\nO QR Code está aguardando pagamento.")


def _imprimir_resultado_credito(resposta: dict[str, Any], item: Item) -> None:
    """Imprime o que o **servidor** respondeu, não o que nós enviamos.

    Antes esta função usava `args.parcelas` e o `soft_descriptor` de entrada —
    ou seja, repetia o nosso próprio pedido. Se a API ignorasse um campo, o
    terminal continuaria "confirmando". Agora a fonte é a resposta: o que não
    vier dela aparece como não informado.
    """
    order_id = resposta.get("id", "(sem id)")
    cargas = resposta.get("charges") or []
    carga = cargas[0] if cargas else {}
    status = carga.get("status", "desconhecido")

    payment_response = carga.get("payment_response") or {}
    mensagem = payment_response.get("message", "-")
    codigo = payment_response.get("code")
    autorizacao = (payment_response.get("raw_data") or {}).get("authorization_code")

    metodo = carga.get("payment_method") or {}
    dados_cartao = metodo.get("card") or {}
    final = dados_cartao.get("last_digits")
    parcelas = metodo.get("installments")
    fatura = metodo.get("soft_descriptor")
    valor = (carga.get("amount") or {}).get("value")
    if valor is None:
        valor = item.valor_centavos * item.quantidade

    print("\n💳 Pedido de crédito criado")
    print(f"Order ID: {order_id}")
    print(f"Status da cobrança: {status} ({STATUS_LEGIVEL.get(status, 'desconhecido')})")
    print(f"Mensagem do emissor: {mensagem}" + (f" (código {codigo})" if codigo else ""))
    if autorizacao:
        print(f"Autorização: {autorizacao}")
    print(f"Cartão: **** **** **** {final}" if final else "Cartão: ****")
    print(f"Parcelas: {parcelas}x" if parcelas else "Parcelas: (não informado pela API)")
    print(f"Valor total: {formatar_brl(valor)}")
    if fatura:
        print(f"Na fatura do portador: {fatura}")

    if status == "DECLINED":
        print("\n[ATENÇÃO] O pagamento NÃO foi aprovado.")
        print("Use um cartão de teste de aprovação ou verifique os dados enviados.")
    elif status == "IN_ANALYSIS":
        print("\nO PagBank está analisando o risco da transação.")
    elif status in {"PAID", "AUTHORIZED"}:
        print("\nPagamento aprovado pelo ambiente de teste.")


def _executar_pix(args: argparse.Namespace) -> int:
    cliente = _montar_cliente(args)
    item = _montar_item(args)
    pedido = montar_pedido_pix(
        cliente=cliente,
        item=item,
        referencia=_referencia(args, "PIX"),
    )

    if args.dry_run:
        _imprimir_dry_run(pedido)
        return 0

    token, sandbox, timeout = _carregar_configuracao()
    client = PagBankClient(token, sandbox=sandbox, timeout=timeout)

    try:
        resposta = client.criar_pedido(pedido)
    finally:
        client.fechar()

    if args.saida_json:
        print(json.dumps(resposta, ensure_ascii=False, indent=2))
    else:
        _imprimir_resultado_pix(resposta, item)

    return 0


def _executar_credito(args: argparse.Namespace) -> int:
    cliente = _montar_cliente(args)
    item = _montar_item(args)
    cartao = _coletar_cartao(args, cliente)

    # O PagBank exige soft_descriptor no crédito. Se o aluno não informar,
    # derivamos da descrição do pedido — e o dry-run mostra o resultado.
    fatura = normalizar_soft_descriptor(args.soft_descriptor or args.descricao)

    pedido = montar_pedido_credito(
        cliente=cliente,
        item=item,
        referencia=_referencia(args, "CREDITO"),
        cartao=cartao,
        parcelas=args.parcelas,
        soft_descriptor=fatura,
    )

    if args.dry_run:
        _imprimir_dry_run(pedido)
        return 0

    token, sandbox, timeout = _carregar_configuracao()
    client = PagBankClient(token, sandbox=sandbox, timeout=timeout)

    try:
        resposta = client.criar_pedido(pedido)
    finally:
        client.fechar()

    if args.saida_json:
        print(json.dumps(resposta, ensure_ascii=False, indent=2))
    else:
        _imprimir_resultado_credito(resposta, item)

    return 0


def _executar_consulta(args: argparse.Namespace) -> int:
    token, sandbox, timeout = _carregar_configuracao()
    client = PagBankClient(token, sandbox=sandbox, timeout=timeout)

    try:
        resposta = client.consultar_pedido(args.pedido)
    finally:
        client.fechar()

    if args.saida_json:
        print(json.dumps(resposta, ensure_ascii=False, indent=2))
        return 0

    cargas = resposta.get("charges") or []
    carga = cargas[0] if cargas else {}
    status = carga.get("status", resposta.get("status", "desconhecido"))

    print("\n🔎 Pedido consultado")
    print(f"Order ID: {resposta.get('id', args.pedido)}")
    print(f"Status: {status} ({STATUS_LEGIVEL.get(status, 'desconhecido')})")

    if status == "WAITING":
        print("\nO pagamento ainda não foi confirmado.")
    elif status == "PAID":
        print("\nPagamento confirmado.")
    elif status == "DECLINED":
        print("\nO pagamento foi recusado.")

    return 0


def _configurar_saida_utf8() -> None:
    """Evita acentos quebrados no console do Windows."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8")
            except (AttributeError, ValueError):
                pass


def _imprimir_erro(exc: Exception) -> None:
    """Imprime o erro cru e, quando conhecido, uma dica de próxima ação."""
    print(f"\n[ERRO] {exc}", file=sys.stderr)

    if not (isinstance(exc, PagBankError) and exc.detalhes):
        return

    print("\nDetalhes da resposta:", file=sys.stderr)
    if isinstance(exc.detalhes, (dict, list)):
        print(
            json.dumps(exc.detalhes, ensure_ascii=False, indent=2),
            file=sys.stderr,
        )
    else:
        print(str(exc.detalhes)[:1000], file=sys.stderr)

    dica = dica_para(exc.detalhes)
    if dica:
        print(f"\n[DICA] {dica}", file=sys.stderr)


def main(argv: Sequence[str] | None = None) -> int:
    _configurar_saida_utf8()
    load_dotenv()
    parser = criar_parser()
    args = parser.parse_args(argv)

    try:
        if args.comando == "pix":
            return _executar_pix(args)
        if args.comando == "credito":
            return _executar_credito(args)
        return _executar_consulta(args)
    except (PagBankError, ValueError) as exc:
        _imprimir_erro(exc)
        return 1
    except KeyboardInterrupt:
        print("\nCancelado pelo usuário.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
