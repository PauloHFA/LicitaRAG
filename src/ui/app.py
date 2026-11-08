import csv
import io
import time

import streamlit as st

from src.audit.checklist import ChecklistExtractor
from src.audit.deadlines import DeadlinesAndSanctionsExtractor
from src.audit.petitions import PetitionGenerator
from src.audit.report_generator import AuditReportGenerator
from src.audit.risk_detector import RiskDetector
from src.audit.version_diff import VersionComparator
from src.chunking.clause_splitter import HierarchicalClauseSplitter
from src.generation.llm_client import MockLLMClient
from src.generation.responder import GroundedResponder
from src.ingestion.pdf_loader import PDFIngestionPipeline
from src.retrieval.hybrid_retriever import HybridRetriever
from src.retrieval.query_expansion import LegalQueryExpander

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
if "quick_query" not in st.session_state:
    st.session_state.quick_query = ""


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
    expander = LegalQueryExpander()
    return pipeline, splitter, retriever, responder, checklist_ext, deadlines_ext, risk_det, expander


pipeline, splitter, retriever, responder, checklist_ext, deadlines_ext, risk_det, expander = get_services()

# Barra Lateral: Upload e Seleção de Documentos
with st.sidebar:
    st.title("⚖️ Licita-RAG")
    st.caption("Auditoria Jurídica & RAG com Citação Estrita sob a Lei 14.133/2021")
    st.divider()

    st.subheader("📁 Ingestão de Documentos")
    uploaded_file = st.file_uploader(
        "Selecione o arquivo do Edital ou Errata (PDF):",
        type=["pdf"],
        help="Upload com validação de magic bytes (%PDF-), limite de 50MB e OCR inteligente.",
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
tab_chat, tab_checklist, tab_prazos, tab_alertas, tab_impugnacao, tab_dossie, tab_diff = st.tabs([
    "💬 Chat com Citação Estrita",
    "📋 Checklist de Habilitação",
    "⏱️ Prazos & Cronogramas",
    "⚠️ Alertas da Lei 14.133/2021",
    "⚖️ Minuta de Impugnação",
    "📑 Dossiê Executivo",
    "🔄 Comparativo de Versões",
])

# ==============================================================================
# ABA 1: Chat com Citação e Painel Lado a Lado (RF-10, RF-12, RNF-10)
# ==============================================================================
with tab_chat:
    st.header("Consulta Auditável com Citação de Origem")
    st.caption("Toda resposta cita obrigatoriamente [Edital, p. N, item N.N]. À direita, confira o trecho literal.")

    # Atalhos rápidos de consulta
    st.markdown("**⚡ Perguntas Rápidas em 1 Clique:**")
    b1, b2, b3, b4 = st.columns(4)
    with b1:
        if st.button("📋 Qualificação Técnica"):
            st.session_state.quick_query = "Quais são as exigências de qualificação técnica e atestados exigidos?"
    with b2:
        if st.button("⏰ Prazos de Proposta"):
            st.session_state.quick_query = "Qual é o prazo para apresentação de propostas e impugnação?"
    with b3:
        if st.button("💰 Garantia Contratual"):
            st.session_state.quick_query = "Qual é o percentual ou valor da garantia contratual exigida?"
    with b4:
        if st.button("⚠️ Possíveis Ilegalidades"):
            st.session_state.quick_query = "Existe alguma exigência de marca exclusiva ou restrição indevida?"

    col_chat, col_evidence = st.columns([6, 5])

    with col_chat:
        user_query = st.text_input(
            "Faça uma pergunta sobre o edital:",
            value=st.session_state.quick_query,
            placeholder="Ex: Qual é o valor e prazo da garantia contratual?",
        )

        if st.button("Enviar Pergunta") and user_query:
            if not st.session_state.indexed_chunks:
                st.warning("Por favor, carregue um arquivo PDF na barra lateral para iniciar a consulta.")
            else:
                # Expansão semântica e busca híbrida
                expanded_q = expander.expand_query(user_query)
                candidates = retriever.search_in_memory(
                    query=expanded_q,
                    candidates=st.session_state.indexed_chunks,
                    top_candidates=15,
                    top_final=5,
                )

                # Geração Fundamentada com validação
                chat_resp, latencia_ms = responder.generate_response(user_query, candidates)

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

            if msg["citacoes"]:
                cits_str = " | ".join(
                    f"`[{c.documento}, p. {c.pagina}, item {c.item}]`" for c in msg["citacoes"]
                )
                st.markdown(f"📌 **Fontes Auditadas:** {cits_str}")

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
                severity_icon = "🔴" if alert.severidade.value == "alta" else "🟡"
                with st.container(border=True):
                    st.markdown(f"### {severity_icon} {alert.tipo} (Severidade: {alert.severidade.value})")
                    st.warning(alert.descricao)
                    st.markdown(f"**Referência Legal:** `{alert.referencia_legal}` · **Item do Edital:** `{alert.item_edital}`")
        else:
            st.success("Nenhuma incompatibilidade evidente identificada em relação aos dispositivos auditados da Lei nº 14.133/2021.")
    else:
        st.info("Carregue um edital na barra lateral para executar a auditoria de conformidade.")

# ==============================================================================
# ABA 5: Minuta de Impugnação Administrativa (Nova Funcionalidade)
# ==============================================================================
with tab_impugnacao:
    st.header("⚖️ Gerador de Minuta de Impugnação Administrativa")
    st.caption("Gera peça jurídica fundamentada com base no Art. 164 da Lei 14.133/2021 a partir dos alertas identificados.")

    if st.session_state.indexed_chunks:
        deadlines = deadlines_ext.extract_deadlines(st.session_state.indexed_chunks)
        warranty = deadlines_ext.extract_warranty(st.session_state.indexed_chunks)
        alerts = risk_det.analyze_risks(st.session_state.indexed_chunks, deadlines, warranty)

        c1, c2 = st.columns(2)
        with c1:
            empresa_nome = st.text_input("Razão Social da Impugnante:", value="Licita Tech Soluções Ltda.")
        with c2:
            empresa_cnpj = st.text_input("CNPJ da Impugnante:", value="12.345.678/0001-90")

        if alerts:
            st.warning(f"Identificado(s) {len(alerts)} ponto(s) passível(is) de impugnação administrativa no certame.")
            minuta_md = PetitionGenerator.generate_impugnacao(
                edital_numero=st.session_state.edital_name,
                orgao="Órgão Licitante Responsável",
                alerts=alerts,
                razao_social=empresa_nome,
                cnpj=empresa_cnpj,
            )

            st.download_button(
                label="📥 Baixar Minuta de Impugnação (.md)",
                data=minuta_md.encode("utf-8"),
                file_name=f"impugnacao_{st.session_state.edital_name}.md",
                mime="text/markdown",
            )
            with st.expander("Visualizar Minuta Completa da Petição", expanded=True):
                st.markdown(minuta_md)
        else:
            st.success("✅ O edital não possui alertas de risco críticos para fundamentar uma impugnação.")
    else:
        st.info("Carregue um edital na barra lateral para habilitar o gerador de petição de impugnação.")

# ==============================================================================
# ABA 6: Dossiê Executivo de Auditoria (Nova Funcionalidade)
# ==============================================================================
with tab_dossie:
    st.header("📑 Dossiê Executivo de Auditoria Preventiva")
    st.caption("Consolidação integral do certame pronta para exportação à diretoria ou jurídico.")

    if st.session_state.indexed_chunks:
        deadlines = deadlines_ext.extract_deadlines(st.session_state.indexed_chunks)
        penalties = deadlines_ext.extract_penalties(st.session_state.indexed_chunks)
        warranty = deadlines_ext.extract_warranty(st.session_state.indexed_chunks)
        chk_items = checklist_ext.extract_from_chunks(st.session_state.indexed_chunks)
        alerts = risk_det.analyze_risks(st.session_state.indexed_chunks, deadlines, warranty)

        dossier_md = AuditReportGenerator.generate_dossier(
            edital_numero=st.session_state.edital_name,
            orgao="Órgão Licitante Convocante",
            objeto="Fornecimento de bens ou prestação de serviços especificados no edital",
            deadlines=deadlines,
            penalties=penalties,
            warranty=warranty,
            checklist=chk_items,
            alerts=alerts,
        )

        st.download_button(
            label="📥 Baixar Dossiê Executivo Completo (.md)",
            data=dossier_md.encode("utf-8"),
            file_name=f"dossie_executivo_{st.session_state.edital_name}.md",
            mime="text/markdown",
        )

        with st.expander("Visualizar Dossiê Completo", expanded=True):
            st.markdown(dossier_md)
    else:
        st.info("Carregue um edital na barra lateral para gerar o dossiê executivo completo.")

# ==============================================================================
# ABA 7: Comparativo de Versões (Edital vs. Erratas) (Nova Funcionalidade)
# ==============================================================================
with tab_diff:
    st.header("🔄 Comparativo de Versões (Edital vs. Errata/Aditivo)")
    st.caption("Identifica cláusulas alteradas por erratas e classifica o impacto prático para o licitante.")

    if st.session_state.indexed_chunks:
        orig_chunks = [
            c for c in st.session_state.indexed_chunks
            if "errata" not in str(c.metadados.get("documento", "")).lower()
            and "retifica" not in str(c.metadados.get("tipo_documento", "")).lower()
        ]
        errata_chunks = [
            c for c in st.session_state.indexed_chunks
            if "errata" in str(c.metadados.get("documento", "")).lower()
            or "retifica" in str(c.metadados.get("tipo_documento", "")).lower()
        ]

        if errata_chunks and orig_chunks:
            diffs = VersionComparator.compare_versions(orig_chunks, errata_chunks)
            if diffs:
                st.subheader(f"Foram identificadas {len(diffs)} cláusula(s) retificadas:")
                for df in diffs:
                    with st.expander(f"Cláusula {df.item} - Impacto: {df.tipo_impacto}", expanded=True):
                        st.markdown(f"**Documento Retificador:** `{df.documento_retificador}`")
                        st.markdown(f"**Impacto Avaliado:** {df.descricao_impacto}")
                        c1, c2 = st.columns(2)
                        with c1:
                            st.caption(f"Redação Original (Pág. {df.pagina_original}):")
                            st.error(df.redacao_original)
                        with c2:
                            st.caption(f"Redação Retificada (Prevalece - Pág. {df.pagina_retificada}):")
                            st.success(df.redacao_retificada)
            else:
                st.info("Nenhuma cláusula com redação divergente identificada entre o edital e a errata carregada.")
        else:
            st.info("Carregue ao menos um arquivo de Edital e um arquivo de Errata/Retificação na barra lateral para gerar o comparativo.")
    else:
        st.info("Carregue os documentos na barra lateral para visualizar o comparativo de versões.")
