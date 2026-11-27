(() => {
  "use strict";

  const key = value => String(value ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .trim().replace(/\s+/g, " ").toUpperCase();
  const distinct = values => [...new Set(values.filter(Boolean))];
  const number = new Intl.NumberFormat("pt-BR", {maximumFractionDigits: 6});
  const fmt = value => value == null ? "—" : number.format(value);
  const day = value => value ? value.split("-").reverse().join("/") : "—";
  const cities = {natal:"Natal / Parnamirim", fortaleza:"Fortaleza", mossoro:"Mossoró", recife:"Recife"};
  const liveCities = ["natal", "mossoro", "recife"];
  const dateFormat = new Intl.DateTimeFormat("sv-SE", {timeZone:"America/Sao_Paulo",dateStyle:"short"});
  const dateTimeFormat = new Intl.DateTimeFormat("pt-BR", {
    timeZone:"America/Sao_Paulo",dateStyle:"short",timeStyle:"short"
  });
  const marks = {above:"Acima do limite",within:"Dentro do limite",review:"Revisar quantidade",
    no_rule:"Sem regra",allowed:"Permitido",different:"Fora da regra"};
  const osCount = rows => new Set(rows.map(row => row.os)).size;
  const pageSize = 20;

  function stats(data) {
    const usage = data?.items || [];
    const quantityChecked = usage.filter(item => ["above", "within"].includes(item.quantityCheck));
    const codeChecked = usage.filter(item => item.rows.some(row => row.codeCheck !== "no_rule"));
    return {
      usage: data?.usage ? osCount(usage) : null,
      excess: quantityChecked.length ? osCount(quantityChecked.filter(item => item.quantityCheck === "above")) : null,
      quantityChecked: osCount(quantityChecked),
      different: codeChecked.length ? osCount(codeChecked.filter(item => item.rows.some(row => row.codeCheck === "different"))) : null,
      codeChecked: osCount(codeChecked),
      missing: data?.missingReports.length ? osCount(data.missing) : null
    };
  }

  function recordsFor(data, mode) {
    if (mode === "missing") return (data?.missing || []).map(row => ({os:row.os, missing:true, rows:[row]}));
    const items = data?.items || [];
    if (mode === "above") return items.filter(item => item.quantityCheck === "above");
    if (mode === "different") return items.filter(item => item.rows.some(row => row.codeCheck === "different"))
      .map(item => ({...item, rows:item.rows.filter(row => row.codeCheck === "different")}));
    if (mode === "review") return items.filter(item => ["no_rule", "review"].includes(item.quantityCheck)
      || item.rows.some(row => row.codeCheck === "no_rule"));
    return items;
  }

  function people(item, field, mode) {
    if (field === "material") return item.code ? [[item.code, [item.code, item.material].filter(Boolean).join(" · ")]] : [];
    const labels = new Map(item.rows.filter(row => row[field]).map(row => [key(row[field]), row[field]]));
    if (mode === "above" && (labels.size > 1 || item.rows.some(row => !row[field]))) return [];
    return [...labels];
  }

  function ranking(items, field, mode) {
    const counts = new Map();
    for (const item of items) {
      for (const [id, label] of people(item, field, mode)) {
        if (!counts.has(id)) counts.set(id, {id, label, orders:new Set()});
        counts.get(id).orders.add(item.os);
      }
    }
    return [...counts.values()].map(({id, label, orders}) => ({id,label,count:orders.size}))
      .sort((a,b) => b.count - a.count || a.label.localeCompare(b.label, "pt-BR"));
  }

  function ordersByDay(rows, parseDate, city, start, end) {
    const aliases = {
      os:["NUM O S","NUM OS","NUMERO DA OS","NUMERO OS","O S","OS"],
      date:["DATA AGEND","DATA AGENDADA","DATA AGENDAMENTO","DATA DE AGENDAMENTO","DATA DE EXECUCAO DO SERVICO"],
      contract:["CONTRATO"], controller:["CONTROLADOR"],
      technician:["TECNICO","INSTALADOR","EQUIPE"], city:["CIDADE","FILIAL","PRACA"],
      service:["COD SERV","COD SERVICO","CODIGO SERVICO","CODIGO DO SERVICO","SERVICO","TIPO DE SERVICO"]
    };
    const headerKey = value => key(value).replace(/[.\-_]+/g, " ").trim().replace(/\s+/g, " ");
    const headers = rows.findIndex(row => {
      const labels = row.map(headerKey);
      return labels.some(label => aliases.os.includes(label)) && labels.some(label => aliases.date.includes(label));
    });
    if (headers < 0) throw new Error("A aba precisa conter o número da OS e uma coluna de data.");
    const labels = rows[headers].map(headerKey);
    const dateCandidates = ["DATA DE EXECUCAO DO SERVICO", ...aliases.date.slice(0, 4)];
    const dateLabel = dateCandidates.find(label => labels.includes(label));
    const dateBasis = dateLabel === "DATA DE EXECUCAO DO SERVICO" ? "execution" : "scheduled";
    const column = name => aliases[name].map(label => labels.indexOf(label)).find(index => index >= 0) ?? -1;
    const dateColumn = labels.indexOf(dateLabel);
    const groups = new Map();
    const selectedCities = city === "natal" ? ["NATAL","PARNAMIRIM","NATAL / PARNAMIRIM","NATAL/PARNAMIRIM"] :
      [key(city),key(cities[city])];
    for (let index = headers + 1; index < rows.length; index++) {
      const row = rows[index];
      const val = name => row[column(name)];
      if (row.every(cell => cell == null || String(cell).trim() === "")) continue;
      const osCell = val("os");
      const os = String(osCell ?? "").trim();
      const date = parseDate(row[dateColumn]);
      if (!date || !/^[A-Za-z0-9_-]{1,40}$/.test(os) || (typeof osCell === "number" && !Number.isSafeInteger(osCell))) {
        throw new Error("Planilha com data ou OS inválida. Confira os dados da aba antes de importar.");
      }
      if (val("city") && !selectedCities.includes(key(val("city")))) {
        throw new Error("A planilha contém uma praça diferente da selecionada.");
      }
      if (date < start || date > end) continue;
      if (!groups.has(date)) groups.set(date, []);
      const fields = Object.fromEntries(["contract", "service", "technician", "controller"].map(field =>
        [field, String(val(field) ?? "").trim()]));
      groups.get(date).push({os, ...fields});
    }
    if (rows.length === headers + 1 && start === end) groups.set(start, []);
    return {groups, dateBasis};
  }

  function spreadsheetDay(value, parser) {
    if (typeof value === "number") {
      const parsed = parser(value);
      if (!parsed) return "";
      value = [parsed.y, parsed.m, parsed.d].map((part,index) => String(part).padStart(index === 0 ? 4 : 2,"0")).join("-");
    }
    const text = String(value ?? "").trim();
    const brazilian = /^(\d{2})[/.\-](\d{2})[/.\-](\d{4})(?:\s+\d{2}:\d{2}(?::\d{2})?)?$/.exec(text);
    const iso = brazilian ? [brazilian[3],brazilian[2],brazilian[1]].join("-") : text;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) return "";
    const time = new Date(iso+"T12:00:00Z");
    return Number.isFinite(time.getTime()) && time.toISOString().slice(0,10) === iso ? iso : "";
  }

  if (typeof module === "object" && module.exports) {
    module.exports = {stats, recordsFor, ranking, ordersByDay, spreadsheetDay};
    return;
  }

  const el = id => document.getElementById(id);
  const workspace = el("miscWorkspace");
  if (!workspace) return;
  const scope = () => ({
    city:state.allCities ? "" : state.profile,
    start:el("miscStart").value,
    end:el("miscEnd").value
  });
  const active = () => state.activeModule === "stock" && !workspace.hidden &&
    el("stockReportsTab").getAttribute("aria-selected") === "true";
  const canWrite = () => ["admin","controller"].includes(state.authUser?.role);
  const root = "/api/stock/analyses/misc";
  const live = "/api/stock/analyses/imperium/live";
  const query = ({city,start,end}) => "?city="+city+"&start="+start+"&end="+end;
  const sourceNote = "Período do Imperium pela baixa da OS. Cada lançamento mostra a data de baixa do material quando informada.";
  const dates = {scheduled:"data agendada",execution:"data de execução do serviço"};
  let epoch = 0, busy = false, syncing = false, saving = false, data = null, loadedKey = "";
  let page = 1, person = "", preview = null, xlsxPromise = null;
  let ruleService = "", ruleRevision = 0;

  function node(tag, value) {
    const result = document.createElement(tag);
    if (value != null) result.textContent = value;
    return result;
  }

  function option(value, label) {
    const result = node("option", label);
    result.value = value;
    return result;
  }

  function message(text, error = false, id = "miscStatus") {
    el(id).textContent = text;
    el(id).classList.toggle("quality-error", error);
  }

  function controls() {
    const current = scope();
    const allowed = Boolean(cities[current.city]);
    const edit = allowed && canWrite();
    const ready = Boolean(data && loadedKey === query(current));
    el("miscCity").textContent = allowed ? cities[current.city] : "Selecione uma praça no topo para ver os dados.";
    el("miscLoad").disabled = !allowed || busy || syncing || saving;
    el("miscHistory").disabled = el("miscLoad").disabled || !el("miscHistory").value;
    el("miscConsult").disabled = !edit || !liveCities.includes(current.city) || busy || syncing || saving;
    el("miscConsult").title = allowed && !liveCities.includes(current.city) ? "Consulta DataSnap ainda não homologada nesta praça." : "";
    el("miscRuleEditor").hidden = !edit || !ready;
    el("miscImporter").hidden = !edit || !ready;
    el("miscSaveRule").disabled = !ready || busy || syncing || saving;
    el("miscClearRule").disabled = el("miscSaveRule").disabled || !ruleRevision || !data?.rules
      .find(rule => key(rule.service) === ruleService && rule.codes.length);
    el("miscSaveMissing").disabled = !ready || !preview || !el("miscImportDay").value || busy || syncing || saving;
  }

  function baseStatus() {
    if (!scope().city) return "Escolha a praça para carregar as baixas.";
    if (!data?.usage) return "Nenhuma consulta do Imperium salva para este período.";
    return sourceNote+(data.untreated ? " "+fmt(data.untreated)+" linhas sem OS ou código válido ficaram pendentes." : "");
  }

  function renderMetrics() {
    const count = stats(data);
    for (const [id,value] of [["miscUsageCount",count.usage],["miscExcessCount",count.excess],
      ["miscCodeCount",count.different],["miscMissingCount",count.missing]]) el(id).textContent = fmt(value);
    el("miscLimitNote").textContent = count.quantityChecked ?
      fmt(count.quantityChecked)+" OS com quantidade conferida" : "Aguardando baixas com limite aplicável";
    el("miscCodeNote").textContent = count.codeChecked ?
      fmt(count.codeChecked)+" OS com código conferido" : "Aguardando baixas com regra de serviço";
    el("miscCoverage").textContent = data ?
      data.missingReports.length+" de "+data.periodDays+" dias com relatório" : "Aguardando relatório";
  }

  function drawTable(rows, missing) {
    const table = el("miscTable");
    const labels = missing ? ["OS","Data da planilha","Contrato","Técnico","Controlador","Serviço"] :
      ["OS","Material","Quantidade","Limite","Conferência","Lançamentos"];
    const header = node("thead");
    const headerRow = node("tr");
    for (const label of labels) {
      const th = node("th", label);
      th.scope = "col";
      headerRow.append(th);
    }
    header.append(headerRow);
    const body = node("tbody");
    const allowed = new Map((data?.rules || []).map(rule => [key(rule.service),rule.codes]));
    for (const item of rows) {
      const tr = node("tr");
      const first = item.rows[0];
      const codes = distinct(item.rows.map(row => marks[row.codeCheck]));
      const values = missing ? [item.os,day(first.day)+" · "+(dates[first.dateBasis] || "data informada"),
        first.contract,first.technician,first.controller,first.service] :
        [item.os,[item.code,item.material].filter(Boolean).join(" · "),
          [fmt(item.quantity),item.unit].filter(Boolean).join(" "),item.limit,
          marks[item.quantityCheck]+" · Código: "+codes.join(", ")];
      for (const value of values) tr.append(node("td",value || "—"));
      if (!missing) {
        const detail = node("details");
        detail.append(node("summary",item.rows.length+" lançamento(s)"));
        const list = node("ul");
        for (const row of item.rows) {
          const posted = row.postedAt ? dateTimeFormat.format(new Date(row.postedAt)) : "—";
          const parts = [row.technician, row.controller && "Controlador "+row.controller, row.service,
            row.contract && "Contrato "+row.contract, fmt(row.quantity)+(row.unit ? " "+row.unit : ""),
            "Baixa da OS "+day(row.closedDay), "Baixa do material "+posted];
          if (row.codeCheck === "different") parts.push("Permitidos: "+(allowed.get(key(row.service)) || []).join(", "));
          list.append(node("li",parts.filter(Boolean).join(" · ")));
        }
        detail.append(list);
        const cell = node("td");
        cell.append(detail);
        tr.append(cell);
      }
      body.append(tr);
    }
    table.replaceChildren(header,body);
  }

  function drawResults() {
    const mode = el("miscMode").value;
    const field = el("miscRankBy").value;
    const search = key(el("miscSearch").value);
    const records = recordsFor(data,mode).filter(item => !search ||
      key([item.os,item.code,item.material,...item.rows.flatMap(row =>
        [row.contract,row.technician,row.controller,row.service])].filter(Boolean).join(" ")).includes(search));
    const top = ranking(records,field,mode);
    if (person && !top.some(item => item.id === person)) person = "";
    const filtered = person ? records.filter(item => people(item,field,mode).some(([id]) => id === person)) : records;
    const unassigned = osCount(records.filter(item => !people(item,field,mode).length));
    el("miscRankNote").textContent = records.length ?
      "Por OS distintas"+(unassigned ? " · "+fmt(unassigned)+" OS sem atribuição neste ranking" : "") : "Sem ocorrências para classificar.";
    const entries = top.slice(0,10);
    const selected = top.find(item => item.id === person);
    if (selected && !entries.includes(selected)) entries.push(selected);
    el("miscRanking").replaceChildren(...entries.map(item => {
      const li = node("li");
      const button = node("button");
      button.type = "button";
      button.setAttribute("aria-pressed",String(person === item.id));
      button.append(node("span",item.label),node("strong",fmt(item.count)));
      button.addEventListener("click",() => {
        person = person === item.id ? "" : item.id;
        page = 1;
        drawResults();
        const pressed = Array.from(el("miscRanking").querySelectorAll("button")).find(entry =>
          entry.firstElementChild.textContent === item.label);
        pressed?.focus();
      });
      li.append(button);
      return li;
    }));
    const pages = Math.max(1, Math.ceil(filtered.length/pageSize));
    page = Math.min(page,pages);
    drawTable(filtered.slice((page-1)*pageSize,page*pageSize),mode === "missing");
    const empty = mode === "missing" && !data?.missingReports.length ? "Aguardando relatório de OS sem miscelâneas." :
      mode !== "missing" && !data?.usage ? "Aguardando consulta do Imperium." : "Nenhum registro neste filtro.";
    el("miscPageInfo").textContent = filtered.length ?
      fmt(osCount(filtered))+" OS · Página "+page+" de "+pages : empty;
    el("miscPrev").disabled = page <= 1;
    el("miscNext").disabled = page >= pages;
  }

  function renderRule() {
    const entry = data?.rules.find(rule => key(rule.service) === key(el("miscService").value));
    ruleService = key(el("miscService").value);
    ruleRevision = entry?.revision ?? 0;
    el("miscCodes").value = entry?.codes.join("\n") ?? "";
    controls();
  }

  function render() {
    renderMetrics();
    drawResults();
    const services = distinct([...(data?.rules || []).map(rule => rule.service),
      ...(data?.items || []).flatMap(item => item.rows.map(row => row.service))]).sort((a,b) => a.localeCompare(b,"pt-BR"));
    el("miscServiceList").replaceChildren(...services.map(service => option(service,service)));
    controls();
  }

  function resetImport() {
    preview = null;
    el("miscFile").value = "";
    el("miscImportDay").replaceChildren();
    message("", false, "miscImportNote");
  }

  function invalidate() {
    epoch++;
    busy = false;
    loadedKey = "";
    data = null;
    page = 1;
    person = "";
    el("miscHistory").replaceChildren(option("","Nenhuma consulta carregada"));
    el("miscService").value = "";
    renderRule();
    resetImport();
    message("");
    render();
  }

  function valid(current) {
    if (!cities[current.city]) { message("Selecione uma praça no topo."); return false; }
    const days = (Date.parse(current.end)-Date.parse(current.start))/86400000 + 1;
    if (!Number.isFinite(days) || days < 1 || days > 31 || current.end > el("miscEnd").max) {
      message("Informe um período válido de até 31 dias, encerrado até hoje.",true);
      return false;
    }
    return true;
  }

  async function payload(url, body, timeoutMs = 110000) {
    const options = {timeoutMs};
    if (body) Object.assign(options, {
      method:"POST", headers:{"content-type":"application/json"}, body:JSON.stringify(body)
    });
    const result = await request(url,options);
    if (!result?.ok) throw new Error(result?.error || "Resposta indisponível");
    return result;
  }

  async function load({withHistory = true, preferred = ""} = {}) {
    const current = scope();
    if (!active() || !valid(current)) return;
    const id = ++epoch;
    const params = query(current);
    const hasCurrent = loadedKey === params;
    const selectedId = preferred || el("miscHistory").value;
    busy = true;
    controls();
    message("Carregando dados do período…");
    try {
      let run = selectedId;
      let historyError = "";
      if (withHistory) {
        let history = [];
        try {
          history = (await payload(live+params, null, 30000)).history || [];
        } catch (error) {
          historyError = error.message;
        }
        if (id !== epoch) return;
        run = history.find(item => item.id === selectedId)?.id || history[0]?.id || "";
        el("miscHistory").replaceChildren(...(history.length ? history.map(item => {
          const stamp = item.checked_at || item.created_at;
          return option(item.id,stamp ? dateTimeFormat.format(new Date(stamp)) : item.id);
        }) : [option("","Nenhuma consulta salva")]));
        el("miscHistory").value = run;
      }
      const next = await payload(root+params+(run ? "&run="+run : ""));
      if (id !== epoch) return;
      data = next;
      loadedKey = params;
      page = 1;
      if (!hasCurrent && !next.usage && next.missingReports.length) el("miscMode").value = "missing";
      renderRule();
      importNote();
      render();
      message(historyError ? "Histórico Imperium indisponível. "+historyError : baseStatus(),Boolean(historyError));
      return true;
    } catch (error) {
      if (id === epoch) {
        data = null;
        loadedKey = "";
        render();
        message(error.message,true);
      }
    } finally {
      if (id === epoch) {
        busy = false;
        controls();
      }
    }
  }

  async function consult() {
    const current = scope();
    if (syncing || !valid(current) || !liveCities.includes(current.city) || !canWrite()) return;
    const id = epoch;
    syncing = true;
    controls();
    message("Consultando o Imperium e salvando a consulta…");
    try {
      const result = await payload(live,current,120000);
      if (id === epoch) await load({preferred:result.selected?.id});
    } catch (error) {
      if (id === epoch) message(error.message,true);
    } finally {
      syncing = false;
      controls();
    }
  }

  async function saveRule(clear) {
    if (!canWrite() || saving || loadedKey !== query(scope())) return;
    const service = el("miscService").value.trim();
    const codes = clear ? [] : distinct(el("miscCodes").value.split(/[\s,;]+/).filter(Boolean));
    if (!service || (!clear && !codes.length)) {
      message("Informe o serviço e os códigos permitidos.",true);
      return;
    }
    const id = epoch;
    saving = true;
    controls();
    try {
      await payload(root+"/rules",{city:scope().city,service,codes,revision:ruleRevision},30000);
      if (id === epoch && await load({withHistory:false})) message("Regra "+(clear ? "removida." : "salva."));
    } catch (error) {
      if (id === epoch) message(error.message,true);
    } finally {
      saving = false;
      controls();
    }
  }

  function spreadsheetLibrary() {
    if (globalThis.XLSX) return Promise.resolve(globalThis.XLSX);
    if (!xlsxPromise) xlsxPromise = new Promise((resolve,reject) => {
      const script = node("script");
      script.src = "/vendor/xlsx.full.min.js?v=20261123-2";
      script.onload = () => globalThis.XLSX ? resolve(globalThis.XLSX) : reject(new Error("Leitor XLSX indisponível."));
      script.onerror = () => reject(new Error("Leitor XLSX indisponível."));
      document.head.append(script);
    }).catch(error => {
      xlsxPromise = null;
      throw error;
    });
    return xlsxPromise;
  }

  function importNote() {
    if (!preview) return;
    const selected = el("miscImportDay").value;
    const records = preview.groups.get(selected);
    const existing = data?.missingReports.find(report => report.day === selected);
    message(records ?
      fmt(osCount(records))+" OS em "+day(selected)+" pela "+dates[preview.dateBasis]+
        (existing ? " · Versão atual "+existing.version+". Salvar atualiza a versão ativa." : "") :
      "O relatório não contém datas no período selecionado.",false,"miscImportNote");
  }

  async function parseFile() {
    const input = el("miscFile");
    const file = input.files?.[0];
    el("miscImportDay").replaceChildren();
    preview = null;
    controls();
    if (!file) return;
    const current = scope();
    const currentKey = query(current);
    try {
      if (!/\.xlsx$/i.test(file.name) || file.size > 10*1024*1024) throw new Error("Selecione um XLSX de até 10 MB.");
      message("Lendo XLSX…",false,"miscImportNote");
      const [xlsx,buffer] = await Promise.all([spreadsheetLibrary(),file.arrayBuffer()]);
      if (currentKey !== query(scope()) || input.files?.[0] !== file) return;
      const book = xlsx.read(buffer,{type:"array"});
      const sheet = book.SheetNames.find(name => ["CONTRATOS SEM MISCELANEAS","OS SEM MISCELANEAS"].includes(key(name)));
      if (!sheet) throw new Error("Aba Contratos Sem Miscelâneas não encontrada.");
      const rows = xlsx.utils.sheet_to_json(book.Sheets[sheet],{header:1,raw:true,defval:null,blankrows:false});
      const parseDate = value => spreadsheetDay(value,serial => xlsx.SSF.parse_date_code(serial,
        {date1904:Boolean(book.Workbook?.WBProps?.date1904)}));
      const parsed = ordersByDay(rows,parseDate,current.city,current.start,current.end);
      preview = {filename:file.name, ...parsed};
      el("miscImportDay").replaceChildren(...[...parsed.groups.keys()].sort().map(date => option(date,day(date))));
      importNote();
    } catch (error) {
      if (currentKey === query(scope()) && input.files?.[0] === file) message(error.message,true,"miscImportNote");
    }
    controls();
  }

  async function saveMissing() {
    const selected = el("miscImportDay").value;
    const records = preview?.groups.get(selected);
    if (!records || !canWrite() || saving || loadedKey !== query(scope())) return;
    const version = data.missingReports.find(report => report.day === selected)?.version ?? 0;
    const id = epoch;
    saving = true;
    controls();
    try {
      const result = await payload(root+"/missing",{city:scope().city,day:selected,filename:preview.filename,
        dateBasis:preview.dateBasis,records,version},30000);
      if (id === epoch && await load({withHistory:false})) {
        preview.groups.delete(selected);
        if (preview.groups.size) {
          el("miscImportDay").replaceChildren(...[...preview.groups.keys()].sort().map(date => option(date,day(date))));
          importNote();
        } else resetImport();
        el("miscMode").value = "missing";
        page = 1;
        person = "";
        render();
        message(result.reused ? "Este relatório já estava salvo." : "Relatório salvo para "+day(selected)+".");
      }
    } catch (error) {
      if (id === epoch) message(error.message,true,"miscImportNote");
    } finally {
      saving = false;
      controls();
    }
  }

  function open() {
    if (!active()) return;
    const today = dateFormat.format(new Date());
    const yesterday = dateFormat.format(new Date(Date.parse(today+"T12:00:00Z")-86400000));
    for (const target of [el("miscStart"),el("miscEnd")]) {
      target.max = today;
      if (!target.value) target.value = yesterday;
    }
    controls();
    if (!busy && loadedKey !== query(scope())) void load();
  }

  for (const id of ["miscStart","miscEnd"]) el(id).addEventListener("change",() => {
    invalidate();
    if (active()) message("Clique em Ver período para carregar as datas escolhidas.");
  });
  for (const id of ["miscSearch","miscMode","miscRankBy"]) el(id).addEventListener(id === "miscSearch" ? "input" : "change",() => {
    page = 1;
    person = "";
    drawResults();
  });
  el("miscLoad").addEventListener("click",() => void load());
  el("miscHistory").addEventListener("change",() => void load({withHistory:false}));
  el("miscConsult").addEventListener("click",() => void consult());
  el("miscPrev").addEventListener("click",() => { page--; drawResults(); });
  el("miscNext").addEventListener("click",() => { page++; drawResults(); });
  el("miscRuleForm").addEventListener("submit",event => { event.preventDefault(); void saveRule(false); });
  el("miscClearRule").addEventListener("click",() => void saveRule(true));
  el("miscService").addEventListener("input",renderRule);
  el("miscFile").addEventListener("change",() => void parseFile());
  el("miscImportDay").addEventListener("change",() => { importNote(); controls(); });
  el("miscMissingForm").addEventListener("submit",event => { event.preventDefault(); void saveMissing(); });
  el("miscAuditLink").addEventListener("click",() => {
    el("stockDailyTab")?.click();
    el("materialAuditPanel")?.scrollIntoView({block:"start"});
  });
  el("miscQualityLink").addEventListener("click",() => el("stockQualityTab")?.click());
  for (const event of ["dominium:misc-open","dominium:stock-tab-change"]) document.addEventListener(event,open);
  document.addEventListener("dominium:misc-refresh",() => { if (active() && !syncing && !saving) void load(); });
  document.addEventListener("dominium:scope-change",() => { invalidate(); open(); });
  document.addEventListener("dominium:auth-cleared",invalidate);
})();
