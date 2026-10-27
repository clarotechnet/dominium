# Consulta TOA: nome do recurso na árvore — 27/10/2026

## Causa e ajuste

Contrato 4321376: Search encontrou aid 203706151, pid 66627, login Z657615,
status complete, mas detalhes não incluíram Provider com nome. A extensão
interrompia em toa_provider_nao_encontrado, exibido como indisponibilidade.
A árvore Time.get contém o recurso exato e seu nome.

providerById consulta apenas o PID solicitado, exige o mesmo login, recusa
nome vazio/bucket DMV e devolve cópia. resolveTechnicianForRow usa esse nome
como complemento aos dados diretos/cache, antes do fallback de roteamento,
cuja guarda por PID foi preservada. Não escolhe técnicos pelo contrato agregado.
Teste de regressão exercita as funções reais e integra o quality gate.

## Instalação e preservação

Patches cirúrgicos em somente content-main.js e toa-auto-export.js da extensão
C:\DominiumRuntime\ManagedAtlasTOA-20261022\extension. Hashes prévios
verificados antes de escrever; backups em ToaProviderFix-20261027.
Runtime contém recursos adicionais de localização/contatos/selectedProvider:
não foi substituído pelos arquivos completos da versão do repositório.

SHA256 após ajuste:
- content-main.js: 34a8bcc6f0722f0571924e037ac0b39226d5e18422cc312690b724dadb5a9c6c
- toa-auto-export.js: b03bcd2ff71ef6de62abecee6ae198f9472e39d0b74b1200a9dd655dc31b3cbc

Recarregada a extensão e a página TOA no Chrome gerenciado existente; processo
Chrome/perfil autenticado preservados. Um primeiro teste após reload ocorreu
antes da árvore de recursos terminar de carregar (16 nós), falhou fechado;
com a árvore carregada (371 nós), consultas seguintes passaram. Não há retry
novo nem nome presumido quando o recurso não está disponível.
Worker, Hostinger, Estoque/QC e pasta de trabalho de Matheus não foram publicados
ou alterados nesta instalação. Nenhuma baixa real foi enviada.

## Verificação

- Regressão falhou antes do ajuste (nome vazio) e passou depois.
- IDs/logins divergentes, login ausente, bucket e nome vazio são recusados;
  case-insensitive login, cópia retornada e fallback de PID histórico cobertos.
- Revisão independente sem bloqueios; sintaxe de ambos os arquivos aprovada.
- Gate: 955 testes Python, 22 ignorados; JS, Ruff e build aprovados.
- Dois testes Python de sessão secundária e teste de desconexão aprovados.
- Teste auxiliar antigo test-toa-inventory-core.js tem falha preexistente:
  inventory.length é 5, expectativa 4, linha 135; core e teste não modificados.
  Os dois testes auxiliares .js também possuem conflito CommonJS/type:module
  quando invocados diretamente; foram executados em diretório temporário CommonJS.
- Gateway /toa/lookup: HTTP200, ok, contrato exato, aid/pid exatos,
  nome do recurso Billy Djow Barbosa de Andrade, validation.errors vazio.
- Worker privado /api/toa-live/lookup?profile=natal: HTTP200, ok,
  aid exato, duas tarefas, validation_errors e operation_blockers vazios.
  Backend runtime preserva responsabilidade histórica: assigned_technician
  id72142/Rodrigo Costa da Silva, enquanto recurso atual pid66627 e formulário
  são Billy. O runtime Python difere do repo e preserva esses campos históricos.
  Não interpretar os dois nomes como equivalentes nem alterar atribuição/baixa
  com base apenas no nome recuperado. Este ajuste resolve a consulta abortada.

## Continuidade

A consulta já funciona no runtime. Registrar código com skip deploy, pois não
há mudança de Worker/Hostinger. Antes de outro deploy, reler versão corrente e
preservar o trabalho compartilhado. Não repetir a baixa confirmada da OS2662320818.
