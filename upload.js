/* Keep the data in the participant's browser until they press the final Submit button.
 * Consent-aware durable queue. Queues ONLY in IndexedDB until the participant presses Submit.
 * No network requests at initialization, during measurement, or on reconnect.
 * The public browser never receives the S3 bucket credentials or STUDY_SECRET.
 */
(function(root){
'use strict';
const api=(root.STUDY_API_URL||'').replace(/\/$/,'');
const configured=Boolean(api);
const pageInstance=(root.crypto && root.crypto.randomUUID)?root.crypto.randomUUID():String(Date.now())+'_'+Math.random();
let token='', sid='', visit='pilot', initPromise=null, submitting=null, enqueueLock=Promise.resolve();
const status={configured,ready:false,pending:0,error:'',sent:0,receipt:false,submitting:false};
const changed=()=>root.dispatchEvent(new Event('study-upload-status'));
function setError(message){status.error=message;changed();}
// IndexedDB stores checkpoints in this browser in case the page is interrupted.
function db(){return new Promise((resolve,reject)=>{
 const req=indexedDB.open('webgazer-uploads-v1',1);
 req.onupgradeneeded=()=>{const d=req.result;if(!d.objectStoreNames.contains('pending'))d.createObjectStore('pending',{keyPath:'key'});};
 req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);
});}
async function store(mode,method,value){const d=await db();return new Promise((resolve,reject)=>{
 const tx=d.transaction('pending',mode),q=tx.objectStore('pending')[method](value);
 q.onsuccess=()=>{if(method==='getAll')resolve(q.result);};
 tx.oncomplete=()=>{d.close();if(method!=='getAll')resolve();};
 tx.onerror=()=>{d.close();reject(tx.error);};
});}
async function pending(){return (await store('readonly','getAll')).filter(p=>p.sid===sid).sort((a,b)=>a.seq-b.seq);}
const CAPABILITY_KEY='webgazer.anonymous.study.capability.v2_5';
// Ask the server for a random session credential. It can upload but not read study data.
async function newCapability(){
 const response=await fetch(api+'/api/public-session',{
  method:'POST',headers:{'Content-Type':'application/json'},cache:'no-store',body:'{}'});
 if(!response.ok)throw new Error('Could not open a new study session ('+response.status+'). Please try again.');
 const data=await response.json();
 if(!/^[a-f0-9]{32}$/.test(data.session_id)||!data.token)throw new Error('Study server returned an invalid session.');
 localStorage.setItem(CAPABILITY_KEY,JSON.stringify(data));
 return data;
}
async function request(path,body){
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),30000);
 try{
  const res=await fetch(api+path,{method:'POST',mode:'cors',cache:'no-store',signal:controller.signal,
    headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},body:JSON.stringify(body||{})});
  if(!res.ok){const err=await res.text().catch(()=>res.statusText);throw new Error('Upload API '+res.status+': '+err.slice(0,180));}
  return await res.json();
 }finally{clearTimeout(timer);}
}
// Restore the current local session if it exists; otherwise start a new one.
async function start(){
 if(initPromise)return initPromise;
 initPromise=(async()=>{
  if(configured){
    let saved=null;
    try{saved=JSON.parse(localStorage.getItem(CAPABILITY_KEY)||'null');}catch(_){saved=null;}
    // Expired credentials cannot be reused. Preserve queued data, alert the participant.
    if(saved && saved.expires_at && saved.expires_at*1000<=Date.now())
       throw new Error('Your saved study session has expired. Export a local backup and contact the researchers.');
    const data=saved&&saved.session_id&&saved.token?saved:await newCapability();
    token=data.token;sid=data.session_id;visit='pilot';
    if(localStorage.getItem('webgazer.upload.completed.'+sid)==='yes'){
      localStorage.removeItem(CAPABILITY_KEY);
      const fresh=await newCapability();token=fresh.token;sid=fresh.session_id;
    }
    status.pending=(await pending()).length;
  }else{
    sid=sessionStorage.getItem('webgazer.local.session')||pageInstance;
    sessionStorage.setItem('webgazer.local.session',sid);
    visit='pilot';
  }
  status.ready=true;status.error='';changed();
  const hasFinish=configured && localStorage.getItem('webgazer.upload.hasfinish.'+sid)==='yes';
  const existing=configured?localStorage.getItem('webgazer.upload.seq.'+sid):null;
  return {mode:configured?'online':'local',session_id:sid,visit,pending:status.pending,
    needsResume:configured && Number(existing)>0,hasFinish};
 })().catch(e=>{initPromise=null;setError(e.message);throw e;});
 return initPromise;
}
// Add each checkpoint to the local queue, without making an upload request.
function enqueue(kind,data,build){
 if(!configured)return Promise.resolve(false);
 enqueueLock=enqueueLock.catch(()=>{}).then(async()=>{
   if(!status.ready)throw new Error('Study session is not initialized');
   if(status.receipt)throw new Error('Study data already submitted');
   const key='webgazer.upload.seq.'+sid;
   const existing=await pending();
   const seq=Math.max(Number(localStorage.getItem(key)||'0'),existing.reduce((m,p)=>Math.max(m,p.seq+1),0));
   const payload={kind,build,created_at:new Date().toISOString(),data:{...data,page_instance:pageInstance}};
   // Commit locally BEFORE changing the cursor or incrementing the sequence number.
   await store('readwrite','put',{key:sid+'_'+String(seq).padStart(6,'0'),sid,seq,payload});
   localStorage.setItem(key,String(seq+1));
   if(kind==='finish'||kind==='incomplete_finish')localStorage.setItem('webgazer.upload.hasfinish.'+sid,'yes');
   status.pending=(await pending()).length;changed();
   return true;
 });
 return enqueueLock;
}
// Final submission sends the saved batches in order and waits for the server receipt.
async function sendAll(){
 if(!configured||!status.ready)throw new Error('No server study session available');
 if(submitting)return submitting;
 submitting=(async()=>{
   status.submitting=true;status.error='';changed();
   // Do not create a server-side record until the user presses Submit.
   const opened=await request('/api/sessions',{});
   if(opened.session_id!==sid)throw new Error('Study session verification failed. No data were submitted.');
   const all=await pending();
   if(all.length===0 && localStorage.getItem('webgazer.upload.hasfinish.'+sid)!=='yes')
     throw new Error('No saved study data available. Download a backup.');
   for(const entry of all){
     // Reuse stable body/sequence for safe retry; server checks for duplicate content.
     await request('/api/sessions/'+sid+'/batches/'+entry.seq,entry.payload);
     await store('readwrite','delete',entry.key);
     status.sent++;status.pending=(await pending()).length;changed();
   }
   const last=Number(localStorage.getItem('webgazer.upload.seq.'+sid)||'0')-1;
   const ack=await request('/api/sessions/'+sid+'/complete',{last_sequence:last});
   if(ack.status!=='acknowledged')throw new Error('The server did not confirm submission');
   status.receipt=true;status.error='';localStorage.setItem('webgazer.upload.completed.'+sid,'yes');
   localStorage.removeItem(CAPABILITY_KEY);changed();
   return ack;
 })().catch(e=>{setError(e.message);throw e;}).finally(()=>{status.submitting=false;submitting=null;changed();});
 return submitting;
}
// Wait for any local writes to finish before uploading the queue.
async function complete(){await enqueueLock;return sendAll();}
function pendingCount(){return status.pending;}
root.StudyUpload={configured,status,start,enqueue,complete,pending,pendingCount};
})(window);
