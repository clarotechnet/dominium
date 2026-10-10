# Leitor existente do Atlas na captura DESC

Fonte instalada no BotDMV em 10/10/2026, com backup antes da alteração. O código deste diretório depende de `core.js` e `serialCandidates.js` da revisão DESC existente; não é uma segunda aplicação.

- `photoLookup.js` substitui apenas `src/descReview/photoLookup.js` no Bot.
- Adicionar `primaryLookup: buffer => consultarAtlasPorImagemBuffer(buffer)` à criação de `descPhotoLookup` em `index.js`.
- `tests/primary-reader.test.js` deve ficar em `src/descReview/tests/` no Bot. Confirmar os resultados locais e a sintaxe de index.js antes de reiniciar.
- O leitor que já atende o grupo 120363411539759480@g.us é consultado primeiro. OCR é alternativa quando a foto não fornece identificadores. Contrato, tipo, serial canônico e pertencimento à foto continuam obrigatórios.
- Não mudar os grupos de consulta nem habilitar execução real no serviço de revisão. O executor de teste rejeita operações reais explicitamente.

A instância em execução precisa de `pm2 restart Bot` para carregar o novo módulo. O reinício WSL não foi executado pelo acesso remoto, que bloqueia esse comando.
