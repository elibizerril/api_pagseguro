"""Testes da montagem dos payloads (sem rede)."""

from __future__ import annotations

import unittest

from pagbank import (
    Cartao,
    Cliente,
    Item,
    montar_pedido_credito,
    montar_pedido_pix,
    pedido_para_exibicao,
)


def cliente_teste() -> Cliente:
    return Cliente(
        nome="João da Silva",
        email="joao@example.com",
        cpf="12345678909",
        ddd="11",
        telefone="999999999",
    )


def item_teste(quantidade: int = 1) -> Item:
    return Item(
        nome="Curso de APIs",
        valor_centavos=4990,
        quantidade=quantidade,
    )


def cartao_teste() -> Cartao:
    return Cartao(
        numero="4539620659922097",
        mes=12,
        ano=2030,
        cvv="123",
        portador_nome="João da Silva",
        portador_cpf="12345678909",
    )


class PedidoPixTests(unittest.TestCase):
    def test_monta_contrato_atual_com_charges(self) -> None:
        pedido = montar_pedido_pix(
            cliente=cliente_teste(),
            item=item_teste(),
            referencia="PED-TESTE",
        )

        self.assertEqual(pedido["reference_id"], "PED-TESTE")
        self.assertEqual(pedido["customer"]["tax_id"], "12345678909")
        self.assertEqual(pedido["items"][0]["unit_amount"], 4990)
        self.assertEqual(pedido["charges"][0]["amount"]["value"], 4990)
        self.assertEqual(
            pedido["charges"][0]["payment_method"]["type"],
            "PIX",
        )
        self.assertIn(
            "expiration_date",
            pedido["charges"][0]["payment_method"]["pix"],
        )

    def test_total_considera_quantidade(self) -> None:
        pedido = montar_pedido_pix(
            cliente=cliente_teste(),
            item=item_teste(quantidade=2),
            referencia="PED-TESTE",
        )
        self.assertEqual(pedido["charges"][0]["amount"]["value"], 9980)

    def test_referencia_longa_e_rejeitada(self) -> None:
        with self.assertRaises(ValueError):
            montar_pedido_pix(
                cliente=cliente_teste(),
                item=item_teste(),
                referencia="X" * 51,
            )


class PedidoCreditoTests(unittest.TestCase):
    def test_monta_contrato_de_credito(self) -> None:
        pedido = montar_pedido_credito(
            cliente=cliente_teste(),
            item=item_teste(),
            referencia="PED-TESTE",
            cartao=cartao_teste(),
            soft_descriptor="Curso de APIs",
            parcelas=2,
        )

        charge = pedido["charges"][0]
        metodo = charge["payment_method"]

        self.assertEqual(metodo["type"], "CREDIT_CARD")
        self.assertEqual(metodo["installments"], 2)
        self.assertTrue(metodo["capture"])
        self.assertEqual(metodo["soft_descriptor"], "CursodeAPIs")
        self.assertEqual(metodo["card"]["number"], "4539620659922097")
        self.assertEqual(metodo["card"]["exp_month"], 12)
        self.assertEqual(metodo["card"]["exp_year"], 2030)
        self.assertEqual(metodo["card"]["holder"]["tax_id"], "12345678909")

    def test_parcelas_invalidas_sao_rejeitadas(self) -> None:
        with self.assertRaises(ValueError):
            montar_pedido_credito(
                cliente=cliente_teste(),
                item=item_teste(),
                referencia="PED-TESTE",
                cartao=cartao_teste(),
                soft_descriptor="Curso de APIs",
                parcelas=13,
            )

    def test_exibicao_mascara_dados_sensiveis(self) -> None:
        pedido = montar_pedido_credito(
            cliente=cliente_teste(),
            item=item_teste(),
            referencia="PED-TESTE",
            cartao=cartao_teste(),
            soft_descriptor="Curso de APIs",
        )
        exibicao = pedido_para_exibicao(pedido)
        card = exibicao["charges"][0]["payment_method"]["card"]

        self.assertEqual(exibicao["customer"]["tax_id"], "***.***.***-09")
        self.assertEqual(card["number"], "**** **** **** 2097")
        self.assertEqual(card["security_code"], "***")
        self.assertEqual(card["holder"]["tax_id"], "***.***.***-09")

        # A cópia não pode alterar o payload original.
        self.assertEqual(
            pedido["charges"][0]["payment_method"]["card"]["number"],
            "4539620659922097",
        )


class ValidacaoDeEntradaTests(unittest.TestCase):
    def test_item_abaixo_do_minimo_e_rejeitado(self) -> None:
        with self.assertRaises(ValueError):
            Item(nome="X", valor_centavos=99)

    def test_cliente_com_cpf_invalido_e_rejeitado(self) -> None:
        with self.assertRaises(ValueError):
            Cliente(nome="João da Silva", email="joao@example.com", cpf="123")

    def test_cartao_com_luhn_invalido_e_rejeitado(self) -> None:
        with self.assertRaises(ValueError):
            Cartao(
                numero="4539620659922098",
                mes=12,
                ano=2030,
                cvv="123",
                portador_nome="João da Silva",
                portador_cpf="12345678909",
            )


if __name__ == "__main__":
    unittest.main()
