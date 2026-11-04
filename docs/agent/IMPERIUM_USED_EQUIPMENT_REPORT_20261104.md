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
