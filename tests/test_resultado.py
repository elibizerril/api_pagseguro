"""Testes de impressão do resultado de crédito.

Os payloads aqui são **sintéticos**: só os campos que a impressão realmente lê.
Nenhum dado de resposta real (CPF, portador, autorização) é versionado — o que
importa testar é o comportamento do código: mostrar o que a API respondeu e não
o que nós enviamos.
"""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

from main import _imprimir_resultado_credito
from pagbank.payloads import Item


def resposta_credito() -> dict:
    """Resposta mínima no formato observado do `GET /orders` (sem dados reais)."""
    return {
        "id": "ORDE_EXEMPLO-0000-0000-0000-000000000000",
        "charges": [
            {
                "status": "PAID",
                "amount": {"value": 4990, "currency": "BRL"},
                "payment_response": {
                    "code": "20000",
                    "message": "SUCESSO",
                    "raw_data": {"authorization_code": "000000"},
                },
                "payment_method": {
                    "type": "CREDIT_CARD",
                    "installments": 2,
                    "capture": True,
                    "card": {
                        "brand": "visa",
                        "last_digits": "2097",
                    },
                    "soft_descriptor": "CursodeAPIs",
                },
            }
        ],
    }


class ImpressaoCreditoTests(unittest.TestCase):
    def _imprimir(self, resposta: dict) -> str:
        saida = io.StringIO()
        with redirect_stdout(saida):
            _imprimir_resultado_credito(
                resposta, Item(nome="Curso de APIs", valor_centavos=4990)
            )
        return saida.getvalue()

    def test_mostra_dados_da_resposta(self) -> None:
        texto = self._imprimir(resposta_credito())

        self.assertIn("ORDE_EXEMPLO", texto)
        self.assertIn("PAID (pago)", texto)
        self.assertIn("SUCESSO", texto)
        self.assertIn("20000", texto)
        self.assertIn("Autorização: 000000", texto)
        self.assertIn("**** **** **** 2097", texto)  # last_digits
        self.assertIn("Parcelas: 2x", texto)
        self.assertIn("R$ 49,90", texto)

    def test_fatura_vem_da_api_sem_espacos(self) -> None:
        texto = self._imprimir(resposta_credito())

        self.assertIn("Na fatura do portador: CursodeAPIs", texto)

    def test_sem_parcelas_na_resposta_nao_inventa_valor(self) -> None:
        resposta = resposta_credito()
        del resposta["charges"][0]["payment_method"]["installments"]

        texto = self._imprimir(resposta)

        self.assertIn("não informado pela API", texto)
        self.assertNotIn("Parcelas: 1x", texto)

    def test_resposta_sem_cartao_nao_quebra(self) -> None:
        resposta = resposta_credito()
        del resposta["charges"][0]["payment_method"]["card"]

        texto = self._imprimir(resposta)

        self.assertIn("Cartão: ****", texto)

    def test_valor_vem_da_resposta_quando_presente(self) -> None:
        resposta = resposta_credito()
        resposta["charges"][0]["amount"]["value"] = 12345

        texto = self._imprimir(resposta)

        self.assertIn("R$ 123,45", texto)


if __name__ == "__main__":
    unittest.main()
