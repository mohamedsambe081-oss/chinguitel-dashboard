const charts = {}; const nf = new Intl.NumberFormat('fr-FR',{maximumFractionDigits:0});
const $ = id => document.getElementById(id);
function apiUrl(path){ return `/api/${path.replace(/^\//,'')}`; }
function params(extra={}){ const p=new URLSearchParams(); ['uploadId','dateFrom','dateTo','periodMode','category','package'].forEach(id=>{const el=$(id); if(el&&el.value){const key={uploadId:'upload_id',dateFrom:'date_from',dateTo:'date_to',periodMode:'granularity'}[id]||id;p.set(key,el.value)}}); Object.entries(extra).forEach(([k,v])=>p.set(k,v)); return p; }
function fullPeriodParams(extra={}){ const p=new URLSearchParams(); const up=$('uploadId'); if(up&&up.value)p.set('upload_id',up.value); Object.entries(extra).forEach(([k,v])=>p.set(k,v)); return p; }
async function getJson(path, extra={}){ const p=params(extra); const r=await fetch(apiUrl(path)+(p.toString()?`?${p}`:'')); if(!r.ok) throw new Error(await r.text()); return r.json(); }
async function getJsonFullPeriod(path, extra={}){ const p=fullPeriodParams(extra); const r=await fetch(apiUrl(path)+(p.toString()?`?${p}`:'')); if(!r.ok) throw new Error(await r.text()); return r.json(); }
function money(v){ v=Number(v||0); if(Math.abs(v)>=1e9)return (v/1e9).toFixed(2)+'G'; if(Math.abs(v)>=1e6)return (v/1e6).toFixed(2)+'M'; if(Math.abs(v)>=1e3)return (v/1e3).toFixed(1)+'K'; return nf.format(v); }
function pct(v){return v==null?'N/A':`${Number(v).toFixed(1)}%`}

function pctList(values){ const vals=(values||[]).map(v=>Number(v||0)); const total=vals.reduce((a,b)=>a+b,0)||1; return vals.map(v=>Number((v/total*100).toFixed(1))); }
function pctSeriesByPeriod(series){ const n=Math.max(0,...(series||[]).map(s=>(s.data||[]).length)); const totals=Array.from({length:n},(_,i)=>(series||[]).reduce((a,s)=>a+Number((s.data||[])[i]||0),0)||1); return (series||[]).map(s=>({...s,data:(s.data||[]).map((v,i)=>Number((Number(v||0)/totals[i]*100).toFixed(1)))})); }
function pctAxis(){ return {ticks:{callback:v=>v+'%'}}; }
function drawPct(id,type,data,opt={}){ const originalType=type; if(type==='pie'||type==='doughnut') type='bar'; const o={plugins:{tooltip:{callbacks:{label:x=>`${x.dataset.label||x.label}: ${pct(x.raw)}`}}},scales:{y:pctAxis(),x:{ticks:{maxRotation:45,font:{size:9}}}},...opt}; if(originalType==='pie'||originalType==='doughnut'){ delete o.cutout; } draw(id,type,data,o); }
function periodLabel(){ const v=($('periodMode')&&$('periodMode').value)||'week'; return v==='day'?'Day':(v==='month'?'Month':'Week'); }
function destroy(id){ if(charts[id]){charts[id].destroy(); delete charts[id];} }
const palette=['#2E86AB','#F18F01','#C73E1D','#6A994E','#9D4EDD','#577590','#F94144','#43AA8B','#F3722C','#4D908E','#B56576','#277DA1'];
const colors={DATA:'#2E86AB',VOICE:'#F18F01',MIX:'#6A994E',SMS:'#9D4EDD',OTHERS:'#577590',others:'#577590','PAUG Voice':'#F18F01','PAUG Data':'#2E86AB',Subscription:'#6A994E',Others:'#577590'};
function colorFor(name,i=0){ return colors[name]||colors[String(name||'').toUpperCase()]||palette[i%palette.length]; }
function applyChartColors(data,type){
  const labels=data.labels||[];
  (data.datasets||[]).forEach((ds,i)=>{
    const base=colorFor(ds.label,i);
    if(!ds.backgroundColor){
      ds.backgroundColor=(type==='pie'||type==='doughnut'||(type==='bar' && (data.datasets||[]).length===1))?labels.map((l,j)=>colorFor(l,j)):(base+'99');
    }
    if(!ds.borderColor && ds.type!=='bar') ds.borderColor=base;
  });
  return data;
}
function isPercentDataset(ds,chart){
  const label=String(ds.label||'').toLowerCase();
  return label.includes('%')||label.includes('share')||label.includes('rate')||label.includes('variation')||label.includes('contribution')||String((chart.options.scales&&chart.options.scales.y&&chart.options.scales.y.ticks&&chart.options.scales.y.ticks.callback)||'').includes('%');
}
const percentValueLabels={id:'percentValueLabels',afterDatasetsDraw(chart,args,opts){
  if(!opts || opts.display===false) return;
  const type=chart.config.type;
  if(!['bar','pie','doughnut'].includes(type)) return;
  const ctx=chart.ctx; ctx.save(); ctx.font='11px Arial'; ctx.fillStyle='#111827'; ctx.textAlign='center'; ctx.textBaseline='middle';
  chart.data.datasets.forEach((ds,di)=>{
    const meta=chart.getDatasetMeta(di); if(meta.hidden || (ds.type && ds.type!=='bar' && !['pie','doughnut'].includes(ds.type))) return;
    const vals=(ds.data||[]).map(v=>Number(v)||0); const total=vals.reduce((a,b)=>a+Math.abs(b),0)||1;
    meta.data.forEach((el,i)=>{
      const raw=Number(vals[i]||0); if(!raw && type!=='bar') return;
      const label=(type==='pie'||type==='doughnut'||!isPercentDataset(ds,chart)) ? (raw/total*100) : raw;
      const text=(Number.isFinite(label)?label:0).toFixed(1)+'%';
      if(type==='pie'||type==='doughnut'){
        const p=el.tooltipPosition(); ctx.fillText(text,p.x,p.y);
      }else{
        const p=el.tooltipPosition();
        if(chart.options.indexAxis==='y') { ctx.textAlign='left'; ctx.fillText(text,p.x+10,p.y); ctx.textAlign='center'; }
        else ctx.fillText(text,p.x,p.y-12);
      }
    });
  }); ctx.restore();
}};
if(typeof Chart!=='undefined' && Chart.register){ try{Chart.register(percentValueLabels);}catch(e){} }
function mergePlugins(base,opt){ return {...base,...((opt&&opt.plugins)||{}),valueLabels:{display:true,...(((opt&&opt.plugins)||{}).valueLabels||{})}}; }
function draw(id,type,data,opt={}){ const c=$(id); if(!c || typeof Chart==='undefined') return; destroy(id); const originalType=type; if(type==='pie'||type==='doughnut') type='bar'; if((originalType==='pie'||originalType==='doughnut') && opt){ delete opt.cutout; } data=applyChartColors(data,type); const basePlugins={legend:{position:'bottom',labels:{boxWidth:10,font:{size:10}}},tooltip:{callbacks:{label:x=>`${x.dataset.label||x.label}: ${money(x.raw)}`}},valueLabels:{display:type==='bar'}}; charts[id]=new Chart(c,{type,data,options:{responsive:true,maintainAspectRatio:false,plugins:mergePlugins(basePlugins,opt),scales:{y:{beginAtZero:true,ticks:{callback:v=>money(v)}},x:{ticks:{maxRotation:45,font:{size:9}}}},...opt,plugins:mergePlugins(basePlugins,opt)}}); }
function showTab(tab){ document.querySelectorAll('.tab').forEach(b=>b.classList.toggle('active',b.dataset.tab===tab)); document.querySelectorAll('.screen').forEach(s=>s.classList.toggle('active',s.id===tab)); loadActive(); }
async function loadMeta(){ const m=await getJson('meta/'); const cat=$('category'), pack=$('package'); const cv=cat.value, pv=pack.value; cat.innerHTML='<option value="">All</option>'; (m.categories||[]).forEach(x=>cat.insertAdjacentHTML('beforeend',`<option value="${x}">${x}</option>`)); cat.value=cv; pack.innerHTML='<option value="">All</option>'; (m.packages||[]).forEach(x=>pack.insertAdjacentHTML('beforeend',`<option value="${x}">${x}</option>`)); pack.value=pv; ['dateFrom','dateTo'].forEach(id=>{const el=$(id); if(m.date_min)el.min=m.date_min; if(m.date_max)el.max=m.date_max;}); if(m.date_min&&!$('dateFrom').value)$('dateFrom').value=m.date_min; if(m.date_max&&!$('dateTo').value)$('dateTo').value=m.date_max; }
async function loadKpisTo(boxId){ const k=await getJson('kpis/'); const box=$(boxId); if(!box)return; box.innerHTML=''; [['Total revenue',money(k.total_revenue),'#0070C0'],['Average/day',money(k.daily_average),'#0070C0'],['Packages',k.packages||0,'#6B2D8E'],['WoW %',pct(k.wow_percent), k.wow_percent>=0?'#0070C0':'#6B2D8E']].forEach(a=>box.insertAdjacentHTML('beforeend',`<article class="kpi" style="--c:${a[2]}"><span>${a[0]}</span><strong>${a[1]}</strong></article>`));}
async function loadOverview(){
  try{
    const k=await getJsonFullPeriod('kpis/');
    const sub=Number(k.total_revenue||0); const grand=sub; const pv=0,pd=0,ot=0;
    [['ovPv',pv],['ovPd',pd],['ovSub',sub],['ovOt',ot]].forEach(([id,val])=>{ const pctEl=$(id+'Pct'), revEl=$(id+'Rev'); if(pctEl)pctEl.textContent=grand?Math.round(val/grand*100)+'%':'0%'; if(revEl)revEl.textContent=(id==='ovSub'?'':'To import · ')+money(val)+' MRU'; });
    draw('overDonut','doughnut',{labels:['PAUG Voice','PAUG Data','Subscription','Others'],datasets:[{data:[pv,pd,sub,ot],backgroundColor:['#6B2D8E','#0070C0','#0070C0','#6B2D8E'],borderWidth:0}]},{cutout:'64%'});
  }catch(e){ console.error('Overview KPI load error',e); }
  try{
    const adv=await getJsonFullPeriod('advanced-dashboard/');
    const weekly=(adv.weekly&&adv.weekly.revenue)||[];
    draw('overLine','line',{labels:(adv.weekly&&adv.weekly.labels)||[],datasets:[{label:'Subscription',data:weekly,borderColor:'#0070C0',backgroundColor:'rgba(0,112,192,.08)',tension:.25},{label:'PAUG Voice',data:weekly.map(()=>0),borderColor:'#6B2D8E',tension:.25},{label:'PAUG Data',data:weekly.map(()=>0),borderColor:'#0070C0',tension:.25},{label:'Others',data:weekly.map(()=>0),borderColor:'#6B2D8E',tension:.25}]});
    renderOverviewVariationTable(adv);
  }catch(e){ console.error('Overview trend load error',e); }
  if(typeof loadDemandDashboard==='function'){
    await loadDemandDashboard(true);
    // After moving the percentage dashboard into Overview, resize charts after layout is visible.
    setTimeout(()=>Object.values(charts).forEach(ch=>ch && ch.resize && ch.resize()),80);
    setTimeout(()=>Object.values(charts).forEach(ch=>ch && ch.resize && ch.resize()),350);
  }
}
async function loadSubscription(){ await loadKpisTo('subKpis'); const adv=await getJson('advanced-dashboard/'); const labels=adv.category_share.labels||[], vals=adv.category_share.revenue||[], total=vals.reduce((a,b)=>a+Number(b||0),0)||1; ['VOICE','DATA','MIX','SMS','OTHERS'].forEach(cat=>{let i=labels.findIndex(x=>String(x).toUpperCase()===cat); let v=i>=0?vals[i]:0; $(cat.toLowerCase()+'Pct').textContent=Math.round(v/total*100)+'%'; $(cat.toLowerCase()+'Rev').textContent=money(v)+' MRU';}); draw('subCat','line',{labels:adv.category_evolution.labels,datasets:(adv.category_evolution.series||[]).map(s=>({label:s.name,data:s.data,borderColor:colors[s.name]||'#999',backgroundColor:'rgba(0,112,192,.04)',tension:.25}))}); $('subDonutLbl').textContent=(adv.kpis.reference_period_label?('Reference '+adv.kpis.reference_period_label+': '):'')+(adv.kpis.reference_week||''); draw('subDonut','doughnut',{labels,datasets:[{data:vals,backgroundColor:labels.map(l=>colors[l]||colors[String(l).toUpperCase()]||'#94a3b8'),borderWidth:0}]},{cutout:'62%'}); table('subCompare',adv.wow_table.headers,adv.wow_table.rows,['category','previous','current','change','share']); }
function table(id,heads,rows,keys){ const t=$(id); if(!t)return; t.querySelector('thead').innerHTML='<tr>'+heads.map(h=>`<th>${h}</th>`).join('')+'</tr>'; t.querySelector('tbody').innerHTML=(rows||[]).map(r=>'<tr>'+keys.map(k=>{let v=r[k]; if(k.includes('change')) return `<td class="${Number(v)>=0?'pos':'neg'}">${v==null?'N/A':v+'%'}</td>`; if(k==='share'||k==='contribution') return `<td>${Number(v||0).toFixed(1)}%</td>`; if(typeof v==='number')v=money(v); return `<td>${v??''}</td>`}).join('')+'</tr>').join(''); }
function tablePercent(id,heads,rows,keys){ const t=$(id); if(!t)return; const totals={}; keys.forEach(k=>{ if(k!=='category'&&!k.includes('change')&&k!=='share'&&k!=='contribution') totals[k]=(rows||[]).reduce((a,r)=>a+Number(r[k]||0),0)||1; }); t.querySelector('thead').innerHTML='<tr>'+heads.map(h=>`<th>${h}</th>`).join('')+'</tr>'; t.querySelector('tbody').innerHTML=(rows||[]).map(r=>'<tr>'+keys.map(k=>{let v=r[k]; if(k==='category')return `<td>${v??''}</td>`; if(k.includes('change')) return `<td class="${Number(v)>=0?'pos':'neg'}">${v==null?'N/A':v+'%'}</td>`; if(k==='share'||k==='contribution') return `<td>${Number(v||0).toFixed(1)}%</td>`; return `<td>${((Number(v||0)/totals[k])*100).toFixed(1)}%</td>`;}).join('')+'</tr>').join(''); }

