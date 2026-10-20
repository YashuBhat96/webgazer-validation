/* Research quality metrics. Pure functions, testable in Node and the browser.
   Units: CSS pixels and milliseconds. No interpolation or position smoothing. */
(function(root){
  'use strict';
  const mean=a=>a.length?a.reduce((x,y)=>x+y,0)/a.length:null;
  const sd=a=>a.length>1?Math.sqrt(mean(a.map(v=>(v-mean(a))**2))):null;
  const CFG=Object.freeze({
    analysisStartMs:300, // avoids treating the first gaze transition as settled fixation
    analysisEndMs:2000,
    minSamples:12,
    minCoveragePct:70,
    coverageBinMs:100,
    maxGapMs:600,
    minCallbackValidityPct:75,
    maxMeanErrorDeg:6,
    maxPointErrorDeg:8,
    maxMeanErrorPx:220,
    maxPointErrorPx:300,
    // Screening only, not a validated claim that WebGazer data are suitable for any AOI.
    minUsablePoints:5,
  });
  // Work out sample coverage, gaps, target error, and how spread out predictions are.
  function measure(samples, target, opts={}){
    const C={...CFG,...opts}, span=C.analysisEndMs-C.analysisStartMs;
    const valid=samples.filter(s=>s && Number.isFinite(s.t) && Number.isFinite(s.x) && Number.isFinite(s.y)
      && s.t>=C.analysisStartMs && s.t<C.analysisEndMs).sort((a,b)=>a.t-b.t);
    const bins=Math.ceil(span/C.coverageBinMs), seen=new Set();
    valid.forEach(s=>seen.add(Math.min(bins-1,Math.floor((s.t-C.analysisStartMs)/C.coverageBinMs))));
    const coveragePct=bins?100*seen.size/bins:0;
    const gaps=valid.slice(1).map((s,i)=>s.t-valid[i].t);
    const maxGapMs=valid.length?Math.max(valid[0].t-C.analysisStartMs,C.analysisEndMs-valid[valid.length-1].t,...gaps):span;
    const callbackRateHz=span?valid.length/(span/1000):0;
    const mx=mean(valid.map(s=>s.x)), my=mean(valid.map(s=>s.y));
    const dx=mx==null?null:mx-target.x, dy=my==null?null:my-target.y;
    const sampleError=valid.map(s=>Math.hypot(s.x-target.x,s.y-target.y));
    const rmse=valid.length?Math.sqrt(mean(sampleError.map(v=>v*v))):null;
    const successive=valid.slice(1).map((s,i)=>Math.hypot(s.x-valid[i].x,s.y-valid[i].y));
    const reasons=[];
    if(valid.length<C.minSamples)reasons.push('insufficient_samples');
    if(coveragePct<C.minCoveragePct)reasons.push('insufficient_time_coverage');
    if(maxGapMs>C.maxGapMs)reasons.push('long_sample_gap');
    return {n:valid.length,usable:reasons.length===0,reasons,coveragePct,maxGapMs,callbackRateHz,
      accuracyMeanPx:mx==null?null:Math.hypot(dx,dy),
      meanSampleErrorPx:mean(sampleError),rmsePx:rmse,
      precisionRmsPx:mx==null?null:Math.sqrt(mean(valid.map(s=>(s.x-mx)**2+(s.y-my)**2))),
      precisionRmsSuccessivePx:successive.length?Math.sqrt(mean(successive.map(v=>v*v))):null,
      signedErrorXPx:dx,signedErrorYPx:dy,
      meanX:mx,meanY:my,intervalMeanMs:mean(gaps),intervalSdMs:sd(gaps)};
  }
  // A good mean cannot hide a failed corner of the screen in this check.
  function screenCheck(points,opts={}){
    const C={...CFG,...opts};
    const usable=points.filter(p=>p && p.usable && Number.isFinite(p.accuracyMeanPx));
    const errors=usable.map(p=>p.accuracyDeg!=null?p.accuracyDeg:p.accuracyMeanPx);
    const useDeg=usable.every(p=>p.accuracyDeg!=null);
    const meanError=mean(errors), maxError=errors.length?Math.max(...errors):null;
    const failed=points.flatMap((p,i)=>p && p.reasons && p.reasons.length?p.reasons.map(r=>`point_${i+1}:${r}`):[]);
    if(usable.length<C.minUsablePoints)failed.push('missing_usable_screen_regions');
    if(meanError==null||meanError>(useDeg?C.maxMeanErrorDeg:C.maxMeanErrorPx))failed.push('mean_accuracy_threshold');
    if(maxError==null||maxError>(useDeg?C.maxPointErrorDeg:C.maxPointErrorPx))failed.push('worst_point_threshold');
    return {pass:failed.length===0,reasons:failed,usableN:usable.length,totalN:points.length,
      meanError,maxError,unit:useDeg?'deg':'px'};
  }
  const exported={CFG,measure,screenCheck};
  if(typeof module!=='undefined'&&module.exports)module.exports=exported;
  root.GazeQuality=exported;
})(typeof window!=='undefined'?window:globalThis);
