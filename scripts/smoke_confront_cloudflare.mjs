/* Verify private Worker route with the same Node fetch transport used by Hostinger. */
import fs from 'node:fs';
const token=fs.readFileSync('C:/DominiumRuntime/DescRelay-20261010/state/relay-token.txt','utf8').trim();
const root='https://dominium-import-bridge.jogador743.workers.dev';
for (const [path,role,authorized] of [
 ['/api/confront/status','controller',true],
 ['/api/confront/jobs','controller',true],
 ['/api/confront/jobs/'+'0'.repeat(32),'controller',true],
 ['/api/confront/status','viewer',true],
 ['/api/confront/status','controller',false],
]) {
 try {
  const response=await fetch(root+path,{
   method:'GET',signal:AbortSignal.timeout(15000),headers:{
    ...authorized?{Authorization:'Bearer '+token}:{},
    'X-Dominium-Role':role,
    'X-Dominium-Actor':'user-999999',
  }});
  let value={};
  try {value=await response.json();} catch {}
  console.log(path,role,authorized?'authenticated':'anonymous',
    'status='+response.status,'json='+Boolean(value.ok),
    'error_code='+String(value.error||'').slice(0,80));
 } catch(error) {console.log(path,'network_error='+error.name);}
}
