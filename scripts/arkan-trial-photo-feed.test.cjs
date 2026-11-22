'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const data=JSON.parse(fs.readFileSync('data/arkan-trial-photo-feed.json','utf8'));
assert.equal(data.mode,'trial');
assert.equal(data.catalogTotal,4218);
assert.ok(Array.isArray(data.items));
assert.equal(data.items.length,data.trialImages);
const seen=new Set();
for(const x of data.items){
  assert.ok(!seen.has(x.id),'duplicate product id');seen.add(x.id);
  assert.equal(x.status,'trial_unverified');
  assert.equal(x.catalogMatch,'not_visually_verified');
  assert.equal(x.rights,'source_rights_unconfirmed');
  assert.ok(/^https:\/\//.test(x.imageUrl));
  assert.ok(x.name && x.category);
  assert.equal(typeof x.id,'string');
}
assert.ok(!fs.readFileSync('scripts/arkan-trial-photo-feed.cjs','utf8').includes('writeFileSync(\'index.html\''));
console.log('PASS: trial feed is unverified, deduplicated, and separate from production seeds: '+data.trialImages+' records');
