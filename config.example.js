/* ---------------------------------------------------------------------------
   Template. Copy to config.js and fill in — config.js is gitignored.

   Or skip the file entirely: with no config.js the page asks for the values on
   first run and keeps them in this browser's local storage. That is the whole
   difference. Either way the keys reach the browser at runtime and are visible
   to anyone using the deployed page, so the things that actually protect you
   are, and remain:

     · firestore.rules          — only your signed-in UID can read or write
     · Maps key referrer limit  — the key only works on your own domain

   The service-account JSON is a different animal: it bypasses the rules
   entirely. That one never goes in a browser, a repo, or a chat window.
--------------------------------------------------------------------------- */
window.APP_CONFIG = {

  // Firebase Console → Project settings → Your apps → Web app → SDK setup
  firebase: {
    apiKey:            "",
    authDomain:        "apartment-hunter-41fd6.firebaseapp.com",
    projectId:         "apartment-hunter-41fd6",
    storageBucket:     "apartment-hunter-41fd6.firebasestorage.app",
    messagingSenderId: "1085228370812",
    appId:             ""      // 1:1085228370812:web:…
  },

  // Maps Platform browser key. Needs Maps JavaScript, Geocoding, Routes and
  // Directions APIs, restricted by HTTP referrer to the domains you serve from.
  mapsApiKey: "",

  // Only these signed-in Google accounts may load Maps. Leave empty and any
  // signed-in account can — which still keeps random visitors from spending
  // your quota, but is looser. Not a security boundary: the key is in the page
  // either way. Daily quota caps in Cloud Console are the real limit.
  allowedEmails: ["you@example.com"],

  // Appended to candidate addresses that do not name a city, when geocoding.
  defaultCity: "Kraków",
  defaultRegion: "pl"
};
