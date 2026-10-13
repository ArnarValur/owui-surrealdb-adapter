# SemVer 0.x until API stable

> **Recorded:** 2026-06-11 11:21
> **Status:** accepted

The adapter's `pyproject.toml` version was set to `2.0.0` as a naming artifact from the "v2 rewrite" framing. The actual API is pre-1.0 — still finding bugs (e.g. metadata-only collections) and the VectorDBBase contract hasn't been stress-tested across OWUI upgrades. We adopt SemVer `0.x.y` starting from the existing `v0.1.0` git tag. The pyproject.toml version will be corrected to match. Version 1.0.0 is reserved for when the adapter survives at least one OWUI major version bump and the cascade delete + metadata collection patterns are battle-proven.
