# 🧾 MENTORIA_STATE — Pagamentos PagBank/PagSeguro (sandbox)

> Estado local deste subprojeto. O `MENTORIA_STATE.md` da raiz continua sendo
> o da Pokédex; não misturar as decisões.

## Projeto

- Nome: Pagamentos PagBank/PagSeguro — sandbox
- Pasta: `E:\Projeto\API` (movido de `workspace\API` em 28/10/2026)
- Fonte: Orders API do PagBank (PagSeguro)
- Base sandbox: `https://sandbox.api.pagseguro.com`
- Fase atual: 1 — PIX + cartão de crédito implementados; falta validação real
  com token de sandbox
- Nível do aluno: A (começando), conforme estado da Pokédex

## Decisões

- Escopo fase 1: **A** — PIX + crédito agora; débito em fase própria.
- Linguagem: Python 3.13 + `requests` + `python-dotenv` + stdlib.
- Arquitetura: CLI → DTOs validados → payload builders → `PagBankClient`.
- PIX no formato atual: `charges[].payment_method.type = PIX` (não o antigo
  `qr_codes` de topo).
- Crédito: `charges[].payment_method.type = CREDIT_CARD`, `capture: true`.
- Débito: **não implementado e não simulado**; exige 3DS obrigatório.
- Dry-run sem token: sim, com dados sensíveis mascarados.
- Testes: `unittest`, sem rede, com sessão HTTP falsa.
- Token: somente via `.env` (`PAGBANK_TOKEN`), nunca em argumento/print.
- Caminho de trabalho: `E:\Projeto\API` a partir de 28/10/2026.

## Já aprendido

- Diferença entre PagSeguro (marca antiga) e PagBank (API atual).
- Orders API: JSON, `Authorization: Bearer`, `POST /orders`.
- Valor monetário em centavos; uso de `Decimal` para evitar float.
- DTO de entrada ≠ payload da API ≠ resposta da API.
- PIX atual: cobrança em `charges`, QR em `charges[0].qr_code`.
- Crédito: `charges` com cartão, parcelas e captura.
- Débito: 3DS obrigatório; não é um simples POST.
- Erros: 4xx/5xx/rede não devem virar sucesso vazio.
- Segurança: mascarar CPF/cartão/CVV; token fora do código.

## Evidências

- `python -m unittest discover -s tests -v` → **45 testes verdes**
  (executado no caminho antigo, `workspace\API`).
- Dry-run PIX: payload com `charges[0].payment_method.type = PIX`, valor 4990,
  CPF mascarado.
- Dry-run crédito: `CREDIT_CARD`, cartão `**** **** **** 2097`, CVV `***`.
- Primeira requisição **real** ao sandbox executada (PIX, token configurado).
  Resposta: `HTTP 400`, `code 40010`, `error PIX_KEY_NOT_FOUND`,
  `parameter_name: charges[0].payment_method.type`.
- Diagnóstico: o payload PIX está correto; a **conta sandbox do PagBank não tem
  chave PIX de endereçamento ativa**. A doc oficial exige "pelo menos uma chave
  PIX de endereçamento ativa associada" antes de integrar PIX, e a chave é
  escolhida pela conta (não vai no payload).
- Nossa apresentação de erro real funcionou: mostrou status HTTP, code, error,
  description e parameter_name.
- Segunda resposta real, crédito: `HTTP 400`, `code 40002`, `must not be empty`,
  `parameter_name: charges[0].seller.soft_descriptor`.
- Diagnóstico: o crédito exige `soft_descriptor` (nome na fatura do portador).
  Pela documentação (OpenAPI de `POST /orders` e Objeto Order), o campo fica em
  `charges[0].payment_method.soft_descriptor` (1-22 caracteres, sem acentos ou
  caracteres especiais) — e **não** em um objeto `seller`, que não existe na doc
  atual. O `parameter_name` aponta o caminho interno da validação.
- Correção aplicada: `normalizar_soft_descriptor()` em `validacao.py`,
  `soft_descriptor` obrigatório em `montar_pedido_credito()`, flag
  `--soft-descriptor` no CLI (padrão: derivado de `--descricao`).
- **Crédito aprovado no sandbox** após a correção:
  `ORDE_FA74B938-D26F-46AF-9957-288C6249184F`, `status PAID`,
  `payment_response.message = SUCESSO`, cartão `**** **** **** 2097`,
  fatura `Curso de APIs`. Confirma que `payment_method.soft_descriptor` é o
  caminho correto (o `seller` do erro era só o caminho interno da validação).
