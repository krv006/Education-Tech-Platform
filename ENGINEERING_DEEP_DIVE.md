# Engineering Deep Dive — LiveKit, Backend Concepts & Production Incidents

Project-specific explanations, not generic tutorials. Every claim below is
grounded in this repo's actual code and commit history (hashes/file
references included) — nothing here is hypothetical.

**Contents:**
1. [LiveKit — what it is, and the problems we actually hit](#1-livekit--what-it-is-and-the-problems-we-actually-hit)
2. [CORS vs CSRF](#2-cors-vs-csrf)
3. [Incident: an unpinned dependency crash-looped the whole backend](#3-incident-an-unpinned-dependency-crash-looped-the-whole-backend)
4. [Incident: Jazzmin admin theme broke `/admin/` in production](#4-incident-jazzmin-admin-theme-broke-admin-in-production)
5. [SimpleJWT's stateless model vs. single-device-session](#5-simplejwts-stateless-model-vs-single-device-session)
6. [RBAC — Role-Based Access Control](#6-rbac--role-based-access-control)

---

## 1. LiveKit — what it is, and the problems we actually hit

### What is LiveKit

LiveKit is an open-source, self-hostable **WebRTC SFU** (Selective Forwarding
Unit) — a real-time media server. Its job is to sit between participants in a
video/audio call and forward each person's stream to everyone else who needs
it, instead of every browser connecting peer-to-peer to every other browser
(which doesn't scale past a handful of people). Core pieces relevant to this
project:

- **Rooms** — a named session; participants join with a signed JWT that
  grants specific permissions (publish camera, subscribe, screen-share,
  room-admin, etc.)
- **`livekit-server`** — the actual SFU (Go binary), handles signaling +
  media relay
- **Egress** — a separate service (also Go, uses a headless Chrome to
  composite the room's video layout, then encodes it) for recording a room
  to a file, or streaming it out
- **Server API** — lets your backend do things *to* a live room from
  outside (kick a participant, change their permissions, start/stop a
  recording) without the backend touching media itself

It's the open-source alternative to hosted services like Twilio Video, Agora,
or Daily — you run the servers yourself instead of paying per-participant-
minute, at the cost of operating that infrastructure.

### How this project uses it

Self-hosted via `docker-compose` — `livekit-server` + a separate `egress`
container ([docker-compose.prod.yml](docker-compose.prod.yml)). Django
(`apps/live/services.py`) never touches media; it only does three things
through LiveKit's Python SDK: issues join tokens (`issue_room_token`), calls
the server API for moderation (`grant_screen_share`, `ban_participant`), and
calls the Egress API to start/stop recordings.

### Problems actually hit, and how they were solved — in order

| Commit | Problem | Fix | Why |
|---|---|---|---|
| `53f12ec` | On Docker Desktop, LiveKit announced its **internal container IP** for WebRTC media — browsers couldn't actually connect (media never flowed, even though signaling worked) | `--node-ip 127.0.0.1` | LiveKit needs to tell clients an IP they can actually reach; the container's own IP isn't reachable from the host's browser |
| `0cb52fb` | Default 1080p recording preset was too CPU-heavy | Dropped to 720p/30 (~2x less CPU), added cpu/mem limits, room `empty_timeout`, documented required frontend settings (simulcast, adaptiveStream, dynacast) | First pass at making self-hosting affordable — a recurring theme, since self-hosting means *you* pay for every encode cycle |
| `85cf96b` | Recording silently didn't work in **dev** at all | Dev `docker-compose.yml` was missing the `egress` container and `livekit.yaml` was missing the Redis address egress needs to coordinate with LiveKit | Egress and LiveKit talk to each other over Redis — without it configured, egress has no way to receive room events |
| `06dfee7` | Recordings were being **rejected** ("insufficient CPU") | Raised `cpus: 2 → 4` on the egress container | Discovered live: LiveKit's own egress has admission control — it estimates each room-composite job costs ~4.0 CPU and refuses jobs it doesn't have headroom for. This is the exact mechanism behind the "resource exhausted" error text still handled in `_friendly_egress_error()` today. |
| `c24a628` | Server-to-server egress/moderation calls were suspected of getting 401s | Added `LIVEKIT_API_URL` so Django calls LiveKit directly over the internal Docker network (`http://livekit:7880`) instead of routing back out through Caddy/TLS | Calling your own reverse proxy from inside the same Docker network is pointless overhead and a plausible source of auth weirdness — direct internal networking is both faster and simpler |
| `fe4f0ef` | Starting a recording right when a teacher's token was issued sometimes failed with "room does not exist" | Retry loop, up to 2 minutes, specifically on that error string | Real race condition: issuing a token doesn't mean the browser has *actually* opened the WebRTC connection yet — the room genuinely doesn't exist in LiveKit until the first participant joins |
| `9066a06` | Recordings could get stuck in a fake "still recording" state (e.g. after a backend restart mid-recording) | Rewrote to an idempotent **"ensure" lifecycle** — every token issuance checks LiveKit for an already-active egress and adopts it, or starts fresh; stuck jobs auto-fail after a timeout | Treats recording as "make sure this is happening" rather than "start it once," because there's no durable job queue and the token endpoint can legitimately be hit multiple times per lesson |
| `89fe844` | Egress got "permission denied" writing to the `/out` volume | Egress container runs as root | Docker volume UID/GID mismatch between the egress image's default user and the mounted host volume's ownership — a standard self-hosting/ops gotcha, not a LiveKit design issue |
| `4be20d8` | A prior fix (egress root override) broke an unrelated Caddy route | Dropped the override, restored the route | The ops surface here is tightly coupled — this server also runs other projects behind the same Caddy, so infra changes for one service can have side effects on another |
| `d68bbf1` | Egress CPU cost was still the limiting factor for how many lessons could record simultaneously | Custom `EncodingOptions` at 480p/15fps instead of the 720p30 preset (LiveKit's preset enum doesn't even have anything below 720p — had to use the `advanced` field, not a preset) | Direct continuation of the same cost problem from `06dfee7` — lower target resolution/framerate should reduce actual compositor+encode load, though not yet confirmed with real measurement |

### What's still genuinely unsolved

- **Concurrency ceiling**: even after the 480p change, `egress` is capped at
  `cpus: 3` (down from 4) — LiveKit's own docs say room-composite egress
  needs 2–6 CPUs, not a number that scales cleanly with resolution. This is
  still an open, unverified risk for anything beyond ~1 simultaneous
  recording. Needs confirming against real `docker stats egress` usage
  during an actual recording before trusting it in production.
- **No egress webhook**: LiveKit fires an `egress_ended` webhook with real
  duration/file-size/etc., but nothing in this codebase listens for it — the
  system only ever checks "does a non-empty file exist on disk," never
  LiveKit's own report.
- **No S3/cloud storage, no compression pipeline, no adaptive streaming** —
  all recordings sit on a single local Docker volume, served as one raw MP4
  via HTTP Range requests.

---

## 2. CORS vs CSRF

### CORS — Cross-Origin Resource Sharing

**The problem it solves:** browsers enforce the *same-origin policy* —
JavaScript on one website is normally forbidden from reading responses from
a different website. "Origin" means protocol + domain + port together, so
`https://edu-front-silk.vercel.app` and `https://edu.thesofmebel.uz` are two
completely different origins even though they're the same product.

This matters directly here because the frontend (Vercel) and backend
(`thesofmebel.uz`) genuinely are different origins. Without anything special,
the frontend's `fetch()`/`axios` calls would be **blocked by the browser
itself** — the request might even reach Django and get a valid response, but
the browser would refuse to hand that response back to the frontend's JS.
This is a browser-side rule; Django never "knows" it's being blocked.

**CORS is the exception mechanism**: the server sends back response headers
(`Access-Control-Allow-Origin`, etc.) that explicitly say "these origins are
allowed to read my responses." That's what `CORS_ALLOWED_ORIGINS` in
[root/settings/base.py:195](root/settings/base.py:195) does (via
`django-cors-headers`). `CORS_ALLOW_CREDENTIALS = True` additionally allows
the `Authorization` header to be sent along with cross-origin requests.

### CSRF — Cross-Site Request Forgery

**A different problem**, easy to confuse with CORS by name alone: this is an
*attack*, not a browser restriction. If you're logged into a site via a
cookie, and a malicious page has a hidden form auto-submitting to that site,
the browser attaches your cookie automatically — the target site sees what
looks like a legitimate authenticated request, because the cookie rode along
without your knowledge.

**CSRF protection** is the server requiring a secret token — one only a page
actually served by the real site would know — proving a state-changing
request genuinely came from your own frontend.

### The distinction that matters here

CSRF specifically attacks **cookie-based** auth (cookies are what get sent
automatically). This project's API uses **JWT bearer tokens**
(`Authorization: Bearer <token>`) — a malicious page can't make a victim's
browser attach a custom header the way it can a cookie. So the REST API is
largely immune to CSRF by construction.

**Where CSRF still matters here**: the Django **admin panel** (`/admin/`) is
the one part of this app still using traditional session-cookie login — that's
why `CSRF_TRUSTED_ORIGINS` ([root/settings/base.py:213](root/settings/base.py:213))
and `CsrfViewMiddleware` exist. They protect `/admin/`, not `/api/v1/...`.

| | CORS | CSRF |
|---|---|---|
| What it is | Browser rule about which origins can *read* a response | Attack abusing automatic cookie-sending |
| Enforced by | The browser, via server response headers | The server, via a required secret token |
| Relevant to | Every cross-origin frontend↔backend call | Only cookie/session-authenticated requests (the admin, here) |
| In this project | Lets the Vercel frontend talk to the API at all | Protects `/admin/`, not the JWT API |

CORS/CSRF settings here went through three real iterations (hardcoded
allowlist → explicit `CORS_ALLOWED_ORIGINS`/`CSRF_TRUSTED_ORIGINS` → dropping
`ALLOWED_HOSTS` validation in favor of Caddy) — getting both right for a
split frontend/backend with two different auth mechanisms (JWT for the API,
cookies for the admin) took real trial and error, not a one-line config.

---

## 3. Incident: an unpinned dependency crash-looped the whole backend

### What "unpinned" means
`requirements.txt` originally had `Django>=6.0` — no upper bound. Every fresh
`pip install` (no cached packages) resolves that range against whatever the
*newest* matching PyPI version is **right now**. Six months later, the same
file can silently install a different Django release than what was actually
tested — nobody edited the file, but the resolved result changed.

### What happened
1. Django **6.1** removed `django.utils.cache.cc_delim_re` — an internal,
   undocumented utility. Django doesn't promise internals like this stay
   forever, only its public API.
2. The DRF version in use still did `from django.utils.cache import
   cc_delim_re` somewhere internally — hadn't yet caught up to the removal.
3. A rebuild without Docker's cached layers (`pip install` re-resolves from
   scratch) picked up Django 6.1 fresh.
4. Django imports `rest_framework` on startup (it's in `INSTALLED_APPS`).
   That import chain hit the missing `cc_delim_re` and raised `ImportError`
   — **before the app finished booting**, before serving a single request.

### What "crash-looped" means, concretely
`docker-compose.prod.yml` runs the backend with `restart: unless-stopped` —
if the process dies, Docker restarts it automatically. Here the failure
wasn't transient: every restart hit the exact same import error in a
fraction of a second, and got restarted again immediately, forever. Health
checks fail continuously, logs repeat the same traceback every few seconds,
and the site is fully down — restarting doesn't fix it, because restarting
*is* what's happening, in a tight loop, since the cause is baked into the
dependency combination itself.

### The fix
```
Django>=6.0,<6.1
```
An explicit upper bound. `pip install` can never silently jump to 6.1 (or
7.0) again — pinned to the entire tested 6.0.x line. Upgrading later is still
possible, just deliberately, after confirming DRF has caught up.

### The lesson
An open-ended version range plus an uncached rebuild is an implicit bet that
every future release of a dependency stays compatible forever — often false,
especially when a *second* dependency reaches into the first one's internals.
This project's `requirements.txt` has the same defensive-pinning pattern
applied twice (`redis>=5.0,<6.0`, with its own documented `channels_redis` +
`redis-py` 8.x incident) — this wasn't a one-off lesson.

---

## 4. Incident: Jazzmin admin theme broke `/admin/` in production

### Why Django hashes static files in production
In prod, static files aren't served as `admin.css` — they're served as
`admin.a3f9c1.css`, hash derived from content. This is cache-busting:
browsers cache static files forever, which only stays safe if the filename
*changes* when the content does. `collectstatic` builds a **manifest**
(`"admin.css" → "admin.a3f9c1.css"`), and every `{% static %}` tag resolves
through it at request time.

### Why the strict check exists
`ManifestStaticFilesStorage` deliberately **raises a hard error** if a
template asks for a path that isn't in the manifest — intentional, to catch
broken static references before they silently 404 for users. In dev
(`DEBUG=True`) this strict check is bypassed entirely, so a broken reference
is invisible until `DEBUG=False` is actually exercised.

### What Jazzmin did
Jazzmin's base template referenced something like `{% static
'vendor/bootswatch' %}` — a **folder path**, not a real file. There's no
literal manifest entry for a folder. On every `/admin/` request,
`ManifestStaticFilesStorage` raised `ValueError`, uncaught, and Django turned
it into a full `500` — for every admin page, since the reference is in the
base template all of them extend. A bug in Jazzmin's own template, only
surfacing once deployed with strict manifest storage, which dev never runs.

### The fix
```python
class ForgivingManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    def stored_name(self, name):
        try:
            return super().stored_name(name)
        except ValueError:
            return name
```
([apps/core/staticfiles.py](apps/core/staticfiles.py)) — if the strict lookup
fails, fall back to the original, unhashed filename instead of crashing the
page. That one broken reference loses cache-busting (cosmetic), while every
other file still gets the strict, correct treatment.

### The second fix — closing the dev/prod gap that let this slip through
`root/settings/stagetest.py`: `dev.py`'s settings, but with `DEBUG=False` and
the same WhiteNoise manifest storage prod uses — a way to reproduce prod-only
500s **locally**, without a real deploy. Its own docstring: *"Faqat 500
xatolarni lokalda qayta tiklash uchun — deploy'da ishlatilmaydi."*

### The pattern
A dev/prod parity gap: broken static references are structurally invisible
in dev because dev deliberately skips the check prod enforces. The fix wasn't
just patching one Jazzmin reference — it made the whole class of failure
non-fatal, *and* added a way to test the strict path before deploying again.

---

## 5. SimpleJWT's stateless model vs. single-device-session

### What "stateless" means for JWT, and why it's attractive
A JWT is a signed blob issued once at login, containing claims + a
signature. The server needs to remember nothing to validate it later — check
the signature and expiry, done. No database lookup, no shared session store,
any server instance can validate independently. This is why stateless auth
scales well.

The mirror-image cost: **the server can't "forget" or revoke a token early.**
Once issued, a JWT is valid until it naturally expires (60 min access tokens
here), no matter what happens server-side — there's no session row to
delete, because there never was one.

### The requirement that broke this assumption
Only one device logged in per account at a time — a second login should stop
the first one. That's a *stateful* question ("which session is currently
active?") on a system designed to need no state. Stock SimpleJWT can't
answer it — a token issued 5 minutes ago knows nothing about a login that
happened 1 minute ago on a different device.

### How the gap was bridged — a minimal state layer on top of stateless tokens
1. **`DeviceSession`** ([apps/accounts/models.py:108](apps/accounts/models.py:108))
   — one row per user, holding `session_jti`: the ID of whichever refresh
   token is currently "the active session."
2. At login, `enforce_single_session()`
   ([apps/accounts/services.py:216](apps/accounts/services.py:216)) checks
   for an existing `DeviceSession` with a *different* `session_jti`:
   - No `force` → the just-issued tokens are immediately blacklisted, login
     returns `409 device_conflict` with the other device's label.
   - `force=true` → the *old* session's jti gets blacklisted instead, the new
     one becomes the active `DeviceSession`, also cached in Redis for 7 days.
3. **Every request** goes through `SingleSessionJWTAuthentication`
   ([apps/accounts/authentication.py](apps/accounts/authentication.py)): reads
   the `session_jti` claim in the *current* token, compares against whatever
   `DeviceSession` currently says is active (Redis first, DB fallback) — if
   they don't match, `401`, even though the token's own signature/expiry are
   still perfectly valid.

The extra state check is what actually revokes a token early — the token
itself says it's fine; the external record is what overrides that.

### Why this design, not something simpler
- **Redis-first**: hitting the DB on every request would defeat much of the
  point of stateless tokens — cached lookups keep the common case fast.
- **`session_jti` survives refresh rotation**: SimpleJWT rotates refresh
  tokens periodically (`ROTATE_REFRESH_TOKENS=True`); if `session_jti` were
  the token's own jti, it would change on every rotation, making "still the
  same session" meaningless. It's deliberately copied forward through
  rotations to stay a stable identifier for the whole login session.
- **Blacklist too**: the old refresh token is also blacklisted, so it can't
  mint fresh access tokens either — the state check alone would already
  block future requests, this closes the token-reuse path too.

### The documented gap
WebSocket auth (`ws_auth.py`) uses a separate path that doesn't go through
this check — a device kicked off via a new login stops working for REST
calls immediately, but an already-open WebSocket (chat, board) might keep
running until it naturally disconnects.

### The bug this design created
Because "active session" is a *positive* record (must exist and match),
there was no way to represent "nobody is logged in" — only "device A" or
"device B." Without an explicit logout clearing the row, there was no path
back to "no active session" — exactly what a missing `POST /auth/logout/`
caused: the same device trying to log in again the next day got permanently
`409`'d, forced to always pass `force=true`. Fixed by adding a real logout
endpoint that clears the `DeviceSession` row, the Redis key, and blacklists
the refresh token.

---

## 6. RBAC — Role-Based Access Control

### The general idea
Instead of granting permissions per-user, define a small set of **roles**,
attach a bundle of permissions to each, and assign every user exactly one
role. Access control becomes: look up the role, look up what it can do,
check if the requested action is in that list — instead of `if
user.email == 'alice@...'` scattered through the code, which doesn't scale
and can't be audited.

### How this project implements it
Everything lives in one file, [apps/core/permissions.py](apps/core/permissions.py):

```python
ROLE_PERMISSIONS: dict[str, set[str]] = {
    SUPER_ADMIN: {'*'},
    ADMIN: {'course.view', 'course.moderate', 'lesson.cancel', ...},
    TEACHER: {'course.create', 'lesson.schedule', 'room.moderate', ...},
    STUDENT: {'course.view', 'course.enroll', 'lesson.rate', ...},
    PARENT: {'child.create', 'link.request', 'consent.manage', ...},
}
```

Permissions are dotted keys (`module.action`) — a purpose-built vocabulary,
not Django's generic per-model CRUD permissions, since real actions here
(schedule a lesson, moderate a room) don't map onto plain CRUD.

```python
def user_has_perm(user, perm):
    if not user or not user.is_authenticated: return False
    if user.is_superuser: return True
    return role_has_perm(getattr(user, 'role', ''), perm)

def RequirePerm(*perms):
    class _RequirePerm(BasePermission):
        def has_permission(self, request, view):
            return all(user_has_perm(request.user, p) for p in perms)
    return _RequirePerm
```
`RequirePerm(...)` is a **factory returning a DRF permission class** — every
view declares `permission_classes = [RequirePerm('room.moderate')]` instead
of hand-checking roles.

### The rule this enforces
`ARCHITECTURE.md`: *"Ruxsatlar faqat registry'da... View'da hech qachon `if
user.role == ...` yozilmaydi"* — permissions live only in this dictionary. A
view is never allowed to hand-check a role, because with 5 roles and dozens
of actions, letting permission logic leak into individual views means the
same question could get answered two different ways in two files — and
nobody notices until it causes a real bug.

### RBAC answers "can you do this kind of thing" — not "which rows"
`RequirePerm('attendance.view')` says a parent is *allowed to view
attendance* as a category — nothing about *whose*. That's a second, separate
layer: the **selector** (`apps/lessons/selectors.py`) filters the actual
queryset, so a parent's query only returns rows for students with an
`APPROVED` `ParentChildLink`. RBAC is the gate at the door; selectors are the
row-level filter for what's actually returned once through it. A missing
selector filter, not a missing RBAC check, is what would leak another
family's data.

### A real bug from a registry/reality mismatch
Frontend had been told teachers could also create student accounts, but
`child.create` was only granted to `PARENT`. Fix: one line in the registry
(`TEACHER: {..., 'child.create'}`) — but the service logic underneath still
needed to branch on *who* is creating (parent gets an auto-approved link,
teacher doesn't) — RBAC decided "is this allowed," the service still had to
decide what "allowed" means for that specific caller.

### A documented design compromise
Role codes (`'teacher'`, `'student'`, ...) are hardcoded as raw strings in
this file rather than imported from `User.Role`
(`apps/accounts/models.py`), with a comment explaining why: importing them
would create a circular import (`accounts` needs `core` for base models;
`core.permissions` would need `accounts` for role names). Rather than
restructuring app boundaries, the roles are duplicated by hand — an explicit
acknowledgment that this is a workaround, and the two lists must be kept in
sync manually, one level up from the exact problem this registry pattern was
built to prevent within permission logic itself.
