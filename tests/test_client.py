"""Testes do cliente HTTP usando uma sessão falsa (sem internet)."""

from __future__ import annotations

import unittest
from typing import Any

import requests

from pagbank import ConfigError, PagBankClient, PagBankError


class RespostaFalsa:
    def __init__(
        self,
        status_code: int,
        payload: Any = None,
        texto: str = "",
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = texto

    def json(self) -> Any:
        if self._payload is None:
            raise ValueError("resposta sem JSON")
        return self._payload


class SessaoFalsa:
    def __init__(
        self,
        resposta: RespostaFalsa | None = None,
        excecao: Exception | None = None,
    ) -> None:
        self.headers: dict[str, str] = {}
        self.resposta = resposta
        self.excecao = excecao
        self.chamadas: list[tuple[str, str, dict[str, Any]]] = []
        self.fechada = False

    def request(self, metodo: str, url: str, **kwargs: Any) -> RespostaFalsa:
        self.chamadas.append((metodo, url, kwargs))
        if self.excecao:
            raise self.excecao
        assert self.resposta is not None
        return self.resposta

    def close(self) -> None:
        self.fechada = True


class PagBankClientTests(unittest.TestCase):
    def test_token_ausente_gera_config_error(self) -> None:
        with self.assertRaises(ConfigError):
            PagBankClient("")

    def test_envia_bearer_e_url_de_sandbox(self) -> None:
        sessao = SessaoFalsa(RespostaFalsa(201, {"id": "ORDE_1"}))
        client = PagBankClient("TOKEN_123", session=sessao)

        resposta = client.criar_pedido({"reference_id": "teste"})

        self.assertEqual(resposta, {"id": "ORDE_1"})
        self.assertEqual(sessao.headers["Authorization"], "Bearer TOKEN_123")
        metodo, url, kwargs = sessao.chamadas[0]
        self.assertEqual(metodo, "POST")
        self.assertEqual(url, "https://sandbox.api.pagseguro.com/orders")
        self.assertEqual(kwargs["json"], {"reference_id": "teste"})

    def test_remove_prefixo_bearer_duplicado(self) -> None:
        sessao = SessaoFalsa(RespostaFalsa(201, {"id": "ORDE_1"}))
        PagBankClient("Bearer TOKEN_123", session=sessao)
        self.assertEqual(sessao.headers["Authorization"], "Bearer TOKEN_123")

    def test_usa_url_de_producao_quando_sandbox_false(self) -> None:
        sessao = SessaoFalsa(RespostaFalsa(201, {"id": "ORDE_1"}))
        client = PagBankClient("TOKEN", sandbox=False, session=sessao)

        client.criar_pedido({})

        self.assertEqual(
            sessao.chamadas[0][1],
            "https://api.pagseguro.com/orders",
        )

    def test_erro_http_inclui_status_e_mensagens(self) -> None:
        sessao = SessaoFalsa(
            RespostaFalsa(
                400,
                {
                    "error_messages": [
                        {"description": "CPF inválido"},
                        {"description": "E-mail inválido"},
                    ]
                },
            )
        )
        client = PagBankClient("TOKEN", session=sessao)

        with self.assertRaises(PagBankError) as contexto:
            client.criar_pedido({})

        erro = contexto.exception
        self.assertEqual(erro.status_code, 400)
        self.assertIn("CPF inválido", str(erro))
        self.assertIn("E-mail inválido", str(erro))

    def test_erro_404_real_do_sandbox(self) -> None:
        """Contrato observado em 28/10/2026 ao consultar um ORDE inexistente."""
        sessao = SessaoFalsa(
            RespostaFalsa(
                404,
                {"error_messages": [{"code": "NOT_FOUND", "description": "Not Found"}]},
            )
        )
        client = PagBankClient("TOKEN", session=sessao)

        with self.assertRaises(PagBankError) as contexto:
            client.consultar_pedido("ORDE_00000000-0000-0000-0000-000000000000")

        erro = contexto.exception
        self.assertEqual(erro.status_code, 404)
        self.assertIn("HTTP 404", str(erro))
        self.assertIn("Not Found", str(erro))

    def test_erro_401_real_do_sandbox(self) -> None:
        """Contrato observado em 28/10/2026 com token inválido."""
        sessao = SessaoFalsa(
            RespostaFalsa(
                401,
                {
                    "error_messages": [
                        {
                            "code": "UNAUTHORIZED",
                            "description": (
                                "Invalid credential. Review AUTHORIZATION header"
                            ),
                        }
                    ]
                },
            )
        )
        client = PagBankClient("TOKEN", session=sessao)

        with self.assertRaises(PagBankError) as contexto:
            client.consultar_pedido("ORDE_FA74B938-D26F-46AF-9957-288C6249184F")

        erro = contexto.exception
        self.assertEqual(erro.status_code, 401)
        self.assertIn("Invalid credential", str(erro))

    def test_erro_sem_description_nao_quebra(self) -> None:
        """Respostas de erro nem sempre têm os mesmos campos."""
        sessao = SessaoFalsa(
            RespostaFalsa(422, {"error_messages": [{"code": "ALGO"}]})
        )
        client = PagBankClient("TOKEN", session=sessao)

        with self.assertRaises(PagBankError) as contexto:
            client.criar_pedido({})

        self.assertIn("ALGO", str(contexto.exception))

    def test_erro_de_rede_vira_pagbank_error(self) -> None:
        sessao = SessaoFalsa(excecao=requests.ConnectionError("sem rede"))
        client = PagBankClient("TOKEN", session=sessao)

        with self.assertRaises(PagBankError) as contexto:
            client.criar_pedido({})

        self.assertIn("Não foi possível falar com o PagBank", str(contexto.exception))

    def test_sucesso_sem_json_vira_pagbank_error(self) -> None:
        sessao = SessaoFalsa(RespostaFalsa(201, None, texto="<html>"))
        client = PagBankClient("TOKEN", session=sessao)

        with self.assertRaises(PagBankError):
            client.criar_pedido({})

    def test_consulta_pedido_monta_url(self) -> None:
        sessao = SessaoFalsa(RespostaFalsa(200, {"id": "ORDE_1"}))
        client = PagBankClient("TOKEN", session=sessao)

        client.consultar_pedido("ORDE_1")

        metodo, url, _ = sessao.chamadas[0]
        self.assertEqual(metodo, "GET")
        self.assertEqual(
            url,
            "https://sandbox.api.pagseguro.com/orders/ORDE_1",
        )

    def test_fechar_delega_para_sessao(self) -> None:
        sessao = SessaoFalsa()
        client = PagBankClient("TOKEN", session=sessao)
        client.fechar()
        self.assertTrue(sessao.fechada)

    def test_repr_nao_expoe_token(self) -> None:
        sessao = SessaoFalsa()
        client = PagBankClient("TOKEN_SECRETO", session=sessao)
        self.assertNotIn("TOKEN_SECRETO", repr(client))


if __name__ == "__main__":
    unittest.main()
