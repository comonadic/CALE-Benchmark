FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends libreoffice-calc fonts-noto-cjk && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir openpyxl==3.1.5 pypdf==6.10.0
WORKDIR /
COPY assertions.json /tests/assertions.json
COPY grade.py /tests/grade.py
COPY test.sh /tests/test.sh
RUN chmod +x /tests/test.sh
