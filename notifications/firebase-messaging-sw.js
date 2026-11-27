'use strict';
self.addEventListener('notificationclick',event=>{event.stopImmediatePropagation();event.notification.close();event.waitUntil((async()=>{const url=new URL('../index.html',self.registration.scope).href;const cs=await self.clients.matchAll({type:'window',includeUncontrolled:true});const c=cs.find(x=>x.url===url);if(c)return c.focus();return self.clients.openWindow(url)})())});
importScripts('https://www.gstatic.com/firebasejs/10.14.1/firebase-app-compat.js','https://www.gstatic.com/firebasejs/10.14.1/firebase-messaging-compat.js');
firebase.initializeApp({
            apiKey: "AIzaSyBLSGAvoS-H-tS2tmh76LZx_nkjoY--7tg",
            authDomain: "arkan-pharm.firebaseapp.com",
            projectId: "arkan-pharm",
            storageBucket: "arkan-pharm.firebasestorage.app",
            messagingSenderId: "975951355293",
            appId: "1:975951355293:web:549cd2fe28682b5cf12374",
            measurementId: "G-07P81LT4YQ"
        });
const messaging=firebase.messaging();
messaging.onBackgroundMessage(p=>{if(p.notification)return;const n=p.data||{};return self.registration.showNotification(n.title||'أركان فارم',{body:n.body||'',icon:new URL('../icons/arkan-192.png',self.registration.scope).href})});
