'use strict';
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),cp=require('node:child_process'),assert=require('node:assert/strict');
const original=path.resolve(__dirname,'arkan-publish-matched-assets.cjs');
const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'arkan-asset-test-'));
try{
 fs.mkdirSync(path.join(tmp,'data'));fs.mkdirSync(path.join(tmp,'images'));
 const rows=Array.from({length:4490},(_,i)=>'{ name: "'+(i===0?'دواء تجريبي 500 مجم':'صنف '+(i+1))+'", cat: "أدوية" }').join(',\n');
 fs.writeFileSync(path.join(tmp,'index.html'),'const EXACT_MASTER_ITEMS = [\n'+rows+'\n];\nconst PDF_EXCLUDED_MASTER_POSITIONS = new Set([4490]);\nconst verifiedImageSeeds = {\n};\nconst imageSeedBatches = [];\n');
 fs.writeFileSync(path.join(tmp,'data/arkan-auto-published-images.json'),'{"version":1,"byId":{}}\n');
 const img=path.join(tmp,'images/1.webp');
 cp.execFileSync('python',['-c','from PIL import Image\nImage.new("RGB",(400,400),(255,255,255)).save('+JSON.stringify(img)+',"WEBP",quality=90)'],{stdio:'pipe'});
 assert.ok(fs.statSync(img).size>=700,'fixture too small');
 fs.writeFileSync(path.join(tmp,'results_v2.csv'),'\uFEFFcode,name,name_en,status,reason,score,support,ver,image,source_url,source_page\n'+
   '1,"دواء تجريبي 500 مجم","Test Medicine 500mg",auto,multi_source_2,0.95,2,,images/1.webp,https://example.com/1.webp,https://example.com/p/1\n'+
   '2,"صنف 2",,review,conflicting_images,0.98,2,,images/2.webp,https://example.com/2.webp,https://example.com/p/2\n');
 const out=JSON.parse(cp.execFileSync(process.execPath,[original],{cwd:tmp,encoding:'utf8'}).trim());
 assert.equal(out.published,1);
 const saved=JSON.parse(fs.readFileSync(path.join(tmp,'data/arkan-auto-published-images.json'),'utf8'));
 assert.equal(saved.byId['1'].independentlyVerified,false);
 assert.equal(saved.byId['2'],undefined);
 assert.ok(fs.statSync(path.join(tmp,'assets/product-images/1.webp')).size>=700);
 console.log('PASS: actual WebP asset moved to published directory and frontend manifest, conflicting photo blocked');
}finally{fs.rmSync(tmp,{recursive:true,force:true})}
