'use strict';
const fs=require('node:fs'),crypto=require('node:crypto'),path=require('node:path');
const report=JSON.parse(fs.readFileSync('data/arkan-asset-publication-report.json','utf8'));
const manifest=JSON.parse(fs.readFileSync('data/arkan-auto-published-images.json','utf8'));
const ids=report.ids||[];
if(report.published!==ids.length)throw Error('Reported publish count does not match published IDs');
const hashes=new Set();
for(const id of ids){
  if(!/^\d+$/.test(id))throw Error('Invalid published ID: '+id);
  const entry=manifest.byId?.[id];
  const file=path.join('assets','product-images',id+'.webp');
  if(!entry||!fs.existsSync(file))throw Error('Published file missing: '+id);
  const data=fs.readFileSync(file);
  if(data.length<700||data.length>100*1024||data.toString('ascii',0,4)!=='RIFF'||
     data.toString('ascii',8,12)!=='WEBP')throw Error('Corrupt published WebP: '+id);
  const hash=crypto.createHash('sha256').update(data).digest('hex');
  if(hash!==entry.sha256)throw Error('Published image hash mismatch: '+id);
  if(hashes.has(hash))throw Error('Duplicate uploaded photo: '+id);
  hashes.add(hash);
  if(entry.status!=='candidate_preview'||entry.independentlyVerified!==false)
    throw Error('Unverified photo incorrectly marked as approved: '+id);
  const u=new URL(entry.url);
  if(u.protocol!=='https:'||!u.pathname.endsWith('/assets/product-images/'+id+'.webp'))
    throw Error('Invalid published photo location: '+id);
}
console.log(JSON.stringify({validatedLocalAssets:ids.length,published:report.published,
  status:ids.length?'LOCAL_ASSETS_VALID_PENDING_GITHUB_PUSH':'NO_MATCHED_IMAGES_IN_BATCH'}));
