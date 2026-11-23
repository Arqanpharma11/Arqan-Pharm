'use strict';
// Runs only in GitHub Actions. It never downloads an image in the storefront.
const fs=require('node:fs');
const html=fs.readFileSync('index.html','utf8');
const master=html.match(/const EXACT_MASTER_ITEMS\s*=\s*\[([\s\S]*?)\n\s*\];/);
if(!master)throw Error('Master catalog missing');
const items=[...master[1].matchAll(/\{\s*name:\s*"([^"]+)"\s*,\s*cat:\s*"([^"]+)"/g)]
  .map((m,i)=>({id:i<4218?i+1:230000+i-4218,name:m[1],cat:m[2]}));
const excluded=(html.match(/const PDF_EXCLUDED_MASTER_POSITIONS\s*=\s*new Set\(\[([^\]]+)\]\)/)||[])[1];
if(!excluded)throw Error('Missing PDF master exclusions');
const exclusions=new Set(excluded.split(',').map(x=>+x.trim()));
if(items.length-exclusions.size!==4489)throw Error('Approved PDF catalog cardinality mismatch');
const start=html.indexOf('const ENGLISH_BRAND_REFERENCE = ');
let english={};
if(start>=0){
  const begin=html.indexOf('{',start),end=html.indexOf('\n};',begin);
  if(begin>=0&&end>=0)english=JSON.parse(html.slice(begin,end+2));
}
const imageStart=html.indexOf('const verifiedImageSeeds = {');
const imageEnd=html.indexOf('const imageSeedBatches',imageStart);
if(imageStart<0||imageEnd<imageStart)throw Error('Image seed map missing');
const known=new Set([...html.slice(imageStart,imageEnd).matchAll(/^\s*'(\d+)':\s*\{/gm)].map(x=>x[1]));
const csvValue=x=>'"'+String(x||'').replace(/"/g,'""').replace(/[\r\n]/g,' ')+'"';
const active=items.filter((x,i)=>!exclusions.has(i+1)&&!known.has(String(x.id)));
active.sort((a,b)=>Number(a.cat==='أدوية')-Number(b.cat==='أدوية')||a.id-b.id);
const cursorFile='data/arkan-v2-cursor.json';
const cursor=fs.existsSync(cursorFile)?JSON.parse(fs.readFileSync(cursorFile,'utf8')):{offset:0};
const offset=Number(cursor.offset||0)%Math.max(1,active.length);
const budget=Math.max(1,Math.min(30,Number(process.env.ARKAN_V2_BATCH_SIZE||24)));
const batch=[...active.slice(offset),...active.slice(0,offset)].slice(0,budget);
const dest='data/arkan-v2-search-input.csv';
fs.writeFileSync(dest,'\uFEFFcode,name,name_en,category\n'+batch.map(x=>[x.id,x.name,english[x.name]?.brand||'',x.cat].map(csvValue).join(',')).join('\n')+'\n');
console.log(JSON.stringify({catalogItems:items.length,uncovered:active.length,excluded:exclusions.size,offset,batch:batch.length}));
function splitCSV(line){
  let out=[],current='',quoted=false;
  for(let i=0;i<line.length;i++){
    const c=line[i];
    if(c==='"'){if(quoted&&line[i+1]==='"'){current+='"';i++;}else quoted=!quoted;}
    else if(c===','&&!quoted){out.push(current);current='';}
    else current+=c;
  }
  out.push(current);return out;
}
if(process.argv.includes('--ingest')){
  const file='results_v2.csv';
  if(!fs.existsSync(file))throw Error('Search results missing; refusing to move cursor');
  const lines=fs.readFileSync(file,'utf8').replace(/^\uFEFF/,'').trim().split(/\r?\n/);
  const fields=splitCSV(lines.shift()),outFile='data/arkan-auto-published-images.json';
  const records=JSON.parse(fs.readFileSync(outFile,'utf8'));records.byId||={};
  const approved=new Map(items.filter((x,i)=>!exclusions.has(i+1)).map(x=>[String(x.id),x]));
  let queued=0,blocked=0;
  for(const line of lines){
    const values=splitCSV(line),r=Object.fromEntries(fields.map((k,i)=>[k,values[i]||'']));
    const product=approved.get(r.code);
    if(!product||r.status!=='auto'||records.byId[r.code]||known.has(r.code))continue;
    if(product.cat==='أدوية'){blocked++;continue;}
    const page=r.source_page||'',url=r.source_url||'';
    if(!/^https:\/\/world\.open(?:food|beauty)facts\.org\/product\/\d+\/?$/.test(page)||
       !/^https:\/\/(?:images|static)\.open(?:food|beauty)facts\.org\//.test(url)||
       !r.name_en||r.name!==product.name){blocked++;continue;}
    records.byId[r.code]={
      url,source:new URL(page).hostname,sourcePage:page,license:'CC BY-SA 3.0',
      catalogName:product.name,englishName:r.name_en,title:r.name_en+' '+r.name,
      status:'pending_independent_ocr_verification'
    };
    queued++;
  }
  if(queued)fs.writeFileSync(outFile,JSON.stringify(records,null,2)+'\n');
  // Advance even if no image was found, preventing endlessly repeating batch one.
  if(lines.length&&active.length)fs.writeFileSync(cursorFile,JSON.stringify({offset:(offset+batch.length)%active.length},null,2)+'\n');
  console.log(JSON.stringify({searched:lines.length,queuedForIndependentOCR:queued,rejectedForAutoPublication:blocked}));
}
