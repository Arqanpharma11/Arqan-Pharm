(() => {
'use strict';
const config = {
            apiKey: "AIzaSyBLSGAvoS-H-tS2tmh76LZx_nkjoY--7tg",
            authDomain: "arkan-pharm.firebaseapp.com",
            projectId: "arkan-pharm",
            storageBucket: "arkan-pharm.firebasestorage.app",
            messagingSenderId: "975951355293",
            appId: "1:975951355293:web:549cd2fe28682b5cf12374",
            measurementId: "G-07P81LT4YQ"
        };
const vapidKey = 'BJ2JVp9NN_DzxpKjn_5o0kCi4lOjdpLHjly00mRasNS3t8jlSDu_fnwrD5_PgYMBeqKimBaK85XZ8z3G-OKe1JM';
async function start() {
 if (!('Notification' in window) || !('serviceWorker' in navigator) || !('PushManager' in window) || !window.firebase || !firebase.messaging) return;
 if (!(await firebase.messaging.isSupported())) return;
 if (!firebase.apps.length) firebase.initializeApp(config);
 const messaging = firebase.messaging();
 const reg = await navigator.serviceWorker.register('./sw.js', {updateViaCache:'none'});
 await navigator.serviceWorker.ready;
 const button = document.createElement('button');
 button.type='button'; button.textContent='🔔 تفعيل إشعارات العروض';
 button.setAttribute('aria-label','تفعيل إشعارات عروض أركان');
 Object.assign(button.style,{position:'fixed',bottom:'12px',left:'12px',zIndex:'60',background:'#166534',color:'#fff',border:'0',borderRadius:'12px',padding:'10px 14px',fontSize:'13px',cursor:'pointer',boxShadow:'0 2px 8px #0002'});
 async function register() {
   const token = await messaging.getToken({vapidKey,serviceWorkerRegistration:reg});
   if (!token) throw new Error('No FCM token');
   button.remove();
 }
 messaging.onMessage(payload => {
   const n=payload.notification||payload.data||{};
   reg.showNotification(n.title||'أركان فارم',{body:n.body||'',icon:new URL('./icons/arkan-192.png',location.href).href,data:{url:reg.scope}}).catch(console.warn);
 });
 if(Notification.permission==='granted') {try{await register();return;}catch(e){console.warn('Arqan push registration:',e);}}
 if(Notification.permission==='denied') return;
 button.addEventListener('click',async()=>{
   button.disabled=true;
   try {
     const permission=await Notification.requestPermission();
     if(permission==='granted'){await register();}
     else if(permission==='denied')button.remove();
   }catch(e){console.warn('Arqan push registration:',e);button.textContent='تعذر التفعيل، حاول مرة أخرى';}
   finally{button.disabled=false;}
 });
 document.body.appendChild(button);
}
start().catch(e=>console.warn('Arqan notifications unavailable:',e));
})();
