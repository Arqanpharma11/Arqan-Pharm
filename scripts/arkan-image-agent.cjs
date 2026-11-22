/* Arkan unattended image discovery and link audit.
   No image is labelled verified merely because a search engine returned it.
   Optional secret: FIREBASE_SERVICE_ACCOUNT_JSON (only for detecting cloud-only new items).
*/
const fs = require('node:fs');
const crypto = require('node:crypto');
const {publish} = require('./arkan-auto-publish.cjs');
const html = fs.readFileSync('index.html','utf8');
const target = 'data/arkan-quick-image-candidates.json';
const stateFile = 'data/arkan-image-agent-state.json';
const queueFile = 'data/arkan-image-review-queue.json';
const reportFile = 'data/arkan-image-agent-report.json';
const publishedFile = 'data/arkan-auto-published-images.json';
const read = (p, fallback) => fs.existsSync(p) ? JSON.parse(fs.readFileSync(p,'utf8')) : fallback;
const write = (p,data) => fs.writeFileSync(p, JSON.stringify(data,null,2)+'\n');
const candidates = read(target,{total:4218,byId:{}});
const state = read(stateFile,{cursor:0,searchCursor:0,checks:{},searched:{}});
const queue = read(queueFile,{byId:{}});
const published = read(publishedFile,{version:1,byId:{}});
const master = html.match(/const EXACT_MASTER_ITEMS\s*=\s*\[([\s\S]*?)\n\s*\];/);
if(!master) throw Error('Master catalog extraction failed: refusing to mutate image data');
const items = [...master[1].matchAll(/\{\s*name:\s*"([^"]+)"\s*,\s*cat:\s*"([^"]+)"/g)].map((m,i)=>({id:String(i+1),name:m[1],cat:m[2]}));
if(!items.length) throw Error('Master catalog empty: refusing to mutate image data');
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
// Egyptian drug index is metadata only: it provides English names, not package photos.
// Keep a strict exact Arabic-name match and refuse conflicting strengths.
const compactArabic=x=>String(x||'').normalize('NFKC').toLowerCase()
  .replace(/[\u064b-\u065f\u0670\u0640]/g,'').replace(/[إأآ]/g,'ا')
  .replace(/ى/g,'ي').replace(/ة/g,'ه').replace(/[^\u0621-\u064a0-9]/g,'');
const digits=x=>(String(x||'').match(/\d+(?:[./]\d+)*/g)||[]).sort();
async function resolveEgyptDrugName(item){
  if(item.en || !/أدوية|دواء/.test(item.cat||''))return item;
  const cached=state.egyptDrugNames?.[item.id];
  if(cached && cached.arabic===item.name)return {...item,en:cached.english,barcode:cached.barcode||''};
  const q=String(item.name||'').trim().replace(/%/g,'').slice(0,65);
  if(q.length<5)return item;
  try {
    const args=new URLSearchParams({q,limit:'20'});
    const response=await fetchJson('https://eg-drugs-api.mahmoudfalous.workers.dev/v1/search?'+args);
    const matches=(response.results||[]).filter(x=>
      compactArabic(x.arabic)===compactArabic(item.name) &&
      JSON.stringify(digits(x.arabic))===JSON.stringify(digits(item.name)) &&
      typeof x.name==='string' && x.name.length>3);
    if(matches.length!==1)return item;
    const found=matches[0];
    if(!state.egyptDrugNames)state.egyptDrugNames={};
    state.egyptDrugNames[item.id]={arabic:item.name,english:found.name,barcode:found.barcode||'',
       source:'Egyptian Drug Database by Mahmoud Mohamed (CC BY 4.0)'};
    return {...item,en:found.name,barcode:found.barcode||''};
  }catch(e){console.warn('Egypt drug metadata unavailable:',e.message);return item;}
}

async function imageAlive(url){
  if(!/^https:\/\//.test(url)) return 'invalid';
  try{
    const response=await fetch(url,{method:'GET',headers:{Range:'bytes=0-2047','User-Agent':'Arkan-Image-Healthcheck/1.0'},signal:AbortSignal.timeout(9000)});
    if([404,410].includes(response.status)){response.body?.cancel();return 'gone'}
    if(!response.ok){response.body?.cancel();return 'unknown'}
    const contentType=(response.headers.get('content-type')||'').toLowerCase();
    // Read only a tiny prefix. Some CDNs ignore Range and stream multi-MB images.
    // Never buffer the entire asset during a lightweight health check.
    const reader=response.body?.getReader();
    if(!reader) return 'unknown';
    const first=await reader.read();
    await reader.cancel().catch(()=>{});
    const bytes=first.value||new Uint8Array();
    const png=bytes.length>=8 && bytes[0]===0x89&&bytes[1]===0x50&&bytes[2]===0x4e&&bytes[3]===0x47;
    const jpeg=bytes.length>=3 && bytes[0]===0xff&&bytes[1]===0xd8&&bytes[2]===0xff;
    const webp=bytes.length>=12 && Buffer.from(bytes.subarray(0,4)).toString()==='RIFF' && Buffer.from(bytes.subarray(8,12)).toString()==='WEBP';
    const gif=bytes.length>=6 && Buffer.from(bytes.subarray(0,3)).toString()==='GIF';
    return (contentType.startsWith('image/')&&(png||jpeg||webp||gif))?'ok':'unknown';
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
    return candidate(item,title,p.image_front_url||p.image_url,'https://'+host+'/product/'+p.code,
      host, 'Open Facts contributors — CC BY-SA 3.0 product photo; database ODbL; attribution/share-alike apply');
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
  // Preserve master categories; never treat a medicine as an unknown consumer good.
  for(const item of cloud){
    const original=byId.get(item.id);
    if(original)byId.set(item.id,{...original,...item,cat:original.cat,name:item.name||original.name,en:item.en||original.en||''});
    else byId.set(item.id,{...item,cat:''});
  }
  const all=[...byId.values()];
  const linked=Object.entries(candidates.byId).filter(([id,c])=>Array.isArray(c)&&c[0]?.startsWith('https://'));
  const budget=Number(process.env.IMAGE_CHECK_BUDGET||20);
  let checked=0,missing=0,healthy=0,gone=0,queued=0,publishedNow=0;
  for(let n=0;n<Math.min(budget,linked.length);n++){
    const [id,c]=linked[(state.cursor+n)%linked.length];
    const status=await imageAlive(c[0]);
    const entry=state.checks[id]||{failures:0};
    if(status==='ok'){entry.failures=0;healthy++}
    if(status==='gone'){entry.failures++;gone++}
    if(entry.failures>=3){
      queue.byId[id]={name:byId.get(id)?.name||'',reason:'candidate_repeated_404_410',results:[],detectedAt:new Date().toISOString()};
      queued++;
    }
    entry.lastStatus=status;entry.checkedAt=new Date().toISOString();
    state.checks[id]=entry;checked++;
    // Never delete a historical or approved image automatically from an uncertain network test.
    // Record repeated 404/410 for review instead.
  }
  if(linked.length)state.cursor=(state.cursor+checked)%linked.length;
  // Recheck automatically published images; retire only after repeated explicit 404/410.
  const publishedEntries=Object.entries(published.byId);
  const publishBudget=Math.min(8,publishedEntries.length);
  for(let i=0;i<publishBudget;i++){
    const [id,record]=publishedEntries[(Number(state.publishedCursor||0)+i)%publishedEntries.length];
    const current=await imageAlive(record.url);
    const previous=state.publishedChecks?.[id]||{failures:0};
    if(current==='ok') previous.failures=0;
    else if(current==='gone') previous.failures++;
    previous.lastStatus=current;previous.checkedAt=new Date().toISOString();
    if(!state.publishedChecks)state.publishedChecks={};
    state.publishedChecks[id]=previous;
    if(previous.failures>=3){
      delete published.byId[id];delete state.searched[id];
      queue.byId[id]={name:byId.get(id)?.name||'',reason:'published_image_repeated_404_410',results:[],retiredAt:new Date().toISOString()};
    }
  }
  if(publishedEntries.length)state.publishedCursor=(Number(state.publishedCursor||0)+publishBudget)%publishedEntries.length;

  // A candidate is not a verified package. Retry missing and suspect items,
  // and revisit old searches periodically instead of permanently skipping a hit.
  const eligibleForSearch=x=>{
    if(published.byId[x.id]) return false;
    const last=state.searched[x.id]?.at;
    // Missing/uncertain results are retried after one day; do not keep
    // hammering the same API on every scheduled run.
    const retryHours=Number(state.searched[x.id]?.hits||0)>0?72:24;
    if(last && Date.now()-Date.parse(last)<retryHours*60*60*1000) return false;
    return true;
  };
  const missingPriority=all.filter(x=>!candidates.byId[x.id] && eligibleForSearch(x));
  // Candidates are not verified: revisit every unpublished candidate periodically.
  const questionable=all.filter(x=>candidates.byId[x.id] && eligibleForSearch(x));
  // Sort by the oldest search attempt. This avoids skipping items as the
  // eligible set shrinks between scheduled executions.
  const oldestFirst=(a,b)=>Date.parse(state.searched[a.id]?.at||'1970-01-01')-Date.parse(state.searched[b.id]?.at||'1970-01-01');
  const outstanding=[...missingPriority.sort(oldestFirst),...questionable.sort(oldestFirst)];
  missing=all.filter(x=>!candidates.byId[x.id] && !published.byId[x.id]).length;
  state.searchPipeline={remainingMissing:missingPriority.length,remainingSuspect:questionable.length,
    eligibleThisRun:outstanding.length};
  if(outstanding.length){
    const searchBudget=Math.min(25,Math.max(0,Number(process.env.IMAGE_SEARCH_BUDGET||5)),outstanding.length);
    for(let i=0;i<searchBudget;i++){
      const item=outstanding[i];
      try{
        const searchedItem=await resolveEgyptDrugName(item);
        const found=await imageSearch(searchedItem);
        state.searched[item.id]={at:new Date().toISOString(),hits:found.length};
        if(!found.length){
          queue.byId[item.id]={name:item.name,en:searchedItem.en||'',results:[],reason:'no_match_found',searchedAt:new Date().toISOString()};
        }
        if(found.length) {
          const eligible=[];
          for(const hit of found){
            const output=publish(searchedItem,hit);
            if(!output)continue;
            if(await imageAlive(output.url)==='ok')eligible.push(output);
          }
          if(eligible.length===1 && !published.byId[item.id]){
            // This is an eligible external image record, not a visually
            // verified medicine pack; do not overwrite admin-approved media.
            published.byId[item.id]=eligible[0];
            publishedNow++;
            delete queue.byId[item.id];
          }else {
            queue.byId[item.id]={name:item.name,en:searchedItem.en||'',results:found,
              reason:eligible.length>1?'ambiguous_multiple_valid_packages':'needs_review'};
            queued++;
          }
        }
      }catch(e){console.error('Search error',item.id,e.message);break}
      await pause(700);
    }
    state.searchCursor=0; // no index in a moving eligible list
  }
  state.lastRun=new Date().toISOString();
  state.lastCatalogSize=all.length;
  const report={runAt:state.lastRun,masterItems:items.length,cloudItems:cloud.length,catalogItems:all.length,candidateLinks:linked.length,autoPublishedCount:Object.keys(published.byId).length,publishedThisRun:publishedNow,missingWithoutCandidate:missing,checked,healthy,gone,queuedThisRun:queued,pendingReview:Object.keys(queue.byId).length,searchEnabled:true,searchProviders:['Wikimedia Commons','Open Food Facts','Open Beauty Facts'],egyptianNamesResolved:Object.keys(state.egyptDrugNames||{}).length,cloudSyncEnabled:!!process.env.FIREBASE_SERVICE_ACCOUNT_JSON,disclaimer:'Automated candidate discovery is not photo verification. Existing approved photos are never overwritten. Automatically published images remain marked as external, not verified packaging.'};
  write(stateFile,state);write(queueFile,queue);write(publishedFile,published);write(reportFile,report);
  console.log(JSON.stringify(report));
}
main().catch(e=>{console.error(e);process.exitCode=1;});