FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Place virtualenv outside project directory so volume mounts don't hide it
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy dependency files and install
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# Copy project code
COPY . .

# Build the Tailwind CSS bundle (downloads its own standalone CLI, no Node.js)
RUN python manage.py tailwind build

# Coleta os estáticos para STATIC_ROOT, de onde o WhiteNoise os serve.
# DEBUG=0 é obrigatório aqui: é o que seleciona o storage com manifesto, e o
# manifesto precisa existir na imagem antes do primeiro request em produção.
# SECRET_KEY é descartável — collectstatic não assina nada.
RUN DEBUG=0 SECRET_KEY=build-only-not-a-real-secret \
    python manage.py collectstatic --noinput --clear

# Diretório de uploads. Em produção é montado como volume nomeado; sem isso as
# fotos somem a cada deploy e o dump do Postgres não as recupera.
RUN mkdir -p /app/media
VOLUME ["/app/media"]

EXPOSE 8000

# Servidor WSGI de produção. O compose de desenvolvimento sobrescreve o comando
# com `manage.py tailwind runserver`, que recompila o CSS a cada alteração.
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
