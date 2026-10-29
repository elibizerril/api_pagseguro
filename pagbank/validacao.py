"""Validações puras usadas antes de montar o payload.

Nenhuma função aqui faz rede. Isso permite testar as regras rapidamente
e evita enviar ao PagBank dados obviamente inválidos.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation

MAX_SOFT_DESCRIPTOR = 22


def somente_digitos(valor: str) -> str:
    """Remove tudo que não for dígito."""
    return re.sub(r"\D", "", valor or "")


def valor_em_centavos(valor: str | int | Decimal) -> int:
    """Converte "49,90", "49.90" ou 4990 para centavos.

    Usar Decimal (e não float) evita erros de arredondamento como
    0.1 + 0.2. Valores monetários não devem passar por float.
    """
    if isinstance(valor, int):
        centavos = valor
    else:
        texto = str(valor).strip().replace("R$", "").replace(" ", "")

        if not texto:
            raise ValueError("Informe um valor.")

        # Aceita "1.234,56" (padrão brasileiro) e "1,234.56" (padrão americano).
        if "," in texto and "." in texto:
            if texto.rfind(",") > texto.rfind("."):
                texto = texto.replace(".", "").replace(",", ".")
            else:
                texto = texto.replace(",", "")
        elif "," in texto:
            texto = texto.replace(",", ".")

        try:
            decimal = Decimal(texto)
        except InvalidOperation as exc:
            raise ValueError(f"Valor inválido: {valor!r}") from exc

        if not decimal.is_finite():
            raise ValueError(f"Valor inválido: {valor!r}")

        if decimal.as_tuple().exponent < -2:
            raise ValueError("Use no máximo 2 casas decimais.")

        centavos = int(decimal * 100)

    if centavos <= 0:
        raise ValueError("O valor deve ser maior que zero.")

    return centavos


def validar_cpf(cpf: str) -> bool:
    """Valida os dois dígitos verificadores do CPF."""
    numeros = somente_digitos(cpf)

    if len(numeros) != 11 or len(set(numeros)) == 1:
        return False

    for tamanho in (9, 10):
        soma = sum(
            int(numeros[i]) * (tamanho + 1 - i)
            for i in range(tamanho)
        )
        digito = (soma * 10) % 11
        if digito == 10:
            digito = 0
        if digito != int(numeros[tamanho]):
            return False

    return True


def validar_luhn(numero: str) -> bool:
    """Valida o dígito verificador de cartões (algoritmo de Luhn)."""
    digitos = somente_digitos(numero)

    if not 13 <= len(digitos) <= 19:
        return False

    soma = 0
    dobrar = False

    for caractere in reversed(digitos):
        digito = int(caractere)
        if dobrar:
            digito *= 2
            if digito > 9:
                digito -= 9
        soma += digito
        dobrar = not dobrar

    return soma % 10 == 0


def validar_validade(mes: int, ano: int, hoje: date | None = None) -> None:
    """Garante mês válido e cartão não vencido."""
    if not 1 <= mes <= 12:
        raise ValueError("Mês de validade inválido.")

    if ano < 100:
        ano += 2000

    referencia = hoje or date.today()

    if (ano, mes) < (referencia.year, referencia.month):
        raise ValueError("O cartão está vencido.")


def mascarar_cpf(cpf: str) -> str:
    """Mostra apenas os dois últimos dígitos do CPF."""
    numeros = somente_digitos(cpf)
    if len(numeros) != 11:
        return "***.***.***-**"
    return f"***.***.***-{numeros[-2:]}"


def mascarar_numero_cartao(numero: str) -> str:
    """Mostra apenas os quatro últimos dígitos do cartão."""
    digitos = somente_digitos(numero)
    if len(digitos) < 4:
        return "****"
    return f"**** **** **** {digitos[-4:]}"


def formatar_brl(centavos: int) -> str:
    """Formata centavos como moeda brasileira, sem depender de locale."""
    reais, resto = divmod(centavos, 100)
    return f"R$ {reais:,}".replace(",", ".") + f",{resto:02d}"


def normalizar_soft_descriptor(texto: str) -> str:
    """Prepara o nome que aparece na fatura do portador.

    Regra observada no sandbox (GET /orders, 28/10/2026): a API **remove os
    espaços**, além de acentos e caracteres especiais. Enviamos "Curso de APIs"
    e ela guardou "CursodeAPIs". Normalizamos igual aqui para que o dry-run
    mostre a fatura real, e não uma versão mais bonita da verdade.
    """
    sem_acento = unicodedata.normalize("NFKD", texto or "")
    sem_acento = "".join(
        caractere
        for caractere in sem_acento
        if not unicodedata.combining(caractere)
    )

    limpo = re.sub(r"[^A-Za-z0-9]+", "", sem_acento)

    if not limpo:
        raise ValueError(
            "Soft descriptor inválido: use letras e números (máx. 22 caracteres)."
        )

    return limpo[:MAX_SOFT_DESCRIPTOR]
