FROM python:3.12-slim

# libpostal downloads its model during `make` (roughly 2 GB), so the first build
# takes a while and produces a sizeable image.
RUN apt-get update && apt-get install -y --no-install-recommends \
    autoconf automake build-essential curl git libtool pkg-config \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 https://github.com/openvenues/libpostal /tmp/libpostal \
    && cd /tmp/libpostal \
    && ./bootstrap.sh \
    && ./configure --datadir=/usr/local/share \
    && make -j"$(nproc)" \
    && make install \
    && ldconfig \
    && rm -rf /tmp/libpostal

WORKDIR /service
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
