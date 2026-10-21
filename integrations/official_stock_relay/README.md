# API Oficial — Estoque (somente leitura)

A UI de Estoque do DOMINIUM chama `GET /api/imperium-official/stocks` para listar estoques e `GET /api/imperium-official/stocks/{id}/items` para ler o saldo. Essas rotas não existem na versão antiga do backend na porta 8765; por isso a opção **API Oficial** respondia 404 após o deploy do Worker VPC.

## Caminho operacional

Hostinger (sessão válida e papel operacional) → Worker `dominium-import-bridge` com credencial privada → `DESC_SERVICE` Workers VPC → relay local autenticado na porta **8793** → cliente HTTP oficial IMPERIUM do backend `C:\DominiumMain`.

Apenas GET de `/api/imperium-official/stocks` e `/api/imperium-official/stocks/{id}/items` é habilitado. Perfis `admin` e `controller` são permitidos; `viewer`, endpoints de escrita, outras cidades e parâmetros inesperados são rejeitados. Nenhuma senha de integração aparece no Worker ou no navegador.

A mesma porta 8793 permanece atendendo DESCONEXÃO; as rotas existentes são preservadas. O processo é supervisionado pelo agendador `DOMINIUM - DESC Relay Watchdog`.

## Arquivos e rollback

O código fonte de `official_stock_bridge.py` e a versão do relay com as rotas de estoque ficam versionados nesta pasta. No servidor, a cópia em execução fica em `C:\DominiumRuntime\DescRelay-20261010\`.

O código anterior do relay foi preservado em `desc_review_relay.pre_stock_20261021.py`. Para rollback, faça backup do arquivo em uso, restaure esse arquivo anterior e reinicie **apenas** o relay da porta 8793, sem interromper o DOMINIUM nas portas 8765/8791. O Worker pode voltar à versão anterior no Wrangler. Evite reiniciar durante alguma consulta DESC/estoque ativa.

## Testes

`node --test integrations/import_bridge/worker.test.mjs tests/test_operational_relay.js` e `python -m unittest tests.test_official_stock_relay`.

O workflow GitHub também realiza um GET autenticado do catálogo antes do upload da Hostinger. Em produção, conferir o carregamento da lista e consultar os itens de um estoque. **Não testar movimentações ou baixas como smoke test**.