- **Crédito recusado** com o cartão de teste `4929291898380766`:
  `ORDE_A696E660-31E5-4980-AD80-33633AE16F8B`, `status DECLINED`,
  `message = NAO AUTORIZADO PELO EMISSOR DO CARTAO`. Prova que o script lê o
  status real e não assume sucesso.
- **Consulta por ID** (`GET /orders/{id}`) funcionando contra o sandbox:
  `ORDE_FA74B938-...` retornou `PAID`.
- **Tratamento de erro validado de ponta a ponta no sandbox** (28/10/2026):
  - `consultar` com ID inexistente → `HTTP 404`, `code NOT_FOUND`,
    `description "Not Found"` (sem `parameter_name`);
  - `consultar` com `PAGBANK_TOKEN` inválido no ambiente → `HTTP 401`,
    `code UNAUTHORIZED`, `description "Invalid credential. Review
    AUTHORIZATION header"`, **mesmo com um pedido que existe**.
  - Ordem de validação observada: **autenticação antes de existência**
    (token inválido + pedido existente = 401, não 404).
- Confirmado na prática que `load_dotenv()` **não** sobrescreve variável já
  definida no ambiente do shell — útil para testes negativos e um risco
  silencioso se sobrar token antigo exportado.
- Esses dois contratos reais viraram testes offline em `tests/test_client.py`
  (404, 401 e erro sem `description`), para não regredir.
- **Fase 1 — crédito: concluída** (aprovado, recusado e consulta validados).
- Cópia para `E:\Projeto\API` feita arquivo por arquivo (sem `__pycache__`).
- Dry-run PIX executado **no caminho novo** (`E:\Projeto\API`): payload completo
  impresso, `charges[0].amount.value = 4990` igual a `items[0].unit_amount`,
  `expiration_date` 24h à frente, CPF mascarado. Isso prova que a cadeia de
  imports (`main` → `pagbank`) sobreviveu à cópia.
- **Suíte completa rodada no caminho novo** (`E:\Projeto\API`): **68 testes, OK**
  (28/10/2026), incluindo os contratos reais de 404/401, a leitura de resposta
  PIX, as dicas de erro e a impressão a partir da resposta real de crédito.
- **Crédito parcelado validado com evidência de servidor** (28/10/2026):
  `ORDE_42C90F19-DCEC-47DE-8C67-42AAA7A7B586` (`GET /orders --json`):
  `status PAID`, `installments: 2`, `card.brand: "visa"`,
  `last_digits: "2097"`, `amount.summary.total = paid = 4990`,
  `payment_response.code 20000`, `authorization_code 145803`,
  `soft_descriptor: "CursodeAPIs"`. Prova que o servidor honrou o parcelamento.
- **Descoberta: a API remove os espaços do `soft_descriptor`.** Enviamos
  `Curso de APIs`, o servidor gravou `CursodeAPIs`. Antes o dry-run e o resumo
  mostravam `Curso de APIs` — nós exibíamos o que pedimos, não o que aconteceu.
  Corrigido nos dois pontos (normalizer + impressão).
- **Impressão agora vem da resposta, não dos argumentos**: parcelas, cartão,
  fatura, valor e autorização são lidos do JSON do servidor. Campo ausente vira
  "não informado pela API" em vez de eco do input.
- `tests/test_resultado.py` cobre esse comportamento com payload **sintético**
  (só os campos que a impressão lê). A fixture com a resposta real de crédito
  foi versionada por engano e **removida** do repositório e do histórico: dados
  de portador e `authorization_code` não pertencem a repo público.
- **Dicas de erro no CLI** (`pagbank/diagnostico.py`): `40010`, `40002` +
  `soft_descriptor`, `UNAUTHORIZED` e `NOT_FOUND` imprimem `[DICA]` com a
  próxima ação. Erro desconhecido **não** ganha dica inventada.
- Estado da chave PIX informado pelo aluno: **aleatória**, **ativa**,
  cadastrada **10 min** antes da última tentativa. Aleatória+ativa é o cenário
  ideal; 10 min ainda está dentro da janela de propagação, então a próxima ação
  é esperar e repetir **uma** vez — sem loop automático, porque cada `POST
  /orders` bem-sucedido cria um pedido novo.
- **Fixture PIX** criado em `tests/fixtures/pix_waiting.json` a partir do
  exemplo **da documentação oficial** (`WAITING`, `charges[0].qr_code.text`,
  `links[rel=QRCODE.PNG]`). Ele prova que o código **lê** o formato atual —
  **não** é evidência de PIX real. Rotulado assim no teste e no estado.
