'use strict';
// Strict automatic publishing: only authoritative, openly reusable product-front records.
// Unknown rights, ambiguous matches, and pharmaceutical products remain in review.
const PUBLISHABLE = new Set(['world.openfoodfacts.org','world.openbeautyfacts.org']);
const norm = s=>String(s||'').toLowerCase().normalize('NFKC')
  .replace(/[\u064b-\u065f]/g,'').replace(/[\u200e\u200f]/g,'')
  .replace(/[^a-z0-9\u0621-\u064a./%]+/g,' ').replace(/\s+/g,' ').trim();
const nums = s=>norm(s).match(/\d+(?:[./]\d+)*/g)||[];
const words = s=>norm(s).split(' ').filter(x=>x.length>=3);
const formGroups = [
  ['tablet','tablets','tab','اقراص','قرص'], ['capsule','capsules','caps','كبسولات','كبسول'],
  ['suppository','suppositories','supp','لبوس'], ['syrup','شراب'],
  ['ampoule','amp','injection','حقن','امبول'],['cream','كريم'],['drops','قطره','قطرة'],
  ['gel','جيل'],['powder','بودر'],['milk','لبن'],['spray','بخاخ']
];
const form = s=>formGroups.findIndex(group=>group.some(x=>new RegExp('(^|\\s)'+x+'(?=\\s|$)').test(norm(s))));
function qualify(item, hit) {
  if(!item||!hit) return {pass:false,reason:'missing_data'};
  if(!PUBLISHABLE.has(hit.provider)) return {pass:false,reason:'source_not_eligible'};
  if(/أدوية|دواء|pharma|medicine/i.test(item.cat||'')) return {pass:false,reason:'medicine_requires_visual_validation'};
  // Only explicitly classified consumer goods may auto-publish; unknown/new
  // products from Firestore cannot bypass medicine safety checks.
  if(!/ألبان|غذاء|مكمل|تغذية|تجميل|عناية|بشرة|شعر|food|beauty|cosmetic|milk/i.test(item.cat||''))
    return {pass:false,reason:'unclassified_product_requires_review'};
  const title=hit.title||'', name=item.en||item.name||'', a=words(name), b=words(title);
  if(a.length<2 || b.length<2) return {pass:false,reason:'insufficient_name_detail'};
  if(a.some(w=>!b.includes(w))) return {pass:false,reason:'brand_or_variant_mismatch'};
  const an=nums(name),bn=nums(title);
  if(an.length!==bn.length || an.some(n=>!bn.includes(n))) return {pass:false,reason:'number_or_pack_mismatch'};
  const fa=form(name),fb=form(title);
  if(fa>=0&&fa!==fb) return {pass:false,reason:'form_missing_or_mismatch'};
  // A matching number without a matching unit is not a verified pack size.
  // Reject 400 ml vs 400 g, and reject added XR/Plus/Extra variants.
  const units=s=>(norm(s).match(/\\d+(?:[./]\\d+)?\\s*(?:mg|mcg|ml|kg|gm|g|مجم|مل|جم)/g)||[])
    .map(x=>x.replace(/\\s+/g,''));
  const au=units(name),bu=units(title);
  if(au.some(u=>!bu.includes(u)))return {pass:false,reason:'unit_mismatch'};
  const variants=['plus','extra','forte','xr','sr','retard','junior'];
  const has=(s,t)=>norm(s).split(' ').includes(t);
  if(variants.some(v=>has(title,v)&&!has(name,v)))return {pass:false,reason:'unexpected_variant'};
  // Require an unambiguous size/stage/pack number; brand alone is unsafe.
  if(!an.length) return {pass:false,reason:'no_size_or_stage'};
  if(!/^https:\/\/(?:images\.openfoodfacts\.org|images\.openbeautyfacts\.org|static\.openfoodfacts\.org|static\.openbeautyfacts\.org)\//.test(hit.imageUrl||''))
    return {pass:false,reason:'untrusted_image_host'};
  if(!/^https:\/\/world\.open(?:food|beauty)facts\.org\/product\/\d+/.test(hit.sourcePage||''))
    return {pass:false,reason:'unverified_product_page'};
  if(!hit.license || !/CC BY-SA 3\.0/i.test(hit.license)) return {pass:false,reason:'license_unconfirmed'};
  return {pass:true,reason:'matched_open_product_record'};
}
function publish(item,hit) {
  const test=qualify(item,hit);
  if(!test.pass) return null;
  return {url:hit.imageUrl,title:hit.title,source:hit.provider,sourcePage:hit.sourcePage,
    license:hit.license,status:'auto_published_strict_unverified_pack',publishedAt:new Date().toISOString(),
    catalogName:item.name,englishName:item.en||'',matchRule:'exact_brand_words_numbers_and_form',
    attributionRequired:true};
}
module.exports={qualify,publish};