# Pagamentos PagBank / PagSeguro — sandbox

Script didático para criar pagamentos via **Orders API** do PagBank (o PagSeguro
passou a usar a marca PagBank) no ambiente de **sandbox**.

> **Status desta etapa:** PIX + cartão de crédito.
> **Débito ainda não:** `DEBIT_CARD` exige autenticação 3DS obrigatória, que
> envolve sessão + SDK no navegador. Isso será uma etapa própria.

---

## O que já funciona

- `POST /orders` para **PIX** no formato atual (`charges[].payment_method.type = PIX`)
- `POST /orders` para **cartão de crédito** (`CREDIT_CARD`)
- consulta de pedido por ID (`GET /orders/{id}`)
- `--dry-run` para montar e conferir o JSON **sem token e sem rede**
- validação local de CPF, cartão (Luhn), validade, CVV e valor em centavos
- mascaramento de CPF, cartão e CVV na saída do dry-run
- erros HTTP e de rede com mensagem e detalhes da resposta
- testes offline com `unittest` (sem internet)

---

## Estrutura

```text
API/
├── main.py                 # CLI: pix, credito, consultar
├── pagbank/
│   ├── client.py           # HTTP + autenticação + erros
│   ├── payloads.py         # DTOs de entrada + montagem do JSON
│   ├── validacao.py        # CPF, Luhn, valor, máscaras
│   └── errors.py           # PagBankError, ConfigError
├── tests/
├── .env.example
└── requirements.txt
```

Separação importante:

```text
CLI
 ↓ coleta e valida
Cliente / Item / Cartao
 ↓ monta
payload JSON (contrato PagBank)
 ↓ envia
PagBankClient
 ↓
Orders API
```

O CLI não monta JSON solto. Assim o contrato pode ser testado sem rede.

---

## Configuração

### 1. Instalar dependências

No PowerShell, sem depender de ativação de venv:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2. Criar o `.env`

```powershell
Copy-Item .env.example .env
notepad .env
```

Preencha:

```env
PAGBANK_TOKEN=seu_token_de_sandbox
PAGBANK_SANDBOX=true
PAGBANK_TIMEOUT=30
```

O token de sandbox é obtido no painel de desenvolvedor do PagBank:

- https://developer.pagbank.com.br/

> Nunca coloque o token no código, no Git ou em print de tela.
> O `.env` já está no `.gitignore`.

---

## Uso

### PIX — dry-run (não precisa de token)

```powershell
.\.venv\Scripts\python.exe main.py pix `
  --valor 49.90 `
  --descricao "Curso de APIs" `
  --nome "João da Silva" `
  --email "joao@example.com" `
  --cpf 12345678909 `
  --dry-run
```

O `--dry-run` imprime o payload com CPF mascarado e **não chama a API**.

### PIX — sandbox real

> ⚠️ **Estado conhecido em 28/10/2026:** nesta conta sandbox o PIX responde
> `400 / 40010 / PIX_KEY_NOT_FOUND` mesmo com chave **aleatória ativa**
> cadastrada há mais de 1h. O payload está conforme a documentação e o crédito
> com o mesmo token é aprovado (`PAID`). O bloqueio é de **configuração de
> conta**, não de código. Ver `MENTORIA_STATE.md` para as hipóteses em aberto.

Remova `--dry-run`:

```powershell
.\.venv\Scripts\python.exe main.py pix `
  --valor 49.90 `
  --descricao "Curso de APIs" `
  --nome "João da Silva" `
  --email "joao@example.com" `
  --cpf 12345678909
```

A resposta traz `id` (ORDE_...), status `WAITING` e o QR Code em
`charges[0].qr_code.text`. O link PNG fica em um link com `rel = QRCODE.PNG`.

### Crédito — dry-run

Use um cartão de teste do sandbox:

```powershell
.\.venv\Scripts\python.exe main.py credito `
  --valor 49.90 `
  --descricao "Curso de APIs" `
  --nome "João da Silva" `
  --email "joao@example.com" `
  --cpf 12345678909 `
  --cartao 4539620659922097 `
  --validade 12/2026 `
  --cvv 123 `
  --portador "João da Silva" `
  --cpf-portador 12345678909 `
  --parcelas 1 `
  --dry-run
