# DOMINIUM UI Redesign

## Escopo

Camada visual aplicada somente ao frontend estatico:

- `static/index.html`
- `static/styles.css`
- `static/app.js`

Nenhum endpoint, payload, regra de baixa, integracao TOA, DataSnap ou fluxo de estoque foi alterado.

## Implementado

- Tokens semanticos finais para superficies, bordas, textos, estados e foco.
- Refinamento de cabecalho, perfis, navegacao lateral, controles, tabelas, paineis e modais.
- Foco visivel e suporte a `prefers-reduced-motion`.
- Termos de uso operacional acessiveis no rodape lateral.
- Exibicao dos termos na primeira abertura de cada versao.
- Registro local da ciencia em `localStorage`, sem envio ao backend.

## Termos

Versao atual: `1.0`

Chave local: `dominium.terms.accepted.v1`

Os termos esclarecem uso autorizado, conferencia dos dados, tratamento de resultados incertos, credenciais, auditoria e responsabilidade operacional.

## Preservacao

- IDs e seletores existentes foram mantidos.
- Os novos elementos usam IDs exclusivos.
- O tema escuro existente foi preservado e refinado.
- Nenhuma dependencia nova foi adicionada.
- O Motion existente foi preservado sem ampliar animacoes continuas.

## Validacao

Executado em 28/07/2026:

- `node --check static\app.js`: aprovado.
- `python -m unittest test_app.py`: 16 testes aprovados.
- `python -m unittest discover -p "test_*.py"`: 446 testes aprovados.
- Integridade de seletores: 303 seletores de ID do JavaScript encontrados no HTML, sem IDs duplicados.
- Validacao visual isolada em `1366x768` com quatro perfis: sem overflow e sem erro de console.
- Validacao visual isolada em `1024x768`: sem overflow e com termos acessiveis no rodape.
- `git diff --check` nos arquivos desta etapa: aprovado.

Comandos de reproducao:

```powershell
node --check static\app.js
python -m unittest test_app.py
python -m unittest discover -p "test_*.py"
git diff --check -- static\index.html static\styles.css static\app.js UI_REDESIGN_PROGRESS.md
```

## Sites

O painel depende do backend Python local e de integracoes internas. A publicacao em producao exige uma camada de API acessivel, autenticada e isolada antes de hospedar o frontend fora da maquina operacional.
