import enum
from dataclasses import dataclass


class CategoriaHabilitacao(enum.StrEnum):
    """Categorias legais de habilitação em conformidade com os artigos 62 a 70 da Lei nº 14.133/2021."""
    JURIDICA = "Habilitação Jurídica"
    FISCAL_TRABALHISTA = "Regularidade Fiscal, Social e Trabalhista"
    TECNICA = "Qualificação Técnica"
    ECONOMICA = "Qualificação Econômico-Financeira"


@dataclass
class ExtractedChecklistItem:
    """Item estruturado do checklist de habilitação (RF-13, CA-09)."""
    categoria: str
    descricao: str
    citacao: str
    obrigatorio: bool = True


@dataclass
class ExtractedDeadline:
    """Prazo processual ou operacional normalizado do certame (RF-14, RN-06)."""
    tipo: str  # ex: "Impugnação", "Esclarecimentos", "Abertura da Sessão", "Entrega", "Garantia"
    descricao: str
    prazo_valor: str
    dias_uteis_ou_corridos: str  # "dias úteis", "dias corridos" ou "data fixa"
    citacao: str


@dataclass
class ExtractedPenalty:
    """Sanção administrativa ou penalidade contratual extraída."""
    tipo: str  # "Advertência", "Multa", "Impedimento de licitar", "Inidoneidade"
    descricao: str
    citacao: str


@dataclass
class ExtractedWarranty:
    """Especificações da garantia contratual da licitação."""
    exigida: bool
    percentual_ou_valor: str
    prazo_prestacao: str
    citacao: str
