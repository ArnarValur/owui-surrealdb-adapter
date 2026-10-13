"""
HOTPATCH: Gemini tool calls are dropped because the delta carries no `index`.

Google's OpenAI-compatible endpoint (generativelanguage.googleapis.com/v1beta/openai)
streams a complete tool call in a single delta and omits the `index` field.
Open WebUI's stream reader in utils/middleware.py does:

    tool_call_index = delta_tool_call.get('index')
    if tool_call_index is not None:
        ... accumulate ...

so a tool call without `index` is silently skipped. It never reaches the
execution loop, and the user gets an empty assistant message.

This patch assigns a positional index when the provider omits one.

Idempotent. Run:
    python hotpatches/gemini_tool_call_index.py --owui-root /app/backend/open_webui
"""

import argparse
import pathlib
import sys

MARKER = "HOTPATCH gemini-tool-call-index"

OLD = """                                        for delta_tool_call in delta_tool_calls:
                                            tool_call_index = delta_tool_call.get('index')

                                            if tool_call_index is not None:"""

NEW = """                                        for delta_tool_call in delta_tool_calls:
                                            tool_call_index = delta_tool_call.get('index')

                                            # HOTPATCH gemini-tool-call-index: Google's
                                            # OpenAI-compatible endpoint streams a complete
                                            # tool call with no `index`. Without one the call
                                            # is dropped and the reply comes back empty.
                                            if tool_call_index is None:
                                                tool_call_index = len(response_tool_calls)
                                                delta_tool_call['index'] = tool_call_index

                                            if tool_call_index is not None:"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--owui-root", default="/app/backend/open_webui")
    args = ap.parse_args()

    target = pathlib.Path(args.owui_root) / "utils" / "middleware.py"
    src = target.read_text()

    if MARKER in src:
        print(f"already patched: {target}")
        return 0

    if OLD not in src:
        print(f"ERROR: patch anchor not found in {target}", file=sys.stderr)
        print("Open WebUI upstream changed. Re-check the tool_calls delta reader.", file=sys.stderr)
        return 1

    backup = target.with_suffix(".py.pre-gemini-hotpatch.bak")
    if not backup.exists():
        backup.write_text(src)

    target.write_text(src.replace(OLD, NEW, 1))
    print(f"patched: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
