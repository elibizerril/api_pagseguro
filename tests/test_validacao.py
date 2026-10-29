"""Testes das validações puras (sem rede)."""

from __future__ import annotations

import unittest
from datetime import date

from pagbank.validacao import (
    formatar_brl,
    mascarar_cpf,
    mascarar_numero_cartao,
    normalizar_soft_descriptor,
    validar_cpf,
    validar_luhn,
    validar_validade,
    valor_em_centavos,
)


class ValorEmCentavosTests(unittest.TestCase):
    def test_aceita_ponto_decimal(self) -> None:
        self.assertEqual(valor_em_centavos("49.90"), 4990)

    def test_aceita_virgula_decimal(self) -> None:
        self.assertEqual(valor_em_centavos("49,90"), 4990)

    def test_aceita_moeda_e_milhar_brasileiro(self) -> None:
        self.assertEqual(valor_em_centavos("R$ 1.234,56"), 123456)

    def test_aceita_milhar_americano(self) -> None:
        self.assertEqual(valor_em_centavos("1,234.56"), 123456)

    def test_aceita_inteiro(self) -> None:
        self.assertEqual(valor_em_centavos(100), 100)

    def test_rejeita_vazio(self) -> None:
        with self.assertRaises(ValueError):
            valor_em_centavos("")

    def test_rejeita_texto(self) -> None:
        with self.assertRaises(ValueError):
            valor_em_centavos("abc")

    def test_rejeita_zero_ou_negativo(self) -> None:
        with self.assertRaises(ValueError):
            valor_em_centavos("0")
        with self.assertRaises(ValueError):
            valor_em_centavos("-1.00")

    def test_rejeita_mais_de_duas_casas(self) -> None:
        with self.assertRaises(ValueError):
            valor_em_centavos("1.999")


class CpfTests(unittest.TestCase):
    def test_cpf_valido(self) -> None:
        self.assertTrue(validar_cpf("123.456.789-09"))

    def test_cpf_com_todos_digitos_iguais_e_invalido(self) -> None:
        self.assertFalse(validar_cpf("111.111.111-11"))

    def test_cpf_com_digito_errado_e_invalido(self) -> None:
        self.assertFalse(validar_cpf("123.456.789-00"))

    def test_cpf_curto_e_invalido(self) -> None:
        self.assertFalse(validar_cpf("123"))


class CartaoTests(unittest.TestCase):
    def test_luhn_aceita_cartao_de_teste(self) -> None:
        self.assertTrue(validar_luhn("4539 6206 5992 2097"))

    def test_luhn_rejeita_digito_alterado(self) -> None:
        self.assertFalse(validar_luhn("4539620659922098"))

    def test_luhn_rejeita_numero_curto(self) -> None:
        self.assertFalse(validar_luhn("1234"))

    def test_validade_futura_e_aceita(self) -> None:
        validar_validade(12, 2026, hoje=date(2026, 10, 28))

    def test_validade_vencida_e_rejeitada(self) -> None:
        with self.assertRaises(ValueError):
            validar_validade(9, 2026, hoje=date(2026, 10, 28))

    def test_mes_invalido_e_rejeitado(self) -> None:
        with self.assertRaises(ValueError):
            validar_validade(13, 2026, hoje=date(2026, 10, 28))


class SoftDescriptorTests(unittest.TestCase):
    def test_remove_espacos_como_a_api(self) -> None:
        # Observado no sandbox: enviado "Curso de APIs", gravado "CursodeAPIs".
        self.assertEqual(normalizar_soft_descriptor("Curso de APIs"), "CursodeAPIs")

    def test_remove_acentos_e_caracteres_especiais(self) -> None:
        self.assertEqual(normalizar_soft_descriptor("Ação & Cia!"), "AcaoCia")

    def test_limita_a_22_caracteres(self) -> None:
        self.assertEqual(len(normalizar_soft_descriptor("X" * 40)), 22)

    def test_texto_sem_letras_ou_numeros_e_rejeitado(self) -> None:
        with self.assertRaises(ValueError):
            normalizar_soft_descriptor("!!!")


class MascarasTests(unittest.TestCase):
    def test_mascara_cpf(self) -> None:
        self.assertEqual(mascarar_cpf("12345678909"), "***.***.***-09")

    def test_mascara_cartao(self) -> None:
        self.assertEqual(
            mascarar_numero_cartao("4539620659922097"),
            "**** **** **** 2097",
        )

    def test_formata_brl(self) -> None:
        self.assertEqual(formatar_brl(4990), "R$ 49,90")
        self.assertEqual(formatar_brl(123456), "R$ 1.234,56")


if __name__ == "__main__":
    unittest.main()
