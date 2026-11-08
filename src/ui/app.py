import csv
import io
import time

import streamlit as st

from src.audit.checklist import ChecklistExtractor
from src.audit.deadlines import DeadlinesAndSanctionsExtractor
from src.audit.risk_detector import RiskDetector
from src.chunking.clause_splitter import HierarchicalClauseSplitter
from src.generation.llm_client import MockLLMClient
from src.generation.responder import GroundedResponder
from src.ingestion.pdf_loader import PDFIngestionPipeline
from src.retrieval.hybrid_retriever import HybridRetriever

# Configuração da página Streamlit
st.set_page_config(
    page_title="Licita-RAG | Auditoria de Editais Públicos",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inicialização de estado de sessão
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "indexed_chunks" not in st.session_state:
    st.session_state.indexed_chunks = []
if "edital_name" not in st.session_state:
    st.session_state.edital_name = "Nenhum edital carregado"
if "feedback_log" not in st.session_state:
    st.session_state.feedback_log = []

# Singletons dos serviços
@st.cache_resource
def get_services():
    pipeline = PDFIngestionPipeline()
    splitter = HierarchicalClauseSplitter()
    retriever = HybridRetriever()
    responder = GroundedResponder(llm_client=MockLLMClient())
    checklist_ext = ChecklistExtractor()
    deadlines_ext = DeadlinesAndSanctionsExtractor()
    risk_det = RiskDetector()
    return pipeline, splitter, retriever, responder, checklist_ext, deadlines_ext, risk_det

pipeline, splitter, retriever, responder, checklist_ext, deadlines_ext, risk_det = get_services()

# Barra Lateral: Upload e Seleção de Documentos
with st.sidebar:
    st.title("⚖️ Licita-RAG")
    st.caption("Assistente RAG com Citação Estrita & Auditoria da Lei 14.133/2021")
    st.divider()

    st.subheader("📤 Ingestão de Editais e Anexos")
    uploaded_file = st.file_uploader(
        "Selecione um edital ou termo de referência (PDF)",
        type=["pdf"],
        help="Upload de até 50 MB com validação de magic bytes e extração de tabelas.",
    )

    doc_type = st.selectbox(
        "Tipo do Documento",
        ["Edital Principal", "Termo de Referência", "Anexo Técnico", "Errata / Retificação"],
    )

    if uploaded_file is not None and st.button("Processar e Indexar Documento"):
        with st.spinner("Extraindo páginas, tabelas e segmentando cláusulas..."):
            file_bytes = uploaded_file.read()
            ingest_res = pipeline.process_file_bytes(file_bytes, filename=uploaded_file.name)

            if ingest_res.sucesso:
                meta = {"documento": uploaded_file.name, "tipo_documento": doc_type}
                new_chunks = splitter.split_ingestion_result(ingest_res, metadados_base=meta)
                st.session_state.indexed_chunks = new_chunks
                st.session_state.edital_name = uploaded_file.name
                st.success(f"Indexado com sucesso! {len(new_chunks)} chunks e {ingest_res.total_paginas} páginas.")
            else:
                st.error(f"Erro na ingestão: {', '.join(ingest_res.erros)}")

    st.divider()
    st.markdown(f"**Edital Ativo:** `{st.session_state.edital_name}`")
    st.markdown(f"**Chunks em Memória:** `{len(st.session_state.indexed_chunks)}`")

# Painel Principal com Abas
tab_chat, tab_checklist, tab_prazos, tab_alertas = st.tabs([
    "💬 Chat com Citação Estrita",
    "📋 Checklist de Habilitação",
    "⏱️ Prazos & Cronogramas",
    "⚠️ Alertas da Lei 14.133/2021",
])

# ==============================================================================
# ABA 1: Chat com Citação e Painel Lado a Lado (RF-10, RF-12, RNF-10)
# ==============================================================================
with tab_chat:
    st.header("Consulta Auditável com Citação de Origem")
    st.caption("Toda resposta cita obrigatoriamente [Edital, p. N, item N.N]. À direita, confira o trecho literal.")

    col_chat, col_evidence = st.columns([6, 5])

    with col_chat:
        user_query = st.text_input(
            "Faça uma pergunta sobre o edital:",
            placeholder="Ex: Qual é o valor e prazo da garantia contratual?",
        )

        if st.button("Enviar Pergunta") and user_query:
            if not st.session_state.indexed_chunks:
                st.warning("Por favor, carregue um arquivo PDF na barra lateral para iniciar a consulta.")
            else:
                # 1. Recuperação Híbrida
                candidates = retriever.search_in_memory(
                    query=user_query,
                    candidates=st.session_state.indexed_chunks,
                    top_candidates=15,
                    top_final=5,
                )

                # 2. Geração Fundamentada
                chat_resp, latencia_ms = responder.generate_response(user_query, candidates)

                # Registra no histórico
                st.session_state.chat_history.append({
                    "pergunta": user_query,
                    "resposta": chat_resp.resposta,
                    "citacoes": chat_resp.citacoes,
                    "encontrado": chat_resp.encontrado,
                    "confianca": chat_resp.confianca,
                    "latencia_ms": latencia_ms,
                    "timestamp": time.strftime("%H:%M:%S"),
                })

        # Exibe histórico de mensagens
        st.subheader("Histórico de Conversas")
        for idx, msg in enumerate(reversed(st.session_state.chat_history)):
            st.markdown(f"**🧑 Usuário ({msg['timestamp']}):** {msg['pergunta']}")
            st.markdown(f"**🤖 Licita-RAG:** {msg['resposta']}")

            # Citações formatadas
            if msg["citacoes"]:
                cits_str = " | ".join(
                    f"`[{c.documento}, p. {c.pagina}, item {c.item}]`" for c in msg["citacoes"]
                )
                st.markdown(f"📌 **Fontes Auditadas:** {cits_str}")

            # Botões de Avaliação da Resposta (RF-18)
            f_col1, f_col2, f_col3 = st.columns([1, 1, 6])
            with f_col1:
                if st.button("👍 Útil", key=f"up_{idx}"):
                    st.toast("Feedback registrado: Resposta útil!")
                    st.session_state.feedback_log.append({"idx": idx, "score": "util"})
            with f_col2:
                if st.button("👎 Incorreta", key=f"down_{idx}"):
                    st.toast("Feedback registrado: Resposta marcada para revisão.")
                    st.session_state.feedback_log.append({"idx": idx, "score": "incorreta"})

            st.divider()

    with col_evidence:
        st.subheader("📄 Painel de Evidências (Texto da Fonte)")
        if st.session_state.chat_history:
            last_msg = st.session_state.chat_history[-1]
            if last_msg["citacoes"]:
                for cit in last_msg["citacoes"]:
                    with st.container(border=True):
                        st.markdown(f"**Documento:** {cit.documento} · **Página:** {cit.pagina} · **Item:** `{cit.item}`")
                        st.info(f"“{cit.trecho}”")
            else:
                st.info("Nenhuma evidência documental localizada para a consulta anterior.")
        else:
            st.caption("Os trechos literais extraídos das páginas do PDF aparecerão aqui.")

# ==============================================================================
# ABA 2: Checklist de Habilitação (RF-13, RF-19, CA-09)
# ==============================================================================
with tab_checklist:
    st.header("Checklist de Habilitação (Lei nº 14.133/2021)")
    st.caption("Classificação automatizada nos 4 eixos dos Artigos 62 a 70.")

    if st.session_state.indexed_chunks:
        checklist_items = checklist_ext.extract_from_chunks(st.session_state.indexed_chunks)

        if checklist_items:
            table_data = [
                {
                    "Categoria": item.categoria,
                    "Descrição da Exigência": item.descricao,
                    "Citação Fonte": item.citacao,
                    "Obrigatório": "Sim" if item.obrigatorio else "Não",
                }
                for item in checklist_items
            ]
            st.dataframe(table_data, use_container_width=True)

            # Exportação para CSV (RF-19)
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=["Categoria", "Descrição da Exigência", "Citação Fonte", "Obrigatório"])
            writer.writeheader()
            writer.writerows(table_data)
            csv_bytes = output.getvalue().encode("utf-8")

            st.download_button(
                label="📥 Exportar Checklist em CSV",
                data=csv_bytes,
                file_name=f"checklist_{st.session_state.edital_name}.csv",
                mime="text/csv",
            )
        else:
            st.info("Nenhum item de habilitação foi localizado no documento carregado.")
    else:
        st.info("Carregue um edital na barra lateral para gerar o checklist automático.")