function renderOverviewVariationTable(adv){
  const t=$('overviewVariationTable'); if(!t) return;
  const pl=periodLabel();
  const labels=(adv && adv.weekly && adv.weekly.labels) || [];
  const revenue=(adv && adv.weekly && adv.weekly.revenue) || [];
  const lastIdx=Math.max(0, revenue.length-1);
  const prevIdx=Math.max(0, revenue.length-2);
  const current=Number(revenue[lastIdx]||0);
  const previous=revenue.length>1 ? Number(revenue[prevIdx]||0) : 0;
  const change=previous ? Number(((current-previous)/previous*100).toFixed(1)) : (current ? 100 : 0);
  if($('overviewVariationTitle')) $('overviewVariationTitle').textContent=pl+' variation — selected period vs previous '+pl.toLowerCase();
  if($('overviewVariationSub')) $('overviewVariationSub').textContent=(labels[prevIdx]||'Previous')+' → '+(labels[lastIdx]||'Selected');
  const rows=[
    {offer:'PAUG VOICE',previous:0,current:0,change:0,status:'To import'},
    {offer:'PAUG DATA',previous:0,current:0,change:0,status:'To import'},
    {offer:'SUBSCRIPTION',previous,current,change,status:'Imported data'},
    {offer:'OTHERS',previous:0,current:0,change:0,status:'To import'}
  ];
  const totalCurrent=rows.reduce((a,r)=>a+Number(r.current||0),0)||1;
  rows.forEach(r=>{ r.contribution=Number((Number(r.current||0)/totalCurrent*100).toFixed(1)); });
  t.querySelector('thead').innerHTML='<tr><th>Offer</th><th>Previous '+pl+'</th><th>Selected '+pl+'</th><th>Variation %</th><th>Contribution %</th><th>Status</th></tr>';
  t.querySelector('tbody').innerHTML=rows.map(r=>`<tr><td>${r.offer}</td><td>${money(r.previous)}</td><td>${money(r.current)}</td><td class="${Number(r.change)>=0?'pos':'neg'}">${pct(r.change)}</td><td>${r.contribution.toFixed(1)}%</td><td>${r.status}</td></tr>`).join('');
}
async function loadTimeSeries(){ const adv=await getJson('advanced-dashboard/'); const pl=periodLabel(); if($('tsRevenueeTitle'))$('tsRevenueeTitle').textContent='Revenuee by '+pl; if($('tsStackedTitle'))$('tsStackedTitle').textContent='Stacked Category Revenuee by '+pl; draw('weeklyRevenuee','bar',{labels:adv.weekly.labels,datasets:[{label:'Revenuee',data:adv.weekly.revenue,backgroundColor:'rgba(0,112,192,.55)'}]}); draw('wowRate','bar',{labels:adv.weekly.labels,datasets:[{label:'WoW %',data:adv.weekly.wow,backgroundColor:(adv.weekly.wow||[]).map(v=>Number(v)>=0?'#0070C0':'#6B2D8E')}]},{plugins:{legend:{display:false},tooltip:{callbacks:{label:x=>pct(x.raw)}}},scales:{y:{beginAtZero:false,ticks:{callback:v=>v+'%'}}}}); draw('stacked','line',{labels:adv.stacked.labels,datasets:(adv.stacked.series||[]).map(s=>({label:s.name,data:s.data,borderColor:colors[s.name]||'#999',backgroundColor:(colors[s.name]||'#999')+'33',fill:true,tension:.25}))},{scales:{x:{stacked:true},y:{stacked:true,ticks:{callback:v=>money(v)}}}}); }
async function loadAnalytics(){
  const a=await getJson('advanced-dashboard/');
  const gran=(($('periodMode')&&$('periodMode').value)||'week').toLowerCase();
  const pl=periodLabel();
  const changeName = gran==='day' ? 'DoD' : (gran==='month' ? 'MoM' : 'WoW');

  if($('anKpiTitle')) $('anKpiTitle').innerHTML='<span>1</span>'+pl+' Revenuee Summary — KPI Cards';
  if($('anMaTitle')) $('anMaTitle').textContent='2. '+pl+' Revenuee Trend with Moving Average';
  if($('anAvgTitle')) $('anAvgTitle').textContent=pl+' Revenuee Overview';
  if($('anRevenueeBarsTitle')) $('anRevenueeBarsTitle').textContent='3. '+pl+' Revenuee Bars';
  if($('anWowTitle')) $('anWowTitle').textContent=changeName+' Change Rate (%)';
  if($('anCatVDTitle')) $('anCatVDTitle').textContent='4. VOICE & DATA '+pl+' Revenuee';
  if($('anCatMOTitle')) $('anCatMOTitle').textContent='MIX · SMS · OTHERS '+pl+' Revenuee';
  if($('anDataTop5Title')) $('anDataTop5Title').textContent='Top 5 DATA Packs — '+pl+' Evolution';
  if($('anTableTitle')) $('anTableTitle').textContent=changeName+' Comparison Table';
  if($('anStackedTitle')) $('anStackedTitle').textContent='Stacked Area by '+pl;
  if($('anTop15Title')) $('anTop15Title').textContent='7. Top 15 Packages — Reference '+pl;

  const k=a.kpis||{};
  const box=$('anKpis');
  if(box){
    box.innerHTML='';
    [['Reference '+(k.reference_period_label||pl),k.reference_week||'—','#0070C0'],['Ref revenue',money(k.reference_revenue),'#0070C0'],['Daily average',money(k.daily_average),'#6B2D8E'],['Last '+changeName,pct(k.last_wow),Number(k.last_wow)>=0?'#0070C0':'#6B2D8E']]
      .forEach(x=>box.insertAdjacentHTML('beforeend',`<article class="kpi" style="--c:${x[2]}"><span>${x[0]}</span><strong>${x[1]}</strong></article>`));
  }

  // IMPORTANT: these two charts now use the selected period (Day / Week / Month), not fixed daily/monthly data.
  const periodLabels=(a.weekly&&a.weekly.labels)||[];
  const periodRevenuee=(a.weekly&&a.weekly.revenue)||[];
  const maWindow = gran==='day' ? 7 : 3;
  const movingAvg = periodRevenuee.map((_,i)=>{
    const slice=periodRevenuee.slice(Math.max(0,i-maWindow+1), i+1).map(Number);
    return slice.length ? Math.round(slice.reduce((x,y)=>x+y,0)/slice.length) : 0;
  });
  draw('dailyMa','line',{labels:periodLabels,datasets:[{label:pl+' Revenuee',data:periodRevenuee,borderColor:'#0070C0',tension:.2},{label:'MA'+maWindow,data:movingAvg,borderColor:'#6B2D8E',tension:.2}]});
  draw('monthlyAvg','bar',{labels:periodLabels,datasets:[{label:pl+' revenue',data:periodRevenuee,backgroundColor:'rgba(107,45,142,.55)'}]});
  draw('anWeeklyBars','bar',{labels:periodLabels,datasets:[{label:pl+' revenue',data:periodRevenuee,backgroundColor:'rgba(0,112,192,.55)'}]});
  draw('anWow','bar',{labels:periodLabels,datasets:[{label:changeName+' %',data:(a.weekly&&a.weekly.wow)||[],backgroundColor:((a.weekly&&a.weekly.wow)||[]).map(v=>Number(v)>=0?'#0070C0':'#6B2D8E')}]},{plugins:{legend:{display:false}},scales:{y:{ticks:{callback:v=>v+'%'}}}});

  const allCatPct=pctSeriesByPeriod(a.category_evolution.series||[]);
  const vd=allCatPct.filter(s=>['VOICE','DATA'].includes(s.name));
  const mo=allCatPct.filter(s=>['MIX','SMS','OTHERS'].includes(s.name));
  drawPct('catVD','line',{labels:a.category_evolution.labels,datasets:vd.map(s=>({label:s.name+' %',data:s.data,borderColor:colors[s.name],tension:.25}))});
  drawPct('catMO','line',{labels:a.category_evolution.labels,datasets:mo.map(s=>({label:s.name+' %',data:s.data,borderColor:colors[s.name],tension:.25}))});
  drawPct('dataTop10','bar',{labels:a.data_top10.labels,datasets:[{label:'Revenue Share %',data:pctList(a.data_top10.revenue),backgroundColor:'rgba(0,112,192,.6)'}]},{indexAxis:'y',scales:{x:pctAxis(),y:{ticks:{font:{size:9}}}}});
  drawPct('dataTop5','line',{labels:a.data_top5_trend.labels,datasets:pctSeriesByPeriod(a.data_top5_trend.series||[]).map(s=>({label:s.name+' %',data:s.data,tension:.25}))});
  drawPct('anPie','pie',{labels:a.category_share.labels,datasets:[{data:pctList(a.category_share.revenue),backgroundColor:a.category_share.labels.map(l=>colors[l]||'#94a3b8')}]});
  tablePercent('anWowTable',a.wow_table.headers,a.wow_table.rows,['category','previous','current','change','share']);
  drawPct('anStacked','line',{labels:a.stacked.labels,datasets:pctSeriesByPeriod(a.stacked.series||[]).map(s=>({label:s.name+' %',data:s.data,borderColor:colors[s.name]||'#999',backgroundColor:(colors[s.name]||'#999')+'33',fill:true,tension:.25}))},{scales:{x:{stacked:true},y:{stacked:true,ticks:{callback:v=>v+'%'}}}});
  drawPct('top15','bar',{labels:a.top15.labels,datasets:[{label:'Revenue Share %',data:a.top15.share||pctList(a.top15.revenue),backgroundColor:'rgba(107,45,142,.6)'}]},{indexAxis:'y',scales:{x:pctAxis(),y:{ticks:{font:{size:9}}}}});
  heatmap(a.heatmap);
}
function heatmap(h){ const box=$('heatmap'); const weeks=h.weeks||[]; const rows=h.days||[]; const days=['Mon','Tue','Wed','Thu','Fri','Sat','Sun']; box.innerHTML='<div></div>'+weeks.map(w=>`<div class="hm-head">${w}</div>`).join(''); days.forEach(d=>{box.insertAdjacentHTML('beforeend',`<div class="hm-lbl">${d}</div>`); weeks.forEach(w=>{const r=rows.find(x=>x.week===w&&x.day===d)||{revenue:0,level:0}; box.insertAdjacentHTML('beforeend',`<div class="hm-cell" style="--a:${0.12+(r.level||0)*.16}" title="${w} ${d}: ${money(r.revenue)}">${r.revenue?money(r.revenue):''}</div>`);});}); }

