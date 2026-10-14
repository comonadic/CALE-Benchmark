FROM python:3.12-slim-bookworm
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash coreutils libreoffice-calc libreoffice-writer fonts-noto-cjk poppler-utils \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir openpyxl==3.1.5 reportlab==4.4.9 pypdf==6.10.0 pymupdf==1.26.7
WORKDIR /workspace
COPY input-data/ /workspace/input-data/
RUN mkdir -p /workspace/output
