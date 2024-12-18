FROM python:3.12-slim

RUN apt-get update \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir /app

WORKDIR /app
COPY requirements.txt /app
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

ENTRYPOINT ["python", "check-tx.py"]
