# Arqan notifications deployment

Requires Firebase Blaze billing and authorized project owner deployment. From repository root run:

```sh
npm --prefix functions install
npx firebase-tools login
npx firebase-tools deploy --only functions:arqanNotifications --project arkan-pharm
```

Do not deploy Firestore rules or change existing authentication. Endpoint checks admin Firebase UID for sends. Public topic enrollment accepts opted-in registration tokens only; public endpoint is not an identity check for pharmacists. Topic contains public offers only. Test opt-in and unsubscribe on a device before bulk sends. Set billing alerts and monitor public enrollment traffic. Existing pharmacist logins are not Firebase Auth accounts. Browser permission requires a user gesture; no forced prompts. Main PWA worker is unchanged.
