'use strict';
const {onRequest}=require('firebase-functions/v2/https');
const {initializeApp}=require('firebase-admin/app');
const {getAuth}=require('firebase-admin/auth');
const {getMessaging}=require('firebase-admin/messaging');
initializeApp();
const TOPIC='arqan_offers_optin_v1', ROOT="https://arqanpharma11.github.io/Arqan-Pharm/", ORIGIN='https://arqanpharma11.github.io', ADMIN='qpuH4fWGhSYFq0mqTGfIEIn4VS13';
exports.arqanNotifications=onRequest({region:'us-central1',cors:[ORIGIN],maxInstances:2,timeoutSeconds:30},async(req,res)=>{
res.set('Cache-Control','no-store');
if(req.method==='GET')return res.json({ok:true,version:1});
if(req.method!=='POST'||req.get('origin')!==ORIGIN)return res.status(403).json({error:'Forbidden'});
try{
 const b=req.body||{};
 if(b.action==='subscribe'||b.action==='unsubscribe'){
  if(typeof b.token!=='string'||b.token.length<50||b.token.length>4096||!/^[A-Za-z0-9_:\-]+$/.test(b.token))return res.status(400).json({error:'Invalid device token'});
  const result=await (b.action==='subscribe'?getMessaging().subscribeToTopic(b.token,TOPIC):getMessaging().unsubscribeFromTopic(b.token,TOPIC));
  if(result.failureCount)return res.status(400).json({error:'Device registration failed'});
  return res.json({ok:true});
 }
 if(b.action!=='send')return res.status(400).json({error:'Unknown action'});
 const match=(req.get('authorization')||'').match(/^Bearer (.+)$/);
 if(!match)return res.status(401).json({error:'Authentication required'});
 let user;try{user=await getAuth().verifyIdToken(match[1],true)}catch{return res.status(401).json({error:'Invalid session'})}
 if(user.uid!==ADMIN)return res.status(403).json({error:'Admin only'});
 const title=typeof b.title==='string'?b.title.trim():'',body=typeof b.body==='string'?b.body.trim():'';
 if(!title||title.length>100||!body||body.length>500)return res.status(400).json({error:'Invalid title or message'});
 const id=await getMessaging().send({topic:TOPIC,notification:{title,body},webpush:{notification:{icon:ROOT+'icons/arkan-192.png'},fcmOptions:{link:ROOT},headers:{TTL:'86400'}}});
 return res.json({ok:true,messageId:id});
}catch(e){console.error('Arqan notifications:',e.code||e.message);return res.status(502).json({error:'Messaging service unavailable'})}
});
