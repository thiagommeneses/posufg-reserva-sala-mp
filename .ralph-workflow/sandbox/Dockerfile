# Ralph Workflow Sandbox Image
#
# Runs opencode inside an isolated container with only:
# - read/write access to the mounted project dir (/workspace)
# - access to opencode credentials (/home/ralph/.local/share/opencode)
# - network (to reach LLM providers)
# - git + common build tooling
#
# Runs as non-root user `ralph` (UID/GID configurable via build args).

FROM ubuntu:24.04

ARG UID=1000
ARG GID=1000
ARG USERNAME=ralph

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        bash \
        git \
        unzip \
        sudo \
        passwd \
    && rm -rf /var/lib/apt/lists/*

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
    PATH=/home/ralph/.opencode/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

USER ralph
WORKDIR /home/ralph

# Install opencode as the ralph user (installer writes to $HOME/.opencode).
RUN curl -fsSL https://opencode.ai/install | bash \
    && /home/ralph/.opencode/bin/opencode --version

WORKDIR /workspace

CMD ["opencode", "--help"]
