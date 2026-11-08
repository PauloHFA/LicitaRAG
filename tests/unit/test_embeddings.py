import math

from src.retrieval.embeddings import EmbeddingService


def test_embedding_dimension_and_normalization():
    """Valida dimensão configurada e normalização L2 (norma euclidiana = 1.0)."""
    service = EmbeddingService(dimension=384)
    query_vector = service.embed_query("Qual o prazo de validade das propostas?")

    assert len(query_vector) == 384

    # Calcula a norma Euclidiana
    norm = math.sqrt(sum(x * x for x in query_vector))
    assert math.isclose(norm, 1.0, rel_tol=1e-5)


def test_embedding_batch_and_determinism():
    """Valida geração em lote e consistência determinística."""
    service = EmbeddingService(dimension=384)
    texts = [
        "14.1 Garantia contratual de 5%",
        "8.4 Atestado de capacidade técnica",
    ]

    batch = service.embed_documents(texts)
    assert len(batch) == 2
    assert len(batch[0]) == 384
    assert len(batch[1]) == 384

    # Determinismo: o mesmo texto deve produzir o mesmo vetor
    single = service.embed_documents(["14.1 Garantia contratual de 5%"])[0]
    assert batch[0] == single

    # Diferenciação: textos diferentes devem gerar vetores distintos
    assert batch[0] != batch[1]
