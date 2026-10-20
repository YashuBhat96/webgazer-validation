# Public release check

This repository is intended to contain source code and public documentation only.

The distributed ZIP excludes all environment files, sample credential files, participant data, and generated test caches. Automated tests generate disposable credentials at runtime.

The server expects administrator authentication settings, session signing settings, and object storage configuration to be supplied through Railway environment variables. The code deliberately does not contain working credentials.

This check does not establish that previously published Git commits were free of credentials. Any credentials that were ever committed should be revoked and replaced before a public release.
