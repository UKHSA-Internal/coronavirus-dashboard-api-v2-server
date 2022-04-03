FROM python:3.10-bullseye
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

ENV PRE_START_PATH        /opt/prestart.sh
ENV GUNICORN_START_PATH   /opt/start-gunicorn.sh
ENV NUMEXPR_MAX_THREADS   1
ENV WORKERS_PER_CORE      2

ENV USER_NAME             app
ENV USER_GROUP            ${USER_NAME}grp


RUN set -xe;                                                            \
    apt-get update;                                                     \
    apt-get upgrade -y --no-install-recommends --no-install-suggests;   \
    rm -rf /var/lib/apt/lists/*

RUN apt-get remove curl wget; \
    apt-get purge

RUN addgroup --system --gid 102 ${USER_GROUP}

RUN adduser  --system                  \
             --disabled-login          \
             --home /home/${USER_NAME} \
             --gecos ""                \
             --shell /bin/false        \
             --uid 103                 \
             --gid 102                 \
             ${USER_NAME}

# Gunicorn config / entrypoint
COPY --chown=$USER_NAME:$USER_GROUP server/start-gunicorn.sh         $GUNICORN_START_PATH
COPY --chown=$USER_NAME:$USER_GROUP server/gunicorn_conf.py          $GUNICORN_CONF
COPY --chown=$USER_NAME:$USER_GROUP server/uvicorn_worker.py         $WORKER_CLASS_PATH


# Install app requirements
COPY --chown=$USER_NAME:$USER_GROUP ./requirements.txt               $PYTHONPATH/requirements.txt

RUN python3 -m pip install --no-cache-dir -U pip wheel setuptools;               \
    python3 -m pip install -U --no-cache-dir -r $PYTHONPATH/requirements.txt

RUN rm -f $PYTHONPATH/requirements.txt


# Startup
COPY --chown=$USER_NAME:$USER_GROUP server/entrypoint.sh             /opt/entrypoint.sh

# Prestart script
COPY --chown=$USER_NAME:$USER_GROUP server/prestart.py               $PRE_START_PATH

# Application
COPY --chown=$USER_NAME:$USER_GROUP ./app        $PYTHONPATH/app

RUN chmod 0500 -f $PRE_START_PATH;      \
    chmod 0500 -f /opt/entrypoint.sh;   \
    chmod 0500 -Rf $PYTHONPATH/app;     \
    chmod 0500 -f $GUNICORN_START_PATH; \
    chmod 0500 -f $GUNICORN_CONF;       \
    chmod 0500 -f $WORKER_CLASS_PATH;

USER ${USER_NAME}

EXPOSE $GUNICORN_PORT

ENTRYPOINT ["/bin/sh", "/opt/entrypoint.sh"]