function drCompareTable(obj){
  const rows=obj?.rows||[], headers=obj?.headers||[];
  if(!rows.length) return '<table class="wr-ppt-table"><tbody><tr><td>No data</td></tr></tbody></table>';
  const keys=['category','d0','d1','d2','d3','d4','d5','d6','total','change'];
  return `<table class="wr-ppt-table"><thead><tr>${headers.map(h=>`<th>${h}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${keys.map(k=>{let v=r[k]; if(k==='change') return `<td class="${wrRateClass(v)}">${wrRate(v)}</td>`; if(k!=='category') v=wrFmtMillions(v); return `<td>${v??''}</td>`}).join('')}</tr>`).join('')}</tbody></table>`;
}
function drDayKpis(days){
  return `<div class="wr-kpi-row dr-seven">${(days||[]).map(d=>`<div class="wr-kpi"><span>${d.day}</span><strong>${wrFmtMillions(d.revenue)}M</strong><small>${wrRate(d.change)} · ${d.packages} packs</small></div>`).join('')}</div>`;
}
function drPackageTables(tables){
  return `<div class="dr-pack-grid">${(tables||[]).map(t=>`<div>${wrTopPackageTable(t.label,t.rows)}</div>`).join('')}</div>`;
}
async function loadDailyReport(){
  const weekSel=$('dailyReportWeek');
  const selectedBefore=weekSel?weekSel.value:'';
  const a=await getJson('daily-report/', selectedBefore?{week_id:selectedBefore}:{});
  if(weekSel){
    const cur=a.selected_week?.id || '';
    weekSel.innerHTML=(a.weeks||[]).map(w=>`<option value="${w.id}">${w.label}</option>`).join('');
    weekSel.value=cur;
    weekSel.onchange=()=>loadDailyReport();
  }
  const deck=$('dailyReportDeck'); if(!deck) return;
  const k=a.kpis||{}, dr=a.daily_revenue||{}, cad=a.category_daily||{}, days=a.day_kpis||[], groups=a.groups||[];
  const selected=a.selected_week?.label||'—';
  const dateText=a.report_date||new Date().toLocaleDateString('fr-FR');
  deck.innerHTML=`
    <article class="wr-slide"><div class="wr-date">${dateText}</div><h3 class="wr-section-title">Daily Revenuee & KPI</h3><div class="wr-kpi-row"><div class="wr-kpi"><span>Total Week Revenuee</span><strong>${wrFmtMoney(k.selected_revenue)}</strong></div><div class="wr-kpi"><span>Avg / Day</span><strong>${wrFmtMoney(k.avg_daily)}</strong></div><div class="wr-kpi"><span>Best Day</span><strong>${k.best_day||'—'}</strong></div><div class="wr-kpi"><span>Best Day Revenuee</span><strong>${wrFmtMoney(k.best_day_revenue)}</strong></div><div class="wr-kpi"><span>Sun vs Mon</span><strong class="${wrRateClass(k.change_monday_sunday)}">${wrRate(k.change_monday_sunday)}</strong></div></div><div class="wr-box"><h4>Total Revenuee by Day</h4><canvas id="drTotalRevenuee"></canvas></div></article>
    <article class="wr-slide"><div class="wr-date">${dateText}</div><h3 class="wr-section-title">7 Days KPI</h3>${drDayKpis(days)}<div class="wr-note">Chaque carte représente un jour de la semaine sélectionnée.</div></article>
    <article class="wr-slide"><div class="wr-date">${dateText}</div><h3 class="wr-section-title">DATA / VOICE / MIX / SMS / Others by Day</h3><div class="wr-box"><canvas id="drCategoryDaily"></canvas></div></article>
    <article class="wr-slide"><div class="wr-date">${dateText}</div><h3 class="wr-section-title">Day by Day Comparison</h3><p class="wr-subtitle">${selected}</p>${drCompareTable(a.category_compare)}</article>
    <article class="wr-slide"><div class="wr-date">${dateText}</div><h3 class="wr-section-title">Top Packages by Day</h3>${drPackageTables(a.day_package_tables||[])}</article>
    ${groups.map((g,i)=>`<article class="wr-slide"><div class="wr-date">${dateText}</div><h3 class="wr-section-title">Packs rev — Daily</h3><p class="wr-subtitle">${g.name}</p><div class="wr-pack-layout"><div class="wr-box"><canvas id="drGroupChart${i}"></canvas></div><div>${wrTopPackageTable('Top packs in selected week',g.top_week)}</div></div></article>`).join('')}
`;
  drawPptTrend('drTotalRevenuee',dr.labels||[],dr.revenue||[],dr.change_rate||[],'Daily Revenuee','#0070C0');
  drawPptLine('drCategoryDaily',cad.labels||[],(cad.series||[]).map(s=>({name:s.name,data:s.data,color:colors[s.name]||'#0070C0'})));
  groups.forEach((g,i)=>drawPptTrend('drGroupChart'+i,g.labels||[],g.revenue||[],g.change_rate||[],g.name,'#0070C0'));
}

