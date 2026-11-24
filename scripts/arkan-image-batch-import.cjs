'use strict';
// Offline batch importer/exporter for the existing storefront manifest.
// Usage: node scripts/arkan-image-batch-import.cjs [batch.json]
// Batch format: {byId: {"123": {url,source,sourcePage,catalogName, ...}}}
// Only locally hosted, already screened assets with matching SHA-256 are imported.
const fs=require('node:fs'), crypto=require('node:crypto'), path=require('node:path');
const html=fs.readFileSync('index.html','utf8');
const master=html.match(/const EXACT_MASTER_ITEMS\s*=\s*\[([\s\S]*?)\n\s*\];/);
const excluded=html.match(/const PDF_EXCLUDED_MASTER_POSITIONS\s*=\s*new Set\(\[([^\]]+)\]\)/);
if(!master||!excluded)throw Error('Missing catalog or exclusions');
const ex=new Set(excluded[1].split(',').map(x=>Number(x.trim())));
const catalog=new Map([...master[1].matchAll(/\{\s*name:\s*"([^"]+)"\s*,\s*cat:\s*"([^"]+)"/g)].map((m,i)=>[i<4218?String(i+1):String(230000+i-4218),{name:m[1],position:i+1}]).filter(([,v])=>!ex.has(v.position)));
if(catalog.size!==4489)throw Error('Catalog cardinality mismatch');
const start=html.indexOf('const verifiedImageSeeds = {'),end=html.indexOf('const imageSeedBatches',start);
if(start<0||end<start)throw Error('Missing verified seeds');
const seeds=new Set([...html.slice(start,end).matchAll(/^\s*'(\d+)':\s*\{/gm)].map(m=>m[1]));
const file='data/arkan-auto-published-images.json',manifest=JSON.parse(fs.readFileSync(file,'utf8'));
if(!manifest.byId||typeof manifest.byId!=='object'||Array.isArray(manifest.byId))throw Error('Invalid manifest');
const urls=new Set(Object.values(manifest.byId).map(v=>v?.url).filter(Boolean)), hashes=new Set(Object.values(manifest.byId).map(v=>v?.sha256).filter(Boolean));
const approvedReasons=/^(?:multi_source_[2-9]\d*|ocr|barcode)$/;
let added=0;const rejected={};
const reject=r=>rejected[r]=(rejected[r]||0)+1;
if(process.argv[2]){
 const input=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
 if(!input.byId||typeof input.byId!=='object'||Array.isArray(input.byId))throw Error('Invalid batch');
 for(const [id,v] of Object.entries(input.byId)){
  if(!catalog.has(id)||seeds.has(id)||manifest.byId[id]){reject('existing_or_inactive');continue;}
  if(!v||v.catalogName!==catalog.get(id).name||!approvedReasons.test(v.matchReason||'')||!Number.isFinite(v.matchScore)||v.matchScore<0.85){reject('match_evidence');continue;}
  const expected='https://raw.githubusercontent.com/Arqanpharma11/Arqan-Pharm/main/assets/product-images/'+id+'.webp';
  if(v.url!==expected||urls.has(v.url)){reject('url');continue;}
  const asset=path.join('assets','product-images',id+'.webp');
  if(!fs.existsSync(asset)){reject('missing_asset');continue;}
  const bytes=fs.readFileSync(asset),hash=crypto.createHash('sha256').update(bytes).digest('hex');
  if(bytes.length<700||bytes.length>102400||bytes.toString('ascii',0,4)!=='RIFF'||bytes.toString('ascii',8,12)!=='WEBP'||hash!==v.sha256||hashes.has(hash)){reject('invalid_or_duplicate_asset');continue;}
  manifest.byId[id]={...v,status:'candidate_preview',independentlyVerified:false,shownAsProductThumbnail:true};
  urls.add(v.url);hashes.add(hash);added++;
 }
 if(added){fs.writeFileSync(file+'.tmp',JSON.stringify(manifest,null,2)+'\n');fs.renameSync(file+'.tmp',file);}
}
const dir='data/image-batches';fs.mkdirSync(dir,{recursive:true});
const ids=[...catalog.keys()], index={catalogTotal:ids.length,batchSize:100,files:[],note:'External batch export; storefront continues using existing manifest.'};
let seedCount=0,linked=0,missing=0;
for(let i=0;i<ids.length;i+=100){
 const rows=ids.slice(i,i+100).map(id=>{const seed=seeds.has(id),record=manifest.byId[id]||null;if(seed)seedCount++;else if(record?.url)linked++;else missing++;return {id,name:catalog.get(id).name,embeddedSeed:seed,record};});
 const name='images-'+String(i/100+1).padStart(3,'0')+'.json';
 fs.writeFileSync(path.join(dir,name),JSON.stringify({items:rows},null,2)+'\n');index.files.push(name);
}
index.coverage={embeddedSeed:seedCount,manifestLinkOnly:linked,missingFromTheseTwoSources:missing,added,rejected,liveImageHealthNotMeasured:true,firestoreNotMeasured:true};
fs.writeFileSync(path.join(dir,'index.json'),JSON.stringify(index,null,2)+'\n');
console.log(JSON.stringify(index.coverage));
