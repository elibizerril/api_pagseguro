"""Testes do CLI em modo dry-run (sem rede e sem token)."""

from __future__ import annotations

import io
import json
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from main import _extrair_qr_code, _imprimir_resultado_pix, main
from pagbank.payloads import Item

FIXTURES = Path(__file__).parent / "fixtures"

CLIENTE_ARGS = [
    "--nome",
    "João da Silva",
    "--email",
    "joao@example.com",
    "--cpf",
    "12345678909",
]


class CliDryRunTests(unittest.TestCase):
    def test_pix_dry_run_nao_exige_token(self) -> None:
        saida = io.StringIO()

        with redirect_stdout(saida):
            codigo = main(
                [
                    "pix",
                    "--valor",
                    "49.90",
                    "--descricao",
                    "Curso de APIs",
                    *CLIENTE_ARGS,
                    "--dry-run",
                ]
            )

        self.assertEqual(codigo, 0)
        texto = saida.getvalue()
        self.assertIn("[DRY-RUN]", texto)
        self.assertIn('"type": "PIX"', texto)
        self.assertIn('"value": 4990', texto)
        self.assertIn("***.***.***-09", texto)

    def test_credito_dry_run_mascara_cartao_e_cvv(self) -> None:
        saida = io.StringIO()

        with redirect_stdout(saida):
            codigo = main(
                [
                    "credito",
                    "--valor",
                    "49.90",
                    "--descricao",
                    "Curso de APIs",
                    *CLIENTE_ARGS,
                    "--cartao",
                    "4539620659922097",
                    "--validade",
                    "12/2026",
                    "--cvv",
                    "123",
                    "--portador",
                    "João da Silva",
                    "--cpf-portador",
                    "12345678909",
                    "--dry-run",
                ]
            )

        self.assertEqual(codigo, 0)
        texto = saida.getvalue()
        self.assertIn('"type": "CREDIT_CARD"', texto)
        self.assertIn('"soft_descriptor": "CursodeAPIs"', texto)
        self.assertIn("**** **** **** 2097", texto)
        self.assertNotIn("4539620659922097", texto)
        self.assertIn('"security_code": "***"', texto)

    def test_sem_token_mostra_erro_de_configuracao(self) -> None:
        saida_erro = io.StringIO()

        with patch.dict(os.environ, {"PAGBANK_TOKEN": ""}, clear=False):
            with redirect_stderr(saida_erro):
                codigo = main(
                    [
                        "pix",
                        "--valor",
                        "49.90",
                        *CLIENTE_ARGS,
                    ]
                )

        self.assertEqual(codigo, 1)
        self.assertIn("Token ausente", saida_erro.getvalue())

    def test_valor_invalido_mostra_erro(self) -> None:
        saida_erro = io.StringIO()

        with redirect_stderr(saida_erro):
            codigo = main(
                [
                    "pix",
                    "--valor",
                    "abc",
                    *CLIENTE_ARGS,
                    "--dry-run",
                ]
            )

        self.assertEqual(codigo, 1)
        self.assertIn("Valor inválido", saida_erro.getvalue())


class RespostaPixTests(unittest.TestCase):
    """Usa a resposta de exemplo da documentação oficial do PagBank.

    Atenção: é um **fixture de documentação**, não evidência de API real. Serve
    para provar que o nosso código sabe ler o formato `charges[].qr_code` +
    `links[rel=QRCODE.PNG]`, não que o PIX funciona na conta.
    """

    def _resposta_waiting(self) -> dict:
        caminho = FIXTURES / "pix_waiting.json"
        return json.loads(caminho.read_text(encoding="utf-8"))

    def test_extrai_texto_e_link_do_formato_atual(self) -> None:
        texto, link = _extrair_qr_code(self._resposta_waiting())

        self.assertTrue(texto.startswith("000201"))
        self.assertEqual(
            link,
            "https://sandbox.api.pagseguro.com/qrcode/"
            "QRCO_0F63EB5F-61B8-4466-A4C9-7F824193C234/png",
        )

    def test_imprime_copia_e_cola_e_status(self) -> None:
        saida = io.StringIO()

        with redirect_stdout(saida):
            _imprimir_resultado_pix(
                self._resposta_waiting(),
                Item(nome="Curso de APIs", valor_centavos=4990),
            )

        texto = saida.getvalue()
        self.assertIn("ORDE_3D560F48-E086-4F3C-A5A1-B7AB7BEACC2C", texto)
        self.assertIn("WAITING", texto)
        self.assertIn("000201", texto)
        self.assertIn("/png", texto)
        self.assertIn("aguardando pagamento", texto)

    def test_formato_antigo_qr_codes_continua_legivel(self) -> None:
        resposta = {
            "id": "ORDE_ANTIGO",
            "qr_codes": [
                {
                    "text": "000201formato-antigo",
                    "links": [
                        {
                            "rel": "QRCODE.PNG",
                            "href": "https://exemplo/qr.png",
                        }
                    ],
                }
            ],
        }

        texto, link = _extrair_qr_code(resposta)

        self.assertEqual(texto, "000201formato-antigo")
        self.assertEqual(link, "https://exemplo/qr.png")

    def test_resposta_sem_qr_code_nao_quebra(self) -> None:
        texto, link = _extrair_qr_code({"id": "ORDE_X", "charges": [{"status": "DECLINED"}]})

        self.assertIsNone(texto)
        self.assertIsNone(link)


if __name__ == "__main__":
    unittest.main()
