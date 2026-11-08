import argparse
import json
import logging
import time
from pathlib import Path
from typing import Any

from src.eval.metrics import (
    EvaluationReport,
    calculate_citation_accuracy,
    calculate_mrr,
    calculate_recall_at_k,
    evaluate_abstention,
)
from src.generation.llm_client import MockLLMClient
from src.generation.responder import GroundedResponder
from src.retrieval.hybrid_retriever import HybridRetriever
from src.retrieval.rrf import RankedCandidate

logger = logging.getLogger(__name__)


class BenchmarkRunner:
    """Executor automatizado de avaliação e benchmarking de RAG (Seção 13, 14 e 16.3)."""

    def __init__(
        self,
        retriever: HybridRetriever | None = None,
        responder: GroundedResponder | None = None,
    ) -> None:
        self.retriever = retriever or HybridRetriever()
        self.responder = responder or GroundedResponder(llm_client=MockLLMClient())

    def run_benchmark(
        self,
        dataset_path: str | Path,
        simulated_corpus: list[RankedCandidate] | None = None,
    ) -> EvaluationReport:
        """Executa a bateria de testes sobre o dataset JSONL e calcula as métricas consolidadas."""
        path = Path(dataset_path)
        if not path.exists():
            raise FileNotFoundError(f"Conjunto de ouro não encontrado: {path}")

        records: list[dict[str, Any]] = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if line_str:
                    records.append(json.loads(line_str))

        if not records:
            return EvaluationReport(
                total_perguntas=0,
                recall_at_5=0.0,
                mrr=0.0,
                acuracia_citacao=0.0,
                taxa_abstencao_correta=0.0,
                taxa_falsa_recusa=0.0,
                latencia_media_ms=0.0,
            )

        # Corpus sintético representativo caso não seja fornecido
        corpus = simulated_corpus or [
            RankedCandidate(
                chunk_id=1,
                texto="14.1 A garantia contratual é de 5% do valor total adjudicado.",
                pagina=42,
                item="14.1",
            ),
            RankedCandidate(
                chunk_id=2,
                texto="Lote 2 - Item 1: A fonte de alimentação deve possuir redundância com no mínimo 750W.",
                pagina=18,
                item="Lote 2 - Item 1",
            ),
            RankedCandidate(
                chunk_id=3,
                texto="8.4.2 Apresentar atestado de capacidade técnica emitido por pessoa jurídica.",
                pagina=12,
                item="8.4.2",
            ),
        ]

        recalls: list[float] = []
        mrrs: list[float] = []
        citation_accs: list[float] = []
        latencies: list[int] = []
        abstention_predictions: list[dict[str, Any]] = []

        for item in records:
            query = item["pergunta"]
            gold_citations = item.get("citacoes_esperadas", [])
            deve_abster = item.get("deve_abster", False)

            # 1. Recuperação híbrida
            candidates = self.retriever.search_in_memory(
                query=query,
                candidates=corpus,
                top_candidates=10,
                top_final=5,
            )

            retrieved_chunk_ids = [c.candidate.chunk_id for c in candidates]
            # Mapeia chunk_ids esperados baseados na página/item
            gold_chunk_ids: list[int] = []
            for g_cit in gold_citations:
                for c in corpus:
                    if c.pagina == g_cit.get("pagina"):
                        gold_chunk_ids.append(c.chunk_id)

            recalls.append(calculate_recall_at_k(retrieved_chunk_ids, gold_chunk_ids, k=5))
            mrrs.append(calculate_mrr(retrieved_chunk_ids, gold_chunk_ids))

            # 2. Geração e citação
            chat_resp, lat_ms = self.responder.generate_response(query, candidates)
            latencies.append(lat_ms)

            # Acurácia de citação
            pred_cits = [
                {"pagina": c.pagina, "item": c.item, "trecho": c.trecho}
                for c in chat_resp.citacoes
            ]
            if gold_citations:
                citation_accs.append(calculate_citation_accuracy(pred_cits, gold_citations))

            # Abstenção
            absteve = not chat_resp.encontrado or not chat_resp.citacoes
            abstention_predictions.append({
                "deve_abster": deve_abster,
                "absteve": absteve,
            })

        taxa_abstencao, taxa_falsa_recusa = evaluate_abstention(abstention_predictions)

        report = EvaluationReport(
            total_perguntas=len(records),
            recall_at_5=sum(recalls) / len(recalls) if recalls else 0.0,
            mrr=sum(mrrs) / len(mrrs) if mrrs else 0.0,
            acuracia_citacao=sum(citation_accs) / len(citation_accs) if citation_accs else 1.0,
            taxa_abstencao_correta=taxa_abstencao,
            taxa_falsa_recusa=taxa_falsa_recusa,
            latencia_media_ms=sum(latencies) / len(latencies) if latencies else 0.0,
        )

        return report


def main() -> None:
    parser = argparse.ArgumentParser(description="CLI de Benchmark do Licita-RAG")
    parser.add_argument(
        "--dataset",
        default="src/eval/golden_dataset.jsonl",
        help="Caminho do arquivo JSONL do Golden Dataset",
    )
    parser.add_argument(
        "--output",
        default="eval_report.json",
        help="Arquivo JSON para exportar as métricas consolidadas",
    )
    args = parser.parse_args()

    runner = BenchmarkRunner()
    print(f"\n🚀 Iniciando Benchmark do Licita-RAG sobre: {args.dataset}")
    start_time = time.time()

    report = runner.run_benchmark(args.dataset)
    elapsed = time.time() - start_time

    print("\n" + "=" * 60)
    print("           RELATÓRIO DE AVALIAÇÃO SISTEMÁTICA RAG           ")
    print("=" * 60)
    print(f"Total de Consultas Avaliadas : {report.total_perguntas}")
    print(f"Recall@5 (Meta: >= 85%)      : {report.recall_at_5 * 100:.1f}%")
    print(f"MRR (Meta: >= 0.70)          : {report.mrr:.3f}")
    print(f"Acurácia Citação (Meta: >=90%): {report.acuracia_citacao * 100:.1f}%")
    print(f"Abstenção Correta (>= 90%)   : {report.taxa_abstencao_correta * 100:.1f}%")
    print(f"Falsa Recusa (< 10%)         : {report.taxa_falsa_recusa * 100:.1f}%")
    print(f"Latência Média               : {report.latencia_media_ms:.1f} ms")
    print(f"Tempo Total do Benchmark    : {elapsed:.2f} s")
    print("=" * 60 + "\n")

    # Salva relatório em JSON
    report_data = {
        "total_perguntas": report.total_perguntas,
        "recall_at_5": report.recall_at_5,
        "mrr": report.mrr,
        "acuracia_citacao": report.acuracia_citacao,
        "taxa_abstencao_correta": report.taxa_abstencao_correta,
        "taxa_falsa_recusa": report.taxa_falsa_recusa,
        "latencia_media_ms": report.latencia_media_ms,
        "tempo_total_segundos": elapsed,
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
    print(f"Relatório exportado com sucesso para: {args.output}")


if __name__ == "__main__":
    main()
