/* Arkan unattended image discovery and link audit.
   No image is labelled verified merely because a search engine returned it.
   Optional secret: FIREBASE_SERVICE_ACCOUNT_JSON (only for detecting cloud-only new items).
*/
const fs = require('node:fs');
const crypto = require('node:crypto');
const html = fs.readFileSync('index.html','utf8');
const target = 'data/arkan-quick-image-candidates.json';
const stateFile = 'data/arkan-image-agent-state.json';
const queueFile = 'data/arkan-image-review-queue.json';
const reportFile = 'data/arkan-image-agent-report.json';
const read = (p, fallback) => fs.existsSync(p) ? JSON.parse(fs.readFileSync(p,'utf8')) : fallback;
const write = (p,data) => fs.writeFileSync(p, JSON.stringify(data,null,2)+'\n');
const candidates = read(target,{total:4218,byId:{}});
const state = read(stateFile,{cursor:0,searchCursor:0,checks:{},searched:{}});
const queue = read(queueFile,{byId:{}});
const master = html.match(/const EXACT_MASTER_ITEMS\s*=\s*\[([\s\S]*?)\n\s*\];/);
if(!master) throw Error('Master catalog extraction failed: refusing to mutate image data');
const items = [...master[1].matchAll(/\{\s*name:\s*"([^"]+)"\s*,\s*cat:\s*"([^"]+)"/g)].map((m,i)=>({id:String(i+1),name:m[1],cat:m[2]}));
if(items.length!==4218) throw Error('Master catalog count changed: update parser before proceeding');
async function getCloudItems() {
  const raw=process.env.FIREBASE_SERVICE_ACCOUNT_JSON;
  if(!raw) return [];
  const sa=JSON.parse(raw), now=Math.floor(Date.now()/1000);
  const b64=x=>Buffer.from(JSON.stringify(x)).toString('base64url');
  const signed=b64({alg:'RS256',typ:'JWT'})+'.'+b64({iss:sa.client_email,scope:'https://www.googleapis.com/auth/datastore',aud:'https://oauth2.googleapis.com/token',iat:now,exp:now+3600});
  const jwt=signed+'.'+crypto.sign('RSA-SHA256',Buffer.from(signed),sa.private_key).toString('base64url');
  const form=new URLSearchParams({grant_type:'urn:ietf:params:oauth:grant-type:jwt-bearer',assertion:jwt});
  const auth=await fetch('https://oauth2.googleapis.com/token',{method:'POST',body:form,signal:AbortSignal.timeout(10000)});
  if(!auth.ok) throw Error('Firestore token request failed: '+auth.status);
  const token=(await auth.json()).access_token;
  const url='https://firestore.googleapis.com/v1/projects/'+encodeURIComponent(sa.project_id)+'/databases/(default)/documents/settings/catalog';
  const r=await fetch(url,{headers:{Authorization:'Bearer '+token},signal:AbortSignal.timeout(12000)});
  if(r.status===404) return [];
  if(!r.ok) throw Error('Firestore catalog read failed: '+r.status);
  const doc=await r.json(), array=doc.fields?.items?.arrayValue?.values||[];
  const val=f=> f?.stringValue ?? f?.integerValue ?? f?.doubleValue ?? null;
  return array.map(v=>{const a=v.mapValue?.fields||{}; return {id:String(val(a.id)||''),name:String(val(a.name)||''),en:String(val(a.en)||'')};}).filter(x=>x.id&&x.name);
}
const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function imageAlive(url){
  if(!/^https:\/\//.test(url)) return 'invalid';
  try{
    const response=await fetch(url,{method:'GET',headers:{Range:'bytes=0-2047','User-Agent':'Arkan-Image-Healthcheck/1.0'},signal:AbortSignal.timeout(9000)});
    if([404,410].includes(response.status)){response.body?.cancel();return 'gone'}
    if(!response.ok){response.body?.cancel();return 'unknown'}
    const contentType=(response.headers.get('content-type')||'').toLowerCase();
    const bytes=new Uint8Array(await response.arrayBuffer());
    const signature=(bytes[0]===0x89&&bytes[1]===0x50)||(bytes[0]===0xff&&bytes[1]===0xd8)||(bytes[0]===0x52&&bytes[1]===0x49)||(bytes[0]===0x47&&bytes[1]===0x49);
    return (contentType.startsWith('image/')&&signature)?'ok':'unknown';
  }catch{return 'unknown'}
}
const norm=x=>String(x||'').toLowerCase().normalize('NFKC').replace(/[\u064b-\u065f]/g,'').replace(/[^\p{L}\p{N}]+/gu,' ').trim();
function exactEnough(item,title){
  const a=norm(item.en||item.name), b=norm(title);
  const words=a.split(' ').filter(x=>x.length>3);
  // At minimum, exact brand text AND every strength number must occur in the search result.
  if(!words.length || !b.includes(words[0])) return false;
  const nums=(a.match(/\d+(?:[.,/]\d+)*/g)||[]);
  if(nums.some(x=>!(b.match(/\d+(?:[.,/]\d+)*/g)||[]).includes(x))) return false;
  const forms=[['اقراص','tablet','tablets','tab'],['كبسول','capsule','caps'],['لبوس','suppository','supp'],['شراب','syrup'],['امبول','ampoule','amp'],['كريم','cream'],['قطره','قطرة','drops'],['جيل','gel']];
  const type=text=>forms.findIndex(f=>f.some(w=>text.includes(w)));
  return type(a)<0||type(b)<0||type(a)===type(b);
}
// Free, unauthenticated discovery: Wikimedia Commons and Open Food/Beauty Facts.
// Both require polite request rates. Candidate metadata goes to review queue ONLY.
const userAgent = 'ArkanPharmImageIndexer/1.0 (github.com/Arqanpharma11/Arqan-Pharm; public catalogue matching)';
const stripHtml = s => String(s||'').replace(/<[^>]*>/g,' ').replace(/&[^;]+;/g,' ').trim();
async function fetchJson(url) {
  const r=await fetch(url,{headers:{'User-Agent':userAgent,Accept:'application/json'},signal:AbortSignal.timeout(12000)});
  if(!r.ok) throw Error('Public database '+r.status);
  return r.json();
}
function candidate(item,title,imageUrl,sourcePage,provider,license){
  if(!/^https:\/\//.test(imageUrl||'') || !exactEnough(item,title)) return null;
  return {imageUrl,sourcePage,title,provider,license:license||'Review image-specific terms',foundAt:new Date().toISOString(),
          status:'pending_manual_packaging_and_license_review'};
}
async function searchCommons(item){
  const q=(item.en||item.name)+' medicine packaging';
  const args=new URLSearchParams({action:'query',generator:'search',gsrsearch:q,gsrnamespace:'6',gsrlimit:'8',prop:'imageinfo',iiprop:'url|extmetadata',format:'json'});
  const response=await fetchJson('https://commons.wikimedia.org/w/api.php?'+args);
  return Object.values(response.query?.pages||{}).map(p=>{
    const info=p.imageinfo?.[0]||{};
    const meta=info.extmetadata||{};
    return candidate(item,p.title?.replace(/^File:/,'')||'',info.url,
      info.descriptionurl||'', 'Wikimedia Commons',
      stripHtml(meta.LicenseShortName?.value||'Unknown Commons license'));
  }).filter(Boolean);
}
async function searchOpenFacts(item,host){
  const query=(item.en||item.name);
  // Public product searches are explicitly rate-limited, so keep <= 5 searches per run.
  const args=new URLSearchParams({search_terms:query,search_simple:'1',action:'process',json:'1',page_size:'8',
    fields:'code,product_name,product_name_en,brands,quantity,image_front_url,image_url,url'});
  const response=await fetchJson('https://'+host+'/cgi/search.pl?'+args);
  return (response.products||[]).map(p=>{
    const title=[p.brands,p.product_name_en||p.product_name,p.quantity].filter(Boolean).join(' ');
    return candidate(item,title,p.image_front_url||p.image_url,p.url||('https://'+host+'/product/'+p.code),
      host, 'Open Facts data and image licenses: review attribution and reuse requirements');
  }).filter(Boolean);
}
async function imageSearch(item){
  const sources=[];
  const category=String(item.cat||'');
  const hosts=/تجميل|عناية|بشرة|شعر/.test(category)?['world.openbeautyfacts.org']:
    /ألبان|غذاء|مكمل|تغذية/.test(category)?['world.openfoodfacts.org']:
    ['world.openfoodfacts.org','world.openbeautyfacts.org'];
  // Always inspect openly licensed Wikimedia files. No third-party API key needed.
  try{sources.push(...await searchCommons(item));}
  catch(e){console.warn('Commons unavailable:',e.message);}
  await pause(400);
  for(const host of hosts.slice(0,1)){
    try{sources.push(...await searchOpenFacts(item,host));}
    catch(e){console.warn(host+' unavailable:',e.message);}
  }
  const seen=new Set();
  return sources.filter(x=>{if(seen.has(x.imageUrl))return false;seen.add(x.imageUrl);return true}).slice(0,4);
}
async function main(){
  let cloud=[];
  try{cloud=await getCloudItems()}catch(e){console.error('Cloud catalog unavailable:',e.message);if(process.env.FIREBASE_SERVICE_ACCOUNT_JSON)process.exitCode=1;}
  const byId=new Map(items.map(x=>[x.id,x]));
  for(const item of cloud)byId.set(item.id,item);
  const all=[...byId.values()];
  const linked=Object.entries(candidates.byId).filter(([id,c])=>Array.isArray(c)&&c[0]?.startsWith('https://'));
  const budget=Number(process.env.IMAGE_CHECK_BUDGET||20);
  let checked=0,missing=0,healthy=0,gone=0,queued=0;
  for(let n=0;n<Math.min(budget,linked.length);n++){
    const [id,c]=linked[(state.cursor+n)%linked.length];
    const status=await imageAlive(c[0]);
    const entry=state.checks[id]||{failures:0};
    if(status==='ok'){entry.failures=0;healthy++}
    if(status==='gone'){entry.failures++;gone++}
    entry.lastStatus=status;entry.checkedAt=new Date().toISOString();
    state.checks[id]=entry;checked++;
    // Never delete a historical or approved image automatically from an uncertain network test.
    // Record repeated 404/410 for review instead.
  }
  if(linked.length)state.cursor=(state.cursor+checked)%linked.length;
  const outstanding=all.filter(x=>!candidates.byId[x.id] && !queue.byId[x.id] &&
    (!state.searched[x.id] || Date.now()-Date.parse(state.searched[x.id].at||0)>30*24*60*60*1000));
  missing=all.filter(x=>!candidates.byId[x.id]).length;
  if(outstanding.length){
    const searchBudget=Math.min(Number(process.env.IMAGE_SEARCH_BUDGET||5),outstanding.length);
    for(let i=0;i<searchBudget;i++){
      const item=outstanding[(state.searchCursor+i)%outstanding.length];
      try{
        const found=await imageSearch(item);
        state.searched[item.id]={at:new Date().toISOString(),hits:found.length};
        if(found.length){queue.byId[item.id]={name:item.name,en:item.en||'',results:found};queued++}
      }catch(e){console.error('Search error',item.id,e.message);break}
      await pause(700);
    }
    state.searchCursor=(state.searchCursor+searchBudget)%Math.max(1,outstanding.length);
  }
  state.lastRun=new Date().toISOString();
  state.lastCatalogSize=all.length;
  const report={runAt:state.lastRun,masterItems:items.length,cloudItems:cloud.length,catalogItems:all.length,candidateLinks:linked.length,missingWithoutCandidate:missing,checked,healthy,gone,queuedThisRun:queued,pendingReview:Object.keys(queue.byId).length,searchEnabled:true,searchProviders:['Wikimedia Commons','Open Food Facts','Open Beauty Facts'],cloudSyncEnabled:!!process.env.FIREBASE_SERVICE_ACCOUNT_JSON,disclaimer:'Automated candidate discovery is not photo verification. Existing approved photos are never overwritten.'};
  write(stateFile,state);write(queueFile,queue);write(reportFile,report);
  console.log(JSON.stringify(report));
}
main().catch(e=>{console.error(e);process.exitCode=1;});