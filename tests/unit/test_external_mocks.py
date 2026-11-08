import json
from unittest.mock import MagicMock, patch

import pytest

from src.audit.checklist import ChecklistExtractor
from src.audit.deadlines import DeadlinesAndSanctionsExtractor
from src.audit.risk_detector import RiskDetector
from src.chunking.models import ParsedChunk
from src.generation.citation_verifier import PostGenerationCitationVerifier
from src.generation.llm_client import GroqClient, MockLLMClient, OllamaClient, get_llm_client
from src.ingestion.models import TipoChunk
from src.ingestion.ocr_fallback import OCRFallbackProcessor
from src.retrieval.embeddings import EmbeddingService
from src.retrieval.reranker import CrossEncoderReranker
from src.retrieval.rrf import RankedCandidate, RRFScoredCandidate


def test_groq_client_success_and_error():
    """Valida chamadas com mock ao GroqClient cobrindo sucesso e erro de API Key."""
    client = GroqClient(api_key="gsk_test_key_123")
    assert client.api_key == "gsk_test_key_123"

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [
            {"message": {"content": '{"resposta": "ok", "encontrado": true}'}}
        ]
    }
    mock_response.raise_for_status.return_value = None

    with patch("httpx.Client") as mock_client_cls:
        mock_ctx = MagicMock()
        mock_ctx.__enter__.return_value.post.return_value = mock_response
        mock_client_cls.return_value = mock_ctx

        res = client.generate("system", "user")
        assert "ok" in res

    client_no_key = GroqClient(api_key="")
    client_no_key.api_key = ""
    with pytest.raises(ValueError, match="GROQ_API_KEY não configurada"):
        client_no_key.generate("system", "user")


def test_ollama_client_success():
    """Valida chamadas ao OllamaClient com mock de rede."""
    client = OllamaClient(base_url="http://localhost:11434", model="llama3.1")

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "message": {"content": '{"resposta": "ollama_ok"}'}
    }
    mock_response.raise_for_status.return_value = None

    with patch("httpx.Client") as mock_client_cls:
        mock_ctx = MagicMock()
        mock_ctx.__enter__.return_value.post.return_value = mock_response
        mock_client_cls.return_value = mock_ctx

        res = client.generate("system", "user")
        assert "ollama_ok" in res


def test_mock_llm_client_and_factory():
    """Valida MockLLMClient com dicionário e fábrica get_llm_client."""
    client_dict = MockLLMClient(predefined_response={"custom": 123})
    assert json.loads(client_dict.generate("sys", "usr")) == {"custom": 123}

    client_default = MockLLMClient()
    resp_garantia = client_default.generate("sys", "qual a garantia exigida?")
    assert "garantia" in resp_garantia.lower()

    resp_abst = client_default.generate("sys", "pergunta qualquer inexistente")
    assert "não consta" in resp_abst.lower()

    assert isinstance(get_llm_client("ollama"), OllamaClient)
    assert isinstance(get_llm_client("mock"), MockLLMClient)


def test_citation_verifier_invalid_json_and_malformed():
    """Valida verifier com JSON quebrado, tipo inválido de citação ou trecho ausente."""
    verifier = PostGenerationCitationVerifier()
    cand = RRFScoredCandidate(
        candidate=RankedCandidate(chunk_id=1, texto="Texto da pág 10", pagina=10, item="1.1"),
        rrf_score=0.5,
    )

    # 1. JSON quebrado
    res = verifier.verify_response("NÃO É JSON {", [cand])
    assert not res.is_valid
    assert "Falha de formatação JSON" in (res.validation_error or "")

    # 2. Citação sem ser dict e sem página int
    malformed_json = json.dumps({
        "resposta": "Informação encontrada",
        "encontrado": True,
        "citacoes": ["não é dict", {"pagina": "dez", "item": "1.1"}, {"pagina": None}],
    })
    res_malformed = verifier.verify_response(malformed_json, [cand])
    assert not res_malformed.is_valid

    # 3. Trecho citado não confere com a página
    not_matching_snippet = json.dumps({
        "resposta": "Informação encontrada",
        "encontrado": True,
        "citacoes": [
            {"pagina": 10, "item": "99.99", "trecho": "Trecho completamente inexistente no contexto"}
        ],
    })
    res_snippet = verifier.verify_response(not_matching_snippet, [cand])
    assert not res_snippet.is_valid
    assert "não confere" in (res_snippet.validation_error or "")


