# Ralph Workflow Sandbox Image
#
# Runs opencode inside an isolated container with only:
# - read/write access to the mounted project dir (/workspace)
# - access to opencode credentials (/home/ralph/.local/share/opencode)
# - network (to reach LLM providers)
# - git + common build tooling
#
# Includes: Python 3.12, uv, Node.js 22 LTS + npm, Go 1.24, opencode.
# Runs as non-root user `ralph` (UID/GID configurable via build args).

FROM ubuntu:24.04

ARG UID=1000
ARG GID=1000
ARG USERNAME=ralph
ARG NODE_MAJOR=22
ARG GO_VERSION=1.24.3

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# --- System packages + Python 3.12 (native in Ubuntu 24.04) ---
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        wget \
        bash \
        git \
        unzip \
        make \
        sudo \
        passwd \
        gnupg \
        lsb-release \
        python3.12 \
        python3.12-venv \
        python3.12-dev \
        python3-pip \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.12 1 \
    && rm -rf /var/lib/apt/lists/*

# --- Docker CE CLI + Docker Compose plugin ---
# The container accesses the host docker daemon via /var/run/docker.sock.
RUN install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc \
    && chmod a+r /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/* \
    && docker --version \
    && docker compose version

# --- Node.js 22 LTS + npm ---
RUN curl -fsSL https://deb.nodesource.com/setup_${NODE_MAJOR}.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && node --version && npm --version

# --- Go ---
RUN curl -fsSL "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz" \
    | tar -C /usr/local -xzf - \
    && /usr/local/go/bin/go version

ENV PATH=/usr/local/go/bin:${PATH}

# --- uv (Python package manager) ---
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && mv /root/.local/bin/uv /usr/local/bin/uv \
    && mv /root/.local/bin/uvx /usr/local/bin/uvx \
    && uv --version

# --- Create non-root user ---
# ubuntu:24.04 ships with a default `ubuntu` user at UID 1000. If our target
# UID/GID collides with it, remove it so we can create our own user cleanly.
RUN set -eux; \
    if getent passwd "${UID}" >/dev/null; then \
        existing_user="$(getent passwd "${UID}" | cut -d: -f1)"; \
        /usr/sbin/userdel -r "${existing_user}" 2>/dev/null || /usr/sbin/userdel "${existing_user}"; \
    fi; \
    if getent group "${GID}" >/dev/null; then \
        existing_group="$(getent group "${GID}" | cut -d: -f1)"; \
        /usr/sbin/groupdel "${existing_group}" 2>/dev/null || true; \
    fi; \
    /usr/sbin/groupadd -g "${GID}" "${USERNAME}"; \
    /usr/sbin/useradd  -m -u "${UID}" -g "${GID}" -s /bin/bash "${USERNAME}"; \
    echo "${USERNAME} ALL=(ALL) NOPASSWD: ALL" > "/etc/sudoers.d/${USERNAME}"; \
    chmod 0440 "/etc/sudoers.d/${USERNAME}"

ENV HOME=/home/ralph \
    PATH=/home/ralph/.opencode/bin:/home/ralph/.local/bin:/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    GOPATH=/home/ralph/go

USER ralph
WORKDIR /home/ralph

# --- Install opencode as ralph ---
RUN curl -fsSL https://opencode.ai/install | bash \
    && /home/ralph/.opencode/bin/opencode --version

WORKDIR /workspace

CMD ["opencode", "--help"]
