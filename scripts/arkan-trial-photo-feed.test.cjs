'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const data=JSON.parse(fs.readFileSync('data/arkan-trial-photo-feed.json','utf8'));
assert.equal(data.mode,'trial');
const html=fs.readFileSync('index.html','utf8');
const master=html.match(/const EXACT_MASTER_ITEMS\s*=\s*\[([\s\S]*?)\n\s*\];/);
assert.ok(master,'catalog master missing');
const expectedCatalogSize=[...master[1].matchAll(/\{\s*name:\s*"[^"]+"\s*,\s*cat:\s*"[^"]+"/g)].length;
assert.equal(data.catalogTotal,expectedCatalogSize);
assert.ok(Array.isArray(data.items));
assert.equal(data.items.length,data.trialImages);
const seen=new Set();
const usedImageUrls=new Set();
for(const x of data.items){
  assert.ok(!seen.has(x.id),'duplicate product id');seen.add(x.id);
  assert.ok(!usedImageUrls.has(x.imageUrl),'ambiguous image URL reused for another catalog item');
  usedImageUrls.add(x.imageUrl);
  assert.equal(x.status,'trial_unverified');
  assert.equal(x.catalogMatch,'not_visually_verified');
  assert.equal(x.rights,'source_rights_unconfirmed');
  assert.ok(/^https:\/\//.test(x.imageUrl));
  assert.ok(x.name && x.category);
  assert.equal(typeof x.id,'string');
}
assert.ok(!fs.readFileSync('scripts/arkan-trial-photo-feed.cjs','utf8').includes('writeFileSync(\'index.html\''));
console.log('PASS: trial feed is unverified, deduplicated, and separate from production seeds: '+data.trialImages+' records');
