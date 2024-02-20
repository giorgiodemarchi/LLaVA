FROM pytorch/pytorch:2.1.2-cuda12.1-cudnn8-runtime

ARG APP_HOME=/app
WORKDIR ${APP_HOME}

ARG PIP_DISABLE_PIP_VERSION_CHECK=1
ARG PIP_NO_CACHE_DIR=1

COPY requirements.txt requirements.txt

RUN apt-get update && apt-get install --no-install-recommends -y \
  # text editor
  nano \
  ffmpeg \
  # cleanup cache etc
  && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
  && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY ./ ./

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8200"]