async function loadActive(){ const id=document.querySelector('.screen.active')?.id; try{ if(id==='overview')await loadOverview(); if(id==='subscription')await loadSubscription(); if(id==='timeseries')await loadTimeSeries(); if(id==='analytics')await loadAnalytics(); if(id==='weeklyreport')await loadWeeklyReport(); if(id==='dailyreport')await loadDailyReport(); if(id==='detail')await loadDetail(); }catch(e){console.error(e);} }
document.addEventListener('DOMContentLoaded',async()=>{ document.querySelectorAll('.tab').forEach(b=>b.addEventListener('click',()=>showTab(b.dataset.tab))); ['applyFilters','uploadId','periodMode','category','package','dateFrom','dateTo'].forEach(id=>{const el=$(id); if(el)el.addEventListener(id==='applyFilters'?'click':'change',()=>loadActive());}); const up=$('uploadId'), del=$('deleteUploadId'), btn=$('deleteUploadBtn'); if(up&&del){up.addEventListener('change',()=>{del.value=up.value; if(btn)btn.disabled=!up.value;});} await loadMeta(); await loadActive(); });

let currentDetailCategory = 'DATA';
function openDetail(cat){
  currentDetailCategory = cat;
  const tab = $('detailTab');
  if(tab){ tab.style.display=''; tab.textContent = cat + ' DETAIL'; }
  showTab('detail');
}
async function loadDetail(){
  const cat = currentDetailCategory || 'DATA';
  const a = await getJson('detail-dashboard/', {category: cat});
  const theme = colors[cat] || '#0070C0';
  const pl=periodLabel(); if($('detailTitle')) $('detailTitle').textContent = cat + ' — Detail'; if($('detailLineTitle')) $('detailLineTitle').textContent='Revenuee by '+pl; if($('detailStatTitle')) $('detailStatTitle').textContent='Full Statistical Table — by '+pl;
  if($('detailSub')) $('detailSub').textContent = 'Detailed dashboard for ' + cat + ' packages using imported revenue data';
  const k = a.kpis || {};
  const box = $('detailKpis');
  if(box){
    box.innerHTML='';
    [['Total revenue',money(k.total_revenue),theme],['Packages',k.packages||0,'#6B2D8E'],['Transactions',k.rows||0,'#0070C0'],['Last WoW',pct(k.last_wow),Number(k.last_wow)>=0?'#0070C0':'#6B2D8E']]
      .forEach(x=>box.insertAdjacentHTML('beforeend',`<article class="kpi" style="--c:${x[2]}"><span>${x[0]}</span><strong>${x[1]}</strong></article>`));
  }
  draw('detailLine','line',{labels:a.weekly.labels,datasets:[{label:cat+' revenue',data:a.weekly.revenue,borderColor:theme,backgroundColor:theme+'22',fill:true,tension:.25}]});
  draw('detailTop','bar',{labels:a.top10.labels,datasets:[{label:'Revenuee',data:a.top10.revenue,backgroundColor:theme+'99'}]},{indexAxis:'y'});
  draw('detailWow','bar',{labels:a.weekly.labels,datasets:[{label:'WoW %',data:a.weekly.wow,backgroundColor:(a.weekly.wow||[]).map(v=>Number(v)>=0?'#0070C0':'#6B2D8E')} ]},{plugins:{legend:{display:false},tooltip:{callbacks:{label:x=>pct(x.raw)}}},scales:{y:{ticks:{callback:v=>v+'%'}},x:{ticks:{maxRotation:45,font:{size:9}}}}});
  draw('detailAvg','line',{labels:a.weekly.labels,datasets:[{label:'Average / transaction',data:a.weekly.average,borderColor:'#6B2D8E',backgroundColor:'rgba(245,158,11,.12)',fill:true,tension:.25}]});
  const st = $('detailStat');
  if(st){
    st.querySelector('tbody').innerHTML = (a.stat_rows||[]).map(r=>`<tr><td>${r.rank}</td><td>${r.period}</td><td>${money(r.revenue)}</td><td class="${Number(r.wow)>=0?'pos':'neg'}">${r.wow==null?'N/A':r.wow+'%'}</td><td>${r.packages}</td><td>${r.top_package}</td><td>${money(r.top_package_revenue)}</td></tr>`).join('');
  }
  const sc = $('detailSubcat');
  if(sc){
    sc.querySelector('tbody').innerHTML = (a.subcategories||[]).map(r=>`<tr><td>${r.rank}</td><td>${r.package}</td><td>${money(r.revenue)}</td><td>${r.share}%</td><td>${r.periods}</td><td>${money(r.average)}</td><td class="${Number(r.trend)>=0?'pos':'neg'}">${r.trend==null?'N/A':r.trend+'%'}</td></tr>`).join('');
  }
  if($('detailSubcatCount')) $('detailSubcatCount').textContent = (a.subcategories||[]).length + ' packages';
}


