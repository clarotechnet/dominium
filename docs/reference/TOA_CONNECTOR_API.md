# DOMINIUM TOA Connector

Camada local e somente leitura que transforma a sessao autorizada do Oracle
Field Service em uma interface estavel para o DOMINIUM.

## Limites de seguranca

- nao contorna login, token, DUO, CAPTCHA ou permissao de bucket;
- nao salva usuario, senha, cookie, token ou cabecalho de autenticacao;
- nao altera atividades, rotas, tecnicos ou inventario no TOA;
- nao devolve nome, endereco, telefone ou e-mail de cliente;
- marca explicitamente quando a resposta veio de cache antigo;
- aceita apenas contratos numericos de 5 a 18 digitos;
- fica exposta apenas no servidor local do DOMINIUM.

## Endpoints

### Estado

`GET /api/toa/v1/status`

Informa se a sessao viva esta autenticada e quantos contratos sanitizados estao
no cache.

### Contrato

`GET /api/toa/v1/contracts/{contrato}`

Por padrao tenta atualizar pela sessao viva. Se a sessao estiver indisponivel,
devolve o ultimo retrato local com `freshness.stale: true`.

Parametros opcionais:

- `refresh=false`: nao tenta navegar no TOA;
- `allow_stale=false`: recusa cache e exige consulta viva.

Exemplo local:

`http://127.0.0.1:8765/api/toa/v1/contracts/4252617?refresh=false`

### Especificacao

`GET /api/toa/v1/openapi.json`

## Campos operacionais

- contrato, atividade e numero de agendamento/WO;
- data, janela, inicio e fim;
- cidade, tipo e status;
- tecnico, login e observacao;
- uma ou mais OS/tarefas e respectivos codigos de baixa;
- equipamentos instalados, retirados e do cliente;
- materiais/miscelaneas e quantidades;
- origem, horario da coleta e indicador de cache.

O conector nao autoriza baixa no Imperium por si so. Escritas continuam passando
pelas validacoes e confirmacoes operacionais existentes no DOMINIUM.
