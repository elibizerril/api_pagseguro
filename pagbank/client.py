"""Cliente HTTP da Orders API do PagBank.

Responsabilidade única: falar HTTP. Ele não decide o que é um PIX, não
monta payload e não imprime resultado. Essa separação permite trocar o
transporte ou testar com uma sessão falsa.
"""

from __future__ import annotations

from typing import Any

import requests

from .errors import ConfigError, PagBankError

SANDBOX_BASE_URL = "https://sandbox.api.pagseguro.com"
PRODUCAO_BASE_URL = "https://api.pagseguro.com"


class PagBankClient:
    """Cliente mínimo para criar e consultar pedidos."""

    def __init__(
        self,
        token: str,
        *,
        sandbox: bool = True,
        timeout: int = 30,
        session: requests.Session | None = None,
    ) -> None:
        token = (token or "").strip()
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
        if not token:
            raise ConfigError(
                "Token ausente. Preencha PAGBANK_TOKEN no arquivo .env."
            )

        self.token = token
        self.sandbox = sandbox
        self.base_url = SANDBOX_BASE_URL if sandbox else PRODUCAO_BASE_URL
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def criar_pedido(self, pedido: dict[str, Any]) -> dict[str, Any]:
        """POST /orders — cria o pedido e a cobrança."""
        return self._requisitar("POST", "/orders", json=pedido)

    def consultar_pedido(self, order_id: str) -> dict[str, Any]:
        """GET /orders/{id} — consulta o estado atual do pedido."""
        order_id = (order_id or "").strip()
        if not order_id:
            raise ValueError("Informe o ID do pedido (ORDE_...).")
        return self._requisitar("GET", f"/orders/{order_id}")

    def _requisitar(
        self,
        metodo: str,
        caminho: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{caminho}"

        try:
            resposta = self.session.request(
                metodo,
                url,
                timeout=self.timeout,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise PagBankError(
                "Não foi possível falar com o PagBank. "
                "Verifique sua conexão e tente novamente.",
                detalhes=str(exc),
            ) from exc

        if resposta.status_code >= 400:
            corpo = _corpo_da_resposta(resposta)
            raise PagBankError(
                "PagBank recusou a requisição "
                f"(HTTP {resposta.status_code}): {_mensagens_de_erro(corpo)}",
                status_code=resposta.status_code,
                detalhes=corpo,
            )

        try:
            corpo = resposta.json()
        except ValueError as exc:
            raise PagBankError(
                "O PagBank respondeu com sucesso, mas o corpo não era JSON.",
                status_code=resposta.status_code,
                detalhes=(resposta.text or "")[:1000],
            ) from exc

        if not isinstance(corpo, dict):
            raise PagBankError(
                "O PagBank respondeu em um formato inesperado.",
                status_code=resposta.status_code,
                detalhes=corpo,
            )

        return corpo

    def fechar(self) -> None:
        self.session.close()

    def __repr__(self) -> str:
        # Nunca inclua o token no repr.
        return f"PagBankClient(base_url={self.base_url!r}, sandbox={self.sandbox})"


def _corpo_da_resposta(resposta: requests.Response) -> Any:
    try:
        return resposta.json()
    except ValueError:
        return (resposta.text or "").strip()[:1000]


def _mensagens_de_erro(corpo: Any) -> str:
    if isinstance(corpo, dict):
        erros = corpo.get("error_messages") or corpo.get("errors")
        if isinstance(erros, list):
            mensagens = []
            for erro in erros:
                if isinstance(erro, dict):
                    mensagens.append(
                        str(
                            erro.get("description")
                            or erro.get("message")
                            or erro
                        )
                    )
                else:
                    mensagens.append(str(erro))
            if mensagens:
                return " | ".join(mensagens)

        for chave in ("message", "error", "description"):
            if corpo.get(chave):
                return str(corpo[chave])

    if isinstance(corpo, str) and corpo.strip():
        return corpo.strip()[:500]

    return "sem detalhes"
