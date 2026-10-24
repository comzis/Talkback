# app/Dockerfile
FROM python:3.11-slim

ARG UID=502
ARG GID=20

WORKDIR /app

RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && if ! getent group ${GID} >/dev/null; then groupadd --gid ${GID} appgroup; fi \
    && useradd --uid ${UID} --gid ${GID} --create-home --no-log-init appuser \
    && mkdir -p /cache/huggingface /app/data \
    && chown -R ${UID}:${GID} /app /cache

COPY requirements.txt .
# CPU wheel first. A later install must not replace it with the CUDA build.
RUN pip install --no-cache-dir torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt \
    && python -c "import importlib.util, torch; print(torch.__version__); banned=[name for name in ('nvidia', 'nvidia_cublas', 'nvidia_cuda_runtime') if importlib.util.find_spec(name)]; \
assert not banned, banned"

COPY --chown=${UID}:${GID} . .

ENV HF_HOME=/cache/huggingface \
    HUGGINGFACE_HUB_CACHE=/cache/huggingface/hub \
    SENTENCE_TRANSFORMERS_HOME=/cache/huggingface/sentence-transformers \
    HOME=/home/appuser

USER ${UID}:${GID}

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
