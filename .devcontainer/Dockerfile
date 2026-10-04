FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

RUN rm -f /etc/apt/sources.list.d/yarn.list

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates postgresql-client \
    && rm -rf /var/lib/apt/lists/*

ARG GO_VERSION=1.25.14

ARG GO_SHA256=a21ae5633a269bcd7e90cf767e48225633795e99d831742cbf3397064fee7712

RUN curl -fsSL "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz" -o /tmp/go.tar.gz \
    && echo "${GO_SHA256}  /tmp/go.tar.gz" | sha256sum -c - \
    && rm -rf /usr/local/go \
    && tar -C /usr/local -xzf /tmp/go.tar.gz \
    && rm /tmp/go.tar.gz

ENV PATH="/usr/local/go/bin:${PATH}"
RUN ln -sf /usr/local/go/bin/go /usr/local/bin/go

COPY python/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt \
    && python -m pip install --no-cache-dir torch==2.8.0 \
       --index-url https://download.pytorch.org/whl/cpu

USER vscode
