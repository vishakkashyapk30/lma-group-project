# syntax=docker/dockerfile:1.7
# Backend image: FastAPI (uvicorn) with the core dependencies only. Heavy extras are opt-in:
#   docker build -f docker/backend.Dockerfile --build-arg EXTRAS=ocr,speech,models,vision,translation .
ARG PYTHON_VERSION=3.12

# ---- 1. dependency venv: invalidated only by pyproject.toml (and EXTRAS) -----------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS venv
ARG EXTRAS=""
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1
RUN python -m venv /venv
WORKDIR /build
COPY pyproject.toml ./
# Build tools only when an extra may need to compile (kept out of the final image either way).
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked --mount=type=cache,target=/var/lib/apt,sharing=locked \
    if [ -n "$EXTRAS" ]; then rm -f /etc/apt/apt.conf.d/docker-clean; apt-get update && apt-get install -y --no-install-recommends build-essential git; fi
RUN python - <<'PY' > /tmp/requirements.txt
import os, tomllib
p = tomllib.load(open("pyproject.toml", "rb"))["project"]
reqs = list(p["dependencies"])
for extra in filter(None, (e.strip() for e in os.environ.get("EXTRAS", "").split(","))):
    reqs += p["optional-dependencies"][extra]
print("\n".join(dict.fromkeys(reqs)))
PY
RUN --mount=type=cache,target=/root/.cache/pip \
    /venv/bin/pip install -r /tmp/requirements.txt && find /venv -name __pycache__ -type d -prune -exec rm -rf {} +

# ---- 2. runtime ---------------------------------------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS runtime
ARG EXTRAS=""
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PATH=/venv/bin:$PATH \
    PYTHONPATH=/app/src VS_CONFIG_DIR=/app/configs VS_DATA_DIR=/app/data HF_HOME=/app/data/.hf
# Runtime system libraries only for the OCR extra (tesseract binary for pytesseract, libGL-free OpenCV needs libglib).
RUN if echo ",$EXTRAS," | grep -q ",ocr,"; then \
      apt-get update && apt-get install -y --no-install-recommends tesseract-ocr libglib2.0-0 && rm -rf /var/lib/apt/lists/*; fi
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin vs \
    && mkdir -p /app/data && chown -R vs:vs /app/data
COPY --from=venv /venv /venv
WORKDIR /app
COPY pyproject.toml ./
COPY configs ./configs
COPY scripts ./scripts
COPY src ./src
USER vs
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=5 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status == 200 else 1)"]
CMD ["uvicorn", "vakeel_sahayak.api.asgi:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

# ---- 3. test target (compose --profile test): runtime + pytest + the tests ---------------------------------------------
FROM runtime AS test
USER root
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir "pytest>=8" "pytest-asyncio>=0.23" "hypothesis>=6" "pyyaml" "reportlab>=4"
COPY tests ./tests
USER vs
ENV HOME=/tmp
HEALTHCHECK NONE
CMD ["pytest", "-p", "no:cacheprovider", "tests/unit", "tests/integration", "tests/system"]

FROM runtime AS final
