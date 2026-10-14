FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends bash coreutils libreoffice-calc libreoffice-writer fonts-noto-cjk poppler-utils && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir openpyxl==3.1.5 python-docx==1.2.0 pypdf==6.10.0 reportlab==4.4.9
WORKDIR /workspace
COPY input-data/ /workspace/input-data/
RUN mkdir -p /workspace/output