function drawMoneyAndRate(chartId, labels, revenue, rate, label='Revenuee'){
  draw(chartId,'bar',{
    labels,
    datasets:[
      {type:'bar',label,data:revenue,backgroundColor:'rgba(0,112,192,.55)',yAxisID:'y'},
      {type:'line',label:'Change rate %',data:rate,borderColor:'#6B2D8E',backgroundColor:'rgba(239,68,68,.12)',tension:.25,yAxisID:'y1'}
    ]
  },{plugins:{tooltip:{callbacks:{label:x=>x.dataset.yAxisID==='y1'?pct(x.raw):`${x.dataset.label}: ${money(x.raw)}`}}},scales:{y:{beginAtZero:true,ticks:{callback:v=>money(v)}},y1:{position:'right',grid:{drawOnChartArea:false},ticks:{callback:v=>v+'%'}},x:{ticks:{maxRotation:45,font:{size:9}}}}});
}


function wrFmtMoney(v){ return money(v); }
function wrFmtMillions(v){ return (Number(v||0)/1000000).toFixed(3); }
function wrRateClass(v){ return Number(v)>=0 ? 'wr-positive' : 'wr-negative'; }
function wrRate(v){ return v==null || isNaN(Number(v)) ? 'N/A' : Number(v).toFixed(1)+'%'; }
function wrSimpleTable(rows, valKey='revenue'){
  if(!rows || !rows.length) return '<tr><td colspan="2">No data</td></tr>';
  return rows.map(r=>`<tr><td>${r.package}</td><td>${wrFmtMillions(r[valKey])}</td></tr>`).join('');
}
function wrCompareTable(rows){
  return `<table class="wr-ppt-table"><thead><tr><th>Category</th><th>Last Week</th><th>Selected Week</th><th>Change %</th></tr></thead><tbody>${(rows||[]).map(r=>`<tr><td>${r.category}</td><td>${wrFmtMillions(r.previous)}</td><td>${wrFmtMillions(r.current)}</td><td class="${wrRateClass(r.change)}">${wrRate(r.change)}</td></tr>`).join('')}</tbody></table>`;
}
function wrTopPackageTable(title, rows){
  return `<div><div class="wr-mini-title">${title}</div><table class="wr-ppt-table"><thead><tr><th>Pack</th><th>Millions</th></tr></thead><tbody>${wrSimpleTable(rows)}</tbody></table></div>`;
}
function drawPptTrend(chartId, labels, values, rates, label, color='#0070C0'){
  // Report charts: bar only. Change Rate curve removed by request.
  draw(chartId,'bar',{labels,datasets:[
    {type:'bar',label,data:values,backgroundColor:color+'99',borderColor:color,yAxisID:'y'}
  ]},{plugins:{legend:{position:'bottom',labels:{font:{size:10}}},tooltip:{callbacks:{label:x=>`${x.dataset.label}: ${wrFmtMillions(x.raw)}M`}}},scales:{y:{beginAtZero:true,ticks:{callback:v=>(Number(v)/1000000).toFixed(1)}},x:{ticks:{autoSkip:true,maxTicksLimit:8,maxRotation:0,minRotation:0,font:{size:9}}}}});
}
function drawPptLine(chartId, labels, series){
  draw(chartId,'line',{labels,datasets:series.map(s=>({label:s.name,data:s.data,borderColor:s.color||colors[s.name]||'#0070C0',backgroundColor:(s.color||colors[s.name]||'#0070C0')+'22',tension:.25,pointRadius:2}))},{plugins:{legend:{position:'bottom'}},scales:{y:{beginAtZero:true,ticks:{callback:v=>(Number(v)/1000000).toFixed(1)}},x:{ticks:{autoSkip:true,maxTicksLimit:8,maxRotation:0,minRotation:0,font:{size:9}}}}});
}
/* ── Weekly Report helpers ──────────────────────────────────────────── */
function wrCategoryCompareTable(rows){
  const fmtN=v=>Number(v||0).toLocaleString('fr-FR',{maximumFractionDigits:0});
  const arrow=v=>Number(v)>=0?'▲':'▼';
  const total=(rows||[]).find(r=>r.category==='TOTAL')||{};
  const dataRows=(rows||[]).filter(r=>r.category!=='TOTAL');
  const catLabel=c=>c==='DATA'?'DATA_PAUG_REVENUE':c==='VOICE'?'VOICE_PAUG_REVENUE':c==='SMS'?'SMS_REVENUE':c;
  const rowsHtml=dataRows.map(r=>`<tr>
    <td>${catLabel(r.category)}</td>
    <td>${fmtN(r.previous)}</td><td>${fmtN(r.current)}</td>
    <td class="${wrRateClass(r.change)}">${arrow(r.change)} ${wrRate(r.change)}</td>
    <td class="${wrRateClass(r.change)}">${wrRate(r.change)}</td>
  </tr>`).join('');
  const totRow=`<tr class="wr-total-row">
    <td>TOTAL_REVENUE</td>
    <td>${fmtN(total.previous)}</td><td>${fmtN(total.current)}</td>
    <td class="${wrRateClass(total.change)}">${arrow(total.change||0)} ${wrRate(total.change)}</td>
    <td class="${wrRateClass(total.change)}">${wrRate(total.change)}</td>
  </tr>`;
  return `<table class="wr-ppt-table wr-compare-full"><thead><tr><th>Date</th><th>Prev Week</th><th>Sel Week</th><th>Diff</th><th>Cont.</th></tr></thead><tbody>${rowsHtml}${totRow}</tbody></table>`;
}
function wrPacksPillarsTable(groups){
  const fmtN=v=>Number(v||0).toLocaleString('fr-FR',{maximumFractionDigits:0});
  const arrow=v=>Number(v)>=0?'▲':'▼';
  const totalPrev=groups.reduce((s,g)=>s+(g.previous_top||[]).reduce((a,p)=>a+Number(p.revenue||0),0),0)||1;
  const totalCur=groups.reduce((s,g)=>s+(g.current_top||[]).reduce((a,p)=>a+Number(p.revenue||0),0),0);
  const rows=groups.map(g=>{
    const prev=(g.previous_top||[]).reduce((s,p)=>s+Number(p.revenue||0),0);
    const cur=(g.current_top||[]).reduce((s,p)=>s+Number(p.revenue||0),0);
    const chg=prev?((cur-prev)/prev*100):null;
    const cont=totalPrev?((cur-prev)/totalPrev*100):null;
    return `<tr><td>${g.name}</td><td>${fmtN(prev)}</td><td>${fmtN(cur)}</td>
      <td class="${wrRateClass(chg)}">${arrow(chg||0)} ${wrRate(chg)}</td>
      <td class="${wrRateClass(cont)}">${wrRate(cont)}</td></tr>`;
  }).join('');
  const totChg=totalPrev?((totalCur-totalPrev)/totalPrev*100):null;
  const totRow=`<tr class="wr-total-row"><td>Total subscription</td><td>${fmtN(totalPrev)}</td><td>${fmtN(totalCur)}</td>
    <td class="${wrRateClass(totChg)}">${arrow(totChg||0)} ${wrRate(totChg)}</td>
    <td class="${wrRateClass(totChg)}">${wrRate(totChg)}</td></tr>`;
  return `<div class="wr-arrow-connector">▼</div><table class="wr-ppt-table wr-compare-full"><thead><tr><th>Packs Pillars</th><th>Prev Week</th><th>Sel Week</th><th>Diff</th><th>Cont.</th></tr></thead><tbody>${rows}${totRow}</tbody></table>`;
}
function drawWaterfallBar(id,labels,vals){
  const totalIdx=vals.length-1;
  const bgColors=vals.map((v,i)=>i===totalIdx?'#0070C0':(Number(v)>=0?'#0070C0':'#6B2D8E'));
  draw(id,'bar',{labels,datasets:[{label:'%',data:vals.map(v=>v==null?0:Number(v).toFixed(1)),backgroundColor:bgColors,borderWidth:0}]},{
    plugins:{legend:{display:false},tooltip:{callbacks:{label:x=>`${Number(x.raw).toFixed(1)}%`}}},
    scales:{y:{ticks:{callback:v=>v+'%'},grid:{color:'rgba(0,0,0,.06)'}},x:{ticks:{autoSkip:false,maxRotation:30,font:{size:9}}}}
  });
}
function drawGroupedPackBars(id,prevData,curData,packLabels,prevLabel,curLabel){
  draw(id,'bar',{labels:packLabels,datasets:[
    {label:prevLabel,data:prevData,backgroundColor:'#0070C0bb',borderWidth:0},
    {label:curLabel,data:curData,backgroundColor:'#6B2D8Ebb',borderWidth:0}
  ]},{plugins:{legend:{position:'bottom',labels:{font:{size:9}}}},scales:{y:{beginAtZero:true,ticks:{callback:v=>(Number(v)/1000000).toFixed(2)}},x:{ticks:{autoSkip:false,font:{size:9},maxRotation:30}}}});
}
async function loadWeeklyReport(){
  const weekSel=$('weeklyReportWeek');
  const selectedBefore=weekSel?weekSel.value:'';
  const a=await getJson('weekly-report/', selectedBefore?{week_id:selectedBefore}:{});
  if(weekSel){
    const cur=a.selected_week?.id||'';
    weekSel.innerHTML=(a.weeks||[]).map(w=>`<option value="${w.id}">${w.label}</option>`).join('');
    weekSel.value=cur;
    weekSel.onchange=()=>loadWeeklyReport();
  }
  const deck=$('weeklyReportDeck'); if(!deck) return;
  const k=a.kpis||{}, tr=a.total_revenue||{}, recharge=a.total_recharge||tr, ad=a.avg_daily||{}, cad=a.category_avg_daily||{};
  const selected=a.selected_week?.label||'—', previous=a.previous_week?.label||'No previous week';
  const dateText=a.report_date||new Date().toLocaleDateString('fr-FR');
  const groups=a.groups||[];
  const prevShort=previous.split('→')[0]?.trim()||previous;
  const selShort=selected.split('→')[0]?.trim()||selected;

  /* Slide 5-6 data */
  const compareRows=a.category_compare?.rows||[];
  const totalRow=compareRows.find(r=>r.category==='TOTAL')||{};
  const catRowsNoTotal=compareRows.filter(r=>r.category!=='TOTAL');
  const prevTotal=Number(totalRow.previous||0)||1;
  const catContrib=catRowsNoTotal.map(r=>((Number(r.current||0)-Number(r.previous||0))/prevTotal*100));
  const totalContrib=(Number(totalRow.current||0)-Number(totalRow.previous||0))/prevTotal*100;
  const slide6CatLabels=[...catRowsNoTotal.map(r=>r.category==='DATA'?'PKG_REV':r.category==='VOICE'?'VOICE_PAUG':r.category),'TOTAL'];
  const slide6CatContrib=[...catContrib,totalContrib];
  const packWfLabels=[]; const packWfContrib=[];
  groups.forEach(g=>{
    const prev=(g.previous_top||[]).reduce((s,p)=>s+Number(p.revenue||0),0);
    const cur=(g.current_top||[]).reduce((s,p)=>s+Number(p.revenue||0),0);
    packWfLabels.push(g.name);
    packWfContrib.push(prevTotal?((cur-prev)/prevTotal*100):null);
  });
  const packPrev=groups.reduce((s,g)=>s+(g.previous_top||[]).reduce((a,p)=>a+Number(p.revenue||0),0),0);
  const packCur=groups.reduce((s,g)=>s+(g.current_top||[]).reduce((a,p)=>a+Number(p.revenue||0),0),0);
  packWfLabels.push('Total packs'); packWfContrib.push(prevTotal?((packCur-packPrev)/prevTotal*100):null);

  deck.innerHTML=`
  <!-- SLIDE 2: Weekly Revenuee & Recharge -->
  <article class="wr-slide">
    <div class="wr-slide-header"><div class="wr-date">${dateText}</div><h3 class="wr-section-title">Weekly Revenuee &amp; Recharge</h3></div>
    <div class="wr-kpi-row">
      <div class="wr-kpi"><span>Total Revenuee</span><strong>${wrFmtMoney(k.selected_revenue)}</strong></div>
      <div class="wr-kpi"><span>Last Week</span><strong>${wrFmtMoney(k.previous_revenue)}</strong></div>
      <div class="wr-kpi"><span>Change Rate</span><strong class="${wrRateClass(k.change)}">${wrRate(k.change)}</strong></div>
      <div class="wr-kpi"><span>Avg Rev / Week</span><strong>${wrFmtMoney(k.avg_daily)}</strong></div>
      <div class="wr-kpi"><span>Packages</span><strong>${k.packages||0}</strong></div>
    </div>
    <div class="wr-stacked-charts">
      <div class="wr-box wr-tall"><h4>Total Revenuee</h4><canvas id="wrTotalRevenuee"></canvas></div>
      <div class="wr-box wr-tall"><h4>Total Recharge</h4><canvas id="wrTotalRecharge"></canvas></div>
    </div>
  </article>

  <!-- SLIDE 3: Average Revenue per Week (total) -->
  <article class="wr-slide">
    <div class="wr-slide-header"><div class="wr-date">${dateText}</div><h3 class="wr-section-title">Average Revenue per Week</h3></div>
    <div class="wr-box wr-tall-xl"><h4>Average Revenue per Week (Millions MRU)</h4><canvas id="wrAvgDaily"></canvas></div>
  </article>

  <!-- SLIDE 4: Average Revenue per Week — DATA / VOICE / MIX vertical stack -->
  <article class="wr-slide">
    <div class="wr-slide-header"><div class="wr-date">${dateText}</div><h3 class="wr-section-title">Average Revenue per Week</h3></div>
    <div class="wr-cat-grid">
      <div class="wr-cat-label">Millions</div><div class="wr-box wr-cat-chart"><h4>DATA Average Revenue per Week</h4><canvas id="wrCatData"></canvas></div>
      <div class="wr-cat-label">Millions</div><div class="wr-box wr-cat-chart"><h4>Voice AVG rev</h4><canvas id="wrCatVoice"></canvas></div>
      <div class="wr-cat-label">Millions</div><div class="wr-box wr-cat-chart"><h4>MIX Average Revenue per Week</h4><canvas id="wrCatMix"></canvas></div>
    </div>
  </article>

  <!-- SLIDE 5: Comparison tables (category + packs pillars) -->
  <article class="wr-slide">
    <div class="wr-slide-header"><div class="wr-date">${dateText}</div><h3 class="wr-section-title">Weekly revenue vs last week comparison</h3></div>
    <div class="wr-tables-block">
      ${wrCategoryCompareTable(compareRows)}
      ${wrPacksPillarsTable(groups)}
    </div>
  </article>

  <!-- SLIDE 6: Waterfall contribution bars -->
  <article class="wr-slide">
    <div class="wr-slide-header"><div class="wr-date">${dateText}</div><h3 class="wr-section-title">Weekly revenue vs last week comparison</h3></div>
    <div class="wr-stacked-charts">
      <div class="wr-box wr-tall"><h4>Total Rev — contribution by category (%)</h4><canvas id="wrWfCat"></canvas></div>
      <div class="wr-box wr-tall"><h4>Total Packs — contribution by pillar (%)</h4><canvas id="wrWfPacks"></canvas></div>
    </div>
  </article>

  <!-- SLIDES 7-10: One per pack group (line trend + grouped bars + waterfall) -->
  ${groups.map((g,i)=>`
  <article class="wr-slide">
    <div class="wr-slide-header"><div class="wr-date">${dateText}</div><h3 class="wr-section-title">Packs rev — <em>${g.name}</em></h3></div>
    <div class="wr-box wr-tall-xl"><h4>${g.name} — Weekly Revenuee (Millions MRU)</h4><canvas id="wrGroupTrend${i}"></canvas></div>
    <div class="wr-pack-bottom">
      <div class="wr-box wr-pack-grouped"><h4>${g.name} — Prev vs Current by pack</h4><canvas id="wrGroupBars${i}"></canvas></div>
      <div class="wr-box wr-pack-wf"><h4>${g.name} — Change % by pack</h4><canvas id="wrGroupWf${i}"></canvas></div>
    </div>
  </article>`).join('')}

  <!-- SLIDE 11: Data Packs (MauriNet + Raha + Beinatna) -->
  <article class="wr-slide">
    <div class="wr-slide-header"><div class="wr-date">${dateText}</div><h3 class="wr-section-title">Data Packs rev</h3></div>
    <div class="wr-box wr-tall-xl"><h4>MauriNet &amp; MauriNet + Raha + Beinatna (Millions MRU)</h4><canvas id="wrDataCombo"></canvas></div>
  </article>
  `;

  /* Draw all charts */
  drawPptTrend('wrTotalRevenuee',tr.labels||[],tr.revenue||[],tr.change_rate||[],'Total Revenuee','#0070C0');
  drawPptTrend('wrTotalRecharge',recharge.labels||[],recharge.revenue||[],recharge.change_rate||[],'Total Recharge','#0070C0');
  drawPptTrend('wrAvgDaily',ad.labels||[],ad.total||[],ad.change_rate||[],'Average Revenue per Week','#0070C0');
  const catSeries=Object.fromEntries((cad.series||[]).map(s=>[String(s.name).toUpperCase(),s.data]));
  const labs=cad.labels||[];
  [['DATA','wrCatData','#0070C0'],['VOICE','wrCatVoice','#6B2D8E'],['MIX','wrCatMix','#6B2D8E']].forEach(([name,id,color])=>drawPptTrend(id,labs,catSeries[name]||[],[],name,color));
  drawWaterfallBar('wrWfCat',slide6CatLabels,slide6CatContrib);
  drawWaterfallBar('wrWfPacks',packWfLabels,packWfContrib);
  groups.forEach((g,i)=>{
    drawPptTrend('wrGroupTrend'+i,g.labels||[],g.revenue||[],g.change_rate||[],g.name,'#0070C0');
    const prevPacks=g.previous_top||[], curPacks=g.current_top||[];
    const allPacks=[...new Set([...prevPacks.map(p=>p.package),...curPacks.map(p=>p.package)])];
    const pm=Object.fromEntries(prevPacks.map(p=>[p.package,Number(p.revenue||0)]));
    const cm=Object.fromEntries(curPacks.map(p=>[p.package,Number(p.revenue||0)]));
    drawGroupedPackBars('wrGroupBars'+i,allPacks.map(p=>pm[p]||0),allPacks.map(p=>cm[p]||0),allPacks,prevShort,selShort);
    const wfLabels=[...allPacks,g.name];
    const gPrev=prevPacks.reduce((s,p)=>s+Number(p.revenue||0),0);
    const gCur=curPacks.reduce((s,p)=>s+Number(p.revenue||0),0);
    const wfVals=allPacks.map(p=>{const pv=pm[p]||0,cv=cm[p]||0; return pv?(cv-pv)/pv*100:null;});
    wfVals.push(gPrev?(gCur-gPrev)/gPrev*100:null);
    drawWaterfallBar('wrGroupWf'+i,wfLabels,wfVals);
  });
  const combo=a.data_packs_combo||{};
  drawPptLine('wrDataCombo',combo.labels||[],(combo.series||[]).map((s,i)=>({name:s.name,data:s.data,color:i?'#0070C0':'#0070C0'})));
}
const exportBtn=document.getElementById('exportPptx');
const pptModal=document.getElementById('pptModal');
const openPptSelector=document.getElementById('openPptSelector');
const closePptModal=document.getElementById('closePptModal');
const applyPptSelectionBtn=document.getElementById('applyPptSelection');
const exportPptSelected=document.getElementById('exportPptSelected');
function syncPptOptions(source){
  if(!source) return;
  const input=source.target && source.target.matches('input[type="checkbox"]') ? source.target : null;
  if(!input) return;
  document.querySelectorAll(`.ppt-options input[value="${input.value}"]`).forEach(x=>{ if(x!==input) x.checked=input.checked; });
}
document.querySelectorAll('.ppt-options').forEach(box=>box.addEventListener('change',syncPptOptions));
if(openPptSelector && pptModal){
 openPptSelector.addEventListener('click',()=>pptModal.classList.remove('hidden'));
}
if(closePptModal && pptModal){
 closePptModal.addEventListener('click',()=>pptModal.classList.add('hidden'));
}
if(applyPptSelectionBtn && pptModal){
 applyPptSelectionBtn.addEventListener('click',()=>pptModal.classList.add('hidden'));
}
if(exportPptSelected){
 exportPptSelected.addEventListener('click',exportWithSelection);
}

