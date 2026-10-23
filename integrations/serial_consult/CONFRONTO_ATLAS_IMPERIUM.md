# DOMINIUM | Confronto Atlas × IMPERIUM — Recursos → Pendente

## Implementação em 22/10/2026

A funcionalidade foi desenvolvida no checkout isolado:
`C:\DominiumRuntime\SerialMultiCityPatch-20261022`

### Interface e segurança

- Nova entrada **Pendente** logo após **Consultar Seriais** no menu Recursos.
- Suporte até 500 seriais por trabalho, quatro praças, consulta Analítico/Sintético.
- Backend de trabalhos SQLite durável, fila e progresso, recuperação segura após interrupções.
- Confronto somente leitura e categorização conservadora: convergente, divergente,
  revisão, inconclusivo. Histórico não confirma posse atual.
- CSV protegido contra execução de fórmulas.
- Hostinger: sessão DOMINIUM obrigatória; POST usa CSRF; somente admin/controller.
- Worker privado Cloudflare exige token e papel; VPC encaminha ao relay DESC
  em loopback. Cookies e CSRF do navegador não são encaminhados.
- Relay verifica token novamente e separa trabalhos por **ID autenticado**;
  um operador não abre dados de outro pelo ID do trabalho.

### Infraestrutura Atlas encontrada

- Chrome for Testing em `D:\Dominium\Tools\ChromeForTesting-156\chrome-win64\chrome.exe`
- Extensão real em `C:\DominiumRuntime\ManagedAtlasTOA-20261022\extension`
- Atlas consultado pela fila do BotDMV, não por navegador do operador:
  `POST /atlas/queue-query` → extensão → `POST /atlas/resolve-query`
  → `GET /atlas/query-result/{requestId}`.
- Bridge BotDMV executa no Ubuntu/WSL, Windows porta 8787 mapeada ao WSL.
- Consulta Atlas serial fictício foi enfileirada e respondida como negativa;
  um serial **real** ainda precisa ser validado junto ao estoque.

### Código

- `integrations/serial_consult/confront_engine.py`: regras e lotes.
- `integrations/serial_consult/atlas_bridge_client.py`: cliente de fila existente.
- `integrations/serial_consult/confront_job_runner.py`: SQLite e retomada.
- `integrations/serial_consult/confront_http.py`: API privada e worker.
- `integrations/serial_consult/confront_export.py`: CSV.
- `integrations/serial_consult/desc_review_relay.py`: extensão do relay.
- `deploy/hostinger-web/confront-policy.js`, `operational-relay.js`,
  `server.js`: autenticação, CSRF, isolamento e roteamento.
- `integrations/import_bridge/worker.mjs`: encaminhamento VPC com token.
- `static/confront.js`, `static/index.html`, `static/app.js`: painel.

### Deploy e rollback

- Relay DESC ativo em `C:\DominiumRuntime\DescRelay-20261010` recebeu
  patch mínimo com preservação de REPORTs e serviços existentes.
- Backup: `C:\DominiumRuntime\DescRelay-20261010\backups\pre-confront-20261022-191438`.
- Relay na porta 8793 foi reiniciado e passou o smoke local com autenticação.
- Worker `dominium-import-bridge` foi publicado e passou smoke privado via Node:
  controller=200; viewer=403; sem token=401; trabalho inexistente=404.
- Publicação Hostinger do frontend será realizada após testes e commit Git.
- O bot WSL, Chrome gerenciado e IMPERIUM não foram reiniciados por esta implementação.

### Validações e limites restantes

- Quality gate, testes HTTP, Python e Node executados; os resultados devem
  ser conferidos na versão final antes do push.
- Não há confronto positivo com equipamento real validado. Antes de confiar
  nas categorias de "divergente" ou "convergente", estoque deve conferir casos.
- A fila original do BotDMV ainda opera em memória e não oferece idempotência;
  o adaptador evita novo POST automático quando o envio ficou incerto.
- A porta 8787 do WSL escuta em todas as interfaces; restringir pela rede
  numa etapa posterior sem quebrar acesso do Chrome/WhatsApp existente.
- Nenhuma operação de baixa, movimentação ou alteração de cadastro é
  oferecida pelo módulo.


## Endurecimento e melhorias de 22/10/2026

