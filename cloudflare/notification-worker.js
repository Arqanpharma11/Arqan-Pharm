const ROOT='https://arqanpharma11.github.io/Arqan-Pharm/',ORIGIN=new URL(ROOT).origin,PROJECT='arkan-pharm',TOPIC='arqan_offers_optin_v1',ADMIN='qpuH4fWGhSYFq0mqTGfIEIn4VS13';
let cached;
const enc=new TextEncoder();
const b64=x=>btoa(String.fromCharCode(...x)).replace(/=/g,'').replace(/\+/g,'-').replace(/\//g,'_');
async function oauth(env){
 if(cached&&cached.exp>Date.now()+60000)return cached.token;
 const a=JSON.parse(env.FCM_SERVICE_ACCOUNT_JSON);
 if(a.project_id!==PROJECT)throw Error('Wrong project');
 const now=Math.floor(Date.now()/1000);
 const jwt=b64(enc.encode(JSON.stringify({alg:'RS256',typ:'JWT'})))+'.'+b64(enc.encode(JSON.stringify({iss:a.client_email,scope:'https://www.googleapis.com/auth/firebase.messaging',aud:'https://oauth2.googleapis.com/token',iat:now,exp:now+3600})));
 const key=await crypto.subtle.importKey('pkcs8',Uint8Array.from(atob(a.private_key.replace(/-----[^-]+-----|\s/g,'')),c=>c.charCodeAt(0)),{name:'RSASSA-PKCS1-v1_5',hash:'SHA-256'},false,['sign']);
 const sig=await crypto.subtle.sign('RSASSA-PKCS1-v1_5',key,enc.encode(jwt));
 const r=await fetch('https://oauth2.googleapis.com/token',{method:'POST',body:new URLSearchParams({grant_type:'urn:ietf:params:oauth:grant-type:jwt-bearer',assertion:jwt+'.'+b64(new Uint8Array(sig))})});
 const j=await r.json();if(!r.ok||!j.access_token)throw Error('OAuth failed');
 cached={token:j.access_token,exp:Date.now()+Number(j.expires_in||3600)*1000};return cached.token;
}
export default {async fetch(req,env){
 const origin=req.headers.get('Origin');const headers={'Access-Control-Allow-Origin':ORIGIN,'Access-Control-Allow-Methods':'GET, POST, OPTIONS','Access-Control-Allow-Headers':'Content-Type, Authorization','Cache-Control':'no-store','Vary':'Origin','Content-Type':'application/json'};
 const reply=(data,status=200)=>new Response(JSON.stringify(data),{status,headers});
 if(req.method==='OPTIONS')return new Response(null,{status:origin===ORIGIN?204:403,headers});
 if(req.method==='GET')return reply({ok:!!(env.FCM_SERVICE_ACCOUNT_JSON&&env.FIREBASE_WEB_API_KEY),version:2});
 if(req.method!=='POST'||origin!==ORIGIN)return reply({error:'Forbidden'},403);
 if(!env.FCM_SERVICE_ACCOUNT_JSON||!env.FIREBASE_WEB_API_KEY)return reply({error:'Service not configured'},503);
 try{
 const raw=await req.text();if(raw.length>8192)return reply({error:'Payload too large'},413);
 const b=JSON.parse(raw);
 if(b.action==='send'){
 const m=(req.headers.get('Authorization')||'').match(/^Bearer (.+)$/);if(!m)return reply({error:'Authentication required'},401);
 const r=await fetch('https://identitytoolkit.googleapis.com/v1/accounts:lookup?key='+encodeURIComponent(env.FIREBASE_WEB_API_KEY),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({idToken:m[1]})});
 if(!r.ok)return reply({error:'Invalid session'},401);
 const u=(await r.json()).users?.[0];if(!u||u.localId!==ADMIN||u.disabled)return reply({error:'Admin only'},403);
 const title=typeof b.title==='string'?b.title.trim():'',body=typeof b.body==='string'?b.body.trim():'';
 if(!title||title.length>100||!body||body.length>500)return reply({error:'Invalid message'},400);
 const token=await oauth(env);
 const f=await fetch('https://fcm.googleapis.com/v1/projects/'+PROJECT+'/messages:send',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({message:{topic:TOPIC,notification:{title,body},webpush:{notification:{icon:ROOT+'icons/arkan-192.png'},fcm_options:{link:ROOT},headers:{TTL:'86400'}}}})});
 if(!f.ok)return reply({error:'FCM send rejected',upstream:f.status},502);
 return reply({ok:true,messageId:(await f.json()).name});
 }
 if(!['subscribe','unsubscribe'].includes(b.action))return reply({error:'Unknown action'},400);
 if(typeof b.token!=='string'||b.token.length<50||b.token.length>4096||!/^[A-Za-z0-9_:\-]+$/.test(b.token))return reply({error:'Invalid token'},400);
 const token=await oauth(env);
 const sub=b.action==='subscribe';
 const url='https://iid.googleapis.com/iid/v1:'+(sub?'batchAdd':'batchRemove');
 const r=await fetch(url,{method:'POST',headers:{Authorization:'Bearer '+token,'access_token_auth':'true','Content-Type':'application/json'},body:JSON.stringify({to:'/topics/'+TOPIC,registration_tokens:[b.token]})});
 const result=await r.json();
 if(!r.ok||!Array.isArray(result.results)||result.results.length!==1||result.results[0].error)return reply({error:'Topic operation rejected',upstream:r.status},502);
 return reply({ok:true});
 }catch(e){console.error('Notification worker failed',e.name);return reply({error:'Service unavailable'},502)}
}};
