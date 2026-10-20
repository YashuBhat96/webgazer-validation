# Changes in v2.5

1. Removed participant invitation links and admin invitation generation. Public `/api/public-session` issues random, expiring, upload-only credentials automatically. Data collection remains controlled by a final manual submit button.
2. Removed admin authenticator code. Password is verified using Argon2id and the researcher token is held only in live page JavaScript memory. Closing or refreshing the page requires entering the password again; token expires in 30 minutes even if the tab stays open.
3. Created dashboard cards for completed, incomplete, uploading and total sessions, computed from **all** stored session objects rather than truncating counts to 250.
4. Added an authenticated bulk study ZIP export, with original compressed JSON, CSV data tables, manifests, overall study CSV and per-session PNG plots. Kept per-session ZIP downloads.
5. Added an open-study kill switch, per-process registration throttling, and per-session size/batch limits. These controls do not stop a sophisticated or distributed adversary. Add managed edge protection before wider public use.
6. Preserved WebGazer 2.0.1, 25 visual search trials, optional name/sex, previous tracker experience yes/no, and all previous raw/derived gaze calculations.

Tests: 5 FastAPI tests; browser smoke; dashboard headless browser smoke; JavaScript manual submission tests; quality regression and gaze kinematics tests. No real Railway bucket, security penetration test, or webcam performance study was conducted.
