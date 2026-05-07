"""
Tests that QdrantClient is instantiated with api_key in all server modules.
"""
from unittest.mock import patch, MagicMock


def test_obsidian_indexer_has_api_key_constant(monkeypatch):
    """obsidian_indexer must read QDRANT_API_KEY from the environment."""
    monkeypatch.setenv("QDRANT_URL", "http://127.0.0.1:6333")
    monkeypatch.setenv("QDRANT_API_KEY", "test-key-123")

    import importlib
    import server.obsidian_indexer as obsidian_indexer
    importlib.reload(obsidian_indexer)

    assert obsidian_indexer.QDRANT_API_KEY == "test-key-123"


def test_vault_tool_passes_api_key(monkeypatch):
    """vault_tool must pass api_key= when constructing QdrantClient."""
    import server.vault_tool as vault_tool_module

    # Directly set the module-level constant so _run sees the test value
    monkeypatch.setattr(vault_tool_module, "QDRANT_API_KEY", "test-key-456")
    monkeypatch.setattr(vault_tool_module, "QDRANT_URL", "http://127.0.0.1:6333")

    # Reset singleton
    vault_tool_module._tool_instance = None

    with patch("server.vault_tool.QdrantClient") as mock_client_class:
        mock_instance = MagicMock()
        mock_instance.query_points.return_value = MagicMock(points=[])
        mock_client_class.return_value = mock_instance

        # Patch fastembed TextEmbedding at its import path inside _run
        with patch("fastembed.TextEmbedding") as mock_embed:
            mock_embed_instance = MagicMock()
            # _run calls next(iter(...)).tolist(), so we need an object with .tolist()
            fake_vector = MagicMock()
            fake_vector.tolist.return_value = [0.1] * 384
            mock_embed_instance.embed.return_value = iter([fake_vector])
            mock_embed.return_value = mock_embed_instance

            tool = vault_tool_module.get_vault_tool()
            tool._run("any query")

    mock_client_class.assert_called_once()
    kwargs = mock_client_class.call_args.kwargs
    assert kwargs.get("api_key") == "test-key-456", (
        f"Expected api_key='test-key-456' but got: {mock_client_class.call_args}"
    )
