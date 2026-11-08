FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b
RUN apt-get update && apt-get install -y --no-install-recommends iptables \
    zlib1g=1:1.3.dfsg+really1.3.1-1+deb13u1 \
    && rm -rf /var/lib/apt/lists/*
RUN python -m pip uninstall -y pip && rm -rf /usr/local/lib/python3.12/ensurepip
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /egress
COPY deploy/egress/policy.py ./policy.py
HEALTHCHECK --interval=2s --timeout=3s --start-period=10s --retries=2 \
    CMD ["python", "/egress/policy.py", "health"]
CMD ["python", "/egress/policy.py", "run"]
