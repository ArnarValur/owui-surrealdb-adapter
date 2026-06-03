# owui-surrealdb-adapter — Docker overlay for Open WebUI
#
# Extends the official OWUI image to add SurrealDB vector backend support.
# No fork required — injects adapter via patch.py at build time.
#
# Build:  docker build -t owui-surrealdb .
# Run:    docker run -e VECTOR_DB=surrealdb -e SURREALDB_URI=ws://surreal:8000/rpc owui-surrealdb

FROM ghcr.io/open-webui/open-webui:latest

# Install the adapter package
COPY . /tmp/owui-surrealdb-adapter
RUN pip install --no-cache-dir /tmp/owui-surrealdb-adapter && \
    rm -rf /tmp/owui-surrealdb-adapter

# Patch OWUI's factory.py + type.py to register surrealdb backend
RUN python -m owui_surrealdb_adapter.patch --owui-root /app/backend/open_webui
