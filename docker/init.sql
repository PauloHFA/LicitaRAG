-- Inicialização do banco de dados para Licita-RAG
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Configuração padrão de busca textual em português
COMMENT ON EXTENSION vector IS 'Extensão pgvector para busca por similaridade semântica';
