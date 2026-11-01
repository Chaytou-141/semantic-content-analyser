FROM python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159
RUN apt-get update && apt-get install -y --no-install-recommends iptables \
    && rm -rf /var/lib/apt/lists/*
RUN python -m pip uninstall -y pip && rm -rf /usr/local/lib/python3.12/ensurepip
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /egress
COPY deploy/egress/policy.py ./policy.py
HEALTHCHECK --interval=2s --timeout=3s --start-period=10s --retries=2 \
    CMD ["python", "/egress/policy.py", "health"]
CMD ["python", "/egress/policy.py", "run"]
