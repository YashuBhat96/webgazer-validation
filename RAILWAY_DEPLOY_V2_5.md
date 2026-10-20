# Railway deployment | WebGazer validation v2.5

## Architecture

One Railway deployment for FastAPI, webpage and researcher portal; one **private Railway Storage Bucket** for research data. GitHub is the deployment source, **not GitHub Pages**. The frontend, admin portal and API share the same HTTPS domain so browser CORS exceptions are unnecessary.

## 1. Create private GitHub repository

Push the **contents of this folder** to a private GitHub repository. Preserve the root-level `Dockerfile`, `railway.json`, `index.html`, `upload.js` and `backend/`. Never commit `.env`, passwords, bucket credentials, or participant data.

## 2. Create Railway web service and private bucket

* Create a Railway project and deploy from that repository. Keep the **repository root** as the build root; Railway builds using the included Dockerfile.
* Add a **Storage Bucket** to the Railway project. Reference its endpoint, bucket name, access key and secret key as service environment variables. Keep the bucket private. Confirm the bucket's S3 endpoint and addressing mode in Railway's current documentation.
* Generate an HTTPS public domain for the FastAPI service. Use that exact HTTPS origin as `PUBLIC_BASE_URL`.

## 3. Generate researcher secrets, locally

Install `argon2-cffi`, then run:

```bash
python3 -m pip install 'argon2-cffi>=23,<26'
python3 backend/make_admin_hash.py
python3 backend/create_admin_secrets.py
```

The password script prints a password hash. Use a unique strong password, preferably from a password manager. The secrets script prints TWO independently generated secrets. Put all three in Railway's environment variables, **not in the GitHub repository**. There is no 6 digit authenticator code in v2.5.

## 4. Add service environment variables

Configure the following variables directly in Railway. No environment file or credential values are included in the repository. Required:

* `PUBLIC_BASE_URL`: Exact Railway HTTPS origin, e.g. `https://your-study.up.railway.app`
* `STUDY_SECRET`: Random 40+ character secret to sign anonymous session upload credentials
* `ADMIN_PASSWORD_HASH`: Password hash from the script
* `ADMIN_SESSION_SECRET`: Separate random 40+ character secret to sign 30 minute administrator tokens
* `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`: Railway bucket values
* `S3_REGION`: Usually `auto` for Railway bucket (verify your bucket)
* `S3_ADDRESS_STYLE`: Usually `virtual` (verify your bucket)

Optional:

* `PUBLIC_STUDY_ENABLED=true`: Set to `false` to stop issuing NEW anonymous sessions immediately; it does not revoke existing unexpired capabilities.
* `PUBLIC_SESSION_MAX_PER_HOUR_PER_IP=120`: In-process basic request throttle. For public deployment use a proper managed edge rate limiter as well; shared/proxied IPs need care.

## 5. Test endpoints and behavior

* `https://YOUR_DOMAIN/`: Participant page. No invitation link. Optional name, previous eye tracker experience yes/no, guided setup, WebGazer calibration, 12 point validation and **25 search trials**.
* `https://YOUR_DOMAIN/admin`: Admin page; password only, required again if the page closes or refreshes. Dashboard counts full submitted sessions and offers per-session and all-study ZIP downloads.
* `GET /health`: Minimal public service status; no private data.
* `POST /api/public-session`: Public creation of a random capability, no study data transmitted.
* `POST /api/sessions`, `/api/sessions/{session_id}/batches/{seq}`, `/api/sessions/{session_id}/complete`: Requires a valid short-lived session bearer token scoped to that session. No participant GET/list/read endpoint exists.
* `POST /admin/api/login`: Requires the admin password and returns short-lived bearer token. All admin reads/export routes require that token; browser keeps it only in webpage memory.

Verify storage with a fake pilot session: click the final button; dashboard should update within 20 sec, mark it complete, and export ZIP with raw JSON, multiple CSV tables and at least some PNG gaze plots. Test interrupted submission and retry.

## 6. Limitations and institutional approval

* Anonymous public participation allows repeat completions and spam. Counts represent sessions, **not verified unique people**. Use edge protection, quota alerting, abuse monitoring and explicit participant eligibility / consent procedures. A valid invitation is no longer a prerequisite.
* Admin password-only authentication is intentional, but is weaker than MFA. Admin bearer tokens remain valid for up to 30 minutes if intercepted, although they are never stored in cookies or browser storage. Use HTTPS, avoid third-party scripts on the admin page, and consider an institutional identity proxy.
* Dashboard browser export is limited to ~350 MB of compressed bucket objects; larger datasets need the command-line export or a paginated archive job. On Railway, rendering many plots could exceed request timeout and memory; test before public deployment.
* No real Railway service or bucket was connected during automated tests, and no live webcam validation has been completed.
* Optional names, demographics and raw gaze can be sensitive research information. Obtain approval for Railway storage and implement private backups, institutional retention schedules and access controls. No uploaded webcam images are stored by design.
