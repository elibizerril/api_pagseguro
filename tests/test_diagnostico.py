"""Testes das dicas de diagnóstico, usando os erros reais do sandbox.

Os três primeiros payloads abaixo são cópias literais das respostas que o
PagBank devolveu em 28/10/2026 para esta conta.
"""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr

from main import _imprimir_erro
from pagbank import PagBankError
from pagbank.diagnostico import dica_para

PIX_KEY_NOT_FOUND = {
    "error_messages": [
        {
            "code": "40010",
            "error": "PIX_KEY_NOT_FOUND",
            "description": "Pix key was not found for pix payment method",
            "parameter_name": "charges[0].payment_method.type",
        }
    ]
}

SOFT_DESCRIPTOR_VAZIO = {
    "error_messages": [
        {
            "code": "40002",
            "description": "must not be empty",
            "parameter_name": "charges[0].seller.soft_descriptor",
        }
    ]
}

NAO_AUTORIZADO = {
    "error_messages": [
        {
            "code": "UNAUTHORIZED",
            "description": "Invalid credential. Review AUTHORIZATION header",
        }
    ]
}

PEDIDO_INEXISTENTE = {
    "error_messages": [{"code": "NOT_FOUND", "description": "Not Found"}]
}


class DicaTests(unittest.TestCase):
    def test_pix_sem_chave(self) -> None:
        self.assertIn("chave PIX", dica_para(PIX_KEY_NOT_FOUND))

    def test_40002_so_vira_dica_se_for_soft_descriptor(self) -> None:
        self.assertIn("soft_descriptor", dica_para(SOFT_DESCRIPTOR_VAZIO))
        outro = {
            "error_messages": [
                {"code": "40002", "parameter_name": "customer.name"}
            ]
        }
        self.assertIsNone(dica_para(outro))

    def test_token_invalido(self) -> None:
        self.assertIn("PAGBANK_TOKEN", dica_para(NAO_AUTORIZADO))

    def test_pedido_inexistente(self) -> None:
        self.assertIn("ORDE_", dica_para(PEDIDO_INEXISTENTE))

    def test_corpo_desconhecido_nao_inventa_dica(self) -> None:
        self.assertIsNone(dica_para({"error_messages": [{"code": "99999"}]}))
        self.assertIsNone(dica_para("texto puro"))
        self.assertIsNone(dica_para(None))


class DicaNoCliTests(unittest.TestCase):
    def test_erro_real_impresso_mostra_detalhes_e_dica(self) -> None:
        erro = PagBankError(
            "PagBank recusou a requisição (HTTP 400): "
            "Pix key was not found for pix payment method",
            status_code=400,
            detalhes=PIX_KEY_NOT_FOUND,
        )
        saida_erro = io.StringIO()

        with redirect_stderr(saida_erro):
            _imprimir_erro(erro)

        texto = saida_erro.getvalue()
        self.assertIn("HTTP 400", texto)
        self.assertIn("PIX_KEY_NOT_FOUND", texto)
        self.assertIn("[DICA]", texto)
        self.assertIn("Minhas chaves", texto)

    def test_erro_de_validacao_local_nao_mostra_dica(self) -> None:
        saida_erro = io.StringIO()

        with redirect_stderr(saida_erro):
            _imprimir_erro(ValueError("Valor inválido"))

        texto = saida_erro.getvalue()
        self.assertIn("[ERRO] Valor inválido", texto)
        self.assertNotIn("[DICA]", texto)


if __name__ == "__main__":
    unittest.main()
