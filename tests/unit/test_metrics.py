from src.eval.metrics import (
    calculate_citation_accuracy,
    calculate_mrr,
    calculate_recall_at_k,
    evaluate_abstention,
)


def test_recall_at_k():
    gold = [105, 106]
    # No top-3, não está
    assert calculate_recall_at_k([101, 102, 103], gold, k=3) == 0.0
    # No top-5, o 105 está na 4ª posição
    assert calculate_recall_at_k([101, 102, 103, 105, 104], gold, k=5) == 1.0


def test_mrr():
    gold = [205]
    # Primeiro match está na 1ª posição => MRR = 1.0
    assert calculate_mrr([205, 201, 202], gold) == 1.0
    # Primeiro match está na 2ª posição => MRR = 0.5
    assert calculate_mrr([201, 205, 202], gold) == 0.5
    # Primeiro match está na 4ª posição => MRR = 0.25
    assert calculate_mrr([201, 202, 203, 205], gold) == 0.25
    # Nenhum match => MRR = 0.0
    assert calculate_mrr([201, 202, 203], gold) == 0.0


def test_citation_accuracy():
    gold_citations = [
        {"pagina": 42, "item": "14.1"},
        {"pagina": 15, "item": "5.2.1"},
    ]

    # Predição com citação 100% correta
    pred_correct = [{"pagina": 42, "item": "14.1."}]
    assert calculate_citation_accuracy(pred_correct, gold_citations) == 1.0

    # Predição com página errada
    pred_wrong_page = [{"pagina": 43, "item": "14.1"}]
    assert calculate_citation_accuracy(pred_wrong_page, gold_citations) == 0.0

    # Predição mista (1 certa, 1 errada) => 50%
    pred_mixed = [
        {"pagina": 42, "item": "14.1"},
        {"pagina": 99, "item": "99.9"},
    ]
    assert calculate_citation_accuracy(pred_mixed, gold_citations) == 0.5


def test_evaluate_abstention():
    predictions = [
        {"deve_abster": True, "absteve": True},    # Acerto de abstenção
        {"deve_abster": True, "absteve": False},   # Falha (inventou resposta)
        {"deve_abster": False, "absteve": False},  # Respondeu certo
        {"deve_abster": False, "absteve": True},   # Falsa recusa
    ]

    taxa_abstencao, taxa_falsa_recusa = evaluate_abstention(predictions)
    assert taxa_abstencao == 0.5  # 1 de 2
    assert taxa_falsa_recusa == 0.5  # 1 de 2
