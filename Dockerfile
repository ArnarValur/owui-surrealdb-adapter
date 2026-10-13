# owui-surrealdb-adapter — Docker overlay for Open WebUI
#
# Extends the official OWUI CUDA image (arm64). No frontend build, no custom base.
# No fork required — injects adapter via patch.py at build time.
#
# Build:  docker build -t owui-surrealdb .
# Run:    docker run -e VECTOR_DB=surrealdb -e SURREALDB_URI=ws://surreal:8000/rpc owui-surrealdb

FROM ghcr.io/open-webui/open-webui:0.11.3-cuda

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

# HOTPATCH gemini-tool-call-index (added 2026-09-08)
# Google's OpenAI-compatible endpoint streams tool calls without an `index`
# field, so OWUI silently drops them and the reply comes back empty.
# See hotpatches/gemini_tool_call_index.py for the full write-up.
COPY hotpatches/ /tmp/hotpatches/
RUN python /tmp/hotpatches/gemini_tool_call_index.py --owui-root /app/backend/open_webui && \
    python /tmp/hotpatches/gemini_thought_signature.py --owui-root /app/backend/open_webui && \
    rm -rf /tmp/hotpatches
