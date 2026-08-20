# Apartment Hunter — scraping API

FastAPI service that fetches a listing through ScrapingBee and runs three Claude
passes over it: text, photographs, then a reconciliation of the two. Returns a
validated object keyed exactly like the form fields in the page.

It exists because the ScrapingBee and Anthropic keys cannot live in a public
static page — unlike the Maps key, they have no origin restriction and bill by
usage. They stay here, in `.env`, and never reach a browser.

## Run it

```bash
cd server
cp .env.example .env      # fill in the two keys
docker compose up -d --build
curl localhost:8080/api/health
```

`/api/health` lists anything misconfigured rather than failing silently.

## You need a hostname, not an IP

The page is served from GitHub Pages over HTTPS. A browser will refuse to call
`http://<ip>` from an HTTPS page — that is mixed content, blocked with no
override — and no public CA will issue an ordinary certificate for a bare IP.
So the server needs a name and a certificate. Three ways, cheapest first:

**sslip.io** — no signup, no account. Any hostname of the form
`203-0-113-5.sslip.io` resolves to `203.0.113.5`. Let's Encrypt issues for it
over the HTTP-01 challenge, so:

```bash
sudo certbot --nginx -d 203-0-113-5.sslip.io      # your IP, dashes not dots
```

Port 80 must be reachable for the challenge and for renewals. Wildcards are not
supported, but a single host is all this needs.

**DuckDNS** — free account, gives `something.duckdns.org`, supports the DNS-01
challenge so port 80 can stay shut. Slightly more setup, a bit tidier.

**A real domain** — about €10/year, and worth it if this outlives the flat
search. Point an A record at the IP and run the same certbot command.

Whichever you pick, that hostname is what goes in `CORS_ORIGINS` on the server
and in the `API_BASE` repo secret for the page.

## nginx

The container binds to `127.0.0.1:8080`, so nginx is the only route in:

```nginx
location /apartment-hunter/ {
    proxy_pass         http://127.0.0.1:8080/;
    proxy_set_header   Host $host;
    proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header   X-Forwarded-Proto $scheme;
    proxy_read_timeout 300s;     # the photo pass is not quick
}
```

Then set `apiBase` in the page's config to
`https://your-server/apartment-hunter` (the `API_BASE` repo secret in CI).

## How the page authenticates with this server

There is no shared secret, no API key for the page, and no password. The chain
is entirely Google's:

1. You sign in with Google in the browser. Firebase hands the page an **ID
   token** — a JWT signed by Google, valid about an hour, carrying your `sub`
   (user id), `email`, and `aud` (the Firebase project id).
2. Every call to this API sends it: `Authorization: Bearer <token>`.
3. This server fetches Google's **public signing certificates** and verifies the
   signature, the issuer, the audience matches `FIREBASE_PROJECT_ID`, and that
   it has not expired. A forged or edited token fails the signature check; a
   token from a different Firebase project fails the audience check.
4. The verified `email` is then checked against `ALLOWED_EMAILS`.

The useful property is that **this server holds no credential for authentication
at all** — only a public project id. Nothing here can be stolen and replayed to
impersonate you, and there is no service-account JSON in this stack. The tokens
the page sends are short-lived and scoped to your project.

What it does *not* protect against: if someone gets into your Google account
they get the scraper too. And `ALLOWED_EMAILS` is the only thing standing
between "any Google account on earth" and your ScrapingBee credits, which is why
an empty value is reported as a misconfiguration.

CORS is separate and does a different job: it stops *other websites* from making
authenticated calls using a signed-in visitor's browser. `CORS_ORIGINS` must
list exactly the origin the page is served from.

## Access

Every endpoint requires a Firebase ID token, verified against Google's published
certificates — **no service-account JSON is used anywhere in this stack**, so
there is no admin credential to leak. The token's email must appear in
`ALLOWED_EMAILS`.

Leaving `ALLOWED_EMAILS` empty is treated as a misconfiguration and reported by
`/api/health`, because any Google account could then spend your credits.

There is also a per-user daily cap (`DAILY_JOB_CAP`, default 60) and a limit on
concurrent jobs. Both are in-memory: they reset when the container restarts, and
they are a cost guard rather than a security control.

## Endpoints

| method | path | purpose |
|---|---|---|
| `POST` | `/api/scrape` | `{url, candidate_id?}` → `{job_id, stages[]}`; returns at once |
| `GET` | `/api/scrape/{job_id}` | progress, then the result |
| `GET` | `/api/health` | configuration check |

Jobs run in the background so the page stays usable while one is in flight.
Progress moves through `fetching → parsing → photos → text_pass → photo_pass →
reconcile → done`, weighted so the bar tracks real elapsed time rather than
step count.

## The three passes

1. **Text** — description plus whatever structured fields the site exposed.
   Sees no images.
2. **Photographs** — up to `MAX_PHOTOS` images, downscaled to `PHOTO_MAX_PX` and
   re-encoded as JPEG. Deliberately not shown the description, so the advert's
   adjectives cannot colour what it reports seeing. Only asked about fields a
   photograph can honestly answer — never the deposit.
3. **Reconcile** — sees both and decides. Text wins on money, dates and contract
   terms; photographs win on condition, light and space, because listings
   describe every flat as bright and spacious.

Each pass is forced through a tool `input_schema` with `tool_choice`, so the
reply always matches the requested shape. Values are then re-validated in
`schema.py` before they go anywhere near the browser — the model is not trusted
to have obeyed, only pressured into it.

Every field is nullable and the prompt insists null is a good answer. Absence of
evidence never becomes "No": a listing that fails to mention a bathtub returns
null, not a negative. The page surfaces the nulls in a popup as things to check
at the viewing.

## Cost

Photographs dominate. Twelve images at 1024 px is roughly 15–20k input tokens,
and the reconcile pass re-reads both summaries. Assume three calls per listing.
`MAX_PHOTOS` is the dial that matters; `DAILY_JOB_CAP` is the ceiling.
