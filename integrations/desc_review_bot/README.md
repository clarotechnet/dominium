# DESC — vínculo WhatsApp / Imperium

Aplicar os módulos em `BotDMV/src/descReview` e adicionar a `createDescReview` em index.js:

```js
verifyImperium: require('./src/descReview/orderClient').createOrderVerifier({connectionFile:path.join(DATA_DIR,'desc_review','order-check-connection.json')}),
```

A conexão privada fica no runtime, fora do Git. Configurar origin HTTPS do relay e token de autenticação no JSON indicado. Reiniciar Bot com `pm2 restart Bot`.

O relay Windows importa imperium_api do runtime configurado por DOMINIUM_IMPERIUM_RUNTIME_ROOT e consulta somente OS em campo / detalhe / recurso. Nenhuma execução de baixa é habilitada.

430 usa Atlas canônico com contrato coincidente e vínculo WhatsApp → recurso Imperium. Consulta da OS selecionada precisa ter contrato/cidade/OS/recurso exatos e menos de cinco minutos. Conclusão, login do técnico e declaração de materiais completos no TOA não são exigidos para essa retirada confirmada. Entradas e materiais presentes continuam bloqueados.409 preserva movimentos, conclusão e materiais; códigos pedidos divergentes bloqueiam. OS aberta sem seleção impede propor criação duplicada. Aprovação continua simulada.

## Consulta manual de serial

A foto aceita zoom por roda, clique e botões. A consulta Atlas é somente leitura. Aplicar exige confirmação explícita, contrato compatível, foto e revisão atuais; o resultado fica registrado na evidência daquela foto. O histórico permanece somente leitura.

Para atualizar o runtime existente, copie esta pasta de integração e execute o instalador com o Python do servidor. Ele valida os pontos de instalação e a sintaxe, preserva histórico e opções do store, cria backup e altera somente o helper, as rotas/capacidade do servidor DESC e a allowlist do proxy privado.

```powershell
& 'C:\DominiumRuntime\Python312\python.exe' .\install_manual_serial.py
& 'C:\DominiumRuntime\Python312\python.exe' .\install_manual_serial.py --apply
```

Depois, reinicie o relay Windows pelo procedimento existente e o Bot com `pm2 restart Bot` no ambiente do Bot. O site habilita a consulta somente quando o Bot anuncia `manual_serial`; a baixa continua em modo de teste. As raízes podem ser indicadas por `--bot-root` e `--relay-root`.
