# DESC, Adesão e lote 106 — revalidação em 29/10/2026

## Decisões vigentes do operador

Continuar a ADR-004. Contrato enviado pelo técnico no grupo DESC é o gatilho
para pesquisar no TOA; não tomar mensagem, nome do serviço ou HTTP 200 como
prova de baixa. Grupo, técnico, bucket e atividade precisam conferir.

**Exceção nova e explícita:** manter **ativado o lote 106 às 23h de Brasília**,
nas quatro cidades, para O.S. de desconexão/retirada ainda em campo no dia.
As demais baixas gerais continuam desligadas. Não usar a exceção para
reativar o varredor de Adesão ou produtivas gerais.

## Fontes recuperadas

Reanalisados os ZIPs Jader/Imperium, Integração Imperium x Technet e Synia.
Os três ZIPs reenviados são idênticos em bytes aos anteriores. Também foram
analisados quatro históricos de grupos DESC: NTL/PWM, CE, MRO e PE.
Arquivos privados e mensagens originais não são versionados.

Evidências dos grupos: contrato sozinho; contrato e código na mesma linha;
contrato, código e observação em linhas separadas; contrato com relato sem
código; avisos com endereço e agenda. Recife utiliza frequentemente nove
dígitos. Endereço, horário e número de equipamentos não são códigos de baixa.

Evidências da API permanecem: número e data importada do TOA; arrays vazios
quando não há itens; saldo/código do instalador; HTTP 200 significa fila;
confirmar resultado antes de reenviar. A API não deve ser considerada
equivalente por descrição sem comprovação atual.

## Estado real encontrado

- Runtime principal servido na porta 8765, no diretório
  `C:\DominiumRuntime\Imperium\FerramentaImperiumDireto-OLLAMA`.
  `C:\DominiumMain`/8791 é outra árvore; não substituí-la.
- Bot online no Ubuntu/WSL, `/home/technet/BotDMV`; processo PM2 `Bot`.
- Código do runtime é diferente da main. As correções legadas precisam ser
  cirúrgicas; não sobrescrever o Imperium inteiro a partir do clone web.
- Confirmados desligados: executor geral, produtivas gerais, WhatsApp
  automático e `external_execution_enabled` do runner.
- O lote 106 foi reativado pelo endpoint existente e relido: `enabled=true`,
  `server_scheduler_active=true`, 23:00, Brasília, DataSnap, quatro cidades.
- A primeira prévia recebeu 409 por operação concorrente; uma leitura
  posterior de Natal retornou 67 O.S. em campo no filtro desconexão, igual
  ao print. Nenhuma baixa foi feita nessa conferência.
- Cliente HTTP legado não tinha consultas de estoque. O cliente atual foi
  testado isoladamente: consulta oficial retornou 369 estoques, incluindo
  RETORNO ativo, id 2. Não houve transferência nem baixa nesse teste.

## Correções preparadas e verificadas

1. Parser reconhece candidatos de 7–9 dígitos e contratos compactos de
   sete dígitos+código. Múltiplos contratos ou interpretações compactas
   conflitantes bloqueiam. Comandos, telefone e serial isolados não
   viram contrato. `FR` não inventa 430; o TOA define o código.
2. Agenda e endereço não contaminam o código. A caixa de mensagens do
   runtime preserva contratos de Recife com nove dígitos.
3. Alocação agrupa equipamentos em uma única O.S. por código, deduplica
   seriais compartilhados no mesmo código/direção e bloqueia cruzamentos.
   O runner usa a evidência completa mesmo quando somente um código foi
   solicitado. Filho único preserva todos os equipamentos TOA+CSV.
4. Planejador oficial rejeita itens em assinatura/INST GPON - INST CABO,
   inclusive rótulos com prefixo numérico. Arrays vazios são preservados.
5. Qualquer miscelânea exigida sem cobertura bloqueia antes de transferir
   outros itens. Removida a tolerância de até quatro itens ausentes na
   árvore web; a rotina legada recebeu guarda equivalente sem substituir
   suas regras de catálogo.
6. Lote 106 repete apenas leituras 409, com limite e janela de horário;
   preserva recibos por IdOS, execução uma vez por dia e nenhum reenvio
   de POST incerto.

## Verificação e limites

Staging Windows: 76 testes Python e 9 Node aprovados, incluindo dependências
legadas e guardas de setor. Quality gate da árvore web: 982 testes Python,
22 ignorados, JavaScript, Ruff e build aprovados. Os novos testes portáveis
de runtime e parser foram incluídos no gate para futuras alterações.
Revisão independente corrigiu escopo da data e reconciliação do filho único.

**Ainda não homologado:** automação completa DESC multiOS, protocolo de baixa
sem equipamentos das O.S. acompanhantes e automação completa Adesão por API.
O complemento legado utiliza DataSnap para preparar estoque; a transferência
integral pela API oficial e a confirmação assíncrona com itens precisam de
validação própria. Consulta oficial RETORNO não comprova transferência.

**Não declarar lote das 23h executado:** foi habilitado e testado por simulação,
mas a execução operacional precisa ser conferida após o horário.

## Publicação/instalação

Instalados oito arquivos após validar hashes de origem e staging. Backup:
`C:\DominiumRuntime\Backup\DescAdesao-20261029-152337`.
Patches da API legada e plano oficial preservaram o restante das fontes.
Serviço 8765 reiniciado, PID 12064; bot PM2 online, PID 154981.
Oito hashes instalados conferidos. Agendador 106 foi relido ativo após a
recarga; os outros executores foram relidos desligados. Navegadores,
DominiumMain/8791 e módulos de estoque paralelos preservados.

O gate final também executa 14 testes portáveis do agendador e 12 da caixa
de mensagens, além dos 982 testes principais e dos testes JavaScript.
Não houve nova baixa, movimentação de estoque nem consulta enviada a grupos.


## Prévia real do lote 106 após a recarga

Consulta somente leitura nas quatro cidades aprovada, sem erros:
Natal/Parnamirim 67 O.S.; Fortaleza 54; Mossoró 10; Recife 141.
São 272 elegíveis nesta leitura, zero baixas/transferências. Estes números
não reservam o lote: às 23h o servidor precisa reler as O.S. ainda em campo.


## Consultas reais ao TOA após a instalação

Dois contratos extraídos dos grupos enviados pelo operador foram consultados
pelo endpoint local de leitura `/api/toa-live/lookup`, com perfil explícito.
Mossoró e Recife responderam HTTP 200, uma atividade do contrato correto,
concluída, com uma tarefa cada. O caso Recife usa nove dígitos. Não houve
baixa, transferência ou envio de mensagem aos grupos.

O resultado dessa consulta genérica não expôs bucket no resumo; não usá-la
como prova de que todas as guardas do executor por grupos foram aprovadas.
A validação de bucket no fluxo específico permanece obrigatória e fechada.
