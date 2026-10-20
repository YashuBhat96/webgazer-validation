import asyncio, pathlib, re
from playwright.async_api import async_playwright
base=pathlib.Path(__file__).resolve().parent
src=(base/'index.html').read_text()
FAKE='''window.webgazer={tracker:{model:Promise.resolve(),getEyePatches:async()=>false,positionsArray:null},getTracker(){return this.tracker},setRegression(){return this},setGazeListener(){return this},showVideo(){return this},showFaceOverlay(){return this},showFaceFeedbackBox(){return this},showPredictionPoints(){return this},begin(){return this},isReady(){return true},removeMouseEventListeners(){return this},setVideoViewerSize(){return this},clearData(){return Promise.resolve()},recordScreenPosition(){return this},pause(){return this}};window.__wgReady=Promise.resolve(true);'''
src=re.sub(r'<script>\s*/\* ---- Face-model files[\s\S]*?</script>',f'<script>{FAKE}</script>',src,count=1)
src=src.replace('<script src="./quality.js"></script>','<script>'+ (base/'quality.js').read_text()+'</script>')
src=src.replace('<script src="./gaze_kinematics.js"></script>', '<script>'+ (base/'gaze_kinematics.js').read_text()+'</script>')
src=src.replace('<script src="./deploy-config.js"></script>', '<script>window.STUDY_API_URL="";</script>')
mock_storage="const __mockStorage=new Map();window.__mockSession={getItem:k=>__mockStorage.get(k)||null,setItem:(k,v)=>__mockStorage.set(k,String(v))};"
up=(base/'upload.js').read_text().replace('sessionStorage.', 'root.__mockSession.')
src=src.replace('<script src="./upload.js"></script>', '<script>'+mock_storage+up+'</script>')
src=src.replace('})();\n</script>\n</body>', '''window.__audit={
 getSearchTrialCount:()=>SEARCH_TRIALS,makeTrial, pointStats,computeResults,needPass,scoreStream,scoreSearch,saveSearch,saveSession,saveQuality,saveKinematics,
 enableMockSubmit:()=>{$('#instruct').classList.remove('on');show('done');$('#submitStudyData').disabled=false;StudyUpload.configured=true;StudyUpload.status.ready=true;StudyUpload.complete=async()=>({status:'acknowledged',session_id:'mock'});},
 syntheticBadCheck:()=>{const pts=[0,0,0,0,400].map(err=>({usable:true,reasons:[],accuracyMeanPx:err,accuracyDeg:err}));return GazeQuality.screenCheck(pts).pass;},
 emptySearch:()=>{searchTrials=[];scoreSearch();return lastSearch.rocByDur[100].auc;},
 getState:()=>({passed,calibrated,lastSummary}),setState:()=>{calibrated=true;passed=true;},
 seedRaw:()=>{recording=true;pid='LOCALSESSION';t0=0;pxPerCm=40;distCm=60;distSource='tape measure';sessionLog=[{t:100,phase:'validate',ev:'gaze',taskId:'main_1',attempt:1,targetX:100,targetY:100,x:101,y:100,rawX:101,rawY:100,smX:101,smY:100,w:1440,h:900,d:60}];},
 setSearch:()=>{const tr=makeTrial();tr.id=1;tr.status='completed';tr.startedAt=1000;tr.endedAt=6000;tr.quality={usable:true};tr.gaze=Array.from({length:151},(_,i)=>({t:1100+i*30,x:tr.targets[0].x,y:tr.targets[0].y,rx:tr.targets[0].x,ry:tr.targets[0].y,smx:tr.targets[0].x,smy:tr.targets[0].y}));searchTrials=[tr];scoreSearch();return lastSearch.validTrials;},
 setSummary:()=>{const rs=Array.from({length:12},(_,k)=>({i:k+1,x:400,y:350,n:50,mgx:400,mgy:350,
   accPx:1,precPx:1,accX:1,accY:1,precX:1,precY:1,usable:true,coveragePct:100,maxGapMs:50,
   callbackRateHz:30,reasons:[],invalidCallbacks:0,attempts:1,interrupted:false}));
   computeResults(rs,{intervals:Array(100).fill(33),nGot:600,nNull:0,resultsRaw:rs,resultsSm:rs,pauses:0,interruptedN:0});}
};
})();
</script>
</body>''')
async def main():
 async with async_playwright() as pl:
  b=await pl.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-gpu'])
  page=await b.new_page(viewport={'width':1440,'height':900},accept_downloads=True)
  errs=[];page.on('pageerror',lambda e:errs.append(str(e)))
  await page.set_content(src,wait_until='domcontentloaded')
  assert 'Gaze Check' in await page.title()
  await page.click('#toDemo')
  assert not await page.locator('#p-demo').evaluate('(x)=>x.classList.contains("on")'), 'experience yes/no required'
  await page.locator('input[name=eyeTrackerExperience][value=no]').check()
  await page.fill('#participantName','')
  await page.click('#toDemo')
  assert not await page.locator('#p-demo').evaluate('(x)=>x.classList.contains("on")'), 'name and consent required'
  await page.fill('#participantName','Test Participant')
  await page.locator('#consentAgree').check()
  assert await page.locator('#pid').count()==0, 'visible participant ID field should be removed'
  assert await page.locator('#operatorRole').count()==0, 'operator selector should be removed'
  assert await page.locator('input[name=demoGender]').count()==0, 'gender selector should be removed'
  await page.click('#toDemo')
  await page.locator('#p-demo.on').wait_for(timeout=5000)
  assert await page.evaluate('window.__audit.needPass()')
  v=await page.evaluate('''() => {window.__audit.setState(); window.__audit.setSummary();return window.__audit.getState().lastSummary.screenQuality.pass;}''')
  assert v
  tr=await page.evaluate('''() => {let runs=[];for(let i=0;i<300;i++){const tr=window.__audit.makeTrial();runs.push(tr&&tr.stim.length===18&&tr.targets.length===2);}return runs;}''')
  assert all(tr), f'stimulus placement failure: {sum(tr)}/{len(tr)}'
  # Check at the documented minimum practical desktop size; failures must be reported.
  await page.set_viewport_size({'width':1280,'height':720})
  more=await page.evaluate('''() => {let good=0;for(let i=0;i<100;i++) good+=!!window.__audit.makeTrial();return good;}''')
  print('Layouts at 1280x720:',more,'/100')
  await page.set_viewport_size({'width':1440,'height':900})
  assert await page.evaluate('window.__audit.getSearchTrialCount()') == 50, 'visual search must use 50 rounds'
  assert not await page.evaluate('window.__audit.needPass()')
  assert await page.evaluate('window.__audit.syntheticBadCheck()') is False
  assert await page.evaluate('window.__audit.setSearch()') == 1
  await page.evaluate('window.__audit.seedRaw()')
  async with page.expect_download() as d:
   await page.evaluate('window.__audit.saveSearch()')
  dl=await d.value
  assert 'gaze_search_item_metrics_' in dl.suggested_filename
  async with page.expect_download() as d2:
   await page.evaluate('window.__audit.saveSession()')
  djson=await d2.value
  assert 'gaze_session_' in djson.suggested_filename
  assert await page.evaluate('window.__audit.emptySearch()') is None
  async with page.expect_download() as dm:
   await page.evaluate('window.__audit.saveKinematics()')
  dk=await dm.value
  assert 'gaze_kinematic_samples_' in dk.suggested_filename
  assert await page.locator('#submitStudyData').count()==1
  assert await page.locator('#submitStudyData').evaluate('(e)=>getComputedStyle(e).minHeight')=='86px'
  await page.evaluate('window.__audit.enableMockSubmit()')
  await page.click('#submitStudyData')
  await page.wait_for_function("document.getElementById('doneSaved').textContent.includes('Submission confirmed')")
  assert await page.locator('#submitStudyData').inner_text()=='DATA SUBMITTED ✓'
  print('Browser smoke PASS: consent, 50 trials, no participant ID, experience yes/no, large submit control, state gate, rendered metrics, search scoring, session JSON and search CSV downloads, bad check, empty search, 300/300 18-item trials')
  print('Page errors:',errs)
  assert not errs,errs
  await b.close()
asyncio.run(main())
