"""Generate two independent secrets; keep both in Railway environment variables."""
import secrets
print('ADMIN_SESSION_SECRET='+secrets.token_urlsafe(48))
print('STUDY_SECRET='+secrets.token_urlsafe(48))
