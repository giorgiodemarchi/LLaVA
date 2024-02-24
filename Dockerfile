FROM pytorch/pytorch:2.1.2-cuda12.1-cudnn8-runtime

ARG APP_HOME=/app
WORKDIR ${APP_HOME}

ARG PIP_DISABLE_PIP_VERSION_CHECK=1
ARG PIP_NO_CACHE_DIR=1

ARG CONTROLLER_CMD="python -m llava.serve.controller --host 0.0.0.0 --port 10000"
ARG WORKER_CMD="python -m llava.serve.model_worker --host 0.0.0.0 --controller http://localhost:10000 --port 40000 --worker http://localhost:40000 --model-path liuhaotian/llava-v1.5-13b --load-4bit"

RUN apt-get update && apt-get install --no-install-recommends -y \
  git \ 
  # text editors
  nano \
  vim  \
  # supervisor for running multiple servers
  supervisor  \
  # cleanup cache etc to keep image small
  && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
  && rm -rf /var/lib/apt/lists/*

# the idea is that we can place this Dockerfile anywhere, so let's install remotely
RUN pip install git+https://github.com/giorgiodemarchi/LLaVa

RUN pip install protobuf

RUN mkdir -p /etc/supervisor/conf.d && \
    echo "[supervisord]" > /etc/supervisor/conf.d/supervisord.conf && \
    echo "nodaemon=true" >> /etc/supervisor/conf.d/supervisord.conf && \
    echo "" >> /etc/supervisor/conf.d/supervisord.conf && \
    echo "[program:controller]" >> /etc/supervisor/conf.d/supervisord.conf && \
    echo "command=$CONTROLLER_CMD" >> /etc/supervisor/conf.d/supervisord.conf && \
    echo "redirect_stderr=true" >> /etc/supervisor/conf.d/supervisord.conf && \
    echo "autostart=true" >> /etc/supervisor/conf.d/supervisord.conf && \
    echo "autorestart=true" >> /etc/supervisor/conf.d/supervisord.conf && \
    echo "" >> /etc/supervisor/conf.d/supervisord.conf && \
    echo "[program:worker]" >> /etc/supervisor/conf.d/supervisord.conf && \
    echo "command=$WORKER_CMD" >> /etc/supervisor/conf.d/supervisord.conf && \
    echo "redirect_stderr=true" >> /etc/supervisor/conf.d/supervisord.conf && \
    echo "autostart=true" >> /etc/supervisor/conf.d/supervisord.conf && \
    echo "autorestart=true" >> /etc/supervisor/conf.d/supervisord.conf

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]


### docker run -p 10000:10000 --gpus all --ipc=host --ulimit memlock=-1 --ulimit stack=67108864 llava