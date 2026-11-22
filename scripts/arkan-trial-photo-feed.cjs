'use strict';
// A separate, explicitly unverified trial catalogue. Never writes approved seeds.
const fs = require('node:fs');
const html = fs.readFileSync('index.html','utf8');
const m=html.match(/const EXACT_MASTER_ITEMS\s*=\s*\[([\s\S]*?)\n\s*\];/);
if(!m) throw Error('Cannot extract Arqan catalog');
const items=[...m[1].matchAll(/\{\s*name:\s*"([^"]+)"\s*,\s*cat:\s*"([^"]+)"/g)].map((x,i)=>({id:String(i+1),name:x[1],category:x[2]}));
const load=(path,fallback)=>fs.existsSync(path)?JSON.parse(fs.readFileSync(path,'utf8')):fallback;
const config=load('data/arkan-trial-image-config.json',{});
if(config.PUBLISH_DESTINATION!=='isolated_trial_preview_only' ||
   config.ALLOW_UNVERIFIED_IN_PHARMACIST_PORTAL!==false ||
   config.SHOW_UNVERIFIED_BADGE!==true ||
   config.OVERWRITE_ADMIN_APPROVED_IMAGES!==false ||
   Number(config.MIN_CONFIDENCE_SCORE)<95) {
  throw Error('Unsafe trial configuration: refusing to generate image feed');
}
const candidates=load('data/arkan-quick-image-candidates.json',{byId:{}});
const queue=load('data/arkan-image-review-queue.json',{byId:{}});
const state=load('data/arkan-image-agent-state.json',{checks:{}});
const approved=load('data/arkan-auto-published-images.json',{byId:{}});
const clean=s=>String(s||'').normalize('NFKC').replace(/[٠-٩]/g,x=>'٠١٢٣٤٥٦٧٨٩'.indexOf(x)).toLowerCase();
const nums=s=>clean(s).match(/\d+(?:[./]\d+)*/g)||[];
function mismatchedNumbers(name,title) {
  const a=nums(name),b=nums(title);
  return a.some(n=>!b.includes(n));
}
function safeUrl(url) {
  try {let p=new URL(url);return p.protocol==='https:'&&!p.username&&!p.password&&
      !['localhost','127.0.0.1','0.0.0.0'].includes(p.hostname)&&!p.hostname.endsWith('.local');}
  catch{return false}
}
// Build a cross-catalog owner index before accepting any preview photo.
// A URL proposed for two different SKUs is ambiguous regardless of title.
const candidateLists=new Map();
const urlOwners=new Map();
for(const item of items) {
  const id=item.id, list=[];
  const old=candidates.byId?.[id];
  if(Array.isArray(old)&&old.length>=2)list.push({imageUrl:old[0],title:old[1],source:old[2]||'',page:old[3]||''});
  for(const hit of queue.byId?.[id]?.results||[])
    list.push({imageUrl:hit.imageUrl,title:hit.title,source:hit.provider,page:hit.sourcePage||''});
  candidateLists.set(id,list);
  for(const c of list){
    if(!safeUrl(c.imageUrl))continue;
    if(!urlOwners.has(c.imageUrl))urlOwners.set(c.imageUrl,new Set());
    urlOwners.get(c.imageUrl).add(id);
  }
}
const results=[];
let ambiguousLinksSkipped=0;
for(const item of items) {
  if(!config.TRIAL_ALL_PRODUCTS)continue;
  if(!config.AUTO_PUBLISH_MEDICINES && /أدوية|دواء/.test(item.category))continue;
  const id=item.id;
  const list=candidateLists.get(id)||[];
  const old=candidates.byId?.[id];
  const broken=state.checks?.[id];
  const unique=new Set();
  for(const c of list) {
    if(!safeUrl(c.imageUrl)||unique.has(c.imageUrl))continue;
    unique.add(c.imageUrl);
    if((urlOwners.get(c.imageUrl)?.size||0)>1){ambiguousLinksSkipped++;continue;}
    if(broken?.failures>=3&&broken?.lastStatus==='gone'&&old?.[0]===c.imageUrl)continue;
    // Never claim brand/strength was verified by a URL or page title.
    // Only reject an explicit numerical contradiction in comparable scripts.
    if(nums(item.name).length&&nums(c.title).length&&mismatchedNumbers(item.name,c.title))continue;
    results.push({id,name:item.name,category:item.category,imageUrl:c.imageUrl,
      source:String(c.source||'').slice(0,120),sourcePage:safeUrl(c.page)?c.page:'',
      title:String(c.title||'').slice(0,220),status:'trial_unverified',
      catalogMatch:'not_visually_verified',rights:'source_rights_unconfirmed'});
    break;
  }
}
const result={mode:'trial',minimumVerifiedConfidence:config.MIN_CONFIDENCE_SCORE,approvedForProduction:false,version:2,ambiguousLinksSkipped,generatedAt:new Date().toISOString(),catalogTotal:items.length,
  trialImages:results.length,notice:'UNVERIFIED IMAGES. Not for dispensing or identifying medicine. Never imported into approved pharmacy photo seeds.',items:results};
fs.mkdirSync('data',{recursive:true});
fs.writeFileSync('data/arkan-trial-photo-feed.json',JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({catalogTotal:items.length,trialImages:results.length,approvedNotChanged:Object.keys(approved.byId||{}).length}));
