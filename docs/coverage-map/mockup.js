// Design-only preview. Loads a local static evidence snapshot, never an API.
(async () => {
  const response = await fetch('mockup-data.json');
  if (!response.ok) throw new Error('Static evidence snapshot unavailable');
  const data = await response.json();
  let layer='providers', year='2026', state='TX';
  const $=s=>document.querySelector(s);
  const pretty=n=>n.toLocaleString('en-US');
  const percent=r=>`${(r.percent_tenths/10).toFixed(1)}%`;
  const unit=()=>layer==='premiums'?'rate rows':'issuers';
  const labels={premiums:'Premiums',providers:'Providers',prescriptions:'Prescriptions'};
  function paint(){
    const rows=data.datasets[`${layer}-${year}`];
    const scope=layer==='premiums'?'Published rate rows imported and checked, within each cited catalog. This is source-data coverage, not the percentage of household quotes the API can answer.':'Issuers with ACTIVE '+(layer==='providers'?'network':'formulary')+' data ÷ issuers in the published exchange catalog. Includes dental issuers. This is source availability, not market share.';
    $('#scope').textContent=scope;
    $('#map-title').textContent=`${labels[layer]} source availability by state, ${year}`;
    $('#map-desc').textContent='All 50 states and DC. Exact values and unavailable-data reasons are in the table. Alaska and Hawaii are repositioned and scaled.';
    for(const [st,r] of Object.entries(rows)){
      let fill=r.status==='unknown'?'url(#unknown)':r.status==='quarantined'?'url(#quarantine)':r.percent_tenths===0?'white':r.percent_tenths<250?'var(--teal-100)':r.percent_tenths<500?'var(--teal-300)':r.percent_tenths<750?'var(--teal-600)':'var(--teal-800)';
      const p=$(`#state-${st}`); p.style.fill=fill;p.dataset.selected=st===state;
      p.querySelector('title').textContent=`${data.states[st]}: ${r.status==='unknown'?'Unknown':r.status==='quarantined'?'Quarantined; 0 of '+r.denominator+' active':percent(r)}, ${year}`;
      const callout=$(`[data-callout="${st}"] rect`);if(callout)callout.style.fill=fill;
    }
    const r=rows[state];
    $('#state-name').textContent=data.states[state];
    $('#metric').textContent=r.status==='unknown'?'Unknown':r.status==='quarantined'?'Quarantined':percent(r);
    $('#metric').classList.toggle('small',r.status!=='measured');
    $('#fraction').textContent=r.denominator===null?'A comparable denominator is not available.':`${pretty(r.numerator)} of ${pretty(r.denominator)} ${unit()} ${layer==='premiums'?'verified':'with active data'}`;
    $('#active-partial').textContent=r.active_partial===undefined?'—':pretty(r.active_partial);
    $('#q-count').textContent=r.quarantined===undefined?'—':pretty(r.quarantined);
    $('#u-count').textContent=r.unknown===undefined?'Not measured':pretty(r.unknown);
    $('#source-breakdown').hidden=layer==='premiums';
    $('#detail-note').textContent=r.reason;
    $('#row-source').textContent=r.evidence.length?'Evidence: '+r.evidence.join(', '):'No report for this state, layer and year.';
    $('#table-caption').textContent=`${labels[layer]} · Plan year ${year} · Figures as of November 8, 2026`;
    const body=$('#state-rows');body.replaceChildren();
    for(const [st,name] of Object.entries(data.states).sort((a,b)=>a[1].localeCompare(b[1]))){
      const v=rows[st], tr=document.createElement('tr'), th=document.createElement('th');th.scope='row';th.textContent=name;tr.append(th);
      const number=document.createElement('td'), b=document.createElement('strong');b.textContent=v.status==='unknown'?'Unknown':v.status==='quarantined'?'Quarantined':percent(v);number.append(b);
      const sub=document.createElement('span');sub.className='sub';sub.textContent=v.denominator===null?'Denominator unverified':`${pretty(v.numerator)} / ${pretty(v.denominator)} ${unit()}`;number.append(sub);tr.append(number);
      const note=document.createElement('td');note.textContent=layer==='premiums'?(v.status==='measured'?'Source rows verified':'Unknown availability'):v.quarantined!==undefined?`${v.quarantined} quarantined; ${v.unknown} unknown; ${v.active_partial} active with limits`:'Unknown';const why=document.createElement('span');why.className='sub';why.textContent=v.reason;note.append(why);tr.append(note);body.append(tr);
    }
    $('#announcement').textContent=`${labels[layer]}, ${year}. ${data.states[state]}: ${$('#metric').textContent}. Table updated.`;
  }
  for(const b of document.querySelectorAll('[data-layer]')){b.disabled=false;b.addEventListener('click',()=>{layer=b.dataset.layer;for(const x of document.querySelectorAll('[data-layer]'))x.setAttribute('aria-pressed',x===b);paint()})}
  $('#year').disabled=false;$('#year').addEventListener('change',e=>{year=e.target.value;paint()});
  $('#state').disabled=false;$('#state').addEventListener('change',e=>{state=e.target.value;paint()});
  paint();
})().catch(()=>{document.querySelector('#announcement').textContent='Preview controls unavailable. The saved 2026 provider table remains below.'});
