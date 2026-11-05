# Integração de leitura — Equipamentos Utilizados (Imperium / DataSnap)

**Estado: CONTRATO VALIDADO OFFLINE / EXTRAÇÃO NÃO HOMOLOGADA.**
Origem: `TECHNET_DATASNAP_RELATORIO_1.0.zip`, recebido em 04/11/2026.
Não é um conector pronto, não contém captura binária de consultas nem resultados da tela.

## Formulário correto e distinção importante

O fluxo solicitado é **Consultas → Equipamentos Utilizados**, formulário
`TFrmConEquipUtilizados`, eventos `BtnConsultarClick` / `BtnExportarClick`.

- `TDtmOrdemServico.GetEquipamentosUtilizados` está na RTTI do cliente;
  isso **não** prova que seja método remoto.
- `TDtmOrdemServico.AS_GetRecords` é o método DataSnap que pode ser preparado.
- `CdsConsolidadoEquip` → `DspConsolidadoEquip`: visão consolidada.
- `CdsConsolidadoOS` → `DspConsolidadoOS`: visão por ordem.
- Parâmetros de ambas: `@RETURN_VALUE`, `@DataIni`, `@DataFim`,
  `@IdParceiro`, `@IdTipoServico`, `@IdGrupoEquipamento`.

**Não confundir** com `TDtmMovEstoque` /
`Dspsp_EquipamentosUtilizadosParceiro`. Este último aparece em outra
função do cliente e **não** substitui o relatório deste formulário.

## Compatibilidade do cliente Windows

O ZIP descreve `ClientVCL.exe` de **47.284.224 bytes** com SHA-256
`44b9e565d1158aa456e55b56a34e2edbb524f2fb2762e427059de0b430545f55`.
No DESKTOP-K7J3E1N, o arquivo `TechNETNatal\ClientVCL.exe` inspecionado
tinha **47.300.096 bytes**, hash
`958e5646d3738980c4e8599057cf699c1f055623d46da0c49208fab3053f73ac`.
Os offsets da evidência não podem ser usados como offsets da versão instalada;
o contrato de parâmetros exige revalidação dinâmica no cliente alvo.

## Entregue em código

- `integrations/serial_consult/used_equipment_report_contract.json`:
  contrato versionado e sem dados pessoais.
- `integrations/serial_consult/used_equipment_report.py`:
  valida formulário, providers, datas, pacotes **capturados** e versão do EXE;
  faz somente a preparação do método, sem `execute`.
- `scripts/probe_used_equipment_report.py`: comandos operacionais de teste.
- `tests/test_used_equipment_report_contract.py`: testes offline com fakes
  que falham caso a sonda execute consulta/baixa de dados.

Exemplos (ambiente de desenvolvimento Windows):

```powershell
python scripts/probe_used_equipment_report.py --contract
python scripts/probe_used_equipment_report.py --exe "C:\Imperium\ClientVCL.exe"
python scripts/probe_used_equipment_report.py --profile natal --probe --confirm-tcp
```

O último comando exige usuário/senha digitados no terminal. Para usar as
credenciais DPAPI já configuradas no mesmo PC/conta autorizada:
`--local-credentials`. **Somente** conectar e preparar; o resultado
`method_prepared=true` não significa que houve extração de equipamentos.

O TCP legado DataSnap **não garante TLS**. Testar apenas na rede corporativa
ou VPN; não abrir a porta publicamente, não versionar tokens, dados de clientes,
capturas ou `credentials.dat`.

## Bloqueio que impede download automático

Na investigação anterior, requisições binárias **sintetizadas** para
`DspConsolidadoEquip`, `DspConsolidadoOS` e outro provider resultaram
em timeout (25 e 90 s), apesar do sucesso de autenticação e preparação.
Isso não valida formato ou parâmetros, e não prova falta de equipamentos.

Falta obter de modo autorizado uma captura **somente do pedido de leitura**
`AS_GetRecords` real, executado pela versão instalada de `ClientVCL.exe`,
para cada provider e filtro. A evidência deve remover credenciais, sessão,
contratos, nomes, seriais e outras informações identificáveis; não disponibilizar
tráfego TCP bruto com autenticação.