- Origem do token confirmada pelo aluno: **Portal do Desenvolvedor
  (portaldev)**. A chave PIX foi cadastrada, segundo ele, **na mesma conta**.
  Logo, a hipótese de "conta errada" cai; restam três suspeitos para o `40010`:
  1. chave ainda não propagada para a API (~15-60 min);
  2. chave **não ativa** (tipo CPF/e-mail/telefone depende de validação);
  3. limitação do ambiente sandbox para chaves PIX dessa conta.
- **PIX: propagação descartada por evidência.** Chave aleatória + ativa + >1h e
  erro **idêntico** em tentativas espaçadas → `40010` não é tempo. A chave
  aleatória é o tipo que não depende de validação do Banco Central, então a
  janela de sincronização também não explica.
- Hipóteses restantes, em ordem:
  1. **conta diferente**: a chave está numa conta e o token em outra. O aluno
     afirma que é a mesma, mas isso é crença, não artefato — falta comparar
     **CPF/CNPJ e número de conta** no app x portaldev;
  2. **a Orders API consulta um registro de chaves que o app não escreve**
     (limitação do sandbox). Não existe endpoint de listar/gerenciar chaves na
     Orders API — `llms.txt` confirmado — então a API só sabe dizer
     "achou"/"não achou";
  3. **recebimento PIX não habilitado** no seller do token (sem conta de
     recebimento).
- Catálogo oficial confirma: `40010 pix_key_not_found` = "A chave Pix não foi
  encontrada, impossibilitando a geração do QR Code"
  (`reference/codigos-de-erro-order`).
- ⚠️ **Correção de uma afirmação anterior minha**: o catálogo de erros lista
  `40005 idempotency_key_in_use`, então a Orders API **suporta** chave de
  idempotência — o header não está no OpenAPI, mas o erro existe. O teste
  barato (mesma chave duas vezes) fica como pendência.
- Hipótese nova e mais forte que "sincronização": **a chave foi cadastrada em
  outra conta, não na conta dona do token.** A doc separa as origens:
  - token de **sandbox** → Portal do Desenvolvedor (`portaldev.pagbank.com.br`,
    aba **Tokens**);
  - token de **produção** → app/painel PagBank (`Vendas > Integrações >
    Gerar Token`).
  São dois logins/contas distintos. A chave PIX precisa estar na **mesma conta
  que emitiu o token** (o `seller` da requisição), e ela não vai no payload.
- Consequência: se a chave foi criada no app PagBank pessoal e o token veio do
  portaldev, o `40010` é permanente — não é atraso de sincronização.

## Pendências

- Rodar os testes e o dry-run no caminho novo para provar que a cópia está íntegra
  ~~Concluído: 56 testes OK, dry-runs executados.~~
- ~~Cadastrar uma chave PIX aleatória na conta sandbox (PIX > Minhas Chaves) e
  repetir o pedido PIX~~ → chave cadastrada, `40010` persiste. Falta confirmar
  **em qual conta** ela foi cadastrada.
- Confirmar a origem do token (portaldev vs app PagBank) e cadastrar a chave na
  **mesma** conta; se a conta sandbox não tiver área PIX, decidir fallback
  honesto (stub local com resposta gravada, rotulado como fixture) ou suporte
  PagBank.
- ~~Validar um erro 400/401 real~~ → 400 validado (PIX_KEY_NOT_FOUND).
- Rodar crédito real com cartão de teste aprovado e recusado.
  ~~Concluído: `PAID` e `DECLINED` validados.~~
- ~~Registrar as respostas reais (status, order ID, mensagens)~~ → registradas.
- ~~Validar um erro 400/401 real para conferir a apresentação~~ → 400
  (`PIX_KEY_NOT_FOUND`, `soft_descriptor`), 404 e 401 validados; contratos
  viraram testes.
- Decidir a abordagem da fase de débito:
  - checkout hospedado do PagBank (depende de liberação do débito);
  - backend + frontend local com SDK 3DS;
  - outra opção justificada.

## Próxima decisão

**Fase 2 — débito com 3DS:** escolher entre checkout hospedado e fluxo próprio
com SDK/sessão 3DS. Não implementar antes de wireframe e decisão registrada.

## Último checkpoint

Qual a diferença entre `qr_codes` no topo do payload e `charges[].qr_code` na
resposta? (formato antigo vs. formato atual da Orders API)
