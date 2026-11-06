# DOMINIUM — Controle de baixas e Tratativa Claro (06/11/2026)

## Estado da entrega

- **Implementado em branch de homologação:** `feat/controle-baixas-homolog-20261106`.
- **Produção:** não liberar automações de baixa desta branch. Botões "Iniciar improdutivas/produtivas" continuam desabilitados.
- **Controle de baixas:** menu novo, filas por janela, próxima consulta, tratamento humano e prévia das baixas, dados fictícios ou lista Imperium já carregada.
- **Tratativa Claro:** quadro com quatro cidades sob Análise Backlog > Tratativa do dia, reutilizando `/api/backlog/year/status` já chamado pelo módulo existente, sem disparar consultas TOA adicionais. Mostra cartões e exportação CSV para os registros previamente tratados.
- **Fora de Rota:** botão abre aba existente, sem envio externo.
- **Validação:** Node.js `node --test tests/test_close_control_engine.js tests/test_backlog_claro_board.cjs`; regressões de módulo backlog e semiautomática. Capturas Chrome de homologação em diretório local não versionado.
- **Dados de clientes:** não foram adicionados ao GitHub ou ao Graphify.

## Regras de decisão do novo motor

1. Exige contrato e O.S., janela válida e hora dentro da janela antes de sugerir consulta.
2. Exige prova explícita de rota importada, O.S. importada e O.S. presente no Imperium.
3. Para pendente/em rota, nova consulta após **30 minutos**; para iniciada, **15 → 20 → 30 → 30** a partir das leituras reais.
4. Ao encontrar TOA concluído, exige código, detalhe da tarefa, identidade, bucket e materiais validados, além de confirmar que a baixa ainda não consta do Imperium.
5. `confirmationState=sent/uncertain` impede o reenvio e exige conciliação.
6. Planejamento por contrato gera sugestões deduplicadas; `networkCalls=0`, `closesSent=0`.
7. Não salva cooldown em banco nem implementa agendamento: **isso está pendente no backend**.

## Regra de negócios de improdutivas

- O código **430 é retirada produtiva**, jamais classificar como improdutiva.
- Pendente não é improdutiva. Falha de leitura ou ausência de código validado exige tratativa humana.
- O sistema DESC já possui worker operacional próprio. NÃO substituir, interromper ou alterar a automação atual durante a implantação desta interface.
- O painel novo é apenas leitura e não executa baixas.

## Limite de integração com o Worker antigo

O Worker Cloudflare `analise-backlog` ainda mantém a base própria de backlog e endpoints:
- `POST /api/backlog/query`: contratos encontrados na base do Worker;
- `GET /api/backlog/meta`: estado da base;
- `GET /api/fora-rota/sent` e endpoints de confirmação de enviados.

O módulo DOMINIUM `Análise Backlog` utiliza `/api/backlog/year/status` e `/api/backlog/year/fora-rota`, com outra origem de dados. Este PR **não importa a base da Claro do Worker**, não substitui os relatórios do Worker e não sincroniza o histórico `sent` entre esses sistemas. Exibir quatro colunas sobre dados diários do DOMINIUM **não** garante paridade com o gerador completo do Worker.

**Próxima integração necessária para paridade funcional:**
- Criar leitura autenticada pelo backend, sem acesso público a contratos/telefones e sem espalhar credenciais no navegador.
- Consultar de maneira batelada/cached a base do Worker somente com autorização, e cruzar com estado atual confirmado no Imperium; não marcar como improdutiva por histórico isolado.
- Integrar bairro, quantidade, agenda, técnico, geração de mensagem, registro de enviado e deduplicação persistente no DOMINIUM.
- Homologar com rotas reais, auditar divergências, preservar acesso ao Worker antigo até validação completa.

## Importação repetida em 03/11/2026

Logs locais DOMINIUM: **44 importações registradas**, **6 nomes de arquivo distintos**, somente Natal/Parnamirim, em janelas de execução 08:47–17:25. Houve 12 registros na hora 09:00. Somatório de `imported` é **700**, que **não** significa 700 O.S. distintas.

**Risco:** sessões TOA poderiam nem estar abertas em 01/11 e 02/11; ciclos do coletor não provam chamadas Oracle. Não publicar estimativas de requisições Oracle como contagens oficiais.

## TOA: 1 sessão versus 5 logins

**Não distribuir consultas para contornar suspensão por detecção de automação.** Primeiro obter o limite autorizado da Claro para a organização e para cada sessão. Preferir:
- cache compartilhado por contrato/OS com carimbo, janela e status;
- deduplicação global por contrato e cronograma persistente;
- teto diário/hora e cancelamento por HTTP 401/403/429;
- fila central com somente uma leitura simultânea por sessão autorizada;
- expansão para várias sessões apenas com aprovação e **mesmo orçamento global**, para tolerância a falha, não para elevar volume total.

## Rollback

Branch isolada derivada da `main` de `clarotechnet/dominium`. Basta não fazer merge/deploy. Ações operacionais não foram ativadas. O diretório local `C:\DominiumRuntime\ControleBaixasLab-20261106\backups\controle-baixas-20261106` contém cópias pré-mudança de `app.js` e `index.html` (não comitar).
