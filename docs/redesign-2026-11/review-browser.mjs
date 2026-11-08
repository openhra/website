// Headless Chrome CDP review. Start each static site on loopback first.
// Defaults: Chrome debug port 9286, plans 8786, organisation 8787.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const output = path.dirname(fileURLToPath(import.meta.url));
const debug = process.env.REDESIGN_CDP || 'http://127.0.0.1:9286';
const sites = {plans: process.env.PLANS_PREVIEW || 'http://127.0.0.1:8786/', openhra: process.env.OPENHRA_PREVIEW || 'http://127.0.0.1:8787/'};
for (const url of [debug, ...Object.values(sites)]) if (new URL(url).hostname !== '127.0.0.1') throw Error('Local review only');
const tabs = await (await fetch(debug + '/json/list')).json();
const tab = tabs.find(t => t.type === 'page');
const ws = new WebSocket(tab.webSocketDebuggerUrl);
await new Promise(resolve => ws.addEventListener('open', resolve, {once:true}));
let sequence = 0;
const pending = new Map();
ws.addEventListener('message', e => {
  const message = JSON.parse(e.data);
  if (pending.has(message.id)) { pending.get(message.id)(message); pending.delete(message.id); }
});
const call = (method, params={}) => new Promise((resolve,reject) => {
  const id=++sequence;
  pending.set(id, msg => msg.error ? reject(Error(JSON.stringify(msg.error))) : resolve(msg.result));
  ws.send(JSON.stringify({id,method,params}));
});
const evaluate = async expression => {
  const r=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});
  if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
  return r.result.value;
};
const assert=(test,message)=>{if(!test)throw Error(message);};
const pause=ms=>new Promise(r=>setTimeout(r,ms));
const wait=async expression=>{for(let i=0;i<200;i++){if(await evaluate(expression))return;await pause(25);}throw Error('Timeout: '+expression);};
const fits=async()=>{
  const result=await evaluate('({client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth})');
  assert(result.scroll<=result.client,'Page overflow: '+JSON.stringify(result));return result;
};
const screenshot=async(name,full=false)=>{
  const params={format:'png',captureBeyondViewport:full};
  if(full){const metrics=await call('Page.getLayoutMetrics');params.clip={x:0,y:0,width:metrics.cssContentSize.width,height:metrics.cssContentSize.height,scale:1};}
  const result=await call('Page.captureScreenshot',params);
  await fs.writeFile(path.join(output,name+'.png'),Buffer.from(result.data,'base64'));
};
const report=[];
try {
  await call('Page.enable');await call('Network.enable');
  // CAPTCHA is not exercised in a local static preview. Block the external script.
  await call('Network.setBlockedURLs',{urls:['https://www.google.com/recaptcha/*']});
  for(const [site,url] of Object.entries(sites)){
    for(const width of [1280,390,320]){
      await call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
      await call('Page.navigate',{url});
      await wait(`location.href.startsWith('${url}') && document.readyState==='complete'`);
      if(site==='plans') await wait('!document.querySelector("#coverage-state").disabled');
      const dimensions=await fits();
      const audit=await evaluate(`(()=>{
        const headings=[...document.querySelectorAll('main h1,main h2,main h3,main h4')].map(h=>({level:Number(h.tagName[1]),text:h.textContent.trim()}));
        const images=[...document.images].every(i=>i.complete && i.naturalWidth>0);
        const links=[...document.querySelectorAll('a[href^="#"]')].every(a=>document.getElementById(a.hash.slice(1)));
        const status=[...document.querySelectorAll('[data-mcp-preview]')].every(n=>/in development/i.test(n.innerText));
        const captcha=document.querySelector('#contact-captcha').getBoundingClientRect();
        const rgb=s=>(s.match(/[0-9.]+/g)||[]).map(Number);
        const luminance=c=>c.slice(0,3).map(v=>v/255).map(v=>v<=0.04045?v/12.92:((v+0.055)/1.055)**2.4).reduce((a,v,i)=>a+v*[0.2126,0.7152,0.0722][i],0);
        const ratios=[...document.querySelectorAll('body *')].filter(n=>n.getBoundingClientRect().height>0&&[...n.childNodes].some(c=>c.nodeType===3&&c.textContent.trim())&&!n.closest('svg')).map(n=>{
          let bg=n;
          while(bg.parentElement&&rgb(getComputedStyle(bg).backgroundColor)[3]===0)bg=bg.parentElement;
          const fg=luminance(rgb(getComputedStyle(n).color)), ground=luminance(rgb(getComputedStyle(bg).backgroundColor));
          return (Math.max(fg,ground)+0.05)/(Math.min(fg,ground)+0.05);
        });
        const minimumTextContrast=Math.min(...ratios);
        return {minimumTextContrast,headings,images,links,status,h1:document.querySelectorAll('h1').length,landmarks:!!document.querySelector('header nav[aria-label]')&&!!document.querySelector('main')&&!!document.querySelector('footer'),captcha:{width:captcha.width,left:captcha.left,right:captcha.right}};
      })()`);
      assert(audit.minimumTextContrast>=4.5,'Text contrast below AA');
      assert(audit.images && audit.links && audit.status && audit.h1===1 && audit.landmarks,'Document audit failed');
      assert(audit.headings.every((h,i)=>i===0||h.level<=audit.headings[i-1].level+1),'Heading level skipped');
      assert(audit.captcha.width>=304&&audit.captcha.left>=0&&audit.captcha.right<=width,'CAPTCHA clipped');
      await screenshot(`${site}-${width}`);
      await screenshot(`${site}-${width}-full`,true);
      await evaluate(`document.querySelector('${site==='plans'?'#mcp':'#agents'}').scrollIntoView()`);
      await screenshot(`${site}-${width}-mcp`);
      if(site==='plans'){
        await evaluate('document.querySelector("#connect").scrollIntoView()');
        await screenshot(`${site}-${width}-connect`);
      }
      await evaluate('window.scrollTo(0,0);document.activeElement.blur()');
      await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
      await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
      assert(await evaluate('document.activeElement.classList.contains("skip-link")'),'Tab did not reach skip link');
      const focus=await evaluate('({outline:getComputedStyle(document.activeElement).outlineWidth,offset:getComputedStyle(document.activeElement).outlineOffset,top:document.activeElement.getBoundingClientRect().top})');
      assert(parseFloat(focus.outline)>=3&&parseFloat(focus.offset)>=5&&focus.top>=0,'Focus indicator missing');
      await call('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:'dark'}]});
      assert(await evaluate('getComputedStyle(document.body).backgroundColor')==='rgb(255, 255, 255)','Dark preference changes white ground');
      await call('Emulation.setEmulatedMedia',{features:[]});
      report.push({site,width,dimensions,minimumTextContrast:Number(audit.minimumTextContrast.toFixed(2)),imagesLoaded:audit.images,anchorsValid:audit.links,headingOrder:true,visibleDevelopmentLabels:true,captcha:audit.captcha,focus,darkPreferenceWhite:true});
    }
    if(site==='plans'){
      let checked=0;
      for(const year of [2026,2027])for(const layer of ['providers','prescriptions','premiums']){
        await evaluate(`document.querySelector('#coverage-year').value='${year}';document.querySelector('#coverage-year').dispatchEvent(new Event('change'));document.querySelector('[data-coverage-layer="${layer}"]').click()`);
        await wait(`document.querySelector('#coverage-download').getAttribute('href').endsWith('${layer}-${year}.json')`);
        for(const state of ['TX','FL','AK','NY','DC']){
          await evaluate(`document.querySelector('#coverage-state').value='${state}';document.querySelector('#coverage-state').dispatchEvent(new Event('change'))`);
          await wait(`document.querySelector('[data-state="${state}"]').getAttribute('data-selected')==='true'`);
          await fits();checked++;
        }
      }
      report.push({coverageSelections:checked,coveragePageFits:true});
    }
    await call('Emulation.setScriptExecutionDisabled',{value:true});
    await call('Page.navigate',{url});await wait(`document.readyState==='complete'`);await fits();
    report.push({site,width:320,scriptDisabledFits:true});
    await call('Emulation.setScriptExecutionDisabled',{value:false});
    await call('Page.navigate',{url});await wait(`document.readyState==='complete'`);
    await evaluate('const wide=document.createElement("div");wide.id="layout-mutant";wide.style.width="1000px";wide.style.height="1px";document.body.append(wide)');
    let rejected=false;try{await fits();}catch{rejected=true;}
    assert(rejected,'Overflow mutant accepted');
    await evaluate('document.querySelector("#layout-mutant").remove()');await fits();
    report.push({site,overflowNegativeControl:true});
  }
  await fs.writeFile(path.join(output,'browser-checks.json'),JSON.stringify(report,null,2)+'\n');
  console.log('PASS: redesign browser review (both sites at 1280/390/320, 30 coverage selections, no-script, dark preference, focus, overflow mutants)');
}finally{ws.close();}
