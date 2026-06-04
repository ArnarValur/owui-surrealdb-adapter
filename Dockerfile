# owui-surrealdb-adapter — Docker overlay for Open WebUI
#
# Extends the official OWUI image to add SurrealDB vector backend support.
# No fork required — injects adapter via patch.py at build time.
#
# Build:  docker build -t owui-surrealdb .
# Run:    docker run -e VECTOR_DB=surrealdb -e SURREALDB_URI=ws://surreal:8000/rpc owui-surrealdb

FROM ghcr.io/open-webui/open-webui:0.9.6

# Install the adapter package
COPY . /tmp/owui-surrealdb-adapter
RUN pip install --no-cache-dir /tmp/owui-surrealdb-adapter && \
    rm -rf /tmp/owui-surrealdb-adapter

# Backup originals before patching (rollback safety)
RUN cp /app/backend/open_webui/retrieval/vector/factory.py \
       /app/backend/open_webui/retrieval/vector/factory.py.bak && \
    cp /app/backend/open_webui/retrieval/vector/type.py \
       /app/backend/open_webui/retrieval/vector/type.py.bak

# Patch OWUI's factory.py + type.py to register surrealdb backend
RUN python -m owui_surrealdb_adapter.patch --owui-root /app/backend/open_webui