Não executar SQL diretamente, não tentar `AS_Execute`, não sintetizar
`@Banco`, `@IdParceiro`, grupos ou demais parâmetros. IDs variam
entre cidades/empresas e precisam ser confirmados no cliente.

Para liberar uma implementação operacional:

1. Validar pedido binário e filtros reais de ambos os providers, com versão
   do EXE e perfil, sem credenciais/dados pessoais no repositório.
2. Executar **uma consulta controlada, somente de leitura**, com resposta
   íntegra e conferência de cabeçalho/esquema de ambos os datasets.
3. Comparar por `NumeroWO`/`NumOs`, código, serial e quantidade com um XLSX
   exportado do próprio Imperium, sem misturar movimento histórico e consulta.
4. Definir transformação completa do processo do vídeo (Atlas, Chips Atlas,
   IMPERIUM, CHIP IMPERIUM, Assinantes, Nomes) e armazenar o resultado por cidade
   e data, com download. Dois datasets Imperium sozinhos não definem as seis abas.
5. Vincular o backend local protegido ao endpoint da análise diária e ao botão,
   com timeout, progresso, cancelamento, histórico e controle de autorização.

**Até completar essas etapas, a rota atual continua buscando apenas histórico
salvo; nenhum botão deve fingir consultar ou baixar dados do Imperium.**

## Validação deste checkpoint

- Contrato e adapter: 8 testes novos aprovados.
- Testes dirigidos do catálogo diário e enriquecimento: total de 16 testes Python
  aprovados incluindo os 8 novos; 8 testes JavaScript da análise diária aprovados.
- `python scripts/generate_agent_context.py --check`: passou.
- `python scripts/quality_gate.py`: 1.022 testes Python, 22 ignorados,
  3 erros de `PermissionError [WinError 32]` ao remover `query.sqlite3`
  e `jobs.sqlite3` de diretórios temporários. **Todos os três reproduzidos**
  na branch anterior, sem este módulo. A suíte geral NÃO está aprovada.
- Nenhuma consulta DataSnap de negócio feita por este checkpoint, nenhum
  registro importado e nenhum deploy de produção.

## Evidência adicional: captura local da consulta real (04/11/2026)

Diagnóstico realizado **somente no DESKTOP-LTGB862**, onde o usuário
acessou `TFrmConEquipUtilizados` para NET/Natal em 03/11/2026.
Arquivo `.pcapng` **permanece no computador de origem**, não copiar,
versionar ou publicar: contém dados de operações e possivelmente dados pessoais.

Foi possível remontar a direção **servidor → cliente** sem lacunas
(273.557 bytes de mensagens DataSnap) e interpretar sete mensagens:
uma de preparação e respostas de dois datasets.

| Dataset | Provider correspondente ao contrato | Registros MIDAS | Campos |
| --- | --- | ---: | ---: |
| Consolidado | DspConsolidadoEquip | 89 | 5 |
| Por OS | DspConsolidadoOS | 1142 | 19 |

São **contagens reais do cabeçalho** e também **foram decodificados todos
os registros em memória** após corrigir o tamanho de BCD. A consulta
capturada produziu 7.330 bytes do consolidado e 265.679 bytes por OS
(o segundo dataset chegou dividido em cinco blocos `data`).

O campo `Qtd` é MIDAS tipo 5 / BCD, com metadados size=10, mas cada
registro usa **18 bytes** (dois bytes precisão/sinal-escala + dezesseis
bytes de dígitos BCD). Nos 1.231 registros observados a precisão foi 16
e a escala foi 2, sem nibbles inválidos. O leitor `midas_reader.py`
agora interpreta o valor como texto decimal exato, JSON-safe, evitando
perda de precisão. Referência de formato: Embarcadero Data.FmtBcd.TBcd,
https://docwiki.embarcadero.com/Libraries/Sydney/en/Data.FmtBcd.TBcd.

