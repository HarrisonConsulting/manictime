FROM python:3.10-slim-bullseye

# Install dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    postgresql-client \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && apt-get update \
    && apt-get install -y sudo \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

# Configure Python environment
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install Python tools and testing dependencies
RUN pip install --upgrade pip \
    && pip install pytest pytest-cov pylint black isort mypy requests-mock

WORKDIR /workspace

# Switch to non-root user
USER $USERNAME