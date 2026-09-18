# Correção da ponte TOA: miscelâneas ausentes no Dominium Primário

## Objetivo

Corrigir a consulta **somente leitura** do TOA para que o Dominium Primário receba e exiba as miscelâneas capturadas na atividade antes da tratativa humana de baixa. Não alterar a baixa automática, não alterar o Imperium e não abrir/navegar no TOA visualmente.

## Pacotes comparados

- Bridge antigo em uso pelo Primário: `integrations/toa_cloud_bridge/extension-central-2.6.3`
- Bridge novo entregue: `C:\Users\User\Downloads\toa (1)\toa\toa-bridge.zip`
- Primário: `C:\Users\Public\Documents\Dominium_Technet\DOMINIUM_APP`

## O que mudou no bridge novo

O bridge novo é maior e acrescenta principalmente:

1. suporte à ponte Cloudflare/D1 e configuração remota;
2. captura de localização e o novo `location-network-hook.js`;
3. ajustes de fila, diagnóstico e testes da ponte cloud.

Ele **não** alterou a regra principal de inventário/miscelâneas: `toa-inventory-core.js` é idêntico no bridge antigo e no novo. Portanto, apenas atualizar a extensão não resolve uma miscelânea que some no caminho.

## Fluxo correto que deve ser preservado

```text
TOA delta.Inventory
  -> toa-inventory-core.js classifica item material (código 192)
  -> content-main.js monta snapshot operacional
  -> Cloudflare Worker sanitiza e persiste o snapshot
  -> toa_cloud_client.py retorna o snapshot
  -> app.py adapta ao workspace de baixa
  -> UI apresenta a colagem/miscelâneas para revisão humana
```

O Worker já possui `sanitizeOperationalSnapshot()` e aceita `snapshot.materials`. O Primário também já lê `snapshot.materials` em `_cloud_snapshot_to_live_lookup()`. O defeito precisa ser localizado e corrigido sem suposições, registrando em qual etapa a quantidade virou zero.

## Causa técnica provável e ponto crítico confirmado

Há dois formatos de payload no bridge:

### 1. Consulta operacional/produtiva

`buildOperationalSnapshot()` deve enviar:

```js
materials: equipment(ctx?.materials || capture?.materials)
```

Esse é o formato que o Dominium Primário precisa usar para instalação, troca, adesão e tratativa manual produtiva.

### 2. Consulta de desconexão

`buildDisconnectSnapshot()` envia deliberadamente:

```js
materials: [],
materials_applicable: false,
captured_materials_for_audit: capturedMaterials,
materials_complete: true,
```

Ou seja: as miscelâneas podem ter sido capturadas, mas ficam apenas em `captured_materials_for_audit`; `materials` vem vazio por regra de desconexão. O sanitizador atual também não preserva `captured_materials_for_audit`, `materials_applicable` nem `materials_complete` no contrato cloud v1.

Além disso, o uso atual de `source.materials ?? source.materialsRaw` é inseguro: um array vazio em `source.materials` vence a expressão e impede o fallback para uma lista preenchida. Não usar `??` para decidir entre listas vazias e listas com conteúdo.

## Trabalho solicitado

### A. Criar contrato explícito de inventário no snapshot cloud

No Worker, em `integrations/toa_cloud_bridge/src/core.js`, evoluir o snapshot sem remover compatibilidade:

```js
materials: [...],
captured_materials_for_audit: [...],
materials_applicable: true | false,
materials_complete: true | false,
inventory_diagnostics: {
  inventory_count: 0,
  materials_count: 0,
  captured_materials_count: 0,
  source: "toa-extension-direct"
}
```

Regras:

- Nunca transformar uma lista existente em `[]` silenciosamente.
- Para atividade produtiva, `materials` é a lista operacional.
- Para desconexão, manter `materials: []` e também preservar `captured_materials_for_audit`; essa lista é auditoria e **não pode ser enviada à baixa produtiva**.
- Se houver `materialsRaw`, usar como fallback apenas se a lista operacional estiver ausente ou vazia e a atividade for produtiva. Não misturar o fallback de auditoria de desconexão com materiais operacionais.
- Preservar por item, quando existentes: `inventory_id`, `kind`, `pool`, `action_code`, `material_code`, `description`, `serial`, `quantity`/`used_quantity`, `available_stock`, `point`.

