/* ---------------------------------------------------------------------------
   Apartment Hunter — deployment config.

   Fill this in and commit it. Nothing here is a secret in the usual sense:
   a Firebase web config and a Maps browser key are *designed* to ship in
   client-side code. What protects you is not hiding them, it is:

     · Firestore security rules  — only your signed-in UID can read or write
     · Maps key HTTP referrer restriction — the key only works on your domain

   Never put the service-account JSON (the one in Downloads) in here or
   anywhere else in this repo. That one really is a secret: it is an admin
   credential for the whole project and bypasses all security rules.

   Leave the values empty and the page will ask for them on first run and keep
   them in local storage instead — handy for trying it out before publishing.
--------------------------------------------------------------------------- */
window.APP_CONFIG = {

  // Firebase Console → Project settings → Your apps → Web app → SDK setup
  // Only apiKey and appId are unknown; the rest follow from the project id.
  firebase: {
    apiKey:            "",                                   // ← paste
    authDomain:        "apartment-hunter-41fd6.firebaseapp.com",
    projectId:         "apartment-hunter-41fd6",
    storageBucket:     "apartment-hunter-41fd6.firebasestorage.app",
    messagingSenderId: "1085228370812",
    appId:             ""                                    // ← paste, looks like 1:1085228370812:web:xxxx
  },

  // Google Maps Platform browser key, restricted by HTTP referrer to your
  // Pages domain. Needs Maps JavaScript API, Geocoding API and Routes API.
  mapsApiKey: "",

  // Appended to candidate addresses that do not name a city, when geocoding.
  defaultCity: "Kraków",
  defaultRegion: "pl"
};