function tableCustom(id, heads, rows, cells){
  const t=$(id); if(!t) return;
  t.querySelector('thead').innerHTML='<tr>'+heads.map(h=>`<th>${h}</th>`).join('')+'</tr>';
  t.querySelector('tbody').innerHTML=(rows||[]).map(r=>'<tr>'+cells.map(fn=>`<td>${fn(r)}</td>`).join('')+'</tr>').join('');
}
async function loadDemandDashboard(useFullPeriod=false){
  let a;
  try{
    a= useFullPeriod ? await getJsonFullPeriod('demand-dashboard/') : await getJson('demand-dashboard/');
  }catch(err){
    console.error('Percentage dashboard load error', err);
    ['demandRanking','popularityEvolution','cannibalization','avgRevenuePack','periodRevenue','paretoChart'].forEach(id=>{
      const c=$(id); if(c){ const ctx=c.getContext('2d'); ctx.clearRect(0,0,c.width,c.height); ctx.font='14px Arial'; ctx.fillStyle='#6B2D8E'; ctx.fillText('No data loaded for this chart',20,40); }
    });
    return;
  }
  draw('demandRanking','bar',{labels:a.demand_ranking.labels,datasets:[{label:'Share %',data:a.demand_ranking.share,backgroundColor:'rgba(0,112,192,.65)'}]},{indexAxis:'y',plugins:{tooltip:{callbacks:{label:x=>x.raw+'%'}}},scales:{x:{ticks:{callback:v=>v+'%'}}}});
  draw('popularityEvolution','line',{labels:a.popularity_evolution.labels,datasets:(a.popularity_evolution.series||[]).map(s=>({label:s.name,data:s.data,tension:.25}))},{plugins:{tooltip:{callbacks:{label:x=>x.raw+'%'}}},scales:{y:{ticks:{callback:v=>v+'%'}}}});
  draw('cannibalization','line',{labels:a.cannibalization.labels,datasets:(a.cannibalization.series||[]).map(s=>({label:s.name,data:s.data,tension:.25}))});
  drawPct('avgRevenuePack','bar',{labels:a.demand_ranking.labels,datasets:[{label:'Revenue Share %',data:a.demand_ranking.share,backgroundColor:'rgba(107,45,142,.6)'}]},{indexAxis:'y',scales:{x:pctAxis(),y:{ticks:{font:{size:9}}}}});
  drawPct('periodRevenue','bar',{labels:a.period_revenue.labels,datasets:[{label:'Period Share %',data:a.period_revenue.share,backgroundColor:'rgba(0,112,192,.55)'}]});
  drawPct('paretoChart','bar',{labels:a.pareto.labels,datasets:[{label:'Revenue Share %',data:pctList(a.pareto.revenue),backgroundColor:'rgba(0,112,192,.55)',yAxisID:'y'},{type:'line',label:'Cumulative %',data:a.pareto.cum_share,borderColor:'#6B2D8E',yAxisID:'y'}]},{scales:{y:{min:0,max:100,ticks:{callback:v=>v+'%'}},x:{ticks:{maxRotation:60,font:{size:9}}}}});
  tableCustom('segmentsTable',['Package','Share %','Trend %','Segment'],a.performance_segments,[r=>r.package,r=>r.share+'%',r=>r.trend==null?'N/A':`<span class="${Number(r.trend)>=0?'pos':'neg'}">${r.trend}%</span>`,r=>r.segment]);
  const rows=[...(a.cash_cows||[]).map(r=>({...r,type:'Cash cow'})),...(a.low_profit||[]).map(r=>({...r,type:'Low profitability'}))];
  tableCustom('cashLowTable',['Type','Package','Share %'],rows,[r=>r.type,r=>r.package,r=>r.share+'%']);
}
async function loadML(){
  const a=await getJson('ml-report/');
  tableCustom('mlAnomalies',['Date','Package','Category','Revenuee','Z-score','Method'],a.anomalies?.rows||[],[r=>r.date,r=>r.package,r=>r.category,r=>money(r.revenue),r=>r.z_score,r=>r.method]);
  const fc=a.forecast||{};
  const hist=fc.history||[];
  const pts=fc.points||[];
  const labels=[...hist.map(p=>p.date),...pts.map(p=>p.date)];
  const actual=[...hist.map(p=>p.y),...pts.map(()=>null)];
  const forecast=[...hist.map(()=>null),...pts.map(p=>p.yhat)];
  const lower=[...hist.map(()=>null),...pts.map(p=>p.yhat_lower)];
  const upper=[...hist.map(()=>null),...pts.map(p=>p.yhat_upper)];
  draw('mlForecast','line',{labels,datasets:[{label:'Actual weekly revenue',data:actual,borderColor:'#6B2D8E',backgroundColor:'rgba(107,45,142,.10)',tension:.25},{label:`Forecast ${fc.method||'ARIMA'}`,data:forecast,borderColor:'#0070C0',backgroundColor:'rgba(0,112,192,.12)',fill:false,tension:.25},{label:'Lower 90%',data:lower,borderColor:'#94a3b8',tension:.25},{label:'Upper 90%',data:upper,borderColor:'#94a3b8',tension:.25}]});
  tableCustom('mlClusters',['Cluster','# Packages','Total','Average','Top packages'],a.clusters||[],[r=>'Cluster '+r.cluster,r=>r.packages,r=>money(r.total),r=>money(r.avg),r=>(r.top_packages||[]).join(', ')]);
  tableCustom('mlTrends',['Package','Status','Trend %','Slope','Last revenue'],a.trends||[],[r=>r.package,r=>r.status,r=>r.trend==null?'N/A':`<span class="${Number(r.trend)>=0?'pos':'neg'}">${r.trend}%</span>`,r=>r.slope,r=>money(r.last_revenue)]);
}
function monthlyCompareTable(rows){
  return `<table class="wr-ppt-table"><thead><tr><th>Category</th><th>Previous Month</th><th>Selected Month</th><th>Change %</th><th>Share %</th></tr></thead><tbody>${(rows||[]).map(r=>`<tr><td>${r.category}</td><td>${wrFmtMillions(r.previous)}</td><td>${wrFmtMillions(r.current)}</td><td class="${wrRateClass(r.change)}">${wrRate(r.change)}</td><td>${Number(r.share||0).toFixed(1)}%</td></tr>`).join('')}</tbody></table>`;
}
async function loadMonthlyReport(){
  const sel=$('monthlyReportMonth'); const selectedBefore=sel?sel.value:'';
  const a=await getJson('monthly-report/', selectedBefore?{month_id:selectedBefore}:{});
  if(sel){ const cur=a.selected_month?.id||''; sel.innerHTML=(a.months||[]).map(m=>`<option value="${m.id}">${m.label}</option>`).join(''); sel.value=cur; sel.onchange=()=>loadMonthlyReport(); }
  const deck=$('monthlyReportDeck'); if(!deck) return;
  const k=a.kpis||{}, mr=a.monthly_revenue||{}, groups=a.groups||[], selected=a.selected_month?.label||'—', previous=a.previous_month?.label||'No previous month';
  deck.innerHTML=`
    <article class="wr-slide"><div class="wr-date">${a.report_date||''}</div><h3 class="wr-section-title">Monthly Revenuee & KPI</h3><div class="wr-kpi-row"><div class="wr-kpi"><span>Total Revenuee</span><strong>${wrFmtMoney(k.selected_revenue)}</strong></div><div class="wr-kpi"><span>Previous Month</span><strong>${wrFmtMoney(k.previous_revenue)}</strong></div><div class="wr-kpi"><span>Change</span><strong class="${wrRateClass(k.change)}">${wrRate(k.change)}</strong></div><div class="wr-kpi"><span>Average / Month</span><strong>${wrFmtMoney(k.avg_daily)}</strong></div><div class="wr-kpi"><span>Packages</span><strong>${k.packages||0}</strong></div></div><div class="wr-box"><canvas id="mrRevenuee"></canvas></div></article>
    <article class="wr-slide"><div class="wr-date">${a.report_date||''}</div><h3 class="wr-section-title">Monthly revenue vs previous month comparison</h3><p class="wr-subtitle">${previous} → ${selected}</p>${monthlyCompareTable(a.category_compare?.rows||[])}</article>
    ${groups.map((g,i)=>`<article class="wr-slide"><div class="wr-date">${a.report_date||''}</div><h3 class="wr-section-title">Packs rev — ${g.name}</h3><div class="wr-pack-layout"><div class="wr-box"><canvas id="mrGroup${i}"></canvas></div><div>${wrTopPackageTable('Top packs in selected month',g.top_month)}</div></div></article>`).join('')}
`;
  drawPptTrend('mrRevenuee',mr.labels||[],mr.revenue||[],mr.change_rate||[],'Monthly Revenuee','#0070C0');
  groups.forEach((g,i)=>drawPptTrend('mrGroup'+i,g.labels||[],g.revenue||[],g.change_rate||[],g.name,'#0070C0'));
}
function selectedPptSections(){
  const boxes=[...document.querySelectorAll('#pptSelectionPage input:checked, #pptModalOptions input:checked')];
  const values=[...new Set(boxes.flatMap(o=>String(o.value||'').split(',')).map(v=>v.trim()).filter(Boolean))];
  if(!values.length) return 'weekly_report,daily_report,monthly_report,kpi,categories,demand,daily,weekly,monthly,packages,detail_wow,forecast,ml,anomalies,tables';
  return values.join(',');
}
function buildExportUrl(sections){
  const url=new URL('/reports/export/', window.location.origin);
  ['uploadId','dateFrom','dateTo','category','package'].forEach(id=>{const el=$(id); if(el&&el.value){const key={uploadId:'upload_id',dateFrom:'date_from',dateTo:'date_to'}[id]||id; url.searchParams.set(key,el.value);}});
  const week=$('weeklyReportWeek') || $('dailyReportWeek'); if(week&&week.value) url.searchParams.set('week_id', week.value);
  const month=$('monthlyReportMonth'); if(month&&month.value) url.searchParams.set('month_id', month.value);
  if(typeof currentDetailCategory !== 'undefined' && currentDetailCategory) url.searchParams.set('detail_category', currentDetailCategory);
  url.searchParams.set('sections',sections);
  return url;
}
function countPptSelections(){
  return document.querySelectorAll('#pptSelectionPage input[type="checkbox"]:checked, #pptModalOptions input[type="checkbox"]:checked').length;
}
function applyPptSelection(){
  const status=$('pptSelectionStatus');
  if(status){
    const n=countPptSelections();
    status.textContent = n ? `${n} element(s) selected` : 'No element selected';
  }
}
function exportWithSelection(){
  applyPptSelection();
  window.location.href=buildExportUrl(selectedPptSections()).toString();
}
function exportDefaultWeeklyReport(){
  showTab('exportselector');
  const first=document.querySelector('#pptSelectionPage input');
  if(first) first.focus();
}

