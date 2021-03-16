FROM python:3.9.2-buster
LABEL maintainer="Pouria Hadjibagheri <Pouria.Hadjibagheri@phe.gov.uk>"

# Gunicorn binding port
ENV GUNICORN_PORT 5000

#COPY server/install-nginx.sh          /install-nginx.sh
#
#RUN bash /install-nginx.sh
#RUN rm /etc/nginx/conf.d/default.conf


# Install Supervisord
RUN apt-get update                             && \
    apt-get upgrade -y --no-install-recommends && \
#    apt-get install -y supervisor              && \
    rm -rf /var/lib/apt/lists/*

#COPY server/base.nginx               ./nginx.conf
#COPY server/upload.nginx              /etc/nginx/conf.d/upload.conf
#COPY server/engine.nginx              /etc/nginx/conf.d/engine.conf

COPY ./requirements.txt               /app/requirements.txt

RUN python3 -m pip install --no-cache-dir -U pip                      && \
    python3 -m pip install --no-cache-dir setuptools                  && \
    python3 -m pip install -U --no-cache-dir -r /app/requirements.txt && \
    rm /app/requirements.txt

# Gunicorn config / entrypoint
COPY server/gunicorn_conf.py          /gunicorn_conf.py
COPY server/start-gunicorn.sh         /start-gunicorn.sh
RUN chmod +x /start-gunicorn.sh

#COPY ./start-reload.sh /start-reload.sh
#RUN chmod +x /start-reload.sh

# Custom Supervisord config
#COPY server/supervisord.conf          /etc/supervisor/conf.d/supervisord.conf

# Main service entrypoint - launches supervisord
#COPY server/entrypoint.sh             /entrypoint.sh
#RUN chmod +x /entrypoint.sh


WORKDIR /app

COPY ./app                           ./app

ENV PYTHONPATH /app

EXPOSE 5000

ENTRYPOINT ["/start-gunicorn.sh"]
