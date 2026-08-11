# Apartment Hunter

Weighted scoring for an apartment search: 28 criteria plus custom destinations
with real bike and transit travel times, a hard availability cut-off, a map with
routes to the places you care about, zł/m² statistics and a printable viewing
sheet.

Data lives in Firestore under your Google account and syncs to any browser you
sign in from. Without Firebase configured it falls back to browser local storage
and JSON export/import, which is also the offline interchange format.

## Files

| file | what it is |
|---|---|
| `index.html` | the whole app — no build step, no dependencies to install |
| `config.js` | Firebase web config, Maps key, default city. **Commit this.** |
| `firestore.rules` | security rules — this is what keeps your data private |
| `.gitignore` | blocks service-account JSON from ever being committed |

## Setup

### 1. Firebase

In the [console](https://console.firebase.google.com/project/apartment-hunter-41fd6):

1. **Build → Firestore Database → Create database.** Production mode, region
   `eur3` or `europe-central2`.
2. **Rules tab** → paste the contents of `firestore.rules` → Publish.
3. **Build → Authentication → Get started → Sign-in method → Google → Enable.**
4. **Authentication → Settings → Authorized domains** → add
   `<user>.github.io`. Sign-in fails silently without this.
5. **Project settings → Your apps → Web (`</>`)** → register an app → copy
   `apiKey` and `appId` into `config.js`.

The API key and app ID in a Firebase web config are public identifiers, not
secrets — they identify the project, they do not grant access. The rules do the
access control. That is why this repo can be public.

**The service-account JSON in your Downloads folder is a different thing
entirely.** It is an admin credential that bypasses every rule in
`firestore.rules`. It must never be committed, pasted, or uploaded. `.gitignore`
blocks the usual filenames, but the real protection is not moving it in here.

### 2. Google Maps

Create a browser key in
[Google Cloud Console → Credentials](https://console.cloud.google.com/apis/credentials),
enable **Maps JavaScript API**, **Geocoding API**, **Routes API** and
**Directions API**, then:

- *Application restrictions* → **Websites** → add `https://<user>.github.io/*`
- *API restrictions* → limit to the four APIs above

Paste it into `mapsApiKey` in `config.js`. An unrestricted key on a public page
gets scraped and billed to you.

### 3. Publish

```bash
cd ~/Projects/apartment-hunter
git add -A && git commit -m "apartment hunter"
gh repo create apartment-hunter --public --source=. --push
```

Then **Settings → Pages → Source: `main` / root**. Live at
`https://<user>.github.io/apartment-hunter/`.

## How the scoring works

Every criterion produces a fraction from 0 to 1, or nothing at all if you have
not answered it. The score is `points earned ÷ points available`, counting only
what you filled in — so a half-complete candidate still ranks sensibly instead
of looking terrible. The *Data filled* figure tells you how much of the picture
you actually have, and below 35% a candidate stays "Incomplete" rather than
being ranked off three lucky answers.

Two rules override the score outright: an availability date later than the
cut-off, and whatever you set in *Manual override*. Going over budget does not
eliminate a flat but costs it the single heaviest criterion, falling to zero by
5% over.

Destinations are scored per mode. A place's weight is split across its modes by
the shares you set, so `bike 0.7 / transit 0.3` means the bike time counts for
more than twice as much as the tram time.

## Sync and conflicts

One Firestore document per user, written 1.2 s after you stop typing.
Conflict resolution is last-write-wins on a timestamp. Edit the same flat on
two devices while one is offline and the later save silently wins — fine for one
person with a phone and a laptop, not fine for two people editing together.
