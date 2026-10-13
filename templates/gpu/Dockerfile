# PyTorch image is a third-party dependency; see THIRD_PARTY_NOTICES.md.
FROM pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 DEBIAN_FRONTEND=noninteractive TZ=Asia/Shanghai
WORKDIR /workspace

# Packages may generate SSH host keys on installation: remove them in this SAME layer.
RUN apt-get update && apt-get install -y --no-install-recommends \
      git openssh-client openssh-server nano vim screen tmux curl wget \
      ca-certificates htop unzip zip util-linux \
    && rm -f /etc/ssh/ssh_host_* \
    && useradd --create-home --uid 1000 --shell /bin/bash developer \
    && mkdir -p /run/sshd /workspace/mlflow/artifacts \
    && chown -R developer:developer /workspace /home/developer \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# No private user key, authorized key, password or token is baked into this image.
COPY sshd_config /etc/ssh/sshd_config
COPY requirements.txt /opt/gpu-template/requirements.txt
RUN pip install --no-cache-dir 'jupyterlab>=4,<5' 'mlflow>=3.5' \
    && pip install --no-cache-dir -r /opt/gpu-template/requirements.txt

COPY start_service.sh /usr/local/bin/start-gpu-services
RUN chmod 755 /usr/local/bin/start-gpu-services
EXPOSE 8888
CMD ["/usr/local/bin/start-gpu-services"]
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl --silent --output /dev/null --write-out "%{http_code}" http://127.0.0.1:8888/ | grep -Eq "^(200|302|403)$"
