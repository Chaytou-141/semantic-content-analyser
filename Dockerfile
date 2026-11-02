FROM python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159

ARG MODEL_REVISION=1110a243fdf4706b3f48f1d95db1a4f5529b4d41
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    HF_HOME=/opt/huggingface MODEL_REVISION=${MODEL_REVISION} \
    TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=2
WORKDIR /app

# CPU-only PyTorch avoids shipping CUDA libraries to the EC2 CPU instance.
COPY requirements.txt requirements-linux.lock ./
RUN pip install --no-cache-dir pip==26.2.2 setuptools==84.1.0
RUN pip install --no-cache-dir -c requirements-linux.lock torch==2.14.1+cpu --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -c requirements-linux.lock -r requirements.txt
RUN python -c "import os; from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', revision=os.environ['MODEL_REVISION'], device='cpu')"
# Runtime never installs packages. Keep setuptools (a torch dependency), remove
# the installer and bundled bootstrap wheel after the trusted build is complete.
RUN python -m pip uninstall -y pip && rm -rf /usr/local/lib/python3.12/ensurepip

COPY semantic_analyser ./semantic_analyser
COPY web/index.html web/app.js web/styles.css web/favicon.svg ./web/
COPY web/fonts/InstrumentSans.ttf web/fonts/OFL.txt ./web/fonts/
COPY data/synthetic_articles.csv data/evaluation_queries.csv ./data/
COPY docs/evaluation-rankings.csv ./docs/
RUN useradd --uid 10001 --create-home appuser \
    && mkdir -p /app/runtime \
    && chown -R appuser:appuser /app/runtime /opt/huggingface
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 DATABASE_PATH=/app/runtime/workspace.sqlite3
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"
CMD ["python", "-m", "uvicorn", "semantic_analyser.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-proxy-headers", "--limit-concurrency", "32", "--backlog", "64", "--timeout-keep-alive", "5"]