def test_checklist_long_description_truncation():
    """Valida truncamento de sentenças longas no checklist (> 200 caracteres)."""
    extractor = ChecklistExtractor()
    chunk = ParsedChunk(
        texto="10.1 DA QUALIFICAÇÃO TÉCNICA: " + ("Atestado técnico expedido por órgão oficial competente com carimbo. " * 5),
        pagina=15,
        item="10.1",
        secao="Qualificação Técnica",
    )
    items = extractor.extract_from_chunks([chunk], document_name="Edital")
    assert len(items) >= 1
    assert len(items[0].descricao) <= 205


def test_ocr_fallback_mocked_execution():
    """Valida fluxo de renderização e OCR do Tesseract com mock de sucesso e erro."""
    ocr = OCRFallbackProcessor(lang="por")
    ocr.tesseract_available = True
    ocr.pytesseract = MagicMock()
    ocr.pytesseract.image_to_string.return_value = "Texto reconhecido no OCR mockado"

    mock_page = MagicMock()
    mock_pix = MagicMock()
    mock_pix.tobytes.return_value = b"bytes_imagem"
    mock_page.get_pixmap.return_value = mock_pix

    with patch("PIL.Image.open") as mock_img_open:
        mock_img_open.return_value = MagicMock()

        # Sucesso
        extracted = ocr.process_scanned_page(mock_page, page_num=3)
        assert extracted.texto == "Texto reconhecido no OCR mockado"
        assert extracted.confianca == 0.75
        assert extracted.tipo == TipoChunk.OCR

        # Falha/Exceção no OCR
        ocr.pytesseract.image_to_string.side_effect = RuntimeError("Erro tesseract bin")
        extracted_fail = ocr.process_scanned_page(mock_page, page_num=3)
        assert extracted_fail.texto == ""
        assert extracted_fail.confianca == 0.30


def test_embeddings_and_reranker_edge_cases():
    """Valida listas vazias e exceções simuladas no EmbeddingService e CrossEncoderReranker."""
    emb_service = EmbeddingService()
    assert emb_service.embed_documents([]) == []

    mock_emb = MagicMock()
    mock_emb.tolist.return_value = [0.1] * 384
    emb_service.model = MagicMock()
    emb_service.model.encode.return_value = [mock_emb]
    docs = emb_service.embed_documents(["teste"])
    assert len(docs) == 1
    assert len(docs[0]) == 384

    emb_service.model.encode.side_effect = RuntimeError("GPU out of memory")
    fallback_docs = emb_service.embed_documents(["teste fallback"])
    assert len(fallback_docs) == 1

    reranker = CrossEncoderReranker()
    assert reranker.rerank("query", []) == []

    cand = RRFScoredCandidate(
        candidate=RankedCandidate(chunk_id=1, texto="Texto 1", pagina=1),
        rrf_score=0.015,
    )
    reranker.model = MagicMock()
    reranker.model.predict.return_value = [0.95]
    reranked = reranker.rerank("query", [cand], top_k=1)
    assert reranked[0].rerank_score == 0.95

    reranker.model.predict.side_effect = RuntimeError("Inference error")
    reranked_heuristic = reranker.rerank("query", [cand], top_k=1)
    assert reranked_heuristic[0].rerank_score is not None


def test_deadlines_unmatched_and_risk_clean_edital():
    """Valida comportamento de chunks sem prazos e edital 100% conforme a Lei 14.133."""
    deadlines_ext = DeadlinesAndSanctionsExtractor()
    chunk_clean = ParsedChunk(texto="Texto institucional sobre o órgão público.", pagina=1)
    deadlines = deadlines_ext.extract_deadlines([chunk_clean])
    penalties = deadlines_ext.extract_penalties([chunk_clean])
    warranty = deadlines_ext.extract_warranty([chunk_clean])
    assert deadlines == []
    assert penalties == []
    assert warranty is None

    chunk_conforme = ParsedChunk(
        texto="Prazo para apresentação de propostas: 15 dias úteis. Prazo para impugnação: 5 dias úteis. Garantia contratual de 5% sobre o valor.",
        pagina=2,
    )
    d_list = deadlines_ext.extract_deadlines([chunk_conforme])
    w_item = deadlines_ext.extract_warranty([chunk_conforme])
    detector = RiskDetector()
    alerts = detector.analyze_risks(chunks=[chunk_conforme], deadlines=d_list, warranty=w_item)
    assert alerts == []
