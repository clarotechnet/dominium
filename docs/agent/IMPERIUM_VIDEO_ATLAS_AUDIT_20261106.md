# Dominium — Fluxo comprovado nos vídeos operacionais, 06/11/2026

## Origem da evidência (fora do Git)

Vídeos autorizados no dispositivo **matheusdmc0**, pasta
`C:\Users\mathe\Videos\AulasYouTube`, consultados diretamente.
Quadros de auditoria gerados na subpasta `_dominium_video_review`
do PC de origem, que contém imagens e deve permanecer **fora do Git**.

1. `Relatório Análises de equipamentos [0nRVW8PjBiA].mp4`,
   aproximadamente 471 s: consulta de Equipamentos Utilizados
   no Imperium (Consolidado e Por Ordem de Serviço), extração
   dos seriais; Atlas > Equipamento > Relatórios >
   **Por Equipamentos** em lote; triagem por estados/localização;
   planilhas **Atlas, Imperium, CHIP Imperium, CHIP Atlas,
   Assinantes**. Quadros inspecionados ao longo de 00:16–07:27.
   A aba Assinantes exige conferência de **Falta Baixar** e
   **Fisicamente Estoque**, não inferível de consulta histórica.
2. `Como baixar a QUERY da claro [Umn3XSFY60g].mp4`,
   aproximadamente 404 s: relatório Atlas
   **Por Localização**, escolha de operação e localização,
   NetTask > Filas > relatório analítico e QUERY resultante.
   É outro fluxo, distinto do relatório **Por Equipamentos**.
3. `Relatório de Análise de SUSPEITOS da claro [DR56jbw0cVs].mp4`,
   aproximadamente 446 s: filtra estados Atlas
   **SUSPEITO** e **ANÁLISE DE INVENTÁRIO**, usa Imperium
   Consultar Seriais (movimentações), consulta Atlas
   Por Equipamentos/Rastreabilidade e faz revisão no
   Controlador/OS antes de finalizar a análise.
4. `Baixando SALDO DE MISCELÂNEA da CLARO [EdpyKfQ-yv8].mp4`,
   aproximadamente 171 s: processo separado de saldo de
   material e qualidade, não é a consulta de seriais.

As filmagens demonstram operações com dados particulares.
**Não incluir frames, planilhas brutas, credenciais,
seriais individuais nem capturas dessas telas no repositório.**

## Estado da implementação nesta branch

A operação das análises diárias possui agora três etapas
distintas e somente leitura contra os sistemas de origem:

1. **Pesquisar no Imperium DataSnap** por data/cidade.
   Validação real em Natal em 05/11/2026:
   1.096 linhas por OS, 91 itens consolidados,
   209 seriais únicos (204 de 12 caracteres, 5 ICCIDs
   de 20 caracteres). Dados salvos no Supabase operacional.
2. **Tratar seriais no Imperium**, uma consulta por vez:
   histórico, número de movimentações, divergências e
   estado de confirmação persistidos por serial.
   Pausa/retomada e exportação XLSX de
   *Seriais Tratados* e *Pendências*. Não infere
   posse física por movimentos históricos.
3. **Conferir seriais no Atlas**, agora integrada a partir do
   serviço `imperium_atlas_video.py` via ponte BotDMV
   autorizada (127.0.0.1:8787).
   A página tem ações para um serial ou sequência, pausa e
   atualização de progresso. A integração valida a identidade
   da resposta e registra estado, localização, contrato e
   data de alteração em
   `dominium_imperium_tratamento_itens.evidencia.atlas_video`.
   Não exige migração adicional.
   O identificador de fila é guardado para não reenfileirar
   solicitações pendentes. Se a submissão Atlas ficar incerta,
   a execução é suspensa para auditoria manual.
   Consulta individual da etapa 3 homologada somente em Natal.

### Validação de verdade da terceira etapa

Foi executado um ensaio limitado em **um serial** da coleta
de Natal de 05/11/2026 na API Atlas e no Supabase real:
- Ponte Atlas estava online.
- Solicitação enviada, estado `queued` registrado no banco.
- Uma leitura ainda pendente reutilizou **o mesmo requestId**.
- A leitura seguinte retornou verificado.
- Nova consulta ao Supabase retornou
  `atlas_verificados=1`, `atlas_fila=0`.
- `analise_video_seis_abas_completa=false`;
  os demais seriais não foram processados nessa execução.
- Nenhuma escrita realizada em Imperium nem Atlas.

### Limites ainda pendentes para copiar o vídeo integralmente

- Relatório Atlas **Por Equipamentos** em lote ainda
  não tem integração automatizada homologada com a mesma
  semântica do vídeo. Consultas individuais confirmadas
  não devem ser confundidas com o resultado total.
- As regras de **Assinantes**, incluindo baixa/aceite
  e estoque físico, dependem de evidência independente.
- Mapeamento correto da data `DATA` do XLSX do vídeo
  não é igual a `DataBaixa` ou `DataBaixaMiscelanea`;
  a comparação golden de 28/10 confirmou divergências.
- Os cinco ICCIDs de 20 caracteres não são enviados ao
  template DataSnap individual de 12 caracteres.
- Tratativa individual Atlas/Imperium para Mossoró e Recife
  não homologada, embora **coleta** DataSnap por período
  já tenha sido validada nessas praças.
- Não gerar seis abas finais como se fossem 100% auditadas
  enquanto essas fontes não forem integradas.

## Publicação

A branch de desenvolvimento é
`feat/imperium-two-stage-seriais-20261106`.

Não sobrescrever o working tree
`C:\DominiumMain`: sua `main` local contém 146 commits
à frente/81 atrás de `origin/main` e modificações
não confirmadas em `toa_browser.py`.

A aplicação Windows de produção usa
`C:\DominiumMain`, porta 8791, e o relay local
é iniciado separadamente por
`C:\DominiumRuntime\ImportBridge\supervise.ps1`.
Publicar **frontend e relay juntos** após realizar uma
reconciliação/implantação isolada, nunca fazer reset
ou git pull forçado nesse working tree.

O Supabase operacional é
`haqzzxpocwzntyudrbch`; as três tabelas
`dominium_imperium_*` existentes foram validadas.