# ==============================================================================
# ABA 3: Prazos, Garantias e Sanções (RF-14, RN-06)
# ==============================================================================
with tab_prazos:
    st.header("Prazos Processuais e Condições Contratuais")
    st.caption("Normalização formal de dias úteis versus dias corridos (RN-06).")

    if st.session_state.indexed_chunks:
        deadlines = deadlines_ext.extract_deadlines(st.session_state.indexed_chunks)
        warranty = deadlines_ext.extract_warranty(st.session_state.indexed_chunks)
        penalties = deadlines_ext.extract_penalties(st.session_state.indexed_chunks)

        st.subheader("1. Cronograma e Prazos")
        if deadlines:
            deadlines_table = [
                {
                    "Tipo de Prazo": d.tipo,
                    "Prazo Estipulado": d.prazo_valor,
                    "Contagem": d.dias_uteis_ou_corridos,
                    "Citação": d.citacao,
                    "Descrição": d.descricao,
                }
                for d in deadlines
            ]
            st.dataframe(deadlines_table, use_container_width=True)
        else:
            st.info("Nenhum prazo explícito identificado.")

        st.subheader("2. Garantia de Execução Contratual")
        if warranty:
            g_col1, g_col2, g_col3 = st.columns(3)
            with g_col1:
                st.metric("Garantia Exigida", warranty.percentual_ou_valor)
            with g_col2:
                st.metric("Prazo de Prestação", warranty.prazo_prestacao)
            with g_col3:
                st.markdown(f"**Citação:** `{warranty.citacao}`")
        else:
            st.info("Garantia contratual não identificada.")

        st.subheader("3. Sanções Administrativas e Multas")
        if penalties:
            penalties_data = [
                {"Sanção": p.tipo, "Descrição": p.descricao, "Citação": p.citacao}
                for p in penalties
            ]
            st.dataframe(penalties_data, use_container_width=True)
    else:
        st.info("Carregue um edital na barra lateral para visualizar os prazos e garantias.")