function setAllPptCheckboxes(checked){
  document.querySelectorAll('#pptSelectionPage input[type="checkbox"], #pptModalOptions input[type="checkbox"]').forEach(cb=>{ cb.checked=checked; });
}
document.querySelectorAll('[data-ppt-action="select-all"]').forEach(btn=>btn.addEventListener('click',()=>setAllPptCheckboxes(true)));
document.querySelectorAll('[data-ppt-action="clear-all"]').forEach(btn=>btn.addEventListener('click',()=>setAllPptCheckboxes(false)));
if(document.getElementById('applyPptSelection')) document.getElementById('applyPptSelection').addEventListener('click',applyPptSelection);
if(document.getElementById('exportFromSelection')) document.getElementById('exportFromSelection').addEventListener('click',exportWithSelection);
// Export is done from the visible Apply / Export selection buttons after graph/table selection.
async function loadActive(){ const id=document.querySelector('.screen.active')?.id; try{ if(id==='overview')await loadOverview(); if(id==='ml')await loadML(); if(id==='subscription')await loadSubscription(); if(id==='timeseries')await loadTimeSeries(); if(id==='analytics')await loadAnalytics(); if(id==='weeklyreport')await loadWeeklyReport(); if(id==='dailyreport')await loadDailyReport(); if(id==='monthlyreport')await loadMonthlyReport(); if(id==='exportselector'){} if(id==='detail')await loadDetail(); }catch(e){console.error(e);} }
