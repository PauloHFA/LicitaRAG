# Licita-RAG

Assistente RAG com citação estrita para extração e auditoria de conformidade de editais públicos.

## 1. Visão Geral

O **Licita-RAG** recebe editais e anexos (PDF), indexa o conteúdo preservando a estrutura de cláusulas e numeração de páginas, e permite consultas em linguagem natural. Toda resposta factual cita obrigatoriamente página e item de origem no formato `[Edital X, p. N, item N.N]`.

O sistema também gera automaticamente o checklist de habilitação (jurídica, fiscal, técnica, econômico-financeira) e sinaliza possíveis riscos com base na **Lei nº 14.133/2021**.

---

## 2. Arquitetura

O projeto adota Clean Architecture com Portas e Adaptadores:

* **Ingestão**: `PyMuPDF` (páginas), `pdfplumber` (tabelas) e `pytesseract` (fallback OCR).
* **Chunking**: Segmentação por cláusula numerada via regex (`^\d+(\.\d+)*\.?\s`), preservando hierarquia.
* **Busca Híbrida**: PostgreSQL 16 com `pgvector` (busca semântica) + `tsvector` português (busca lexical), combinados via **Reciprocal Rank Fusion (RRF)**.
* **Reranking**: `bge-reranker-v2-m3` sobre os top candidatos.
* **Geração Fundamentada**: Validador pós-geração contra alucinações e política estrita de abstenção.
* **LLM**: Abstração entre Groq (nuvem gratuita) e Ollama (local).

---

## 3. Estrutura do Repositório

```text
Licita-RAG/
├── docker/                    # Dockerfile, docker-compose.yml e scripts de inicialização
├── src/
│   ├── config.py              # Configurações do sistema via pydantic-settings
│   ├── api/                   # Rotas e schemas FastAPI (REST API assíncrona)
│   ├── ingestion/             # Leitura de PDF, extração de tabelas e OCR
│   ├── chunking/              # Segmentação hierárquica de cláusulas
│   ├── retrieval/             # Busca vetorial, tsvector, RRF e Reranker
│   ├── generation/            # Prompts, clientes LLM e validador de citações
│   ├── audit/                 # Checklist de habilitação e alertas da Lei 14.133/2021
│   ├── db/                    # Modelos ORM SQLAlchemy e conexão assíncrona
│   └── eval/                  # Golden dataset, métricas e benchmark CLI
├── tests/
│   ├── unit/                  # Testes unitários de regex, modelos e métricas
│   ├── integration/           # Testes de integração de ponta a ponta
│   └── security/              # Testes de injeção de prompt e arquivos maliciosos
├── samples/                   # Editais públicos de teste
└── docs/                      # Documentação técnica e ADRs
```

---

## 4. Como Executar

### Pré-requisitos
* Python 3.12+
* Docker e Docker Compose

### Executando com Docker Compose

Suba o banco PostgreSQL com pgvector, Redis e a API:

```bash
docker compose -f docker/docker-compose.yml up --build -d
```

A documentação interativa da API estará disponível em:
* Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
* Health Check: [http://localhost:8000/health](http://localhost:8000/health)

---

## 5. Harness de Testes e Avaliação

### Executar Testes Unitários
```bash
pytest tests/unit/ -v
```

### Executar Testes com Cobertura
```bash
pytest --cov=src --cov-report=term-missing tests/unit/
```

### Verificação de Código e Estilo (Ruff)
```bash
ruff check .
```
