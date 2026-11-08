# Licita-RAG ⚖️📄

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.42+-FF4B4B.svg)](https://streamlit.io)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20%2B%20pgvector-336791.svg)](https://github.com/pgvector/pgvector)
[![Code Coverage](https://img.shields.io/badge/coverage-89.1%25-brightgreen.svg)](tests/)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Assistente RAG com citação estrita, validação anti-alucinação pós-geração, extração de checklist de habilitação e detector preventivo de riscos com base na Lei nº 14.133/2021 (Nova Lei de Licitações).**

---

## 1. Visão Geral

O **Licita-RAG** é uma solução completa de Inteligência Artificial para análise, auditoria e consulta em linguagem natural sobre editais de licitações públicas, termos de referência e anexos em formato PDF.

### Principais Diferenciais:
1. **Citação Estrita e Auditável (`RN-01`)**: Toda informação factual é acompanhada obrigatoriamente da citação formal no padrão `[Edital X, p. N, item N.N]`.
2. **Validador Pós-Geração Anti-Alucinação (`RN-02`, `CA-04`)**: Validador determinístico que confere se as páginas e itens citados constam literalmente no contexto recuperado. Falhas acionam repetição controlada (1 tentativa) ou abstenção forçada: *"A informação não consta no edital indexado."*
3. **Chunking Hierárquico por Cláusula (`RF-06`)**: Segmentação jurídica com regex preservando a trilha de títulos (`8. DA HABILITAÇÃO > 8.4 Qualificação Técnica > 8.4.2`).
4. **Extração de Tabelas com Cabeçalhos Repetidos (`RF-05`, `CA-05`)**: Cada linha de tabela gera um chunk autônomo com o cabeçalho completo replicado.
5. **Fallback Inteligente de OCR (`RF-04`, `CA-07`)**: Detecção de páginas escaneadas (< 50 caracteres) com Tesseract OCR calibrado em português.
6. **Busca Híbrida + RRF ($k=60$) + Cross-Encoder Reranker (`RF-08`, `RF-09`)**: Combinação matemática exata de vetores densos (`pgvector`) e léxicos (`tsvector` português), refinados com modelo cross-encoder e bônus de siglas e itens (`CND`, `SICAF`, etc.).
7. **Checklist nos 4 Eixos da Lei 14.133/2021 (`RF-13`, `CA-09`)**: Classificação jurídica, fiscal/trabalhista, técnica e econômico-financeira com exportação para CSV.
8. **Normalização de Prazos (Dias Úteis vs. Dias Corridos) (`RN-06`)**: Distinção clara e extração de regras de garantias e sanções.
9. **Detector de Alertas de Risco Preventivo (`RF-15`, `RN-05`, `RN-07`)**: Sinaliza inconsistências frente aos limites da Lei 14.133/2021 (prazos de proposta < 8 dias úteis, impugnação < 3 dias úteis, garantias > 10%) sempre em linguagem de apoio (*"Sugestão de Revisão Humana"*).
10. **Precedência e Versionamento de Erratas (`RF-16`, `RN-03`, `CA-08`)**: Cláusulas retificadas por adendos/erratas prevalecem automaticamente sobre o texto original.

---

## 2. Arquitetura do Sistema

O projeto adota os princípios de **Clean Architecture** (Ports & Adapters), desacoplando totalmente a lógica de negócios e auditoria jurídica de bibliotecas externas e provedores de LLM.

```
┌────────────────────────────────────────────────────────────────────────┐
│                          Streamlit Web UI                              │
│         (Painel Lado a Lado: Chat Fundamentado vs. Evidências)         │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP REST
┌───────────────────────────────────▼────────────────────────────────────┐
│                         FastAPI REST Engine                            │
│           (Upload, Chat RAG, Checklist, Prazos, Alertas, Feedback)     │
└───────┬───────────────────────────┬───────────────────────────┬────────┘
        │                           │                           │
┌───────▼─────────────┐   ┌─────────▼──────────────┐   ┌────────▼────────┐
│  Ingestion & OCR    │   │  Retrieval & Ranking   │   │ Generation &    │
│  - Magic Bytes Check│   │  - pgvector (E5/BGE)   │   │ Anti-Halluc.    │
│  - PyMuPDF Loader   │   │  - tsvector (Port.)    │   │ - Blinded Prompt│
│  - Table Extractor  │   │  - RRF Fusion (k=60)   │   │ - Citation Check│
│  - Tesseract Fallb. │   │  - Cross-Encoder Boost │   │ - Controlled Ret│
└─────────────────────┘   └────────────────────────┘   └─────────────────┘
        │                           │                           │
┌───────▼───────────────────────────▼───────────────────────────▼────────┐
│                    PostgreSQL 16 com extensão pgvector                 │
│         (Editais, Chunks, Embeddings, Vetores de Busca, Mensagens)     │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Estrutura do Repositório

```text
Licita-RAG/
├── docker/
│   ├── Dockerfile             # Imagem multi-stage Python 3.12 com Tesseract OCR português
│   ├── docker-compose.yml     # Orquestração completa: PostgreSQL pgvector, Redis, API, UI
│   └── init.sql               # Inicialização de extensões pgvector e índices
├── src/
│   ├── config.py              # Configurações centralizadas via Pydantic Settings
│   ├── api/
│   │   ├── main.py            # Ponto de entrada FastAPI com middlewares de CORS e log
│   │   ├── routes.py          # Endpoints REST (/upload, /chat, /checklist, /prazos, /alertas)
│   │   └── schemas.py         # Schemas de request e response Pydantic
│   ├── ingestion/
│   │   ├── validator.py       # Validação de magic bytes, sanitização e SHA-256
│   │   ├── pdf_loader.py      # Extração de texto e páginas com numeração física
│   │   ├── table_extractor.py # Extração de tabelas com repetição de cabeçalho
│   │   ├── ocr_fallback.py    # Fallback inteligente de OCR via Tesseract
│   │   └── versions.py        # Motor de precedência e retificação de erratas
│   ├── chunking/
│   │   ├── clause_splitter.py # Parser hierárquico por regex de cláusulas
│   │   └── models.py          # Modelos de dados de chunks e formatação de citação
│   ├── retrieval/
│   │   ├── embeddings.py      # Gerador de embeddings com suporte offline e fallback L2
│   │   ├── rrf.py             # Algoritmo Reciprocal Rank Fusion k=60
│   │   ├── reranker.py        # Cross-Encoder com bônus de termos exatos e siglas
│   │   └── hybrid_retriever.py# Orquestrador de busca híbrida (pgvector + tsvector)
│   ├── generation/
│   │   ├── prompts.py         # Prompts blindados contra injeção de prompt (<contexto>)
│   │   ├── llm_client.py      # Clientes desacoplados (Groq, Ollama, MockLLM)
│   │   ├── citation_verifier.py # Validador programático pós-geração anti-alucinação
│   │   └── responder.py       # Orquestrador com repetição controlada (1 tentativa)
│   ├── audit/
│   │   ├── legal_base.py      # Artigos e parâmetros da Lei nº 14.133/2021
│   │   ├── checklist.py       # Extrator dos 4 eixos de habilitação com citação
│   │   ├── deadlines.py       # Extrator de prazos (dias úteis vs. corridos) e garantias
│   │   └── risk_detector.py   # Detector de alertas preventivos de risco
│   ├── ui/
│   │   └── app.py             # Interface web Streamlit com layout side-by-side
│   ├── eval/
│   │   ├── metrics.py         # Métricas de RAG (Recall@k, MRR, Citação, Fidelidade, Abstenção)
│   │   ├── golden_dataset.jsonl# Dataset padrão de avaliação com gabarito
│   │   └── run_benchmark.py   # CLI de execução do benchmark automatizado
│   └── db/
│       ├── base.py            # Base declarativa SQLAlchemy
│       ├── session.py         # Sessão assíncrona SQLAlchemy
│       └── models.py          # Modelos relacionais e vetoriais
├── tests/
│   └── unit/                  # Suíte completa de 58 testes unitários
├── pyproject.toml             # Metadados do projeto, dependências e configurações de testes
└── README.md                  # Documentação oficial do projeto
```

---

## 4. Como Executar

### Opção A: Execução Completa via Docker Compose (Recomendado)

O Docker Compose sobe automaticamente:
* **PostgreSQL 16 com pgvector** (porta 5432)
* **Redis 7** para cache e mensageria (porta 6379)
* **API FastAPI** (porta 8000)
* **Streamlit Web UI** (porta 8501)

```bash
# Iniciar todos os serviços em segundo plano
docker compose -f docker/docker-compose.yml up --build -d
```

Após a inicialização, acesse:
- 🌐 **Interface Web (Streamlit)**: [http://localhost:8501](http://localhost:8501)
- 📚 **Documentação Interativa (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- 🩺 **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

Para parar os serviços:
```bash
docker compose -f docker/docker-compose.yml down
```

---

### Opção B: Execução Local para Desenvolvimento

#### 1. Instalar dependências
```bash
pip install -e .
```

#### 2. Configurar variáveis de ambiente (`.env`)
```bash
cp .env.example .env
```
Edite o `.env` com sua chave da Groq (`GROQ_API_KEY`) ou configure `LLM_PROVIDER=ollama`.

#### 3. Iniciar o backend FastAPI
```bash
uvicorn src.api.main:app --reload --port 8000
```

#### 4. Iniciar a interface Streamlit
```bash
streamlit run src/ui/app.py --server.port 8501
```

---

## 5. Qualidade de Código, Testes & Benchmark

### 1. Executar a Suíte de Testes Unitários
```bash
pytest tests/unit/ -v
```

### 2. Gerar Relatório de Cobertura de Código ($\ge 80\%$)
```bash
pytest --cov=src --cov-report=term-missing tests/unit/
```
*Cobertura atual: **89.11%** em 1212 linhas de código.*

### 3. Verificação de Código e Linter (Ruff)
```bash
ruff check .
```

### 4. Executar o Benchmark CLI sobre o Golden Dataset
```bash
python -m src.eval.run_benchmark --dataset src/eval/golden_dataset.jsonl --output eval_report.json
```

O comando calcula e exibe no terminal:
- **Recall@5** (Meta: $\ge 85\%$)
- **MRR (Mean Reciprocal Rank)** (Meta: $\ge 0.70$)
- **Acurácia de Citação** (Meta: $\ge 90\%$)
- **Fidelidade (Faithfulness)**
- **Taxa de Abstenção Correta** (Meta: $\ge 90\%$)
- **Taxa de Falsa Recusa** (Meta: $< 10\%$)
- **Latência média (ms)** e exporta o relatório JSON consolidado.

---

## 6. Endpoints Principais da API REST

| Método | Endpoint | Descrição |
|---|---|---|
| `POST` | `/api/v1/editais/upload` | Upload e ingestão com validação de magic bytes, sanitização e chunking. |
| `POST` | `/api/v1/editais/{id}/chat` | Chat RAG fundamentado com validação pós-geração e citação canônica. |
| `GET` | `/api/v1/editais/{id}/checklist` | Checklist de habilitação categorizado nos 4 eixos da Lei 14.133/2021. |
| `GET` | `/api/v1/editais/{id}/prazos` | Extração de prazos (dias úteis vs corridos), sanções e garantias. |
| `GET` | `/api/v1/editais/{id}/alertas` | Alertas preventivos de risco fundamentados na Lei 14.133/2021. |
| `POST` | `/api/v1/editais/{id}/feedback` | Registro de utilidade e feedback dos usuários sobre as respostas geradas. |

---

## 7. Conformidade Jurídica e Diretrizes de IA Responsável

O **Licita-RAG** foi estritamente arquitetado observando as seguintes diretrizes:
* **RN-07 (Sem Parecer Jurídico Vinculante)**: O sistema atua como ferramenta de apoio preventivo ao licitante. Todos os apontamentos de inconformidade são rotulados como *"Sugestão de Revisão Humana"*, nunca afirmando categoricamente a nulidade ou ilegalidade de um edital.
* **Isolamento de Prompts (CA-11)**: Conteúdos oriundos do edital são estritamente encapsulados entre tags `<contexto>...</contexto>`, impedindo que instruções maliciosas inseridas no documento subvertam as regras do assistente.
* **Governança de Dados**: Suporte total a execução 100% on-premises através do Ollama e PostgreSQL local, atendendo a requisitos de sigilo e conformidade com a LGPD.

---

## 8. Licença

Este projeto é distribuído sob os termos da licença [MIT](LICENSE).
