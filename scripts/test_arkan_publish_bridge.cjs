'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const cp = require('node:child_process');
const fixture = fs.mkdtempSync(path.join(os.tmpdir(), 'arkan-publish-test-'));
const bridge = path.resolve(__dirname, 'arkan-v2-bridge.cjs');
const run = (...args) => JSON.parse(cp.execFileSync(process.execPath, [bridge, ...args], {
  cwd: fixture, encoding: 'utf8', env: {...process.env, ARKAN_V2_BATCH_SIZE: '3'}
}).trim());
try {
  fs.mkdirSync(path.join(fixture, 'data'));
  const names = ['دواء تجريبي 500 مجم', 'صنف تجريبي بلس 20 مجم', 'صنف تجريبي 10 قرص'];
  const items = Array.from({length:4490}, (_,i) =>
    '{ name: "'+(names[i] || 'صنف '+(i+1))+'", cat: "أدوية" }').join(',\n');
  fs.writeFileSync(path.join(fixture, 'index.html'),
    'const EXACT_MASTER_ITEMS = [\n'+items+'\n];\n'+
    'const PDF_EXCLUDED_MASTER_POSITIONS = new Set([4490]);\n'+
    'const ENGLISH_BRAND_REFERENCE = {\n};\n'+
    'const verifiedImageSeeds = {\n};\nconst imageSeedBatches = [];\n');
  fs.writeFileSync(path.join(fixture,'data/arkan-v2-cursor.json'), '{"offset":0}');
  fs.writeFileSync(path.join(fixture,'data/arkan-auto-published-images.json'), '{"version":1,"byId":{}}');
  assert.equal(run().batch,3);
  fs.writeFileSync(path.join(fixture,'results_v2.csv'),
    'code,name,name_en,status,reason,score,support,source_url,source_page\n'+
    '1,"دواء تجريبي 500 مجم",,auto,ocr,0.92,2,https://images.example.com/1.webp,https://shop.example.com/1\n'+
    '2,"صنف تجريبي بلس 20 مجم",,auto,ocr,0.92,2,http://localhost/2.webp,https://shop.example.com/2\n'+
    '3,"صنف تجريبي 10 قرص",,review,ocr_mismatch,0.99,2,https://images.example.com/3.webp,https://shop.example.com/3\n');
  const result=run('--ingest');
  const saved=JSON.parse(fs.readFileSync(path.join(fixture,'data/arkan-auto-published-images.json'),'utf8'));
  assert.equal(result.publishedCandidateThumbnails,1);
  assert.equal(result.arabicOnlyCandidates,1);
  assert.equal(saved.byId['1'].status,'candidate_preview');
  assert.equal(saved.byId['1'].independentlyVerified,false);
  assert.equal(saved.byId['2'],undefined);
  assert.equal(saved.byId['3'],undefined);
  console.log('PASS: Arabic candidate preview, no false verification, unsafe/mismatched images blocked');
} finally {
  fs.rmSync(fixture,{recursive:true,force:true});
}
