import re

from src.audit.models import CategoriaHabilitacao, ExtractedChecklistItem
from src.chunking.models import ParsedChunk
from src.retrieval.rrf import RankedCandidate

# Padrões léxicos e semânticos associados aos 4 eixos de habilitação da Lei 14.133/2021
PATTERNS_JURIDICA = [
    r"ato\s+constitutivo",
    r"estatuto\s+social",
    r"contrato\s+social",
    r"registro\s+comercial",
    r"junta\s+comercial",
    r"decreto\s+de\s+autoriza[çc][ãa]o",
    r"procura[çc][ãa]o",
]

PATTERNS_FISCAL = [
    r"regularidade\s+fiscal",
    r"receita\s+federal",
    r"fazenda\s+nacional",
    r"fazenda\s+estadual",
    r"fazenda\s+municipal",
    r"fgts",
    r"cndt",
    r"justi[çc]a\s+do\s+trabalho",
    r"débitos\s+trabalhistas",
    r"inss",
    r"dívida\s+ativa",
]

PATTERNS_TECNICA = [
    r"atestado(s)?\s+de\s+capacidade\s+t[ée]cnica",
    r"aptid[ãa]o\s+t[ée]cnica",
    r"conselho\s+regional",
    r"crea",
    r"cau",
    r"cra",
    r"respons[áa]vel\s+t[ée]cnico",
    r"visita\s+t[ée]cnica",
    r"vistoria",
]

PATTERNS_ECONOMICA = [
    r"balan[çc]o\s+patrimonial",
    r"demonstra[çc][õo]es\s+cont[áa]beis",
    r"fal[êe]ncia",
    r"recupera[çc][ãa]o\s+judicial",
    r"[íi]ndice(s)?\s+cont[áa]bei(s)?",
    r"liquidez\s+geral",
    r"liquidez\s+corrente",
    r"solv[êe]ncia\s+geral",
    r"patrim[ôo]nio\s+l[íi]quido",
    r"capital\s+social\s+m[íi]nimo",
]


class ChecklistExtractor:
    """Extrai itens de habilitação divididos nas 4 categorias da Lei nº 14.133/2021 (RF-13, CA-09)."""

    def extract_from_chunks(
        self,
        chunks: list[ParsedChunk | RankedCandidate],
        document_name: str = "Edital",
    ) -> list[ExtractedChecklistItem]:
        """Varre os fragmentos do edital e extrai os itens exigidos com citação obrigatória."""
        checklist_items: list[ExtractedChecklistItem] = []
        seen_descriptions: set[str] = set()

        for chunk in chunks:
            # Considera apenas chunks textuais pertencentes a seções de habilitação ou com termos afins
            texto = chunk.texto.strip()
            texto_lower = texto.lower()

            # Determina qual categoria o trecho contempla
            categoria = self._classify_category(texto_lower, getattr(chunk, "secao", None))
            if not categoria:
                continue

            # Extrai itens/alíneas específicos dentro do chunk
            subitems = self._extract_subitems(texto)
            for sub in subitems:
                clean_sub = self._clean_description(sub)
                if not clean_sub or clean_sub in seen_descriptions:
                    continue

                seen_descriptions.add(clean_sub)
                item_label = chunk.item or "S/N"
                citacao = f"[{document_name}, p. {chunk.pagina}, item {item_label}]"

                checklist_items.append(
                    ExtractedChecklistItem(
                        categoria=categoria.value,
                        descricao=clean_sub,
                        citacao=citacao,
                        obrigatorio=True,
                    )
                )

        return checklist_items

    def _classify_category(
        self,
        text_lower: str,
        section_path: str | None = None,
    ) -> CategoriaHabilitacao | None:
        """Classifica o trecho em uma das 4 categorias canônicas."""
        sec_lower = (section_path or "").lower()

        # Prioriza o título da seção se já contiver a categoria explícita
        if "jurídica" in sec_lower or "juridica" in sec_lower:
            return CategoriaHabilitacao.JURIDICA
        if "fiscal" in sec_lower or "trabalhista" in sec_lower:
            return CategoriaHabilitacao.FISCAL_TRABALHISTA
        if "técnica" in sec_lower or "tecnica" in sec_lower:
            return CategoriaHabilitacao.TECNICA
        if "econôm" in sec_lower or "econom" in sec_lower or "financeira" in sec_lower:
            return CategoriaHabilitacao.ECONOMICA

        # Classificação por pontuação de padrões no corpo do texto
        scores = {
            CategoriaHabilitacao.JURIDICA: sum(bool(re.search(p, text_lower)) for p in PATTERNS_JURIDICA),
            CategoriaHabilitacao.FISCAL_TRABALHISTA: sum(bool(re.search(p, text_lower)) for p in PATTERNS_FISCAL),
            CategoriaHabilitacao.TECNICA: sum(bool(re.search(p, text_lower)) for p in PATTERNS_TECNICA),
            CategoriaHabilitacao.ECONOMICA: sum(bool(re.search(p, text_lower)) for p in PATTERNS_ECONOMICA),
        }

        best_category = max(scores, key=lambda k: scores[k])
        if scores[best_category] > 0:
            return best_category

        return None

    def _extract_subitems(self, text: str) -> list[str]:
        """Divide o chunk em alíneas ou sentenças de exigência."""
        # Se contiver marcadores de alínea (a), b), c) ou traços)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        aliquots: list[str] = []
        current_part: list[str] = []

        for line in lines:
            if re.match(r"^([a-z]\)|\d+\.|\-|\•)\s+", line, re.IGNORECASE):
                if current_part:
                    aliquots.append(" ".join(current_part))
                    current_part = []
            current_part.append(line)

        if current_part:
            aliquots.append(" ".join(current_part))

        return aliquots or [text]

    @staticmethod
    def _clean_description(desc: str) -> str:
        """Remove numerações iniciais desnecessárias e formata em sentença limpa."""
        cleaned = re.sub(r"^([a-z]\)|\d+(?:\.\d+)*\.?|\-|\•)\s+", "", desc, flags=re.IGNORECASE).strip()
        # Limita o comprimento para leitura objetiva no checklist
        if len(cleaned) > 200:
            # Corta na última pontuação antes do limite
            cut = cleaned[:200]
            last_period = cut.rfind(".")
            if last_period > 80:
                cleaned = cut[: last_period + 1]
            else:
                cleaned = cut + "..."
        return cleaned
