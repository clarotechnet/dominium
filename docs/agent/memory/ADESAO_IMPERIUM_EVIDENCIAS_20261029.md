# Integração ADESÃO × Imperium — regras e evidências (29/10/2026)

**Status:** memória técnica curada; decisões operacionais confirmadas pelo usuário e evidências históricas de conversas. **Não é prova de homologação nem autorização para reativar qualquer auto-baixa.**

**Fontes consultadas (arquivos privados, não versionar os originais):**
- Exportação WhatsApp **Jader / imperium**, 23/07–06/10/2026;
- Grupo **Integração Imperium x Technet**, 10/09–28/10/2026;
- Grupo **[Synia + Technet] Consultoria Técnica**, 30/06–14/09/2026;
- PDF `Especificacoes_requisicoes.pdf` (17 páginas) anexo ao grupo Integração: **solicitação de funcionalidades**, não catálogo de endpoints garantidamente implementados.
- Decisões do operador de 29/10/2026; acompanhamento de implementação nos issues [#25](https://github.com/clarotechnet/dominium/issues/25) e [#28](https://github.com/clarotechnet/dominium/issues/28).

## 1. Separação obrigatória por setor/bucket, não por código de baixa

- O fluxo **DESC** nasce de mensagem de contrato de técnico autorizado em grupo DESC e de **atividade oriunda de bucket ADM** confirmado no TOA (por exemplo `NTL-DMV_ADM`; Parnamirim `PWM-DMV_ADM`). Nome da O.S. e código 409 **não** definem o setor. O bucket `NTL-DMV` é de **Adesão**, não DESC.
- DESC: pesquisar contrato/atividade/IdOS exatos no TOA e Imperium; usar o código registrado pelo técnico; equipamento que entra/sai deve ser lançado **uma vez** no único IdOS escolhido para movimentação do contrato por código, **mesmo havendo várias O.S.**. As outras O.S. precisam de baixa **sem duplicar equipamentos**, após comprovar o protocolo de fechamento sem movimentação. **Não lançar miscelâneas em DESC**, inclusive `ENTREGA STREAMING` com código 409.
- **Adesão de outro setor:** fluxo independente no DOMINIUM **somente pela API oficial do Jader**; registrar TODOS os equipamentos de entrada/saída e miscelâneas efetivamente exigidos pelo TOA, com conciliação real. Se a O.S. não exigir miscelânea, **não inventar lançamentos**. Exceções operacionais explicitamente declaradas: `INST GPON - INST CABO` e O.S. de `ASSINATURA` = **somente código de baixa**, sem equipamento nem miscelânea. Conferir a classificação e o IdOS exato para não aplicar a exceção a outros serviços.
- **Estoque insuficiente na Adesão:** antes de bloquear definitivamente, **consultar retorno do material/equipamento no Imperium e complementar** itens faltantes *apenas* quando o retorno e o saldo/código/quantidade/titularidade estiverem confirmados. O termo operacional `retorno` precisa de mapeamento exato da fonte/endpoint — **não inventar transferência, devolução ou saldo**. Se não houver retorno comprovado, bloquear e sinalizar; não emitir baixa incompleta ou duplicada.

## 2. Fatos técnicos confirmados diretamente nas conversas com Imperium

1. `POST /technet/ordemservico` usa objeto `ordemservico` com `numero`, `dataagendamento`, `codigotecnico`, `codigobaixa`, `instaladosserializados`, `instaladosmiscelaneas`, `removidosserializados`. Para itens ausentes, o histórico contém exemplos com **arrays vazios `[]`**; não substituir por strings vazias.
2. **HTTP 200 = solicitação recebida / colocada na fila**, não confirmação de execução. A validação é assíncrona e o callback pode retornar erro. Só marcar O.S. baixada após confirmação no Imperium/retorno. Em timeout, 200 sem confirmação ou callback perdido, reconciliar antes de qualquer reenvio.
3. A validação de existência da O.S. confronta **número e data de agendamento**; a data correta é a importada do TOA no Imperium. Divergência pode retornar `Ordem de serviço não encontrada`. Conciliar importação/estado antes de baixa.
4. **O saldo de miscelânea é consultado no estoque do instalador indicado pelo `codigotecnico`**. O Jader esclareceu em 06/10/2026 que, naquele momento, o código deveria ser **exatamente o do estoque do técnico**; a API **não procurava por descrição**. Mesmo material com descrição equivalente e código diferente podia falhar; não substituí-lo automaticamente sem equivalência oficial/consentimento verificável.
5. Erro SQL `A subconsulta retornou mais de 1 valor` não implica automaticamente falha de login: em 21/08 o Jader identificou caso de **código de equipamento com duas unidades de negócio no mesmo estoque**. Encaminhar código, contexto e retorno do callback; não reenviar cegamente.
6. O histórico da Synia documenta **uma atividade com múltiplas O.S.**, O.S. nem sempre importadas antes da automação, diferenças de códigos do TOA versus baixa manual, erros de login de técnico duplicado e necessidade de reconciliação. Não tratar uma atividade como uma única O.S. nem assumir que todas as O.S. já existem.
7. Em 06/10, busca de equivalência por descrição ainda era **demanda pendente**. Em 14/10 houve declaração de trabalho em evolução sobre equipamentos sem saldo/código e busca por descrição. Consultar estado **atual** do backend antes de assumir entrega.

## 3. Documento de especificação: solicitado ≠ implementado

O PDF de requisitos solicita endpoints de estoque, detalhe completo da O.S., transferência, equivalência oficial `GET /technet/equipamentos/{codigo}/equivalentes`, idempotência, retorno estruturado e estado assíncrono de processamento. **Estas referências são propostas/requisitos**, não prova de que existam ou respondam em produção. Em especial, **não presumir endpoint de `retorno` de miscelânea ou equivalência oficial sem teste read-only**.

A orientação de idempotência do documento é útil ao DOMINIUM, mas validação real no protocolo efetivamente implantado é obrigatória.

## 4. Implementação e pendências, conforme a última verificação de 29/10/2026

- O **executor geral** que varria Imperium/TOA e baixou indevidamente Adesão do contrato 4323425 está **desativado**, inclusive produtivas e lote geral 106 das 23h. **Não reativar** o varredor global como substituto do bot de grupos.
- `BotDMV/src/disconnectPilotCoordinator.js`, `disconnectPilot.js`, extensão TOA e `disconnect_local_runner.py`: alterações locais para validar grupo, técnico e bucket. Conferir **estado real, implantação da extensão e reinício do bot** antes de declarar operacionais; a última sessão não reiniciou PM2.
- `adm_allocation.py`: planejador local de uma única O.S. com equipamentos para vários IdOS do mesmo código. **Fechamento sem equipamentos das O.S. restantes não implementado/homologado**: múltiplas O.S. seguem bloqueadas em execução real. Não duplicar estoque para desbloquear.
- `official_material_resolver.py`: faz conferência de saldo e pode bloquear insuficiência; **não há ainda consulta ao retorno do material com complemento automático validado**. Criar integração de leitura + plano rastreável + testes de saldo parcial, indisponibilidade, códigos divergentes e reenvio incerto. Ver issue #28.
- **Adesão por API oficial**, incluindo exceções de código-only GPON/assinatura e eventual complemento de retorno, **não está habilitada/homologada como automação**.
- Últimos testes reportados: 77 Python e 3 Node em alterações locais DESC. Não usar esses testes como prova do fluxo oficial Adesão.

## 5. Checklist para futuras implementações

1. Ler `AGENTS.md`, `docs/agent/memory/CURRENT_STATE.md`, este documento, issues #25/#28 e o código relevante.
2. Verificar sessão TOA, bucket, grupo/autor e tipo de O.S.; consultar status real Imperium; não confundir setor DESC com título do serviço.
3. Montar **plano prévia** por IdOS: código TOA, datas, técnico, serializados, miscelâneas aplicáveis, estoque exato, retorno verificado, OS dona das movimentações, demais OS sem duplicação.
4. Aplicar **somente** o transporte autorizado por setor (DESC/DataSnap; Adesão/API oficial). Evitar misturar origens.
5. Resposta 200 ou fila de integração não equivale a baixa. Exigir retorno/callback, reconciliação de estado e registro por IdOS/serial/código; não repetir writes incertos.
6. Testes read-only/dry-run, casos de Adesão com/sem itens e com retorno, grupos/buckets cruzados, múltiplas OS e timeout antes de liberar execução. Só depois, com autorização operacional, habilitar o fluxo específico.
7. **Toda alteração significativa futura:** registrar fatos testados, pendências e estado real no `CURRENT_STATE.md` e usar `scripts/agent_memory.py record` quando tiver acesso ao clone; não copiar exportações WhatsApp nem credenciais para o Git.
