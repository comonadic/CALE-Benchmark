FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258

ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 LANG=C.UTF-8
RUN apt-get update && apt-get install -y --no-install-recommends bash coreutils tar libreoffice-calc libreoffice-writer fonts-noto-cjk poppler-utils && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir openpyxl==3.1.5 python-docx==1.2.0 pypdf==6.10.0 pillow==12.3.0 lxml==6.1.1 pypdfium2==5.13.0
RUN apt-get update && apt-get install -y --no-install-recommends procps && rm -rf /var/lib/apt/lists/*
RUN python - <<'INSTALL'
import base64,hashlib,io,platform,tarfile,urllib.request
arch={"aarch64":"arm64","x86_64":"x64"}[platform.machine()]
integrity={"arm64":"Q6Qh6qFmwuBG9rQFiDR6bY3XkFnwTN9AAPrnnDgBvr9sbg1Ql5wrf0lfoCDiV369EUHOzxI4i5OdHW9Vf2/oeA==","x64":"+m01urgelnI+VJxPaKPEK0wixgq42uZ8PeCaUk5tX/8YoDBvSmC/REVQG2jQfJAr8dxunpjJ600FvLrcj1WWTw=="}
url=f"https://registry.npmjs.org/@anthropic-ai/claude-code-linux-{arch}/-/claude-code-linux-{arch}-2.1.296.tgz"
data=urllib.request.urlopen(url,timeout=300).read()
assert base64.b64encode(hashlib.sha512(data).digest()).decode()==integrity[arch],"Claude Code package integrity mismatch"
with tarfile.open(fileobj=io.BytesIO(data),mode="r:gz") as archive:
    binary=archive.extractfile("package/claude").read()
with open("/usr/local/bin/claude","wb") as target:target.write(binary)
import os
os.chmod("/usr/local/bin/claude",0o755)
INSTALL
RUN claude --version
WORKDIR /workspace
RUN mkdir -p /workspace/input-data /workspace/output /logs/agent /logs/verifier
ENV OFFICE_CONFIG_ROOT=/tmp/harbor-office
COPY input-data/ /workspace/input-data/
RUN mkdir -p /workspace/output /tmp/harbor-office && chmod -R a-w /workspace/input-data
