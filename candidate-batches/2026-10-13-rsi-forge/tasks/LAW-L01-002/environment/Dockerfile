FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
RUN apt-get update && apt-get install -y --no-install-recommends bash coreutils tar libreoffice-calc libreoffice-writer fonts-noto-cjk poppler-utils zip unzip && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir openpyxl==3.1.5 python-docx==1.2.0 pypdf==6.10.0 Pillow==12.3.0 lxml==6.1.1 pypdfium2==5.13.0
WORKDIR /workspace
COPY input-data/ /workspace/input-data/
RUN mkdir -p /workspace/output
