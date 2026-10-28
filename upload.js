/* WebGazer study upload (memory-only, fresh-session edition 3.2).
 * Checkpoints and the temporary upload capability live only in this page's memory.
 * Nothing is stored in localStorage, sessionStorage, IndexedDB, or Cache Storage.
 * No gaze/consent/participant records leave the page until Submit Study Data.
 * Reloading or closing this page before submission irreversibly loses unsent data.
 */
(function(root){
'use strict';
const api=(root.STUDY_API_URL||'').replace(/\/$/,'');
const configured=Boolean(api);
const pageInstance=root.crypto?.randomUUID?.()||String(Date.now())+'_'+Math.random();
let token='',sid='',visit='pilot',initPromise=null,submitting=null,enqueueLock=Promise.resolve();
let sequence=0;
const queue=[];
const status={configured,ready:false,pending:0,error:'',sent:0,receipt:false,submitting:false};
const changed=()=>root.dispatchEvent(new Event('study-upload-status'));
function setError(message){status.error=message;changed();}

// Remove persistence left by earlier builds. This discards old, unsubmitted
// checkpoints; the page warns before new deployments are used for recruitment.
function clearLegacyStudyStorage(){
  try{
    for(let i=localStorage.length-1;i>=0;i--){
      const key=localStorage.key(i);
      if(key && (key.startsWith('webgazer.upload.') || key==='webgazer.anonymous.study.capability.v2_5' ||
        key==='gazecheck.device' || key==='gazecheck.cardPx'))localStorage.removeItem(key);
    }
  }catch(_){/* storage may be disabled */}
  try{sessionStorage.removeItem('webgazer.local.session');}catch(_){/* optional */}
  try{if(root.indexedDB)root.indexedDB.deleteDatabase('webgazer-uploads-v1');}catch(_){/* optional */}
}
clearLegacyStudyStorage();

async function request(path,body){
  const controller=new AbortController();
  const timer=setTimeout(()=>controller.abort(),30000);
  try{
    const response=await fetch(api+path,{
      method:'POST',mode:'cors',cache:'no-store',signal:controller.signal,
      headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},
      body:JSON.stringify(body||{})
    });
    if(!response.ok){
      const detail=await response.text().catch(()=>response.statusText);
      throw new Error('Upload API '+response.status+': '+detail.slice(0,180));
    }
    return await response.json();
  }finally{clearTimeout(timer);}
}

function start(){
  if(initPromise)return initPromise;
  initPromise=(async()=>{
    if(configured){
      const response=await fetch(api+'/api/public-session',{
        method:'POST',headers:{'Content-Type':'application/json'},cache:'no-store',body:'{}'
      });
      if(!response.ok)throw new Error('Could not open a new study session ('+response.status+'). Please try again.');
      const data=await response.json();
      if(!/^[a-f0-9]{32}$/.test(data.session_id)||!data.token){
        throw new Error('Study server returned an invalid session.');
      }
      sid=data.session_id;
      token=data.token;
    }else{
      sid=pageInstance;
    }
    visit='pilot';
    status.ready=true;status.error='';status.pending=0;changed();
    return {mode:configured?'online':'local',session_id:sid,visit,pending:0,
      needsResume:false,hasFinish:false};
  })().catch(error=>{initPromise=null;setError(error.message);throw error;});
  return initPromise;
}

function pending(){return Promise.resolve(queue.map(x=>({...x})));}
function enqueue(kind,data,build){
  if(!configured)return Promise.resolve(false);
  enqueueLock=enqueueLock.catch(()=>{}).then(()=>{
    if(!status.ready)throw new Error('Study session is not initialized');
    if(status.receipt)throw new Error('Study data already submitted');
    const payload={kind,build,created_at:new Date().toISOString(),data:{...data,page_instance:pageInstance}};
    queue.push({key:sid+'_'+String(sequence).padStart(6,'0'),sid,seq:sequence,payload});
    sequence+=1;
    status.pending=queue.length;changed();
    return true;
  });
  return enqueueLock;
}

async function sendAll(){
  if(!configured||!status.ready)throw new Error('No server study session available');
  if(submitting)return submitting;
  submitting=(async()=>{
    status.submitting=true;status.error='';changed();
    // This is the first time study data are sent over the network.
    const opened=await request('/api/sessions',{});
    if(opened.session_id!==sid)throw new Error('Study session verification failed. No data were submitted.');
    if(sequence===0)throw new Error('No study data available. Download a backup.');
    // Fail locally instead of sending consent at an invalid sequence position.
    const first=queue[0];
    if(!first || first.seq!==0 || first.payload.kind!=='consent' ||
       first.payload.data.agreed!==true ||
       !String(first.payload.data.typed_name||'').trim() ||
       !first.payload.data.version || !first.payload.data.acknowledged_at){
      throw new Error('Consent must be the first complete study batch. Download a backup.');
    }
    while(queue.length){
      const entry=queue[0];
      await request('/api/sessions/'+sid+'/batches/'+entry.seq,entry.payload);
      queue.shift(); // Remove from memory only after server confirmation.
      status.sent++;status.pending=queue.length;changed();
    }
    const ack=await request('/api/sessions/'+sid+'/complete',{last_sequence:sequence-1});
    if(ack.status!=='acknowledged')throw new Error('The server did not confirm submission');
    status.receipt=true;status.error='';changed();
    return ack;
  })().catch(error=>{setError(error.message);throw error;})
    .finally(()=>{status.submitting=false;submitting=null;changed();});
  return submitting;
}
async function complete(){await enqueueLock;return sendAll();}
function pendingCount(){return status.pending;}
root.StudyUpload={configured,status,start,enqueue,complete,pending,pendingCount};
})(window);
