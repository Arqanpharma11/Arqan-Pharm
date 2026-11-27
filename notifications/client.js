'use strict';
const config={
            apiKey: "AIzaSyBLSGAvoS-H-tS2tmh76LZx_nkjoY--7tg",
            authDomain: "arkan-pharm.firebaseapp.com",
            projectId: "arkan-pharm",
            storageBucket: "arkan-pharm.firebasestorage.app",
            messagingSenderId: "975951355293",
            appId: "1:975951355293:web:549cd2fe28682b5cf12374",
            measurementId: "G-07P81LT4YQ"
        };
const vapidKey='BJ2JVp9NN_DzxpKjn_5o0kCi4lOjdpLHjly00mRasNS3t8jlSDu_fnwrD5_PgYMBeqKimBaK85XZ8z3G-OKe1JM';
const status=document.getElementById('status'), enable=document.getElementById('enable'), disable=document.getElementById('disable'), tokenEl=document.getElementById('token'), test=document.getElementById('test');
const setStatus=s=>status.textContent=s;
let sdk,reg,foregroundBound=false;
const API='https://arqan-notifications.mostafaalaaqweasdq123.workers.dev/';
async function topic(action,token){const r=await fetch(API,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,token}),signal:AbortSignal.timeout(20000)});const j=await r.json();if(!r.ok||!j.ok)throw Error(j.error||'Subscription failed');}

function load(src){return new Promise((resolve,reject)=>{const s=document.createElement('script');const timer=setTimeout(()=>{s.remove();reject(new Error('SDK timeout'));},15000);s.src=src;s.onload=()=>{clearTimeout(timer);resolve()};s.onerror=()=>{clearTimeout(timer);reject(new Error('SDK unavailable'))};document.head.appendChild(s)})}
async function messaging(){if(!sdk){sdk=(async()=>{if(!window.firebase)await load('https://www.gstatic.com/firebasejs/10.14.1/firebase-app-compat.js');if(!firebase.messaging)await load('https://www.gstatic.com/firebasejs/10.14.1/firebase-messaging-compat.js');if(!await firebase.messaging.isSupported())throw new Error('Unsupported browser');if(!firebase.apps.length)firebase.initializeApp(config);return firebase.messaging()})();sdk.catch(()=>{sdk=null})}return sdk}
async function worker(){if(!reg){reg=await navigator.serviceWorker.register('./firebase-messaging-sw.js',{scope:'./',updateViaCache:'none'});if(!reg.active){await new Promise((resolve,reject)=>{const w=reg.installing||reg.waiting;if(!w)return reject(new Error('Worker missing'));const timer=setTimeout(()=>reject(new Error('Worker timeout')),15000);const check=()=>{if(w.state==='activated'){clearTimeout(timer);resolve()}else if(w.state==='redundant'){clearTimeout(timer);reject(new Error('Worker failed'))}};w.addEventListener('statechange',check);check()})}}return reg}
async function run(action){enable.disabled=disable.disabled=true;try{await action()}catch(e){setStatus('تعذر تنفيذ العملية: '+(e.code||e.message||'خطأ غير معروف'));}finally{enable.disabled=disable.disabled=false}}
enable.addEventListener('click',()=>run(async()=>{if(!('Notification' in window)||!('serviceWorker' in navigator)||!('PushManager' in window))throw new Error('المتصفح غير داعم؛ على آيفون افتح التطبيق المثبت');if(await Notification.requestPermission()!=='granted'){setStatus('لم يتم السماح بالإشعارات.');return}setStatus('جاري تسجيل الجهاز…');const m=await messaging(),r=await worker();const token=await m.getToken({vapidKey,serviceWorkerRegistration:r});if(!token)throw new Error('No registration token');tokenEl.value=token;test.hidden=false;setStatus('جاري الاشتراك في عروض أركان…');await topic('subscribe',token);try{localStorage.setItem('arqan_push_optin_v1','yes')}catch{}setStatus('تم الاشتراك في الإشعارات الجماعية بنجاح.');if(!foregroundBound){foregroundBound=true;m.onMessage(p=>{const n=p.notification||p.data||{};r.showNotification(n.title||'أركان فارم',{body:n.body||'',icon:'../icons/arkan-192.png'}).catch(()=>{})})}}));
disable.addEventListener('click',()=>run(async()=>{if(!('serviceWorker' in navigator))return;const existing=await navigator.serviceWorker.getRegistration(location.href);if(existing&&existing.scope===new URL('./',location.href).href){const m=await messaging();if(Notification.permission==='granted'){const token=await m.getToken({vapidKey,serviceWorkerRegistration:existing});if(token)await topic('unsubscribe',token);}await m.deleteToken();const sub=await existing.pushManager.getSubscription();if(sub)await sub.unsubscribe();await existing.unregister()}try{localStorage.setItem('arqan_push_optin_v1','off')}catch{}tokenEl.value='';test.hidden=true;setStatus('تم إيقاف اشتراك الإشعارات على هذا الجهاز.')}));
document.getElementById('copy').onclick=async()=>{try{await navigator.clipboard.writeText(tokenEl.value);setStatus('تم نسخ الرمز.')}catch(e){tokenEl.select();setStatus('انسخ الرمز يدويًا.')}};
