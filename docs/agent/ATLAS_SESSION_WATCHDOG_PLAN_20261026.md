# Atlas: verificação real de sessão no watchdog

> For agentic workers: use superpowers:executing-plans, com testes antes da implementação.

**Goal:** distinguir uma aba Atlas aberta de uma sessão comprovada por consulta real NetTask.

**Architecture:** reutilizar ChromeAtlas/evaluate_query e a tarefa Browser Watchdog
existente (PT5M). Consultar somente um ID previamente confirmado no SQLite aberto
em mode=ro. Persistir resultado sanitizado e timestamp em arquivo próprio do monitor.

**Tech Stack:** Python 3.12, SQLite, Chrome CDP e PowerShell de instalação.

**Spec:** autorização e critérios de ATLAS_QUERY_VERIFICATION_20261026.md;
esta seção define o pequeno ajuste de monitor solicitado após o diagnóstico.

## Design e alternativas

Contar abas é insuficiente. Repetir geração criaria efeitos desnecessários.
Escolha de implementação: consulta real ao ID existente via conector atual,
em quadro oculto temporário. Resultado complete/processing/failed comprova leitura
autenticada; not_found/timeout/erro inesperado é inconclusivo. AtlasAuthRequired
informa login necessário. O arquivo novo sempre substitui a observação anterior.
Nenhuma renovação automática de SSO/captcha é prometida. Anexo anunciado e sessão
válida não significam relatório disponível; este monitor não baixa relatórios.

## Global Constraints

- Somente Atlas/QUERY; sem TOA, baixas, estoques, contratos ou O.S.
- Sem geração, migração ou escrita no SQLite; sem reiniciar/navegar Chrome principal.
- Sem URLs privadas, cookies, tokens, clientes ou texto bruto de exceções nos registros.
- Backup do watchdog antes de patch; manter tarefa e intervalo existentes.
- Atlas/BatAtlas continua responsável pelo anexo404; monitor não resolve esse arquivo.

## Review Focus

- Aba persistente com sessão expirada: resultado login_required, nunca authenticated.
- Timeout ou resposta desconhecida: unknown, sem manter sucesso anterior.
- Banco inexistente/vazio/inválido: unknown e nenhuma criação de banco/QUERY.
- ID malformado no banco: ignorar, sem enviar consulta arbitrária.
- Sessão válida com anexo404: saúde da sessão separada da entrega do relatório.

## Task 1: monitor e instalação

**Files:** criar integrations/serial_consult/atlas_query_health.py,
scripts/install_atlas_session_watchdog.ps1 e tests/test_atlas_query_health.py.

**Interfaces:** latest_queue(db_path)->str|None; inspect_session(remote_id,
chrome_factory=ChromeAtlas, queue_reader=evaluate_query)->dict;
record_health(db_path,output_path)->dict. Instalador copia módulo já publicado
e insere chamada idempotente no watchdog existente após backup.

- [ ] Escrever testes: erroauth=>login_required, timeout=>unknown,
  confirmação real=>authenticated sem statusready, not_found=>unknown,
  DB ausente permanece ausente, seleção de ID válido, banco inalterado,
  persistência substitui sucesso por erro e não revela URL/erro bruto.
- [ ] Executar unittest e confirmar RED pela ausência do comportamento.
- [ ] Implementar somente leitura e instalação com backup.
- [ ] Executar testes QUERY, quality_gate, revisão independente e publicar no GitHub.
- [ ] Instalar no servidor, executar tarefa existente e confirmar JSON/timestamp,
  código implantado, integridade/contagens SQLite e próxima execução agendada.
- [ ] Registrar evidências atuais de Natal e pedido técnico exato para fornecedor.

## Ledger

26/10/2026: sessão autenticada reconfirmada por NetTask. IDs276908463 e276908572
COMPLETO, XLS/HTML/ZIP404, navegação Chrome404. Nenhuma nova QUERY criada.
Plano executado dentro da autorização de corrigir/testar/publicar, sem nova
confirmação. Pre-flight: um componente; instalação consome record_health().

Testes: 9 casos novos RED (monitor ausente) -> GREEN; 51 testes QUERY Python
aprovados. Primeira execução do gate encontrou três imports Selenium ausentes
no ambiente local; dependências declaradas de requirements-dev instaladas.
Revisão independente não encontrou problema crítico/importante; apontou marcação
invertida no instalador. Reclassificado como importante por permitir falso sucesso
de instalação: fixture Windows reproduziu RED, antes da correção.

Verificação final pré-publicação: fixture Windows GREEN em seis verificações
(preservação do prefixo, idempotência, backups, fallback sem dependência,
sintaxe inválida e marcadores invertidos). Gate completo: 913 testes Python,
21 ignorados; JavaScript, Ruff, build e auditoria aprovados, QUALITY_GATE_OK.
Revisão independente concluída; único apontamento corrigido por RED/GREEN.
As alterações operacionais ainda aguardam instalação no servidor neste registro.
