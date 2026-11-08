from dataclasses import dataclass


@dataclass
class LegalArticle:
    """Artigo de referência da legislação de licitações (Lei nº 14.133/2021)."""
    norma: str
    artigo: str
    ementa: str
    texto: str


# Dispositivos fundamentais da Lei nº 14.133/2021 para conformidade de editais
LEGAL_KNOWLEDGE_BASE: list[LegalArticle] = [
    LegalArticle(
        norma="Lei nº 14.133/2021",
        artigo="Art. 55, inciso I, alínea 'a'",
        ementa="Prazos mínimos para apresentação de propostas para aquisição de bens",
        texto=(
            "Art. 55. Os prazos mínimos para apresentação de propostas e lances, contados a partir da data de "
            "divulgação do edital de licitação, são de: I - para a aquisição de bens: a) 8 (oito) dias úteis, quando "
            "adotados os critérios de julgamento de menor preço ou de maior desconto;"
        ),
    ),
    LegalArticle(
        norma="Lei nº 14.133/2021",
        artigo="Art. 55, inciso I, alínea 'b'",
        ementa="Prazos mínimos para apresentação de propostas para serviços e obras comuns",
        texto=(
            "Art. 55. (...) I - para a aquisição de bens: b) 10 (dez) dias úteis, quando adotados os critérios de "
            "julgamento de menor preço ou de maior desconto, no caso de serviços comuns e de obras comuns;"
        ),
    ),
    LegalArticle(
        norma="Lei nº 14.133/2021",
        artigo="Art. 164",
        ementa="Prazo para impugnação ao edital e pedidos de esclarecimento",
        texto=(
            "Art. 164. Qualquer pessoa é parte legítima para impugnar edital de licitação por irregularidade na "
            "aplicação desta Lei ou para solicitar esclarecimento sobre os seus termos, devendo protocolar o "
            "pedido até 3 (três) dias úteis antes da data de abertura do certame."
        ),
    ),
    LegalArticle(
        norma="Lei nº 14.133/2021",
        artigo="Art. 98",
        ementa="Limites da garantia de execução contratual",
        texto=(
            "Art. 98. Nas contratações de obras, serviços e fornecimentos, a garantia poderá ser de até 5% (cinco por cento) "
            "do valor inicial do contrato, autorizada a majoração para até 10% (dez por cento) desde que justificada "
            "mediante a complexidade técnica e os riscos envolvidos."
        ),
    ),
    LegalArticle(
        norma="Lei nº 14.133/2021",
        artigo="Art. 67, § 3º",
        ementa="Limites para exigência de patrimônio líquido ou capital social mínimo",
        texto=(
            "Art. 67. (...) § 3º É vedada a exigência de valores mínimos de faturamento anterior e de índices "
            "de rentabilidade ou de lucratividade para a qualificação econômico-financeira, e a exigência de capital "
            "social ou de patrimônio líquido mínimo não poderá exceder a 10% (dez por cento) do valor estimado da contratação."
        ),
    ),
    LegalArticle(
        norma="Lei nº 14.133/2021",
        artigo="Art. 41, inciso I",
        ementa="Vedação à indicação de marcas ou modelos exclusivos sem ressalva de similaridade",
        texto=(
            "Art. 41. No caso de licitação que envolva o fornecimento de bens, a Administração não poderá indicar marcas, "
            "modelos ou especificações exclusivas, salvo quando fundamentada a necessidade de padronização, sendo sempre "
            "admitida a comprovação de equivalência ou similaridade."
        ),
    ),
    LegalArticle(
        norma="Jurisprudência TCU",
        artigo="Súmula nº 263/TCU",
        ementa="Limite máximo de 50% para quantitativos mínimos em atestados técnicos",
        texto=(
            "Súmula nº 263/TCU. Para a comprovação da capacidade técnico-operacional das licitantes, e desde que limitadas, "
            "simultaneamente, às parcelas de maior relevância e valor significativo do objeto a ser contratado, é legal a "
            "exigência de comprovação da execução de quantitativos mínimos em obras ou serviços similares, não superiores a "
            "50% (cinquenta por cento) dos quantitativos dos itens ou parcelas correspondentes."
        ),
    ),
]


class LegalBaseCatalog:
    """Catálogo de consulta rápida aos dispositivos da Nova Lei de Licitações."""

    def __init__(self) -> None:
        self.articles = {f"{a.norma} - {a.artigo}": a for a in LEGAL_KNOWLEDGE_BASE}

    def get_article(self, artigo_key: str) -> LegalArticle | None:
        return self.articles.get(artigo_key)

    def list_all(self) -> list[LegalArticle]:
        return list(self.articles.values())
