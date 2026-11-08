from pathlib import Path

from src.eval.run_benchmark import BenchmarkRunner


def test_benchmark_runner_executes_on_golden_dataset():
    """Valida execução automatizada do benchmark sobre o Golden Dataset do projeto (RNF-05)."""
    dataset_file = Path("src/eval/golden_dataset.jsonl")
    assert dataset_file.exists()

    runner = BenchmarkRunner()
    report = runner.run_benchmark(dataset_file)

    assert report.total_perguntas >= 3
    assert 0.0 <= report.recall_at_5 <= 1.0
    assert 0.0 <= report.mrr <= 1.0
    assert 0.0 <= report.acuracia_citacao <= 1.0
    assert 0.0 <= report.taxa_abstencao_correta <= 1.0
    assert 0.0 <= report.taxa_falsa_recusa <= 1.0
