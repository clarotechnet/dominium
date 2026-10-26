# Natal — vídeo, comparação e recuperação do relatório atual

Verificado em26/10/2026, America/Sao_Paulo. **Natal tem relatório manual atual
recuperado no DOMINIUM; geração automática confiável ainda não comprovada.**

## Resultado entregue no pipeline existente

ID manual confirmado276922051, atlasBatch03/app-3. O servidor autenticado
baixou o anexo comHTTP200,15.791.658 bytes e20.145 registros, todosNATAL.
SHA256 original82e8d68e4275ab128842c40df0b62badced8b16aa8e91f253bb70a40419b87b1.

Recuperado sem gerar outra QUERY, com manifesto explícito de origem manual:
job3926df0c8a924e8fb455cd4be36f06ac, state=ready. Backup consistente antes da
inclusão: query_jobs.before-recover-manual2051-20261026-093320.sqlite3.
O worker existente interpretou e persistiu o original validado. Não foi
inserido o arquivo antigo20150linhas como se pertencesse a esse novoID.

Manifesto privado: AtlasQueryData/recovered_manual_natal_276922051.json,
origin=user_manual_generation, new_atlas_submissions=0. Execução repetida
reutiliza manifesto/ID existente. Nenhuma baixa, estoque, contrato, OS ou TOA.

Dados de origem consultados no NetTask, corrigidos na recuperação após backup:
submissão09:24:50, início09:24:58, fim09:25:15. O registro de recuperação09:33
permanece no manifesto, separado dos horários reais da fila. URL original
salva privadamente após validação da origem. Backup da correção de horários:
query_jobs.before-manual2051-timestamps-20261026-095059.sqlite3.

## Verificação de fonte, banco, tela e arquivos

- Fonte reparseada igual a todas as linhas salvas no SQLite, sem amostragem.
- Serviço: CSV/XLSX200, arquivos comparados célula por célula, ZIP íntegro e
  sem fórmulas inesperadas. CSV3.014.525 bytes; XLSX Python1.179.814 bytes.
- Cloud Browser autenticado: fila276922051, tabela100linhas/página, total20.145,
  exportações habilitadas e ID recuperado após recarregar a página.
- Downloads reais pelo navegador: CSV3.014.525 bytes e XLSX1.226.746 bytes.
  XLSX íntegro,20.146linhas incluindo cabeçalho,11colunas, sem fórmulas;
  todas as células CSV/XLSX iguais. Não usar igualdade de bytes ZIP entre
  implementações como critério de igualdade de dados.
- SHA256 CSV navegador e213792c09bcb27144634049027e87065e4cbbb495ead2a1277c10d9d7027607.
- SHA256 XLSX navegador6da7e98e2c7249a23f21ab29ae259328a603f681deed1656213ca0ea2e848bfb.
- SHA256 canônico de todas as células exportadas
  d306de64ba6b6cad4fe3e91518949d132bb231cb6d28a85332d12c23e8afac37.
- Banco íntegro:25trabalhos,183.194linhas. QUERY/confront/reports autenticados200.
  Código permanece na versão publicada anterior: pipelineceae3fd, HTTP/UIc94984b,
  monitor de sessão5fa3132. Esta etapa não alterou código de produção nem reiniciou serviços.

## Comparação das requisições

Parâmetros NetTask iguais no manual bom276922051 e automático ruim276921081:
idOperacao179, idTipoLocalizacao5, idTipoEquipamento0, idEstadoEquipamento0,
idLocalizacao0; idClassificacao/idEmpresa/idSubTipoEquipamento vazios.
Não há evidência de filtro diferente para explicar esses dois resultados.

| Caso | Servidor observado | Anexo | Evidência |
| --- | --- | --- | --- |
| 276922051 manual | atlasBatch03 | app-3 | 200; fonte/banco/UI/exportações aprovados |
| 276921081 automático | atlasBatch02 | app-2 | COMPLETO e404 |
| 276921301 manual | atlasBatch04 | app-1 | COMPLETO; usuário confirmou404 |
| 276921309 candidato | não reconfirmado | app-1 | 404; nome diferente do primeiro XLS recebido |
| 276922013 manual | não reconfirmado | app-1 | usuário mostrou processamento completo e404 |
| 276922217 manual | não reconfirmado | — | FALHOU; início/fim09:30:03 fornecidos pelo usuário |

atlasBatch03 também falhou com NPE no ID276921180, conforme log anterior.
Associação entre nó e disponibilidade é evidência, não causa interna provada.
Não afirmar que app-3 elimina qualquer falha.

Uma busca oficial Por Range (276921180–276921309), com navegação de páginas
anunciadas pela própria tela, localizou candidatos do horário do primeiro XLS.
Nenhum vínculo com o arquivo foi confirmado; um candidato foi excluído por
parâmetros de outra praça. Não atribuir o primeiro XLS20150linhas aID suposto.
O ID276922051 conhecido tornou desnecessária a busca por um número adivinhado.

## Análise visual do vídeo enviado (51,27s)

Frames extraídos para análise, sem publicar imagens com identidade/relatórios.
O vídeo demonstra o seguinte caso, não uma garantia estatística:

- 0–11s: abrir relatório, escolher Natal e Empreiteira e solicitar geração.
- 12s: confirmação do ID276922323.
- 20–39s: Visualizar Processos mostra amarelo/processando. A tabela anterior
  continuaNOVA, pois aquela tabela não foi atualizada durante a observação.
- 41s: indicador verde/status.fila.completo; processo09:33:57–09:34:13.
- 44s: Dados da Fila informa atlasBatch03 eCOMPLETO.
- 45–48s: Anexos e início de download peloapp-3; o vídeo não comprova sozinho
  a conclusão/integridade de todos os bytes desse novo arquivo.

Inspeção do JavaScript oficial: visualizarProcessos somente abre a URL GET
/nettask/filas/processos.do?idFila=ID. A página se atualiza a cada20s.
Consulta real dessa mesma página retornou status.fila.completo tanto para
276922323/276922237 como para o automático276921081 que tinha anexo404.
Logo o indicador verde confirma processamento, mas sozinho não comprova
publicação do arquivo. Não atribuir causalidade ao clique de abrir o popup.

O pipeline atual já consulta a fila atéCOMPLETO e espera30s após confirmação
antes de baixar. Não foi aplicado um patch sem evidência para apenas repetir
essa espera. A classificação FALHOU, encontrada antes, foi corrigida/testada/
publicada emceae3fd. Entrega exige arquivo200, parser e dados válidos.

## Continuidade real

Automação ChatGPT Acompanhar QUERY de Natal continua ativa, horária, com prompt
atualizado para distinguir recuperação manual de geração automática. Consulta
natal_recovered_watch_20261026.py confirma o ready manual. O worker continua
leituras/download com backoff dos IDs automáticos existentes. Não criar novas
filas na tarefa de observação. Avisar somente mudança relevante/intervenção nova.
Não pausar a tarefa só pelo ready manual nem concluir meta quatro cidades.

Próxima verificação da meta: geração atual de Natal pelo DOMINIUM que entregue
anexo válido e cumpra o mesmo percurso já aprovado para a recuperação manual.
Não foram gerados outros IDs pelo assistente após o usuário assumir os testes.