```

### Crédito — sandbox real

Remova `--dry-run`. O resultado mostra o status da cobrança:

- `PAID` / `AUTHORIZED`: aprovado no sandbox;
- `DECLINED`: recusado (use outro cartão de teste);
- `IN_ANALYSIS`: em análise.

**O campo `soft_descriptor` é obrigatório no crédito.** É o nome que aparece na
fatura do portador (1-22 caracteres, sem acentos/caracteres especiais). Sem ele
a API responde `40002 must not be empty` em `charges[0].seller.soft_descriptor`.
No payload ele vai em `charges[0].payment_method.soft_descriptor`.

⚠️ **A API remove os espaços.** Observado no sandbox: enviamos `Curso de APIs` e
o `GET /orders` mostrou `CursodeAPIs`. O CLI normaliza igual (remove espaço,
acento e símbolo) para o dry-run mostrar a fatura real, e não uma versão mais
bonita da verdade.

Por padrão o CLI deriva da `--descricao`; para escolher, use:

```powershell
--soft-descriptor "CURSO DE APIS"
```

A partir da resposta, o resumo mostra também `Autorização` (o
`authorization_code` do emissor), útil para conciliar com o extrato. Todos os
campos impressos vêm da **resposta** da API, não dos argumentos enviados — se a
API não devolver um campo, o terminal diz "não informado pela API" em vez de
repetir o que pedimos.

### Consultar um pedido

```powershell
.\.venv\Scripts\python.exe main.py consultar --pedido ORDE_...
```

Use `--json` em qualquer comando real para ver a resposta bruta da API.

---

## Cartões de teste (sandbox)

Dados da documentação do PagBank. Números fictícios: **nunca use em produção**.

| Bandeira | Número | CVV | Validade | Resultado esperado |
|---|---|---|---|---|
| Visa | `4539620659922097` | `123` | `12/2026` | aprovado |
| Visa | `4929291898380766` | `123` | `12/2026` | recusado |
| Mastercard | `5240082975622454` | `123` | `12/2026` | aprovado |
| Mastercard | `5530062640663264` | `123` | `12/2026` | recusado |
| Amex | `345817690311361` | `1234` | `12/2026` | aprovado |
| Elo | `4514161122113757` | `123` | `12/2026` | aprovado |
| Hiper | `6062828598919021` | `123` | `12/2026` | aprovado |

Se a data estiver vencida, consulte a tabela atual:
https://developer.pagbank.com.br/docs/cartoes-de-teste

---

## Status e erros

Status de cobrança que o script traduz:

| Status | Significado |
|---|---|
| `WAITING` | aguardando pagamento (PIX, por exemplo) |
| `PAID` | pago/capturado |
| `AUTHORIZED` | pré-autorizado (crédito com `capture: false`) |
| `IN_ANALYSIS` | em análise de risco |
| `DECLINED` | recusado pelo PagBank ou emissor |
| `CANCELED` | cancelado |

Erros comuns:

- **401/403**: token inválido ou ausente.
- **400**: payload inválido (CPF, e-mail, valor, cartão).
- **5xx**: problema no PagBank; tentar novamente depois.
- **Erro de rede**: sem conexão/DNS/timeout; não é “lista vazia”, é falha.

O cliente nunca transforma erro em sucesso vazio.

### Dicas automáticas

Saídas de erro conhecidas trazem uma linha `[DICA]` depois dos detalhes, com a
próxima ação concreta. O erro cru continua sendo impresso — a dica complementa,
não substitui.

| Código real | Dica |
|---|---|
| `40010` `PIX_KEY_NOT_FOUND` | chave PIX ativa e propagada na conta dona do token |
| `40002` + `soft_descriptor` | informar `--soft-descriptor` |
| `UNAUTHORIZED` (401) | conferir `PAGBANK_TOKEN` e o ambiente (sandbox x produção) |
| `NOT_FOUND` (404) | ID de pedido inexistente naquele ambiente |

Só códigos observados de verdade entram nessa lista. Erro desconhecido não ganha
dica inventada — ver `pagbank/diagnostico.py`.

---

## Segurança

- Token somente no `.env` / servidor.
- Dados de cartão nunca são impressos: o dry-run mascara número e CVV.
- O CLI usa `getpass` para o CVV quando ele não é passado por argumento.
- Evite passar cartão/CVV por argumento em produção: argumentos podem ficar no
  histórico do shell. Nesta demo de sandbox, é aceitável para facilitar o teste.
- Este script não é PCI-compliant e não deve ir para produção sem homologação.

---

## Testes

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Os testes não fazem rede. Eles cobrem:

- conversão de valor para centavos;
- CPF, Luhn e validade;
- montagem do payload PIX e crédito;
- máscaras de dados sensíveis;
- cliente HTTP com sessão falsa (sucesso, erro 400, rede, JSON inválido).

---

## Por que débito ficou para depois?

A documentação do PagBank é explícita:

> Toda cobrança com cartão de débito **deve** ser autenticada pelo protocolo 3DS.

Um `POST /orders` com `DEBIT_CARD` sem `authentication_method` não é uma
integração válida. O fluxo real precisa de:

1. uma sessão 3DS;
2. o SDK do PagBank no navegador para autenticar o portador;
3. envio do `authentication_method` (`id` do 3DS ou dados como `cavv`, `eci`,
   `xid`, `version`) na criação do pedido.

Isso não cabe em um CLI puro. A próxima etapa seria uma pequena página web
local (backend + frontend) com wireframe próprio, ou o checkout hospedado do
PagBank (que também depende de liberação do débito na conta).

Decisão registrada: **não simular aprovação de débito**. Simulação aqui seria
didaticamente enganosa.

---

## Observação sobre o exemplo antigo

`python_apis/06_pagseguro.py` usa o formato antigo de PIX com `qr_codes` no
topo do payload. A Orders API atual cria a cobrança em `charges` com
`payment_method.type = PIX`; a resposta traz `charges[0].qr_code`. Este projeto
segue o formato atual.

---

## Próximos passos possíveis

1. Rodar PIX e crédito no sandbox com o token real e registrar as respostas.
2. Adicionar `--salvar-resposta` para guardar o JSON de cada transação.
3. Implementar consulta de status com polling para PIX.
4. Planejar a fase de débito com 3DS (wireframe + decisão de arquitetura).
5. Escrever testes de integração opcionais, marcados para rodar só com token.