**Bloqueio ainda vigente:** a captura PktMon de `--comp nics` não
registrou conteúdo de aplicação da direção **cliente → servidor**
(somente ACKs), portanto **o pacote original `AS_GetRecords` enviado
pelo ClientVCL NÃO foi recuperado**. Não é correto gerar consultas
DataSnap ao vivo apenas a partir dos datasets recebidos.

Próxima etapa: capturar somente depois do login, com mecanismo que
inclua tráfego de saída, e validar os bytes enviados pelo ClientVCL
e os IDs específicos de parceiro/grupo/tipo antes de liberar qualquer
consulta automática no Dominium. Não anexar a captura bruta a PRs.

Validações nesta atualização: 25 testes dirigidos (incluindo
`tests/test_midas_bcd_used_equipment.py`) aprovados. O quality gate
completo já tinha três falhas preexistentes de testes Atlas QUERY por
bloqueio de SQLite temporário no Windows (ver diagnóstico anterior).

## 05/11/2026 — requisicoes originais recuperadas e consultas reais validadas

**Esta atualizacao substitui o bloqueio de captura da direcao cliente-servidor
descrito acima.** O fluxo de importacao do Excel e as seis abas da interface
ainda nao foram integrados ao novo adaptador.

- Foi feita captura pontual, depois do login, usando Wireshark + Npcap,
  exclusivamente na conexao DataSnap do ClientVCL NET/Natal.
  O arquivo bruto permanece no DESKTOP-LTGB862 e nao foi enviado ao
  repositorio nem ao chat.
- Tráfego cliente-servidor: 7 pacotes com conteudo, 1.620 bytes.
  Uma chamada prepare de 97 bytes para TDtmOrdemServico.AS_GetRecords,
  duas chamadas execute de 667 e 664 bytes e quatro pedidos more_blob.
- Provedores confirmados: DspConsolidadoEquip (packet 605 bytes) e
  DspConsolidadoOS (packet 602 bytes).
- Filtros observados: @IdParceiro=1, @IdTipoServico=%, @IdGrupoEquipamento=%,
  @DataIni=03/11/2026 00:00:00 e @DataFim=03/11/2026 23:59:59.999.
  Este parceiro foi validado APENAS para o perfil Natal/NET.
- Os seis parametros e o corpo do envelope foram comparados byte por byte.
  A geracao local e o codigo proposto produziram exatamente a mesma
  requisicao dos dois providers, sem transferir payloads capturados.
- SHA256 do pedido consolidado:
  b593109aad507e5f7296949a553506433af7115b92f198670f2b56168bbb680d.
- SHA256 do pedido por OS:
  31ad439e925001de6838f90ad6da2e2e180a3bb4f21869efa0e25b48df7d0a02.
- Em DESKTOP-K7J3E1N, usando credenciais locais protegidas e metodo
  AS_GetRecords somente de leitura, a consulta de 03/11/2026 recuperou
  89 linhas consolidadas (schema aprovado) e 1.141 linhas por OS
  (schema aprovado). A captura anterior continha 1.142 linhas por OS.
  A diferenca de uma linha pode ser atualizacao do servidor ou escopo
  de permissao e ainda nao foi conciliada.
- O adaptador isolado em integrations/serial_consult/used_equipment_live_datasnap.py
  oferece build_query (offline) e fetch_read_only (consulta explicita).
  Nao existe acionamento automatico, endpoint publico, escrita de estoque
  ou publicacao das seis abas a partir destes dados.
- O ImperiumV4.exe recebido por upload e presente nos Downloads do LTGB862
  possui 12.335.104 bytes, SHA256
  d0a701970b0d0b1cf177435398201167b0775fee7366fe71af963fc3a953db59.
  Ele nao e o ClientVCL.exe que executa o relatorio; foi examinado
  estaticamente e nao executado pelo diagnostico.

### Condicoes para a fase de interface

Conferir identificadores de parceiros por cidade, controles de acesso e
isolamento por unidade; implementar geracao por periodo usando os dois
datasets Imperium, conciliar com Atlas conforme o video, salvar resultado,
expor historico/download e progressos reais. O botao Consultar periodo
atual continua sendo apenas uma busca do historico, nao uma consulta DataSnap.
