# Imagem do harness do N2 (P5): Cline CLI + JDK 21 + Maven + n2-adapter. Sem credencial de escrita. Versões pinadas (D-40).
# Bases fixadas por digest do índice multi-arquitetura (Docker Hub, conferido em 2026-11-18; a do Maven é a mesma do agent-workflows).
# A imagem dos passos (agent-workflows/Dockerfile) é construída FROM esta: trocar de harness é trocar esta imagem e o n2-adapter.
FROM node:22.23.3-bookworm-slim@sha256:3ed98443660ff48413b5af19ecefce3b9d50845a901a43420d47cc63a9fddbe9 AS cline
# O pacote `cline` traz um binário compilado (Bun embutido) por plataforma; o postinstall o liga em bin/.cline. Só ele vai para a imagem final.
RUN npm install -g --no-audit --no-fund cline@3.0.74 && cp "$(npm root -g)/cline/bin/.cline" /cline && /cline --version

FROM maven:3.9.11-eclipse-temurin-21@sha256:6fdc855a6ed81d288ca7ca37ac6ff5e9308b612485c0801d70b25a858c83d237
RUN apt-get update \
    && apt-get install -y --no-install-recommends git python3 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=cline /cline /usr/local/bin/cline
COPY n2-adapter /opt/n2/n2-adapter
COPY prompts /opt/n2/prompts
COPY workspace /opt/n2/workspace
# O Cline grava estado em ~/.cline; com o root somente leitura do pod, HOME fica no /tmp (emptyDir).
ENV HOME=/tmp DISABLE_TELEMETRY=1 DO_NOT_TRACK=1
USER 10001:10001
