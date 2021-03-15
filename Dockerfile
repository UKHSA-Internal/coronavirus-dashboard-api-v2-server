FROM python:3.9.2-buster
LABEL maintainer="Pouria Hadjibagheri <Pouria.Hadjibagheri@phe.gov.uk>"

# Gunicorn binding port
ENV GUNICORN_PORT 5200

COPY server/install-nginx.sh          /install-nginx.sh

RUN bash /install-nginx.sh
RUN rm /etc/nginx/conf.d/default.conf


# Install Supervisord
RUN apt-get update                             && \
    apt-get upgrade -y --no-install-recommends && \
    apt-get install -y supervisor              && \
    rm -rf /var/lib/apt/lists/*

COPY server/base.nginx               ./nginx.conf
COPY server/upload.nginx              /etc/nginx/conf.d/upload.conf
COPY server/engine.nginx              /etc/nginx/conf.d/engine.conf


RUN python3 -m pip install --no-cache-dir -U pip                      && \
    python3 -m pip install --no-cache-dir setuptools                  && \
    python3 -m pip install --no-cache-dir "uvicorn[standard]" gunicorn

# Gunicorn config
COPY server/gunicorn_conf.py          /gunicorn_conf.py

# Gunicorn entrypoint - used by supervisord
COPY server/start-gunicorn.sh         /start-gunicorn.sh
RUN chmod +x /start-gunicorn.sh

# Custom Supervisord config
COPY server/supervisord.conf          /etc/supervisor/conf.d/supervisord.conf

# Main service entrypoint - launches supervisord
COPY server/entrypoint.sh             /entrypoint.sh
RUN chmod +x /entrypoint.sh


WORKDIR /app

COPY ./app                           ./app
COPY ./requirements.txt              ./requirements.txt

RUN python3 -m pip install -U --no-cache-dir -r ./requirements.txt    && \
    rm ./requirements.txt

EXPOSE 5000

ENTRYPOINT ["/entrypoint.sh"]
