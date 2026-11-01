# Audit tooling stays separate from the application and model image.
FROM python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159
RUN pip install --no-cache-dir pip-audit==2.10.1
WORKDIR /audit
ENTRYPOINT ["pip-audit"]
