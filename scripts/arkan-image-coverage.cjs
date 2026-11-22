'use strict';
// Generate a complete inventory of photo coverage without treating candidate
// URLs as verified packaging. Runs without packages or paid services.
const fs=require('node:fs');
const html=fs.readFileSync('index.html','utf8');
const a=html.match(/const EXACT_MASTER_ITEMS\s*=\s*\[([\s\S]*?)\n\s*\];/);
if(!a)throw Error('Cannot locate master catalog');
const items=[...a[1].matchAll(/\{\s*name:\s*"([^"]+)"\s*,\s*cat:\s*"([^"]+)"/g)]
  .map((m,i)=>({id:String(i+1),name:m[1],category:m[2]}));
const read=(f,d)=>fs.existsSync(f)?JSON.parse(fs.readFileSync(f,'utf8')):d;
const candidates=read('data/arkan-quick-image-candidates.json',{byId:{}});
const published=read('data/arkan-auto-published-images.json',{byId:{}});
const queue=read('data/arkan-image-review-queue.json',{byId:{}});
const state=read('data/arkan-image-agent-state.json',{checks:{}});
const esc=s=>'"'+String(s??'').replace(/"/g,'""').replace(/[\r\n]+/g,' ')+'"';
const rows=items.map(it=>{
  const candidate=candidates.byId[it.id],auto=published.byId[it.id],
    queued=queue.byId[it.id],health=state.checks?.[it.id];
  const status=auto?'auto_published_not_pack_verified':
    candidate?health?.lastStatus==='gone'?'candidate_broken':'candidate_unverified':
    queued?'review_queue':'missing_external_photo';
  return {...it,status,source:auto?.source||candidate?.[2]||'',url:auto?.url||candidate?.[0]||'',
    imageHealth:health?.lastStatus||'not_checked',queuedResults:queued?.results?.length||0};
});
const stats={catalogItems:items.length,candidateUnverified:rows.filter(r=>r.status==='candidate_unverified').length,
 candidateBroken:rows.filter(r=>r.status==='candidate_broken').length,
 autoPublishedNotVerified:rows.filter(r=>r.status==='auto_published_not_pack_verified').length,
 reviewQueueOnly:rows.filter(r=>r.status==='review_queue').length,
 missingExternalPhoto:rows.filter(r=>r.status==='missing_external_photo').length,
 independentlyVerifiedPhotos:'Not measured: admin/Firestore and image assets are outside this manifest',
 updatedAt:new Date().toISOString()};
fs.writeFileSync('data/arkan-image-coverage-report.json',JSON.stringify(stats,null,2)+'\n');
const keys=['id','name','category','status','source','url','imageHealth','queuedResults'];
fs.writeFileSync('data/arkan-image-coverage.csv','\uFEFF'+keys.join(',')+'\n'+rows.map(r=>keys.map(k=>esc(r[k])).join(',')).join('\n')+'\n');
console.log(JSON.stringify(stats));
