# CHECKPOINT - API Jader / Imperium - 17/09/2026

Escopo: DOMINIUM PRIMARIO no PC pessoal. O secundario/modo TV no servidor nao foi alterado.

## Implementado
- Login oficial Imperium permanece server-side via HTTPS e Bearer.
- Captura segura dos headers Id-Usuario, Id-Estoque, Grupo-Usuario e Usuario.
- GET oficial de estoques: /technet/estoques e /technet/estoques/{idinstalador}.
- GET oficial de saldo: /technet/equipamentosestocagem/saldo/{idestoque}.
- Renovacao por novo login em 401/403, uma unica vez nas leituras.
- Normalizacao de estoques e itens para um formato interno estavel do DOMINIUM.
- Novas rotas DOMINIUM /api/imperium-official/* somente para admin/controller.
- Token e credenciais nunca sao devolvidos ao navegador.

## Interface
A tela Estoque ganhou seletor de fonte: Operacional ou API oficial.
Operacional continua sendo o padrao e preserva baixa rapida, PDF e lote.
API oficial e somente consulta; operacoes de escrita ficam desabilitadas nessa fonte.
Ao sair da tela Estoque, a fonte volta para Operacional para nao contaminar outros modulos.

## Validacao real somente leitura
- Login de producao confirmou os quatro headers documentados.
- /technet/estoques respondeu e foi normalizado com sucesso.
- /equipamentosestocagem/saldo/{id} respondeu e foi normalizado com sucesso.
- /estoques/{idinstalador} pode retornar data como objeto unico; parser cobre objeto e lista.
- Nenhuma transferencia, movimentacao ou outra escrita foi disparada nos testes reais.

## Testes
- Python py_compile: OK.
- JavaScript node --check: OK.
- 62 testes Python: OK.
- Backup: backups/jader_api_20260917.

## Pendente por falta de contrato tecnico confirmado
Transferencias e movimentacoes nao foram ligadas a producao. O documento descreve a funcionalidade desejada, mas nao define de forma suficiente o endpoint Imperium real, payload, resposta e semantica de idempotencia para uma escrita segura. Nao inventar POST em producao.
