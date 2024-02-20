FROM pytorch/pytorch:2.1.2-cuda12.1-cudnn8-runtime

ARG APP_HOME=/app
WORKDIR ${APP_HOME}

ARG PIP_DISABLE_PIP_VERSION_CHECK=1
ARG PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install --no-install-recommends -y \
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

# create supervisord configuration file
RUN echo -e "[supervisord] \n\
nodaemon=true \n\
 \n\
[program:controller] \n\
command=python -m llava.serve... \n\
redirect_stderr=true \n\
autostart=true \n\
autorestart=true \n\
\n\
[program:worker] \n\
command=python -m llava.serve... \n\
redirect_stderr=true \n\
autostart=true \n\
autorestart=true" > /etc/supervisor/conf.d/supervisord.conf

# we could also do this with a detached configuration file and copy the file over like so
#COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
# but it could be very sweet if we have everything in one file

# starts both servers
CMD ["/usr/bin/supervisord"]
