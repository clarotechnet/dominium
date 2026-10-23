# DOMINIUM — handoff operacional (memória verificada)

> Estado revisado em 2026-10-23. Para datas futuras, confirmar com o código,
> testes e ambiente real. Não armazenar senhas, tokens, nomes ou seriais de clientes.

## Produto e arquitetura

DOMINIUM é o painel operacional da TECHNET que integra TOA/Oracle Field
Service, IMPERIUM/DataSnap, Atlas, estoque, agenda e fluxos DESC/WhatsApp.
Código no Git; dados de runtime, perfis do Chrome e credenciais fora do Git.

## Estado recente confirmado

- Consultar Seriais suporta Natal/Parnamirim, Fortaleza, Mossoró e Recife.
- Em 2026-10-23, após revisar os três vídeos de treinamento, a aba Pendente ganhou importação local CSV/XLSX da QUERY Claro, filtros explícitos por praça (Mossoró etc.), estado e local, prévia e opção de usar os seriais filtrados no confronto. Exportação direta da QUERY pelo Atlas ainda não é automatizada.
- Recursos → Pendente: confronto Atlas × IMPERIUM de até 500 seriais,
  trabalhos SQLite persistentes, idempotência por requisição, histórico por
  operador/praça, CSV, interface protegida pelo login e ponte privada.
- Um serial real foi consultado somente para validação e retornou informação
  em ambos os sistemas, mas **posse atual não confirmada**; classificação
  correta: `inconclusivo`. Histórico não significa responsável atual.
- Extensão Atlas/TOA fica no Chrome gerenciado separado do Chrome pessoal;
  a fila do Atlas é atendida pelo BotDMV em WSL.
- Pendência importante: entrada Windows 0.0.0.0:8787 ainda ativa na última
  checagem; exige elevação de administrador para remover. O script da
  tarefa de reparação foi corrigido para criar apenas loopback.
- Não declarar equivalência definitiva de estados Atlas/IMPERIUM sem
  validação da área de estoque com exemplos reais.
- Não inferir situação atual dos serviços somente desta memória; fazer
  health check e consultar GitHub Actions antes de afirmar deploy OK.

## Navegação rápida

- `docs/agent/TASK_ROUTER.md`: subsistema → código.
- `.dominium/project-map.md`: mapa e índices auto-gerados.
- `python scripts/agent_memory.py brief`: contexto curto.
- `python scripts/agent_memory.py search "confronto atlas"`: memória pesquisável.
- `python scripts/query_agent_context.py "endpoint"`: símbolos e APIs.
- Confronto: `integrations/serial_consult/`, `static/confront.js`,
  `integrations/import_bridge/worker.mjs`, `deploy/hostinger-web/`.
- `scripts/quality_gate.py`: verificação integrada antes de publicar.

## Ao concluir uma entrega

Atualize este handoff se o estado mudou, registre motivo/decisão/testes
em `docs/agent/memory/OPERATIONS_JOURNAL.md` via
`python scripts/agent_memory.py record`, rode testes e quality gate,
valide commit/deploy e deixe pendências explícitas.
- A etapa automatica da QUERY Atlas foi codificada: praca/EMPREITEIRA, Chrome autenticado isolado, fila NetTask com ID persistido, espera 30s e retry 404 sem gerar duplicatas, tabela e CSV/XLSX. Relay privado e Cloudflare Worker atualizados em 2026-10-23; anexo real segue retornando 404 e nao ha planilha confirmada. Ver docs/agent/ATLAS_QUERY_AUTOMATION.md.

- Em 2026-10-23, ao investigar clique sem retorno da QUERY: frontend
  apagava mensagem na atualização automática; versão corrigida introduz
  histórico persistente na tela e mantém falhas visíveis. O conector
  passa a reutilizar a aba NetHome do watchdog por iframe temporário,
  evitando abrir outro Chrome; preflight somente leitura aprovado.
  Geração real no novo caminho ainda precisa confirmação operacional.