- Chave de idempotência `request_key` (UUID hexadecimal gerado no navegador)
  persistida em índice único parcial SQLite por usuário. Uma repetição de POST
  com a mesma chave reutiliza o trabalho mesmo se ele já estiver concluído.
- `BEGIN IMMEDIATE` protege a criação de trabalhos contra POSTs concorrentes.
  A migração adiciona `request_key` automaticamente sem descartar registros existentes.
- O bloqueio de um segundo trabalho verifica **todos** os trabalhos em andamento
  do mesmo operador, não só os 20 últimos. O erro informa a praça do trabalho ativo.
- Histórico seletivo por praça na interface, permitindo reabrir relatórios do
  mesmo usuário. Nenhum relatório de outro usuário é exibido.
- O Atlas offline não oculta trabalhos históricos.
- Novos testes de regressão da interface JS cobrem histórico, retry com chave
  persistente na mesma tentativa, autenticação e presença da navegação.
- A bateria geral `scripts/quality_gate.py` inclui esses testes.

### Descoberta de rede: requer privilégio administrativo para conclusão

O Windows também tinha um portproxy **0.0.0.0:8787** aberto para WSL,
além de `127.0.0.1:8787`. Identificamos a tarefa agendada
`BOT DMV - WSL Bridge 8787`, que usa o script
`C:\BOT_OFICIAL_DMV\REPARAR_WSL_8787_RUNTIME.ps1` e recriava a
entrada pública após uma recuperação.

O script foi ajustado no próprio servidor: reparações futuras passam a
criar somente a entrada `127.0.0.1`. A tentativa de remover a entrada
pública **já ativa** não foi aplicada, pois o Windows exige elevação de
administrador (`netsh: A operação solicitada exige elevação`).
Não marcar o risco como resolvido até que a regra ativa seja removida
com privilégios apropriados e validada com o Atlas funcionando.
Snapshot de rede antes da mudança em
`output/atlas-network-before-20261022.txt` (diagnóstico local, não Git).
O firewall Windows foi observado desativado nos três perfis; não o ligamos
às cegas, para evitar interrupção dos serviços da base.


## Validação com um equipamento real (22/10/2026)

Foi realizada uma única consulta somente leitura, com identificador previamente
fornecido pela operação. As fontes responderam: Atlas com estado identificado
e DataSnap IMPERIUM com **8 movimentações confirmadas**. A posse atual
**não** pôde ser confirmada e a classificação correta foi `inconclusivo`.

Os provedores reais expuseram:
- Atlas: `estado`, `tipo_localizacao`, `operacao`, `localizacao`;
- IMPERIUM: `Movimento`, `Data`, `EstDestino`, além de número da O.S.,
  contrato e demais detalhes do histórico.

Por isso o relatório agora exibe explicitamente a **última movimentação
histórica IMPERIUM** e os campos de situação/localização do Atlas,
sem apresentar a movimentação como posse comprovada. O CSV recebeu
essas colunas extras no final para não alterar as 13 colunas existentes.
Não foram realizados baixas, transferências ou alterações de equipamentos.

## Vídeos revisados: fluxo operacional de planilhas

Em 2026-10-23 foram inspecionados três vídeos de treinamento do estoque:
baixa da QUERY Claro, relatórios de análise de equipamentos e SUSPEITOS.

**Lacuna anterior:** Pendente apenas aceitava seriais colados.
**Melhoria agora:** bloco inicial na interface permite carregar CSV ou XLSX
localmente (nenhum upload automático), escolher praça/Operação incluindo
Mossoró, filtrar estado (p.ex. SUSPEITO, SUCATA) e local/estoque,
ver a prévia e encaminhar até 500 seriais filtrados ao confronto read-only.

Não presumir a praça quando a planilha não possui coluna de
Cidade/Praça/Operação/Regional: a interface exige confirmação explícita
sobre a origem, evitando cruzamento indevido de Natal e Mossoró.
Seriais com notação científica são ignorados com alerta.
O download diretamente do relatório Claro/Atlas **ainda não é automatizado**;
o operador importa o arquivo exportado no fluxo oficial. Seriais reais,
capturas de vídeos e planilhas confidenciais não são versionados.
Usa fflate 0.8.2 (MIT, licença em static/fflate.LICENSE.txt) apenas no navegador.
