# vim: ft=dockerfile

FROM python:3.8-slim-bullseye

ARG USER_UID
ARG USER_GID
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 USER_UID=$USER_UID USER_GID=$USER_GID

COPY --chown="$USER_UIR":"$USER_GID" ./requirements.txt .

RUN apt-get update \
    && apt-get -y install build-essential perl ruby \
    && pip install --upgrade pip \
    && pip install -r requirements.txt

COPY --chown="$USER_UID":"$USER_GID" ./tools/geniass /tools/geniass
RUN cd /tools/geniass && make

COPY disease-network/delete-old-disease-graphs.cron /etc/cron.daily/delete-old-disease-graphs

WORKDIR /app

RUN groupadd -g "$USER_GID" biomedtext \
    && useradd -m -s /bin/bash -u "$USER_UID" -g "$USER_GID" biomedtext

USER biomedtext
