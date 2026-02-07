# Use Microsoft's official devcontainer Python image
# Includes most remote development tools - adding socat for Antigravity port forwarding
FROM mcr.microsoft.com/devcontainers/python:3.13

# Install socat - required by Antigravity's port forwarder
RUN apt-get update && apt-get install -y --no-install-recommends socat \
    && rm -rf /var/lib/apt/lists/*

# Metadata labels
LABEL org.opencontainers.image.title="Wealth-Ops Dev"
LABEL org.opencontainers.image.description="Development container for Wealth-Ops trading system"
LABEL org.opencontainers.image.source="https://github.com/wealth-ops/wealth-ops"
LABEL project="wealth-ops"

# Install Poetry
ENV POETRY_HOME="/opt/poetry" \
    POETRY_VERSION="1.8.2" \
    POETRY_VIRTUALENVS_CREATE=false
RUN curl -sSL https://install.python-poetry.org | python3 - \
    && ln -s /opt/poetry/bin/poetry /usr/local/bin/poetry

# Set working directory
WORKDIR /workspaces/wealth-ops
