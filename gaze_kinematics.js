/* Postprocessed WebGazer predictions, not ground truth eye-movement events.
 * Degrees are approximate screen-relative visual angles based on screen scaling
 * and viewing distance (measured where provided, otherwise camera-estimated).
 */
(function(root){
'use strict';
const rad2deg=180/Math.PI;
const finite=Number.isFinite;
const round=(x,n=4)=>finite(x)?Number(x.toFixed(n)):null;
// Keep the original gaze coordinates and calculate angles and possible movement events.
function analyze(log,opts={}){
 const pxPerCm=Number(opts.pxPerCm),fallbackDistanceCm=Number(opts.distanceCm);
 const distanceSource=opts.distanceSource||'unknown';
  // The velocity threshold is a choice in this analysis, not a native WebGazer output.
 const threshold=opts.velocityThresholdDegS??35;
 const maxGap=opts.maxGapMs??250, minFix=opts.minFixationMs??100;
 const params={method:'exploratory_ivt',version:'1.0',velocity_threshold_deg_per_s:threshold,
  max_callback_gap_ms:maxGap,min_fixation_ms:minFix,min_fixation_samples:3,
  min_saccade_intervals:2,min_saccade_amplitude_deg:0.5,
  distance_source:distanceSource,angle_reference:'screen center; horizontal positive right, vertical positive up',
  disclaimer:'WebGazer webcam predictions are not validated saccade/fixation ground truth; speed measures are sensitive to noise and irregular timestamps.'};
 const samples=[],events=[];
 let previous=null;
 const atanPos=(px,center,scale,d,reverse)=>Math.atan(((reverse?center-px:px-center)/scale)/d)*rad2deg;
 for(const entry of log||[]){
  if(entry.ev!=='gaze'){
   if(entry.ev==='gaze_null'||entry.ev==='gaze_out_of_bounds')previous=null;
   continue;
  }
  const x=entry.rawX,y=entry.rawY, w=entry.w,h=entry.h;
  if(![x,y,w,h].every(finite)) {previous=null;continue;}
  // A tape measurement is a better starting point than the face-based distance guess.
  // If a physical viewing distance was measured, it takes precedence over noisy face estimates.
  const d=distanceSource==='tape measure'&&fallbackDistanceCm>0?fallbackDistanceCm:
    (Number(entry.d)>0?Number(entry.d):fallbackDistanceCm);
  const hasScale=pxPerCm>0&&d>0;
  const angleX=hasScale?atanPos(x,w/2,pxPerCm,d,false):null;
  const angleY=hasScale?atanPos(y,h/2,pxPerCm,d,true):null;
  const smx=finite(entry.smX)?entry.smX:null, smy=finite(entry.smY)?entry.smY:null;
  const tx=finite(entry.targetX)?entry.targetX:null, ty=finite(entry.targetY)?entry.targetY:null;
  const targetAx=hasScale&&tx!==null?atanPos(tx,w/2,pxPerCm,d,false):null;
  const targetAy=hasScale&&ty!==null?atanPos(ty,h/2,pxPerCm,d,true):null;
  const dx=tx===null?null:x-tx,dy=ty===null?null:y-ty;
  const datum={t_ms:entry.t,t_utc_ms:entry.utcMs??null,phase:entry.phase,task_id:entry.taskId,
   attempt:entry.attempt,raw_x_px:x,raw_y_px:y,smoothed_x_px:smx,smoothed_y_px:smy,
   gaze_x_deg:round(angleX),gaze_y_deg:round(angleY),
   smoothed_x_deg:hasScale&&smx!==null?round(atanPos(smx,w/2,pxPerCm,d,false)):null,
   smoothed_y_deg:hasScale&&smy!==null?round(atanPos(smy,h/2,pxPerCm,d,true)):null,
   target_x_px:tx,target_y_px:ty,target_x_deg:round(targetAx),target_y_deg:round(targetAy),
   error_x_px:dx,error_y_px:dy,error_radial_px:dx!==null&&dy!==null?round(Math.hypot(dx,dy)):null,
   error_x_deg:angleX!==null&&targetAx!==null?round(angleX-targetAx):null,
   error_y_deg:angleY!==null&&targetAy!==null?round(angleY-targetAy):null,
   error_radial_deg:angleX!==null&&targetAx!==null&&angleY!==null&&targetAy!==null?
     round(Math.hypot(angleX-targetAx,angleY-targetAy)):null,
   distance_cm:finite(d)?d:null,distance_source:distanceSource,
   delta_t_ms:null,step_px:null,step_deg:null,velocity_px_per_s:null,velocity_deg_per_s:null,
   viewport_w_css_px:w,viewport_h_css_px:h};
  const same=previous&&previous.phase===datum.phase&&previous.task_id===datum.task_id&&
   previous.attempt===datum.attempt&&previous.viewport_w_css_px===w&&previous.viewport_h_css_px===h;
  if(same){
   const dt=datum.t_ms-previous.t_ms;
   if(dt>0&&dt<=maxGap){
    const dp=Math.hypot(x-previous.raw_x_px,y-previous.raw_y_px);
    datum.delta_t_ms=round(dt);datum.step_px=round(dp);datum.velocity_px_per_s=round(dp*1000/dt);
    if(angleX!==null&&previous.gaze_x_deg!==null&&angleY!==null&&previous.gaze_y_deg!==null){
     const da=Math.hypot(angleX-previous.gaze_x_deg,angleY-previous.gaze_y_deg);
     datum.step_deg=round(da);datum.velocity_deg_per_s=round(da*1000/dt);
    }
   }
  }
  samples.push(datum);previous=datum;
 }
 // Exploratory I-VT classification from raw gaze. Do not label as observed eye movement.
 let i=0;
 while(i<samples.length){
  const s=samples[i];
  if(s.velocity_deg_per_s!==null&&s.velocity_deg_per_s>=threshold){
   let j=i+1;
   while(j<samples.length&&samples[j].delta_t_ms!==null&&samples[j].velocity_deg_per_s!==null&&samples[j].velocity_deg_per_s>=threshold)j++;
   const p=samples[Math.max(0,i-1)],q=samples[j-1],intervals=j-i;
   const amp=finite(p.gaze_x_deg)&&finite(q.gaze_x_deg)?
     Math.hypot(q.gaze_x_deg-p.gaze_x_deg,q.gaze_y_deg-p.gaze_y_deg):null;
   if(intervals>=2&&amp!==null&&amp>=0.5){
    events.push({type:'candidate_saccade',method:'exploratory_ivt_raw',phase:s.phase,task_id:s.task_id,
     attempt:s.attempt,start_ms:p.t_ms,end_ms:q.t_ms,duration_ms:q.t_ms-p.t_ms,
     start_x_px:p.raw_x_px,start_y_px:p.raw_y_px,end_x_px:q.raw_x_px,end_y_px:q.raw_y_px,
     amplitude_px:round(Math.hypot(q.raw_x_px-p.raw_x_px,q.raw_y_px-p.raw_y_px)),amplitude_deg:round(amp),
     peak_velocity_deg_per_s:round(Math.max(...samples.slice(i,j).map(x=>x.velocity_deg_per_s))),
     mean_velocity_deg_per_s:round(samples.slice(i,j).reduce((a,x)=>a+x.velocity_deg_per_s,0)/intervals),
     samples:intervals+1});
   }
   i=j;
  }else i++;
 }
 // Candidate fixation = contiguous low-speed interval with enough samples and no data gap.
 i=0;
 while(i<samples.length){
  const first=samples[i];let j=i+1;
  while(j<samples.length&&samples[j].delta_t_ms!==null&&samples[j].velocity_deg_per_s!==null&&
   samples[j].velocity_deg_per_s<threshold)j++;
  const part=samples.slice(i,j),last=part[part.length-1];
  if(part.length>=3&&last.t_ms-first.t_ms>=minFix&&part.every(p=>p.gaze_x_deg!==null)){
   const centerX=part.reduce((v,p)=>v+p.raw_x_px,0)/part.length;
   const centerY=part.reduce((v,p)=>v+p.raw_y_px,0)/part.length;
   const avgX=part.reduce((v,p)=>v+p.gaze_x_deg,0)/part.length;
   const avgY=part.reduce((v,p)=>v+p.gaze_y_deg,0)/part.length;
   const dispersion=Math.max(...part.map(p=>Math.hypot(p.gaze_x_deg-avgX,p.gaze_y_deg-avgY)));
   // Avoid false positives from a slowly wandering gaze path.
   if(dispersion<=3){
    events.push({type:'candidate_fixation',method:'exploratory_ivt_raw',phase:first.phase,task_id:first.task_id,
     attempt:first.attempt,start_ms:first.t_ms,end_ms:last.t_ms,duration_ms:last.t_ms-first.t_ms,
     centroid_x_px:round(centerX),centroid_y_px:round(centerY),centroid_x_deg:round(avgX),
     centroid_y_deg:round(avgY),max_radial_dispersion_deg:round(dispersion),samples:part.length});
   }
  }
  i=Math.max(j,i+1);
 }
 events.sort((a,b)=>a.start_ms-b.start_ms);
 return {parameters:params,samples,events,summary:{raw_gaze_sample_count:samples.length,
  candidate_fixation_count:events.filter(e=>e.type==='candidate_fixation').length,
  candidate_saccade_count:events.filter(e=>e.type==='candidate_saccade').length,
  invalid_prediction_events:(log||[]).filter(e=>e.ev==='gaze_null'||e.ev==='gaze_out_of_bounds').length}};
}
root.GazeKinematics={analyze};
})(typeof window!=='undefined'?window:globalThis);
