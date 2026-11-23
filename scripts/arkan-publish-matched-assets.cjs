'use strict';
// Publish actual, locally generated WebP files, not remote candidate links.
// A candidate preview is never described as an independently verified pack.
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const root=process.cwd();
const html=fs.readFileSync('index.html','utf8');
const section=html.match(/const EXACT_MASTER_ITEMS\s*=\s*\[([\s\S]*?)\n\s*\];/);
if(!section)throw Error('Missing master catalog');
const items=[...section[1].matchAll(/\{\s*name:\s*"([^"]+)"\s*,\s*cat:\s*"([^"]+)"/g)].map((m,i)=>({
  id:i<4218?String(i+1):String(230000+i-4218),name:m[1],cat:m[2],position:i+1
}));
const match=html.match(/const PDF_EXCLUDED_MASTER_POSITIONS\s*=\s*new Set\(\[([^\]]+)\]\)/);
if(!match)throw Error('Missing PDF exclusions');
const excludes=new Set(match[1].split(',').map(x=>Number(x.trim())));
if(items.length-excludes.size!==4489)throw Error('Catalog cardinality changed');
const catalog=new Map(items.filter(x=>!excludes.has(x.position)).map(x=>[x.id,x]));
const seedStart=html.indexOf('const verifiedImageSeeds = {');
const seedEnd=html.indexOf('const imageSeedBatches',seedStart);
if(seedStart<0||seedEnd<seedStart)throw Error('Image seeds missing');
const seeds=new Set([...html.slice(seedStart,seedEnd).matchAll(/^\s*'(\d+)':\s*\{/gm)].map(x=>x[1]));
const input='results_v2.csv';
if(!fs.existsSync(input))throw Error('No search results');
function parseCSV(t){
  const rows=[];let row=[],value='',quoted=false;
  for(let i=0;i<t.length;i++){
    const c=t[i];
    if(c==='"'){if(quoted&&t[i+1]==='"'){value+='"';i++}else quoted=!quoted}
    else if(c===','&&!quoted){row.push(value);value=''}
    else if((c==='\n'||c==='\r')&&!quoted){if(c==='\r'&&t[i+1]==='\n')i++;row.push(value);if(row.some(x=>x))rows.push(row);row=[];value=''}
    else value+=c;
  }
  row.push(value);if(row.some(x=>x))rows.push(row);
  return rows;
}
const rows=parseCSV(fs.readFileSync(input,'utf8').replace(/^\uFEFF/,''));
const columns=rows.shift()||[];
const required=['code','name','status','reason','score','support','image','source_url','source_page'];
if(required.some(f=>!columns.includes(f)))throw Error('Unexpected image search CSV columns');
const manifestPath='data/arkan-auto-published-images.json';
const manifest=JSON.parse(fs.readFileSync(manifestPath,'utf8'));
manifest.byId ||= {};
const usedUrls=new Set(Object.values(manifest.byId).filter(x=>x&&x.url).map(x=>x.url));
const usedHashes=new Set(Object.values(manifest.byId).filter(x=>x&&x.sha256).map(x=>x.sha256));
const outDir='assets/product-images';fs.mkdirSync(outDir,{recursive:true});
const repo=process.env.GITHUB_REPOSITORY||'Arqanpharma11/Arqan-Pharm';
if(!/^[\w.-]+\/[\w.-]+$/.test(repo))throw Error('Invalid GitHub repo');
const branch='main',budget=Math.min(20,Math.max(1,Number(process.env.ARKAN_ASSET_PUBLISH_BUDGET)||8));
const report={processed:0,published:0,skipped:0,rejected:{},ids:[]};
const reject=reason=>{report.rejected[reason]=(report.rejected[reason]||0)+1};
for(const values of rows){
  if(report.published>=budget)break;
  const r=Object.fromEntries(columns.map((k,i)=>[k,values[i]||'']));
  report.processed++;
  const id=r.code,product=catalog.get(id);
  if(!product||seeds.has(id)||manifest.byId[id]){report.skipped++;continue}
  // Require independent multi-source match or strict OCR. No contradictory review images.
  if(r.status!=='auto'||Number(r.score)<0.85||
     !(/^(?:multi_source_[2-9]\d*|ocr|barcode)$/.test(r.reason))){reject('not_high_confidence');continue}
  if(r.name!==product.name){reject('catalog_mismatch');continue}
  if(!/^\d+$/.test(id)){reject('invalid_id');continue}
  const source=r.source_url||'',page=r.source_page||'';
  try{
    const src=new URL(source);
    if(src.protocol!=='https:'||src.username||src.password||!src.hostname||
      /^(?:localhost|127\.|10\.|192\.168\.|169\.254\.|172\.(?:1[6-9]|2\d|3[01])\.)/.test(src.hostname))
      throw Error('unsafe_source');
    if(page&&new URL(page).protocol!=='https:')throw Error('unsafe_page');
  }catch{reject('unsafe_source');continue}
  const srcPath=path.join('images',id+'.webp');
  if(!fs.existsSync(srcPath)){reject('missing_image_file');continue}
  const data=fs.readFileSync(srcPath);
  if(data.length<700||data.length>100*1024||data.toString('ascii',0,4)!=='RIFF'||
     data.toString('ascii',8,12)!=='WEBP'){reject('invalid_webp');continue}
  const hash=crypto.createHash('sha256').update(data).digest('hex');
  if(usedHashes.has(hash)){reject('duplicate_image');continue}
  const url='https://raw.githubusercontent.com/'+repo+'/'+branch+'/assets/product-images/'+id+'.webp';
  if(usedUrls.has(url)){reject('duplicate_url');continue}
  fs.writeFileSync(path.join(outDir,id+'.webp'),data);
  manifest.byId[id]={
    url,source:new URL(source).hostname,sourcePage:page||source,
    originalImageUrl:source,catalogName:product.name,englishName:r.name_en||'',
    title:[r.name_en,product.name].filter(Boolean).join(' '),
    status:'candidate_preview',independentlyVerified:false,shownAsProductThumbnail:true,
    matchScore:Number(r.score),matchReason:r.reason,sha256:hash,
    provenance:'Image downloaded and matched by image discovery bot; commercial reuse license unverified'
  };
  usedHashes.add(hash);usedUrls.add(url);report.published++;report.ids.push(id);
}
fs.writeFileSync(manifestPath,JSON.stringify(manifest,null,2)+'\n');
fs.writeFileSync('data/arkan-asset-publication-report.json',JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report));
