# E2E Testing Checklist — owui-surrealdb-adapter

> Open WebUI at **<http://localhost:3000>**
> SurrealDB at **ws://localhost:8000**
>
> Check each box as you go. Note any failures inline.
>
> **Last run: 2026-06-04 ~12:20 CEST by Arnar**

---

## 1. Basic RAG Pipeline (Happy Path) ✅

- [x] **Upload a small .md file** (~1 page) to a Knowledge Base
  - Expect: green toast, no errors in `docker logs pluto-open-webui`
  - ✅ Tested: uploaded multiple .md files, all green toast, no errors
- [x] **Ask a question** about the uploaded content
  - Expect: RAG-augmented answer with citation link
  - ✅ Tested: retrieved 3 sources on first query, 2 different sources on follow-up (smart retrieval)
- [x] **Upload a .txt file** — verify non-markdown works too
  - ✅ Tested: .txt files retrievable
- [x] **Upload a .pdf file** — verify PDF parsing + embedding works
  - ✅ Tested: 6MB Carl Jung PDF uploaded, parsed into 1,784 chunks, referenced correctly in chat
- [x] **Upload into KB folder** — OWUI 0.9.6 folder feature
  - ✅ Tested: created folder within KB, uploaded PDF inside it, chat referenced it correctly

---

## 2. Delete Flows ✅

- [x] **Delete a single file** from Knowledge Base UI
  - ✅ Tested: KB-level collection removed. Per-file cache tables persist by OWUI design (reuse for re-adding without re-embedding)
- [x] **Delete an entire Knowledge Base**
  - ✅ Tested: deleted 4 KBs. Verified via SDB query — KB-level UUID collections gone (0 remaining), per-file caches kept by design
- [x] **Re-upload the same file** after deleting it
  - ✅ Tested: works without errors, new chunks created

> **Note:** OWUI intentionally keeps `owui_file-*` tables after KB delete. These are embedding caches so files can be re-added to another KB without re-embedding. This matches Chroma/Qdrant behavior.

---

## 3. Multi-KB Isolation ✅

- [x] **Create Knowledge Base A** — upload `fileA.md`
- [x] **Create Knowledge Base B** — upload `fileB.md` (different content)
- [x] **Ask a question** using only KB-A → should NOT cite KB-B content
- [x] **Ask a question** using only KB-B → should NOT cite KB-A content
- [x] **Delete KB-A** → verify KB-B is untouched
- [x] **Query KB-B** after deleting KB-A → still works
  - ✅ All isolation tests passed

---

## 4. Reconnection / Resilience ✅

- [x] **Restart SurrealDB mid-session**:

  ```bash
  docker restart pluto-surrealdb
  ```

  Wait 10s, then upload a file. Expect: adapter reconnects, upload succeeds.
  - ✅ Tested: restart at 12:31, SurrealDB back running, no errors in OWUI logs. Upload + RAG query worked.
- [x] **Kill and restart SurrealDB**:

  ```bash
  docker stop pluto-surrealdb && sleep 5 && docker start pluto-surrealdb
  ```

  Then ask a RAG question. Expect: works after reconnect (may take ~5s).
  - ✅ Tested: cold stop at 12:32:03, started at 12:32:08. Silent reconnect, clean logs.
- [x] **Check logs** for reconnection messages:

  ```bash
  docker logs pluto-open-webui 2>&1 | grep -i "reconnect\|transport\|retry"
  ```
  - ✅ Tested: no error/panic logs. `_execute_with_retry()` + `_force_reconnect()` handled it silently.

---

## 5. Large Documents ✅

- [x] **Upload a large file** (50+ pages / 100KB+)
  - ✅ Tested: 6MB Carl Jung PDF → 1,784 chunks stored correctly, no timeout
  - Verified via SDB: `owui_file-6ee71cc9: 1784 chunks`
- [x] **Ask a question** about content near the END of the large file
  - ✅ Tested: content referenced correctly, all chunks indexed

---

## 6. Rapid Operations (Stress) ✅

- [x] **Upload 3 files quickly** in succession (don't wait for each to finish)
  - ✅ Tested: 9 .md files uploaded straight into a chat — all succeeded. Then 52 files mass-uploaded into "UnixplorationBuddy" KB — all succeeded, fast. SDB inspection: 70 file tables, 3,265 total chunks, no races.
- [x] **Upload then immediately delete** the same file
  - ✅ Tested: no crash, clean state
- [x] **Upload, delete, re-upload** the same file
  - ✅ Tested: re-uploaded entire UnixplorationBuddy vault folder after deletion — works without duplicate key or stale data errors

---

## 7. Edge Case: Special Characters ✅

- [x] **Upload a file with unicode filename** (e.g. `résumé.md` or `日本語.txt`)
  - ✅ Tested: Icelandic KB "Íslendingabók" with `Ólafur Liljurós.txt` containing Icelandic text — uploaded, embedded, and retrieved perfectly. "Ólafur reið með björgum fram" returned with correct citation.
- [x] **Upload a file with very long name** (100+ chars)
  - ✅ Tested: no issues
- [x] **Upload a file with empty content**
  - ✅ Tested: no crash

---

## 8. Embedding Model Change ✅

- [x] **Note the current embedding model** in OWUI settings (Admin → Settings → Documents)
  - ✅ Was: `sentence-transformers/all-MiniLM-L6-v2` (384d, CPU)
- [x] **Change the embedding model** to a different one (different dimension)
  - ✅ Switched to: `embeddinggemma` via Ollama (768d, 300M params)
- [x] **Upload a new file** after changing
  - Expect: new table created with correct new dimension
  - ✅ Tested: 52 files uploaded to new KB "Testing 1", all embedded with 768d vectors, content viewable
- [x] **Query across old + new files** — may fail (dimension mismatch is expected)
  - Note: this is a known limitation, just verify it doesn't crash silently
  - ✅ Tested: retrieval works for new embeddings. Old 384d tables remain untouched. No crashes.

---

## 9. OWUI Restart Persistence ✅

- [x] **Restart OWUI container**:

  ```bash
  docker restart pluto-open-webui
  ```
  - ✅ Tested: restarted at 12:32:35, serving requests by 12:32:45
- [x] **Verify existing Knowledge Bases still show files**
  - ✅ Tested: KB endpoints returning 200 immediately after restart, files listed
- [x] **Ask a RAG question** — should work without re-indexing
  - ✅ Tested: local model retrieved from collection after restart — no re-indexing needed
- [x] **Upload a new file** — should work without manual intervention
  - ✅ Tested: works cleanly

---

## 10. Concurrent Users ✅

- [x] **Open two browser tabs**, both logged in
- [x] **Upload a file in Tab 1** while **asking a RAG question in Tab 2**
  - Expect: both operations succeed (thread safety test)
  - ✅ Tested: two separate users (admin + valur) on two browsers, two different models (nemotron-3-nano:4b-bf16 + gemini-3.5-flash), querying same UnixplorationBuddy collection simultaneously. Both retrieved 2 sources with correct citations. Thread safety confirmed.

---

## Notes

> - OWUI 0.9.6 supports folders within KBs — tested and works with SurrealDB adapter
> - Mass upload (52 files) completed without issues — adapter handles concurrent inserts cleanly
> - Retrieval is smart: different queries pull different source subsets from the same KB
> - Per-file table caching is by OWUI design, not an adapter leak
