/* DOMINIUM Pendente — import/query workflow from stock training recordings. */
(() => {
  "use strict";
  const reader = window.DominiumQueryImport;
  const $=id=>document.getElementById(id);
  const ui={file:$("confrontQueryFile"),city:$("confrontCity"),
    status:$("confrontEquipmentStatus"),location:$("confrontLocationFilter"),
    assume:$("confrontAssumeCity"),assumeLabel:$("confrontAssumeCityLabel"),
    text:$("confrontQueryStatus"),preview:$("confrontQueryPreview"),
    count:$("confrontQueryCount"),use:$("confrontUseFiltered"),
    serials:$("confrontInput")};
  if(!reader||Object.values(ui).some(x=>!x))return;
  let imported=null, filtered=[];
  const cities={natal:"NATAL",fortaleza:"FORTALEZA",mossoro:"MOSSORO",recife:"RECIFE"};
  function setChoices(select,values,empty){
    const options=[new Option(empty,""),...values.map(v=>new Option(v,v))];
    select.replaceChildren(...options);select.disabled=values.length===0;
  }
  function resetPreview(){
    ui.preview.replaceChildren();ui.use.disabled=true;
    ui.count.textContent="Nenhuma planilha importada";
  }
  function render(){
    ui.city.value=state.profile;
    if(!imported){resetPreview();return;}
    ui.assumeLabel.classList.toggle("hidden",imported.hasCity);
    ui.assume.disabled=imported.hasCity;
    const city=cities[ui.city.value]||"";
    filtered=reader.filter(imported,{
      city, status:ui.status.value, location:ui.location.value,
      assumeCity:ui.assume.checked
    });
    const {records,hasCity,numericRisk}=imported;
    const importedRecords=records.filter(row=>
      (!ui.status.value || reader.normalize(row.status)===reader.normalize(ui.status.value))&&
      (!ui.location.value || reader.normalize(row.location)===reader.normalize(ui.location.value)));
    ui.use.disabled=!filtered.length;
    ui.count.textContent=`${records.length.toLocaleString("pt-BR")} registros na planilha · ${filtered.length.toLocaleString("pt-BR")} seriais filtrados`;
    let warning="";
    if(!hasCity && !ui.assume.checked){
      warning="A planilha não informa cidade/operação. Para evitar classificar outra praça como "+city+
        ", confirme que o arquivo pertence a esta praça.";
    }else if(hasCity && !filtered.length && importedRecords.length){
      warning="Nenhum registro corresponde a "+city+". Confira a coluna de cidade/operação na planilha.";
    }else if(filtered.length>500) {
      warning="Foram encontrados "+filtered.length+" seriais. Cada confronto suporta até 500; refine os filtros.";
      ui.use.disabled=true;
    }else {
      warning="Lista preparada para "+(ui.city.selectedOptions[0]?.textContent||city)+
        ". Use os seriais filtrados para iniciar a consulta read-only.";
    }
    if(numericRisk)warning+=" Atenção: "+numericRisk+" número(s) de série em notação científica foram ignorados.";
    ui.text.textContent=warning;
    const selectedSet=new Set(filtered);
    const preview=records.filter(r=>selectedSet.has(r.serial)).slice(0,15);
    const table=document.createElement("table");table.className="confront-preview-table";
    const header=document.createElement("thead"),tr=document.createElement("tr");
    ["Serial","Estado","Praça/operação","Local"].forEach(t=>{
      const th=document.createElement("th");th.textContent=t;tr.append(th);
    });
    header.append(tr);table.append(header);
    const body=document.createElement("tbody");
    for(const item of preview){
      const line=document.createElement("tr");
      [item.serial,item.status||"—",item.city||"Não informado",item.location||"—"].forEach(value=>{
        const td=document.createElement("td");td.textContent=value;line.append(td);
      });
      body.append(line);
    }
    table.append(body);ui.preview.replaceChildren(table);
  }
  ui.file.addEventListener("change",async()=>{
    resetPreview();imported=null;filtered=[];
    ui.assume.checked=false;
    const file=ui.file.files?.[0];
    if(!file)return;
    ui.text.textContent="Lendo a planilha localmente...";
    try{
      const data=await reader.read(file);
      imported=data;
      const distinct=(field)=>[...new Set(data.records.map(row=>row[field]).filter(Boolean))]
        .sort((a,b)=>a.localeCompare(b,"pt-BR")).slice(0,300);
      setChoices(ui.status,distinct("status"),"Todos os estados");
      setChoices(ui.location,distinct("location"),"Todos os locais");
      render();
    }catch(error){
      imported=null;resetPreview();
      ui.text.textContent="Não foi possível ler a QUERY: "+String(error.message||"Formato inválido");
    }
  });
  ui.status.addEventListener("change",render);
  ui.location.addEventListener("change",render);
  ui.assume.addEventListener("change",render);
  ui.city.addEventListener("change",async()=>{
    const selected=ui.city.value;
    if(selected!==state.profile){
      await switchProfile(selected);
      if(state.profile!==selected){
        ui.text.textContent="Não foi possível mudar a praça. Tente selecionar na barra superior.";
      }
    }
    render();
  });
  ui.use.addEventListener("click",()=>{
    if(!filtered.length||filtered.length>500)return;
    ui.serials.value=filtered.join("\n");
    ui.text.textContent=`${filtered.length} seriais de ${ui.city.selectedOptions[0]?.textContent||""} copiados para o confronto. Confira a lista e clique em Iniciar confronto.`;
    ui.serials.focus();
  });
  document.addEventListener("dominium:module-change",render);
  setInterval(()=>{
    if(state.activeModule==="confront" && ui.city.value!==state.profile)render();
  },2500);
  ui.city.value=state.profile;
  resetPreview();
})();
