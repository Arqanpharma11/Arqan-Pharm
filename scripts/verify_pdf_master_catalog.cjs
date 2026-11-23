// Verify every line of the 2026-11-23 PDF against the shipping catalog.
const fs = require('node:fs');
const assert = require('node:assert/strict');
const html = fs.readFileSync('index.html', 'utf8');
const csv = fs.readFileSync('docs/pdf-master-4489-2026-11-23.csv', 'utf8').replace(/^\uFEFF/, '');
const source = html.match(/const EXACT_MASTER_ITEMS = \[([\s\S]*?)\n        \];/);
assert(source, 'Master catalog not found');
const master = [...source[1].matchAll(/\{\s*name:\s*"([^"]+)",\s*cat:\s*"([^"]+)",\s*price:\s*([\d.]+),\s*disc:\s*([\d.]+)/g)]
  .map((x, i) => ({ index: i+1, name: x[1], category: x[2], price: Number(x[3]), disc: Number(x[4]) }));
assert.equal(master.length, 4783, 'Unexpected master catalog size');
const exclusionText = html.match(/const PDF_EXCLUDED_MASTER_POSITIONS = new Set\((\[[\d,\s]+\])\);/);
assert(exclusionText, 'PDF exclusions not found');
const excluded = new Set(JSON.parse(exclusionText[1]));
const approved = master.filter(x => !excluded.has(x.index));
assert.equal(approved.length, 4489, 'Approved catalog must contain exactly 4489 products');
const normalize = x => String(x || '').normalize('NFKC').toLowerCase()
  .replace(/[٠-٩]/g, d => String(d.charCodeAt(0) - 1632))
  .replace(/٫/g, '.').replace(/[إأآ]/g, 'ا').replace(/ة/g, 'ه')
  .replace(/ى/g, 'ي').replace(/[\s@#$ـ.,،_*/\\%()\-]/g, '');
const byName = new Map(master.map(x => [normalize(x.name), x]));
const manual = {
  'بنتابرن بديل ميبو 30جرام': 4780,
  'بيا ماش 600مجم كبسول': 4782,
  'هيرو بيبى نيوتراديفنس3': 4781,
  'ابيكسيدون 5.مجم': 50,
  'اس 26جولد مرحله 400 1جرام': 217,
  '##جينوفيل وومان 10كيس حجم صغير': 1691,
  '##سوبر كيدز شامبو بيبى 200ملل': 2371,
  '##لنجوكورت5.مجم امبولات': 4783,
  'ليمتليس ومان س ج 30قرص برطمان بينك': 3614,
  'نيرفاكتوري 30اقرص س ج': 3987
};
function parseCsv(text) {
  const rows = []; let row = []; let field = '', quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (ch === '"') {
      if (quoted && text[i + 1] === '"') { field += '"'; i++; }
      else quoted = !quoted;
    } else if (ch === ',' && !quoted) { row.push(field); field = ''; }
    else if ((ch === '\n' || ch === '\r') && !quoted) {
      if (ch === '\r' && text[i + 1] === '\n') i++;
      row.push(field);
      if (row.some(v => v.trim())) rows.push(row);
      row = []; field = '';
    } else field += ch;
  }
  if (row.length || field) { row.push(field); rows.push(row); }
  return rows;
}
const sourceRows = parseCsv(csv);
assert.equal(sourceRows.length, 4490, 'Source document must contain 4489 product rows');
const used = new Set();
for (const [idx, row] of sourceRows.slice(1).entries()) {
  const name = row[3], price = Number(row[4]), discount = Number(row[5]), previous = row[7];
  const item = manual[name] ? master[manual[name] - 1] :
    (byName.get(normalize(name)) || byName.get(normalize(previous)));
  assert(item, 'Missing PDF product at row ' + (idx + 2) + ': ' + name);
  assert.equal(item.price, price, 'Public price differs for ' + name);
  assert.equal(item.disc, discount, 'Discount differs for ' + name);
  assert(approved.some(x => x.index === item.index), 'Product not approved: ' + name);
  assert(!used.has(item.index), 'Duplicate mapped master item for ' + name);
  used.add(item.index);
  assert(['أدوية', 'مستحضرات تجميل', 'ألبان أطفال', 'مكملات وفيتامينات'].includes(item.category), 'Missing product category for ' + name);
}
assert.equal(used.size, 4489);
assert(html.includes('products = enrichProducts(reconcileNovemberCatalog(data.items));'),
  'Firebase catalog must always be reconciled against PDF');
console.log('PASS: 4489/4489 unique PDF records; zero price, discount, and category mismatches in the approved code catalog.');