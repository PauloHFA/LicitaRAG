"""Módulo de cálculo de métricas para o Evaluation Harness do Licita-RAG.

Métricas implementadas conforme a Seção 14 e Seção 16.2 do documento de requisitos:
- Recall@k
- MRR (Mean Reciprocal Rank)
- Acurácia de Citação (Página e Item)
- Fidelidade (Faithfulness)
- Taxa de Abstenção Correta
- Taxa de Falsa Recusa
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class EvaluationReport:
    total_perguntas: int
    recall_at_5: float
    mrr: float
    acuracia_citacao: float
    taxa_abstencao_correta: float
    taxa_falsa_recusa: float
    latencia_media_ms: float


def calculate_recall_at_k(
    retrieved_chunk_ids: list[int],
    gold_chunk_ids: list[int],
    k: int = 5,
) -> float:
    """Calcula se ao menos um dos chunks corretos do gabarito está presente nos top-k recuperados.

    Retorna 1.0 se houver interseção, caso contrário 0.0.
    """
    if not gold_chunk_ids:
        return 1.0
    top_k = set(retrieved_chunk_ids[:k])
    return 1.0 if bool(top_k.intersection(set(gold_chunk_ids))) else 0.0


def calculate_mrr(
    retrieved_chunk_ids: list[int],
    gold_chunk_ids: list[int],
) -> float:
    """Calcula o Reciprocal Rank (1/rank) do primeiro trecho correto recuperado.

    Retorna 0.0 caso nenhum trecho do gabarito esteja na lista recuperada.
    """
    if not gold_chunk_ids:
        return 1.0
    gold_set = set(gold_chunk_ids)
    for rank, chunk_id in enumerate(retrieved_chunk_ids, start=1):
        if chunk_id in gold_set:
            return 1.0 / rank
    return 0.0


def calculate_citation_accuracy(
    predicted_citations: list[dict[str, Any]],
    gold_citations: list[dict[str, Any]],
) -> float:
    """Verifica se as citações geradas conferem em página e número do item com o gabarito.

    Retorna a proporção de citações preditas válidas.
    """
    if not gold_citations and not predicted_citations:
        return 1.0
    if not predicted_citations:
        return 0.0

    hits = 0
    for pred in predicted_citations:
        pred_pag = pred.get("pagina")
        pred_item = str(pred.get("item", "")).strip().rstrip(".")

        for gold in gold_citations:
            gold_pag = gold.get("pagina")
            gold_item = str(gold.get("item", "")).strip().rstrip(".")

            if pred_pag == gold_pag and pred_item == gold_item:
                hits += 1
                break

    return hits / len(predicted_citations)


def evaluate_abstention(
    predictions: list[dict[str, Any]],
) -> tuple[float, float]:
    """Calcula a taxa de abstenção correta e taxa de falsa recusa.

    Cada item em predictions deve ter:
    - 'deve_abster': bool (True se a pergunta não tinha resposta no edital)
    - 'absteve': bool (True se o modelo respondeu que a informação não consta)

    Retorna (taxa_abstencao_correta, taxa_falsa_recusa).
    """
    total_deve_abster = 0
    acertos_abstencao = 0

    total_tem_resposta = 0
    falsas_recusas = 0

    for item in predictions:
        deve_abster = item.get("deve_abster", False)
        absteve = item.get("absteve", False)

        if deve_abster:
            total_deve_abster += 1
            if absteve:
                acertos_abstencao += 1
        else:
            total_tem_resposta += 1
            if absteve:
                falsas_recusas += 1

    taxa_abstencao_correta = (
        (acertos_abstencao / total_deve_abster) if total_deve_abster > 0 else 1.0
    )
    taxa_falsa_recusa = (
        (falsas_recusas / total_tem_resposta) if total_tem_resposta > 0 else 0.0
    )

    return taxa_abstencao_correta, taxa_falsa_recusa