# ==============================================================================
# ABA 4: Alertas Preventivos da Lei nº 14.133/2021 (RF-15, RN-05, RN-07, CA-10)
# ==============================================================================
with tab_alertas:
    st.header("Alertas Preventivos de Conformidade Legal")
    st.caption("Sinalização preventiva de possíveis incompatibilidades com a Lei nº 14.133/2021 (RN-07: sem parecer jurídico).")

    if st.session_state.indexed_chunks:
        deadlines = deadlines_ext.extract_deadlines(st.session_state.indexed_chunks)
        warranty = deadlines_ext.extract_warranty(st.session_state.indexed_chunks)
        alerts = risk_det.analyze_risks(st.session_state.indexed_chunks, deadlines, warranty)

        if alerts:
            for alert in alerts:
                severity_icon = "🔴" if alert.severidade.value == "ALTA" else "🟡"
                with st.container(border=True):
                    st.markdown(f"### {severity_icon} {alert.tipo} (Severidade: {alert.severidade.value})")
                    st.warning(alert.descricao)
                    st.markdown(f"**Referência Legal:** `{alert.referencia_legal}` · **Item do Edital:** `{alert.item_edital}`")
        else:
            st.success("Nenhuma incompatibilidade evidente identificada em relação aos dispositivos auditados da Lei nº 14.133/2021.")
    else:
        st.info("Carregue um edital na barra lateral para executar a auditoria de conformidade.")
