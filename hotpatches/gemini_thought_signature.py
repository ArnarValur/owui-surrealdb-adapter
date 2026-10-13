"""
HOTPATCH: carry Gemini's `thought_signature` through the tool-call round trip.

Gemini 3.x thinking models attach a signed blob to every tool call:

    "tool_calls": [{"id": ..., "extra_content": {"google": {"thought_signature": "..."}}, ...}]

Google requires that blob to come back when the tool result is submitted. If it
is missing the follow-up request is rejected with HTTP 400:

    Function call is missing a thought_signature in functionCall parts.

Open WebUI parses the signature in fine - it survives on the streamed tool call -
but loses it one step later. It rebuilds the conversation from its own internal
`function_call` output records, and those records have no field for it. This
patch adds `extra_content` at the three points where the value is copied:

  1. middleware.py - creating the `function_call` record during streaming
  2. middleware.py - creating it on the non-Responses path
  3. misc.py       - rebuilding the OpenAI `tool_calls` array from those records

`extra_content` is only ever set when the provider sent one, so providers that
do not use it (vLLM, OpenAI, Ollama) serialize byte-for-byte as before.

Idempotent. Run:
    python hotpatches/gemini_thought_signature.py --owui-root /app/backend/open_webui
"""

import argparse
import pathlib
import sys

MARKER = "HOTPATCH gemini-thought-signature"

# 1. Streaming path: the Responses-style function_call item created per chunk.
MW_STREAM_OLD = """                                                    item = {
                                                        'type': 'function_call',
                                                        'id': call_id,
                                                        'call_id': call_id,
                                                        'name': func.get('name', ''),
                                                        'arguments': '',
                                                        'status': 'in_progress',
                                                    }"""

MW_STREAM_NEW = """                                                    item = {
                                                        'type': 'function_call',
                                                        'id': call_id,
                                                        'call_id': call_id,
                                                        'name': func.get('name', ''),
                                                        'arguments': '',
                                                        'status': 'in_progress',
                                                        # HOTPATCH gemini-thought-signature
                                                        **(
                                                            {'extra_content': tc['extra_content']}
                                                            if tc.get('extra_content')
                                                            else {}
                                                        ),
                                                    }"""

# 2. Same record, built after the stream finishes when it does not exist yet.
MW_APPEND_OLD = """                            output.append(
                                {
                                    'type': 'function_call',
                                    'id': call_id or output_id('fc'),
                                    'call_id': call_id,
                                    'name': func.get('name', ''),
                                    'arguments': func.get('arguments', '{}'),
                                    'status': 'in_progress',
                                }
                            )"""

MW_APPEND_NEW = """                            output.append(
                                {
                                    'type': 'function_call',
                                    'id': call_id or output_id('fc'),
                                    'call_id': call_id,
                                    'name': func.get('name', ''),
                                    'arguments': func.get('arguments', '{}'),
                                    'status': 'in_progress',
                                    # HOTPATCH gemini-thought-signature
                                    **({'extra_content': tc['extra_content']} if tc.get('extra_content') else {}),
                                }
                            )"""

# 3. Rebuilding the outgoing OpenAI tool_calls array from the stored records.
MISC_OLD = """            pending_tool_calls.append(
                {
                    'id': item.get('call_id', ''),
                    'type': 'function',
                    'function': {
                        'name': item.get('name', ''),
                        'arguments': arguments,
                    },
                }
            )"""

MISC_NEW = """            pending_tool_calls.append(
                {
                    'id': item.get('call_id', ''),
                    'type': 'function',
                    'function': {
                        'name': item.get('name', ''),
                        'arguments': arguments,
                    },
                    # HOTPATCH gemini-thought-signature: Gemini 3.x requires its
                    # signed blob back on the follow-up turn or Google returns 400.
                    **({'extra_content': item['extra_content']} if item.get('extra_content') else {}),
                }
            )"""

PATCHES = [
    ("utils/middleware.py", [(MW_STREAM_OLD, MW_STREAM_NEW), (MW_APPEND_OLD, MW_APPEND_NEW)]),
    ("utils/misc.py", [(MISC_OLD, MISC_NEW)]),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--owui-root", default="/app/backend/open_webui")
    args = ap.parse_args()
    root = pathlib.Path(args.owui_root)

    # Verify every anchor before writing anything, so a partial apply is impossible.
    plans = []
    for relative_path, replacements in PATCHES:
        target = root / relative_path
        src = target.read_text()
        if MARKER in src:
            print(f"already patched: {target}")
            continue
        for old, _ in replacements:
            if old not in src:
                print(f"ERROR: patch anchor not found in {target}", file=sys.stderr)
                print("Open WebUI upstream changed. Re-check the tool-call rebuild path.", file=sys.stderr)
                return 1
        plans.append((target, src, replacements))

    for target, src, replacements in plans:
        backup = target.with_suffix(".py.pre-thoughtsig-hotpatch.bak")
        if not backup.exists():
            backup.write_text(src)
        patched = src
        for old, new in replacements:
            patched = patched.replace(old, new, 1)
        target.write_text(patched)
        print(f"patched: {target}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
