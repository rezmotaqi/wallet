FROM python:3.10.5-slim-buster
RUN apt-get update \
    && apt-get install -y \
    libpq-dev\
    libssl-dev \
    libffi-dev \
    libatlas-base-dev \
    gcc libffi-dev libssl-dev python-dev \
    cargo \
    rustc \
    wget xvfb \
    libxrender1 \
    libjpeg62-turbo \
    fontconfig fonts-texgyre latexml xindy \
    libxtst6 \
    xfonts-100dpi xfonts-scalable xfonts-cyrillic xfonts-75dpi xfonts-base \
    xz-utils
ENV TZ=UTC
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
RUN mkdir -p /usr/app/core
WORKDIR /usr/app/core
RUN pip --default-timeout=60 --timeout 100 --retries 10 install --upgrade pip
RUN pip --default-timeout=60 --timeout 100 --retries 10 install --upgrade pip setuptools wheel
COPY . .
RUN pip --default-timeout=60 --timeout 100 --retries 10 install -r requirements/develop.txt
