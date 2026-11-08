from unittest.mock import MagicMock, patch

from src.audit.checklist import ChecklistExtractor
from src.audit.deadlines import DeadlinesAndSanctionsExtractor
from src.audit.report_generator import AuditReportGenerator
from src.audit.risk_detector import RiskDetector
from src.chunking.clause_splitter import HierarchicalClauseSplitter
from src.generation.llm_client import MockLLMClient
from src.generation.responder import GroundedResponder
from src.ingestion.pdf_loader import PDFIngestionPipeline
from src.retrieval.hybrid_retriever import HybridRetriever


def test_end_to_end_ingestion_retrieval_and_audit():
    """Valida o fluxo integrado de ponta a ponta do Licita-RAG:

    Ingestão sintética -> Chunking Hierárquico -> Busca Híbrida -> Geração Fundamentada
    -> Extração de Checklist -> Prazos & Garantias -> Alertas de Risco -> Dossiê.
    """
    pipeline = PDFIngestionPipeline()
    splitter = HierarchicalClauseSplitter()

    edital_texto = """1. DO OBJETO
1.1 Aquisição de equipamentos de tecnologia da informação e switches de rede.

3. DOS PRAZOS DO CERTAME
3.1 O prazo para apresentação de propostas e lances será de 10 dias úteis.
3.2 Os pedidos de esclarecimento e impugnações ao edital deverão ser protocolados em até 3 dias úteis antes da abertura.

8. DA HABILITAÇÃO
8.1 Os licitantes deverão apresentar a documentação necessária à habilitação jurídica e fiscal.
8.2 DA REGULARIDADE FISCAL E TRABALHISTA:
8.2.1 Prova de regularidade perante a Fazenda Nacional e Seguridade Social (CND).
8.2.2 Certidão Negativa de Débitos Trabalhistas (CNDT) e regularidade com FGTS.
8.3 DA QUALIFICAÇÃO TÉCNICA:
8.3.1 Apresentação de atestado de capacidade técnica operacional emitido por pessoa jurídica de direito público ou privado.

14. DAS GARANTIAS CONTRATUAIS
14.1 A contratada prestará garantia de execução no valor correspondente a 5% do valor total adjudicado.
"""

    mock_page = MagicMock()
    mock_page.get_text.return_value = edital_texto
    mock_page.find_tables.return_value = []

    mock_doc = MagicMock()
    mock_doc.__len__.return_value = 1
    mock_doc.__iter__.return_value = [mock_page]
    mock_doc.__getitem__.return_value = mock_page

    with patch("pymupdf.open", return_value=mock_doc):
        ingest_result = pipeline.process_file_bytes(b"%PDF-1.4 mock bytes", filename="Edital_PE_01_2026.pdf")

    assert ingest_result.sucesso is True
    assert len(ingest_result.paginas) == 1

    chunks = splitter.split_ingestion_result(
        ingest_result,
        metadados_base={"documento": "Edital_PE_01_2026.pdf", "edital_id": 1},
    )
    assert len(chunks) >= 4

    # 2. Busca Híbrida em Memória
    retriever = HybridRetriever()
    candidates = retriever.search_in_memory(
        query="garantia contratual",
        candidates=chunks,
        top_candidates=10,
        top_final=5,
    )
    assert len(candidates) >= 1
    assert any("garantia" in c.candidate.texto.lower() for c in candidates)

    # 3. Geração Fundamentada com Verificador de Citações
    target_cand = next(c for c in candidates if "garantia" in c.candidate.texto.lower())
    mock_llm = MockLLMClient(predefined_response={
        "resposta": "A garantia contratual é de 5% do valor total.",
        "citacoes": [{
            "documento": "Edital_PE_01_2026.pdf",
            "pagina": target_cand.candidate.pagina,
            "item": target_cand.candidate.item,
            "trecho": "garantia de execução no valor correspondente a 5%",
        }],
        "encontrado": True,
        "confianca": 0.95,
        "chunk_ids": [target_cand.candidate.chunk_id],
    })
    responder = GroundedResponder(llm_client=mock_llm)
    chat_resp, latencia_ms = responder.generate_response(
        query="qual a garantia exigida?",
        candidates=candidates,
    )
    assert chat_resp.encontrado is True
    assert latencia_ms >= 0

    # 4. Extração de Checklist
    checklist_ext = ChecklistExtractor()
    chk_items = checklist_ext.extract_from_chunks(chunks, document_name="Edital_PE_01_2026.pdf")
    assert len(chk_items) >= 2
    categorias = {c.categoria for c in chk_items}
    assert any("Fiscal" in cat or "Técnica" in cat for cat in categorias)

    # 5. Prazos, Sanções e Garantias
    deadlines_ext = DeadlinesAndSanctionsExtractor()
    deadlines = deadlines_ext.extract_deadlines(chunks)
    warranty = deadlines_ext.extract_warranty(chunks)
    assert len(deadlines) >= 2
    assert warranty is not None
    assert warranty.exigida is True

    # 6. Alertas de Risco Preventivos
    detector = RiskDetector()
    alerts = detector.analyze_risks(chunks, deadlines=deadlines, warranty=warranty)
    assert alerts == []

    # 7. Geração de Dossiê Executivo
    dossier = AuditReportGenerator.generate_dossier(
        edital_numero="Edital PE 01/2026",
        orgao="Tribunal de Contas",
        objeto="Aquisição de TI",
        deadlines=deadlines,
        penalties=[],
        warranty=warranty,
        checklist=chk_items,
        alerts=alerts,
    )
    assert "DOSSIÊ EXECUTIVO DE AUDITORIA PREVENTIVA" in dossier
    assert "Edital PE 01/2026" in dossier
    assert "Tribunal de Contas" in dossier
