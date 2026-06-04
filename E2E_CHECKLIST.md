# E2E Testing Checklist — owui-surrealdb-adapter

> Open WebUI at **http://localhost:3000**
> SurrealDB at **ws://localhost:8000**
>
> Check each box as you go. Note any failures inline.

---

## 1. Basic RAG Pipeline (Happy Path)

- [ ] **Upload a small .md file** (~1 page) to a Knowledge Base
  - Expect: green toast, no errors in `docker logs pluto-open-webui`
- [ ] **Ask a question** about the uploaded content
  - Expect: RAG-augmented answer with citation link
- [ ] **Upload a .txt file** — verify non-markdown works too
- [ ] **Upload a .pdf file** — verify PDF parsing + embedding works

---

## 2. Delete Flows

- [ ] **Delete a single file** from Knowledge Base UI
  - Then verify chunks removed: `docker exec pluto-surrealdb /surreal sql --endpoint http://localhost:8000 --username root --password root --namespace owui --database vectors "INFO FOR DB;"` — the `owui_file-{id}` table should be gone
- [ ] **Delete an entire Knowledge Base**
  - Verify all associated tables removed from SurrealDB
- [ ] **Re-upload the same file** after deleting it
  - Expect: works without errors, new chunks created

---

## 3. Multi-KB Isolation

- [ ] **Create Knowledge Base A** — upload `fileA.md`
- [ ] **Create Knowledge Base B** — upload `fileB.md` (different content)
- [ ] **Ask a question** using only KB-A → should NOT cite KB-B content
- [ ] **Ask a question** using only KB-B → should NOT cite KB-A content
- [ ] **Delete KB-A** → verify KB-B is untouched
- [ ] **Query KB-B** after deleting KB-A → still works

---

## 4. Reconnection / Resilience

- [ ] **Restart SurrealDB mid-session**:
  ```bash
  docker restart pluto-surrealdb
  ```
  Wait 10s, then upload a file. Expect: adapter reconnects, upload succeeds.
- [ ] **Kill and restart SurrealDB**:
  ```bash
  docker stop pluto-surrealdb && sleep 5 && docker start pluto-surrealdb
  ```
  Then ask a RAG question. Expect: works after reconnect (may take ~5s).
- [ ] **Check logs** for reconnection messages:
  ```bash
  docker logs pluto-open-webui 2>&1 | grep -i "reconnect\|transport\|retry"
  ```

---

## 5. Large Documents

- [ ] **Upload a large file** (50+ pages / 100KB+)
  - Expect: no timeout, chunks stored correctly
  - Verify chunk count: `docker exec pluto-surrealdb /surreal sql --endpoint http://localhost:8000 --username root --password root --namespace owui --database vectors "SELECT count() FROM owui_file-{FILE_ID} GROUP ALL;"`
- [ ] **Ask a question** about content near the END of the large file
  - Expect: correct answer (verifies all chunks were indexed, not just first batch)

---

## 6. Rapid Operations (Stress)

- [ ] **Upload 3 files quickly** in succession (don't wait for each to finish)
  - Expect: all 3 succeed, no connection race conditions
- [ ] **Upload then immediately delete** the same file
  - Expect: no crash, clean state
- [ ] **Upload, delete, re-upload** the same file
  - Expect: works without "duplicate key" or stale data errors

---

## 7. Edge Case: Special Characters

- [ ] **Upload a file with unicode filename** (e.g. `résumé.md` or `日本語.txt`)
  - Expect: works or clean error, no crash
- [ ] **Upload a file with very long name** (100+ chars)
  - Expect: works or clean error
- [ ] **Upload a file with empty content**
  - Expect: no crash (may produce 0 chunks — that's ok)

---

## 8. Embedding Model Change

- [ ] **Note the current embedding model** in OWUI settings (Admin → Settings → Documents)
- [ ] **Change the embedding model** to a different one (different dimension)
- [ ] **Upload a new file** after changing
  - Expect: new table created with correct new dimension
- [ ] **Query across old + new files** — may fail (dimension mismatch is expected)
  - Note: this is a known limitation, just verify it doesn't crash silently

---

## 9. OWUI Restart Persistence

- [ ] **Restart OWUI container**:
  ```bash
  docker restart pluto-open-webui
  ```
- [ ] **Verify existing Knowledge Bases still show files**
- [ ] **Ask a RAG question** — should work without re-indexing
- [ ] **Upload a new file** — should work without manual intervention

---

## 10. Concurrent Users (if applicable)

- [ ] **Open two browser tabs**, both logged in
- [ ] **Upload a file in Tab 1** while **asking a RAG question in Tab 2**
  - Expect: both operations succeed (thread safety test)

---

## Notes

> Record any failures, unexpected behaviors, or observations here:
>
> ```
>
>
>
> ```
