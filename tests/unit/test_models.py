
from src.db.models import (
    Alerta,
    BaseLegal,
    ChecklistIten,
    Chunk,
    ConversaMensagem,
    Documento,
    Edital,
    SeveridadeAlerta,
    StatusEdital,
    TipoChunk,
    TipoDocumento,
)


def test_status_edital_enum():
    """Valida os estados permitidos no ciclo de vida de um edital."""
    assert StatusEdital.PENDING.value == "PENDING"
    assert StatusEdital.INDEXING.value == "INDEXING"
    assert StatusEdital.READY.value == "READY"
    assert StatusEdital.FAILED.value == "FAILED"


def test_tipo_documento_enum():
    """Valida os tipos de documentos suportados conforme a Seção 10."""
    assert TipoDocumento.EDITAL.value == "edital"
    assert TipoDocumento.TR.value == "TR"
    assert TipoDocumento.ANEXO.value == "anexo"
    assert TipoDocumento.ERRATA.value == "errata"


def test_edital_model_instantiation():
    """Valida instanciação e defaults da entidade Edital."""
    edital = Edital(
        nome="Pregão Eletrônico 42/2026",
        orgao="Ministério da Saúde",
        modalidade="Pregão Eletrônico",
    )
    assert edital.nome == "Pregão Eletrônico 42/2026"
    assert edital.orgao == "Ministério da Saúde"
    assert edital.status == StatusEdital.PENDING


def test_documento_and_chunk_models():
    """Valida metadados e atributos da hierarquia Documento -> Chunks."""
    doc = Documento(
        edital_id=1,
        tipo=TipoDocumento.EDITAL,
        versao=1,
        hash_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        caminho="/uploads/edital_42.pdf",
        paginas=45,
    )
    assert doc.versao == 1
    assert doc.paginas == 45

    chunk = Chunk(
        documento_id=1,
        pagina=12,
        item="8.4.2",
        secao="8. Da Habilitação Técnica",
        tipo=TipoChunk.TEXTO,
        texto="Comprovação de aptidão técnica mediante atestados...",
        metadados={"confianca": 0.95},
    )
    assert chunk.pagina == 12
    assert chunk.item == "8.4.2"
    assert chunk.tipo == TipoChunk.TEXTO
    assert chunk.metadados["confianca"] == 0.95


def test_checklist_and_alerta_models():
    """Valida entidades de auditoria e conformidade."""
    checklist_item = ChecklistIten(
        edital_id=1,
        categoria="Qualificação Técnica",
        descricao="Atestado de capacidade técnica registrado no CREA",
        citacao="[Edital 42, p. 12, item 8.4.2]",
        obrigatorio=True,
    )
    assert checklist_item.obrigatorio is True
    assert "[Edital 42, p. 12, item 8.4.2]" in checklist_item.citacao

    alerta = Alerta(
        edital_id=1,
        tipo="Prazo desproporcional",
        descricao="Prazo de impugnação inferior a 3 dias úteis.",
        item_edital="19.1",
        referencia_legal="Art. 164 da Lei nº 14.133/2021",
        severidade=SeveridadeAlerta.ALTA,
    )
    assert alerta.severidade == SeveridadeAlerta.ALTA
    assert alerta.referencia_legal == "Art. 164 da Lei nº 14.133/2021"


def test_base_legal_model():
    """Valida entidade do índice de legislação isolado."""
    lei = BaseLegal(
        norma="Lei nº 14.133/2021",
        artigo="Art. 67",
        texto="A documentação relativa à qualificação econômico-financeira...",
    )
    assert lei.norma == "Lei nº 14.133/2021"
    assert lei.artigo == "Art. 67"


def test_conversa_mensagem_model():
    """Valida armazenamento do histórico de chat e métricas de latência (RN-08)."""
    msg = ConversaMensagem(
        edital_id=1,
        pergunta="Qual é o valor da garantia exigida?",
        resposta="A garantia contratual é de 5% do valor do contrato.",
        chunk_ids=[101, 102],
        modelo="groq/llama3-70b",
        latencia_ms=1450,
        avaliacao="util",
    )
    assert msg.latencia_ms == 1450
    assert msg.chunk_ids == [101, 102]
    assert msg.avaliacao == "util"
