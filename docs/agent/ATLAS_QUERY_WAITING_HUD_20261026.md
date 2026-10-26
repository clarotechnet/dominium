# QUERY — distinguir espera de processamento

Usuário reportou indicadorDOMINIUM EM AÇÃO contínuo após quarenta minutos.
Print14:37 mostra276935365/276935412 comattachment_transport_timeout.
Código usava fasesolving paraattachment_wait/missing/timeout, que anima
indefinidamente. Não era evidência de processamento contínuo ou de progresso.

Escolha de implementação: manter aviso persistente em fasewaiting com título
AGUARDANDO RESPOSTA e animaçõesCSSpausadas. Preserva IDs, polling, backoff,
bloqueios e exportações; searching/working/solving continuam ativos nasetapas
reais. Nenhuma geração nova. Alternativa de esconderHUD foi rejeitada porque
usuário pediu feedback persistente; falsosucesso seria incorreto.

TestesRED reproduziramsolving/working emlugar dewaiting. GREEN36testesUI; gate947Python com21ignorados eJS/Ruff/build aprovados.
Asset20261026-4 invalida cache deQUERY/motion/CSS. Commitpublicado56581179ed25854da892b9117b4bb4466466068c; Actions40371348485completed/success; trêsassets20261026-4 observados naUI.
Validação real:phasewaiting,títuloAGUARDANDO RESPOSTA eCSSanimationPlayStatepaused,
IDs preservados eCSV/XLSXbloqueados enquantoaguardamanexo.

DiagnósticoChrome: Browser.getVersion/SystemInfo respondem; abaAtlasnão
respondePage.enable/Runtime.evaluate nemevalviaBrowserTargetsession. CPU17%,
RAMlivre8GB,24GBtotal; não concluir falta deRAM/CPU. Worker segueatualizando
registros detimeout, mas não comprova entregadeanexo. Não geraroutropar.
Nenhuma alteraçãoAtlas/TOA/OS/estoque; nenhumrestartChrome/relaynestatarefa.

## Recuperação da aba e verificação final14:48

Browserprocesso respondia, targetpageAtlasnão. Uma interrupçãoPage.stopLoading
respondeu masnãorecuperouRuntime.evaluate. Após confirmar ausência de submissão
incertarecente noSQLite, foi feita UMA recargaPage.reload da abaAtlasexistente.
Chrome eperfil não reiniciados; nenhuma QUERYnova. Sondagem retornouJavaScript
responsivo epagecomplete. LeituraNetTaskreal apósrecarga confirmou276938313
complete comattachment_recognizedtrue(app4): verificação pendente do patchapp4
agora aprovada. Login nãoinferido sópela sondagem: consulta real confirmouacesso.

Worker retomouleituras e os doisIDsautomáticos voltaram de transporttimeoutpara
attachment_http_404. Bancoíntegro,mesmos27jobs/183194linhas. O404existente nãofoi
resolvido pelaUI ourecarga. Não concluir metaautomáticaNatal semarquivo eexports.
Diagnósticosprivados:atlas_single_tab_reload_current.json e
atlas_after_single_tab_reload_current.json; nenhumsegredo/URLcliente emGit.
