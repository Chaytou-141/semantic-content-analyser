FROM python:3.12-slim

ARG MODEL_REVISION=1110a243fdf4706b3f48f1d95db1a4f5529b4d41
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    HF_HOME=/opt/huggingface MODEL_REVISION=${MODEL_REVISION} \
    TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=2
WORKDIR /app

# CPU-only PyTorch avoids shipping CUDA libraries to the EC2 CPU instance.
RUN pip install --no-cache-dir torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN python -c "import os; from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', revision=os.environ['MODEL_REVISION'], device='cpu')"

COPY semantic_analyser ./semantic_analyser
COPY web ./web
COPY data/synthetic_articles.csv data/evaluation_queries.csv ./data/
COPY docs/evaluation-rankings.csv ./docs/
COPY deploy/aws ./deploy/aws
RUN useradd --uid 10001 --create-home appuser \
    && mkdir -p /app/runtime \
    && chown -R appuser:appuser /app/runtime /opt/huggingface
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 DATABASE_PATH=/app/runtime/workspace.sqlite3
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"
CMD ["python", "-m", "uvicorn", "semantic_analyser.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-proxy-headers", "--limit-concurrency", "32", "--backlog", "64", "--timeout-keep-alive", "5"]
