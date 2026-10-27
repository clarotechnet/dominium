'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const source=fs.readFileSync(require('node:path').join(__dirname,'../static/app.js'),'utf8');
function extract(name){
 const start=source.indexOf('function '+name+'(');assert.notEqual(start,-1,name+' missing');
 let parens=1,end=source.indexOf('(',start)+1;
 for(;end<source.length&&parens;end++){if(source[end]==='(')parens++;if(source[end]===')')parens--;}
 const open=source.indexOf('{',end);let depth=0;
 for(let i=open;i<source.length;i++){if(source[i]==='{')depth++;if(source[i]==='}')depth--;if(!depth)return source.slice(source.slice(start-6,start)==='async '?start-6:start,i+1);}
 throw Error('unclosed '+name);
}
function harness(){
 return new Function(`const state={profile:'natal',orders:[]};
 ${extract('toaLiveImperiumMatch')}
 ${extract('validToaCloseSnapshot')}
 ${extract('syncToaLiveOrderSnapshots')}
 ${extract('toaLiveCloseOrder')}
 return {state,syncToaLiveOrderSnapshots,toaLiveCloseOrder};`)();
}
const row=(hash='old')=>({id_os:123,num_os:'90001',contract:'12345',service:'MUDANCA DE PACOTE',status:'EM CAMPO',operation_source:'toa_import',approved_state_hash:hash,operation_identity:{activity_id:'aid',profile_key:'natal',contract:'12345'},import_scope:{source_hash:hash,expected_profile_key:'natal'},operation_blockers:[]});
const capture=(order)=>({aid:'aid',contract:'12345',tasks:[{os_number:'90001'}],imperium_matches:[order]});
test('fresh lookup replaces the old authorization as a complete row before preparing equipment and materials',()=>{
 const h=harness();h.state.orders=[row()];
 const fresh=row('fresh'),c=capture(fresh);
 h.syncToaLiveOrderSnapshots({profile:'natal',results:[c]},h.state.orders);
 const selected=h.toaLiveCloseOrder(c,c.tasks[0]);
 assert.equal(selected.approved_state_hash,'fresh');assert.equal(selected.import_scope.source_hash,'fresh');
 assert.deepEqual(selected.operation_identity,fresh.operation_identity);
 assert.equal(selected.manual_scope,undefined);
});
test('an old capture does not override a newer list after another OS was closed',()=>{
 const h=harness(),c=capture(row('lookup'));h.state.orders=[row('after-close')];
 const selected=h.toaLiveCloseOrder(c,c.tasks[0]);
 assert.equal(selected.approved_state_hash,'after-close');assert.equal(selected.import_scope.source_hash,'after-close');
});
test('delayed lookup cannot replace a list that changed while the lookup was pending',()=>{
 const h=harness();h.state.orders=[row('before')];const requestedOrders=h.state.orders;
 const newer={...row('after-close'),read_only:true,status:'CONCLUIDA'};h.state.orders=[newer];
 const applied=h.syncToaLiveOrderSnapshots({profile:'natal',results:[capture(row('delayed'))]},requestedOrders);
 assert.equal(h.state.orders[0],newer);assert.equal(h.state.orders[0].status,'CONCLUIDA');assert.equal(applied,false);
});
test('lookup does not inject another contract, profile, closed, blocked or unsigned order',()=>{
 for(const changed of [{contract:'other'},{read_only:true},{status:'CONCLUIDA'},{operation_blockers:['already_closed']},{approved_state_hash:''}, {operation_identity:{activity_id:'aid',profile_key:'recife',contract:'12345'}}]){
  const h=harness();h.state.orders=[row('old')];
  h.syncToaLiveOrderSnapshots({profile:'natal',results:[capture({...row('fresh'),...changed})]},h.state.orders);
  assert.equal(h.state.orders[0].approved_state_hash,'old');
 }
 const h=harness();h.state.orders=[row('old')];h.syncToaLiveOrderSnapshots({profile:'recife',results:[capture(row('fresh'))]},h.state.orders);
 assert.equal(h.state.orders[0].approved_state_hash,'old');
});
test('capture activity mismatch never combines an identity from lookup with another approval hash',()=>{
 const h=harness(),c=capture(row('lookup'));h.state.orders=[{...row('other'),operation_identity:{activity_id:'another',profile_key:'natal',contract:'12345'}}];
 assert.equal(h.toaLiveCloseOrder(c,c.tasks[0]),null);
});
test('blocked lookup row cannot borrow an older authorized list row',()=>{
 const h=harness(),c=capture({...row('blocked'),operation_blockers:['already_closed']});h.state.orders=[row('old')];
 assert.equal(h.toaLiveCloseOrder(c,c.tasks[0]),null);
});
test('approved historical and manual sources keep their complete own authorization',()=>{
 for(const operation_source of ['imperium_cache','imperium_history']){
  const h=harness();const fresh={...row('manual'),operation_source,operation_identity:undefined,import_scope:undefined,manual_scope:{profile_key:'natal',state_hash:'manual'}};
  const c=capture(fresh);h.state.orders=[row('old')];h.syncToaLiveOrderSnapshots({profile:'natal',results:[c]},h.state.orders);
  const selected=h.toaLiveCloseOrder(c,c.tasks[0]);assert.equal(selected.operation_source,operation_source);
  assert.equal(selected.approved_state_hash,'manual');assert.equal(selected.manual_scope.state_hash,'manual');
  assert.equal(selected.operation_identity,undefined);assert.equal(selected.import_scope,undefined);
 }
});
test('the real editor and submit keep nine materials, equipment and one coherent fresh approval',async()=>{
 const h=new Function(`const state={profile:'natal',orders:[],closeCodes:[{code:'409',productive:true}],productiveDrafts:{},authUser:{},activeModule:'close'};
 const elements={closeTransport:{value:'official_http'},closeWorkspaceCode:{},closeWorkspaceObservation:{},closeDetailTitle:{scrollIntoView(){}}};
 const calls=[],confirmations=[];
 const normalize=x=>String(x).toUpperCase();const isNoEquipmentService=()=>false;
 const toaLiveEquipmentDraft=x=>x||[];const isToaLiveMaterialOwner=()=>true;const toaLiveMaterialsDraft=x=>x||[];const closeCodeAllowsMaterials=()=>true;
 const defaultMovement=()=> 'install';const operationDraftKey=x=>x.num_os;
 const selectCloseWorkspaceOrder=()=>{};const renderCloseWorkspace=()=>{};const showToast=()=>{};
 const openConfirmation=(...x)=>confirmations.push(x);const apiUrl=x=>x+'?profile=natal';
 const request=async(url,options)=>{calls.push({url,body:JSON.parse(options.body)});return {ok:true,pending_confirmation:true};};
 ${extract('toaLiveImperiumMatch')}
 ${extract('validToaCloseSnapshot')}
 ${extract('syncToaLiveOrderSnapshots')}
 ${extract('toaLiveCloseOrder')}
 ${extract('prepareToaLiveClose')}
 ${extract('submitClose')}
 return {state,calls,confirmations,syncToaLiveOrderSnapshots,prepareToaLiveClose,submitClose};`)();
 const fresh=row('fresh'),c={...capture(fresh),installed_equipment:[{serial:'SERIAL_FIXTURE',type:'emta'}],removed_equipment:[],materials:Array.from({length:9},(_,i)=>({code:String(200+i),quantity:i===0?78:1})),material_paste_key:'fixture'};
 h.state.orders=[row('old')];h.syncToaLiveOrderSnapshots({profile:'natal',results:[c]},h.state.orders);
 assert.equal(h.prepareToaLiveClose(c,{os_number:'90001',close_code:'409'},{openEditor:true,expectedProfile:'natal'}),true);
 const selected=h.confirmations[0][0][0],draft=h.state.productiveDrafts['90001'];
 await h.submitClose(selected,{code:'409'},draft);
 assert.equal(h.calls.length,1);const body=h.calls[0].body;
 assert.equal(body.approved_state_hash,'fresh');assert.equal(body.import_scope.source_hash,'fresh');
 assert.deepEqual(body.installed_equipment,c.installed_equipment);assert.deepEqual(body.materials,c.materials);
 assert.equal(body.materials.length,9);assert.equal(body.materials[0].quantity,78);
});
