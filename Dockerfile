FROM python:3.9.2-buster
LABEL maintainer="Pouria Hadjibagheri <Pouria.Hadjibagheri@phe.gov.uk>"

ENV GUNICORN_PORT         5000
ENV PYTHONPATH            /app
ENV GUNICORN_CONF         /gunicorn_conf.py

# Uvicorn worker class
ENV WORKER_CLASS_MODULE   uvicorn_worker
ENV WORKER_CLASS          APIUvicornWorker
# Import path
ENV WORKER_CLASS          $WORKER_CLASS_MODULE.$WORKER_CLASS
ENV WORKER_CLASS_PATH     /$WORKER_CLASS_MODULE.py

ENV PRE_START_PATH        /prestart.sh
ENV GUNICORN_START_PATH   /start-gunicorn.sh


RUN apt-get update                                                   && \
    apt-get upgrade -y --no-install-recommends --no-install-suggests && \
    rm -rf /var/lib/apt/lists/*

RUN addgroup --system --gid 102 app                                  && \
    adduser  --system --disabled-login --ingroup app                    \
             --no-create-home --home /nonexistent                       \
             --gecos "app user" --shell /bin/false --uid 102 app

# Install app requirements
COPY ./requirements.txt               /$PYTHONPATH/requirements.txt

RUN python3 -m pip install --no-cache-dir -U pip                              && \
    python3 -m pip install --no-cache-dir setuptools                          && \
    python3 -m pip install -U --no-cache-dir -r /$PYTHONPATH/requirements.txt && \
    rm /$PYTHONPATH/requirements.txt

# Gunicorn config / entrypoint
COPY server/start-gunicorn.sh         $GUNICORN_START_PATH
COPY server/gunicorn_conf.py          $GUNICORN_CONF
COPY server/uvicorn_worker.py         $WORKER_CLASS_PATH
COPY server/entrypoint.sh             /entrypoint.sh

# Prestart script
COPY server/prestart.py               $PRE_START_PATH

RUN chmod +x $PRE_START_PATH  && \
    chmod +x /entrypoint.sh

# Application
COPY ./app        /$PYTHONPATH/app

USER app

EXPOSE $GUNICORN_PORT

ENTRYPOINT ["/bin/sh", "/entrypoint.sh"]
