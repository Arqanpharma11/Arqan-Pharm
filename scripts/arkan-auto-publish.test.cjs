'use strict';
const assert=require('node:assert/strict');
const {test}=require('node:test');
const {qualify,publish}=require('./arkan-auto-publish.cjs');
const base={imageUrl:'https://images.openfoodfacts.org/images/products/123/1.jpg',
sourcePage:'https://world.openfoodfacts.org/product/123',provider:'world.openfoodfacts.org',
license:'Open Facts contributors — CC BY-SA 3.0 product photo; database ODbL; attribution/share-alike apply',
title:'Aptamil Stage 2 400g'};
const milk={name:'Aptamil Stage 2 400g',cat:'ألبان أطفال'};
test('publish exactly matched open food package, retain provenance',()=>{
 const r=publish(milk,base);
 assert.ok(r); assert.equal(r.sourcePage,base.sourcePage);
 assert.equal(r.status,'auto_published_strict_unverified_pack');
 assert.equal(r.attributionRequired,true);
});
test('reject wrong stage',()=>assert.equal(qualify(milk,{...base,title:'Aptamil Stage 3 400g'}).pass,false));
test('reject wrong brand',()=>assert.equal(qualify(milk,{...base,title:'Nutrilon Stage 2 400g'}).pass,false));
test('reject medicine without visual validation',()=>assert.equal(qualify({name:'Apexidone 2 mg',cat:'أدوية'},
 {...base,title:'Apexidone 2 mg'}).pass,false));
test('reject untrusted image host',()=>assert.equal(qualify(milk,{...base,imageUrl:'https://example.com/p.png'}).pass,false));
test('reject unknown license',()=>assert.equal(qualify(milk,{...base,license:''}).pass,false));
test('reject ambiguous product without pack size',()=>assert.equal(qualify({name:'Aptamil Milk',cat:'ألبان أطفال'},
 {...base,title:'Aptamil Milk'}).pass,false));
test('reject unknown category from newly added Firestore product',()=>assert.equal(qualify({name:'Aptamil Stage 2 400g',cat:''},base).pass,false));

test('reject wrong pack unit even if amount is identical',()=>assert.equal(
 qualify(milk,{...base,title:'Aptamil Stage 2 400ml'}).pass,false));
test('reject extra variant not present in catalog',()=>assert.equal(
 qualify(milk,{...base,title:'Aptamil Stage 2 400g Extra'}).pass,false));
test('accept correct exact pack metadata for allowed source',()=>assert.equal(
 qualify(milk,base).pass,true));
test('reject required dosage form omitted from product title',()=>assert.equal(
 qualify({name:'Aptamil Stage 2 400g milk',cat:'ألبان أطفال'}, {...base,title:'Aptamil Stage 2 400g'}).pass,false));