Implementar helper explícito, por exemplo `selectOperationalMaterials(source)`, em vez de encadear `??` com arrays.

### B. Corrigir o bridge de origem antes do Worker

No `content-main.js` da nova extensão:

1. garantir que a consulta cloud de atividade produtiva sempre use `buildOperationalSnapshot()`;
2. garantir que `ctx.materials`, `capture.materials` e `materialsRaw` sejam reconciliados sem perder itens válidos;
3. adicionar no snapshot os quatro diagnósticos de contagem;
4. não chamar `buildDisconnectSnapshot()` para uma consulta produtiva só porque o contrato contém uma tarefa de desconexão;
5. manter o comportamento de desconexão como auditável, mas sem fingir que as miscelâneas operacionais existem.

Não usar clique visual, busca global ou abertura de OS na tela para "resolver" a captura.

### C. Adaptar o Dominium Primário

No `app.py`, dentro de `_cloud_snapshot_to_live_lookup()`:

1. manter `activity["materials"]` com a lista operacional do snapshot;
2. propagar, separadamente, `captured_materials_for_audit`, `materials_applicable`, `materials_complete` e `inventory_diagnostics`;
3. quando `materials_applicable` for `false`, exibir no editor: **"Miscelâneas não aplicáveis à baixa de desconexão; captura mantida apenas para auditoria."**;
4. quando `materials_applicable` for `true` e `materials_complete` for `false`, bloquear apenas o envio da baixa e exibir um erro claro de captura incompleta; não apresentar uma lista vazia como se o TOA não tivesse materiais;
5. para material aplicável, alimentar a mesma rotina já usada pela **Colagem TOA**, sem mudar a validação de estoque/RETORNO nem a confirmação humana.

O editor deve mostrar uma linha de diagnóstico não sensível, por exemplo:

```text
TOA: inventário 12 | miscelâneas operacionais 7 | auditoria 0 | captura completa
```

Isso permite descobrir imediatamente se a perda ocorreu no TOA, na extensão, no Worker ou no Primário.

### D. Testes obrigatórios

Adicionar testes automatizados, sem sessão real do TOA e sem tocar no Imperium:

1. **Produtiva com miscelâneas**: `capture.materials` com dois itens deve chegar ao retorno de `/api/toa-live/lookup` com mesmos códigos e quantidades.
2. **Fallback produtivo**: `materials: []` e `materialsRaw` preenchido deve resultar em materiais operacionais preenchidos, quando `materials_applicable !== false`.
3. **Desconexão**: `materials: []`, `captured_materials_for_audit` preenchido e `materials_applicable: false` devem permanecer separados; a lista de auditoria nunca pode ser usada em payload de baixa.
4. **Sem inventário**: diagnosticar contagem zero de forma explícita, sem inventar material.
5. **Sanitização Cloudflare**: confirmar que o Worker não remove campos de material nem os campos de diagnóstico.

Rodar os testes Node do Worker/extensão e a suíte Python pertinente ao Primário. Relatar os comandos e resultados.

## Critérios de aceite

Para uma atividade produtiva que possua miscelâneas no TOA:

1. a resposta da extensão registra `materials_count > 0`;
2. o Worker devolve a mesma quantidade em `result.materials`;
3. `/api/toa-live/lookup` devolve a mesma lista;
4. o card "Miscelâneas / Colagem TOA" abre pré-preenchido;
5. o operador ainda revisa, ajusta ou remove itens antes de confirmar;
6. nenhuma solicitação de baixa é enviada durante essa validação.

## Segurança e limites

- Não registrar cookies, CSRF, credenciais, endereço, telefone, CPF ou dados de cliente.
- Não abrir Chrome/TOA e não iniciar sessões durante os testes.
- Não mudar endpoints do Imperium nem reexecutar baixas.
- O objetivo desta correção é apenas leitura, transmissão íntegra do inventário e revisão humana.
