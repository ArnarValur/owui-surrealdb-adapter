"""Tests for the OWUI patcher (Phase 6, Task 1).

Targets the REAL Open WebUI structure:
    - type.py:    StrEnum VectorType — add SURREALDB = 'surrealdb'
    - factory.py: match/case on VectorType — add case VectorType.SURREALDB

Verifies:
    - Patch inserts enum member and case branch correctly
    - Patch is idempotent (running twice doesn't duplicate)
    - Patch raises on unexpected file structure
"""

import textwrap

import pytest

from owui_surrealdb_adapter.patch import (
    patch_type_py,
    patch_factory_py,
    SURREALDB_MARKER,
)


# -- Fixtures: Real OWUI source snapshots ------------------------------------

TYPE_PY_ORIGINAL = textwrap.dedent("""\
    from enum import StrEnum


    class VectorType(StrEnum):
        MILVUS = 'milvus'
        MARIADB_VECTOR = 'mariadb-vector'
        QDRANT = 'qdrant'
        CHROMA = 'chroma'
        PINECONE = 'pinecone'
        ELASTICSEARCH = 'elasticsearch'
        OPENSEARCH = 'opensearch'
        PGVECTOR = 'pgvector'
        ORACLE23AI = 'oracle23ai'
        S3VECTOR = 's3vector'
        WEAVIATE = 'weaviate'
        OPENGAUSS = 'opengauss'
        VALKEY = 'valkey'
""")


FACTORY_PY_ORIGINAL = textwrap.dedent("""\
    from open_webui.config import (
        ENABLE_MILVUS_MULTITENANCY_MODE,
        ENABLE_QDRANT_MULTITENANCY_MODE,
        VECTOR_DB,
    )
    from open_webui.retrieval.vector.main import VectorDBBase
    from open_webui.retrieval.vector.type import VectorType


    class Vector:
        @staticmethod
        def get_vector(vector_type: str) -> VectorDBBase:
            \"\"\"
            get vector db instance by vector type
            \"\"\"
            match vector_type:
                case VectorType.MILVUS:
                    if ENABLE_MILVUS_MULTITENANCY_MODE:
                        from open_webui.retrieval.vector.dbs.milvus_multitenancy import (
                            MilvusClient,
                        )

                        return MilvusClient()
                    else:
                        from open_webui.retrieval.vector.dbs.milvus import MilvusClient

                        return MilvusClient()
                case VectorType.QDRANT:
                    if ENABLE_QDRANT_MULTITENANCY_MODE:
                        from open_webui.retrieval.vector.dbs.qdrant_multitenancy import (
                            QdrantClient,
                        )

                        return QdrantClient()
                    else:
                        from open_webui.retrieval.vector.dbs.qdrant import QdrantClient

                        return QdrantClient()
                case VectorType.CHROMA:
                    from open_webui.retrieval.vector.dbs.chroma import ChromaClient

                    return ChromaClient()
                case VectorType.VALKEY:
                    from open_webui.retrieval.vector.dbs.valkey import ValkeyClient

                    return ValkeyClient()
                case _:
                    raise ValueError(f'Unsupported vector type: {vector_type}')


    VECTOR_DB_CLIENT = Vector.get_vector(VECTOR_DB)
""")


# -- type.py tests -----------------------------------------------------------


class TestPatchTypePy:
    """Tests for patch_type_py()."""

    def test_adds_surrealdb_member(self):
        result = patch_type_py(TYPE_PY_ORIGINAL)
        assert "SURREALDB = 'surrealdb'" in result

    def test_member_inside_class(self):
        """SURREALDB should be inside the VectorType class body."""
        result = patch_type_py(TYPE_PY_ORIGINAL)
        lines = result.splitlines()
        class_line = next(i for i, l in enumerate(lines) if "class VectorType" in l)
        surrealdb_line = next(i for i, l in enumerate(lines) if "SURREALDB" in l)
        assert surrealdb_line > class_line

    def test_contains_marker(self):
        result = patch_type_py(TYPE_PY_ORIGINAL)
        assert SURREALDB_MARKER in result

    def test_idempotent(self):
        first = patch_type_py(TYPE_PY_ORIGINAL)
        second = patch_type_py(first)
        assert first == second

    def test_valid_python(self):
        result = patch_type_py(TYPE_PY_ORIGINAL)
        compile(result, "<patched-type>", "exec")


# -- factory.py tests --------------------------------------------------------


class TestPatchFactoryPy:
    """Tests for patch_factory_py()."""

    def test_adds_case_branch(self):
        result = patch_factory_py(FACTORY_PY_ORIGINAL)
        assert "case VectorType.SURREALDB:" in result

    def test_imports_adapter(self):
        result = patch_factory_py(FACTORY_PY_ORIGINAL)
        assert "from owui_surrealdb_adapter import SurrealDBClient" in result
        assert "return SurrealDBClient()" in result

    def test_case_before_default(self):
        """SurrealDB case must appear before the case _ default."""
        result = patch_factory_py(FACTORY_PY_ORIGINAL)
        surreal_pos = result.index("case VectorType.SURREALDB:")
        default_pos = result.index("case _:")
        assert surreal_pos < default_pos

    def test_preserves_default_case(self):
        result = patch_factory_py(FACTORY_PY_ORIGINAL)
        assert "case _:" in result
        assert "Unsupported vector type" in result

    def test_contains_marker(self):
        result = patch_factory_py(FACTORY_PY_ORIGINAL)
        assert SURREALDB_MARKER in result

    def test_idempotent(self):
        first = patch_factory_py(FACTORY_PY_ORIGINAL)
        second = patch_factory_py(first)
        assert first == second

    def test_valid_python(self):
        result = patch_factory_py(FACTORY_PY_ORIGINAL)
        compile(result, "<patched-factory>", "exec")

    def test_raises_on_missing_default_case(self):
        """Should raise if case _ is not found."""
        no_default = FACTORY_PY_ORIGINAL.replace("case _:", "# no default")
        with pytest.raises(ValueError, match="(?i)case _"):
            patch_factory_py(no_default)
