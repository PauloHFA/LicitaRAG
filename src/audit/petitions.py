"""Módulo de geração de minutas administrativas de impugnação e pedidos de esclarecimento.

Atende à necessidade prática dos licitantes de transformar alertas de risco da Lei nº 14.133/2021
e da jurisprudência do TCU em peças jurídicas formais devidamente fundamentadas.
"""

from datetime import datetime

from src.audit.risk_detector import RiskAlert


class PetitionGenerator:
    """Gerador automatizado de minutas de impugnação administrativa a editais."""

    @staticmethod
    def generate_impugnacao(
        edital_numero: str,
        orgao: str,
        alerts: list[RiskAlert],
        razao_social: str = "[NOME DA EMPRESA LICITANTE]",
        cnpj: str = "[00.000.000/0001-00]",
    ) -> str:
        """Gera a minuta de impugnação administrativa fundamentada com base nos alertas detectados."""
        if not alerts:
            return (
                "### Minuta de Impugnação Administrativa\n\n"
                "*Nenhum apontamento de inconformidade ou risco foi identificado pelo sistema para fundamentar uma impugnação ao presente edital.*"
            )

        data_hoje = datetime.now().strftime("%d/%m/%Y")

        fundamentos_textos: list[str] = []
        pedidos_itens: list[str] = []

        for idx, alert in enumerate(alerts, start=1):
            item_edital = alert.item_edital or "Cláusula aplicável"
            fundamento = f"""### 2.{idx}. Do(a) {alert.tipo} (Item {item_edital} do Edital)

O instrumento convocatório estabelece em seu **Item {item_edital}** determinação que carece de revisão e alinhamento com a legislação vigente, conforme detalhado a seguir:

> *"{alert.descricao}"*

**Do Direito Aplicável:**
A referida disposição viola frontalmente o mandamento inserto no **{alert.referencia_legal}**, que visa preservar a ampla competitividade, a proporcionalidade e a obtenção da proposta mais vantajosa para a Administração Pública.

A imposição de exigência desproporcional ou em prazo inferior ao preceito legal restringe indevidamente o universo de potenciais proponentes, contrariando o princípio da legalidade estrita e da isonomia, basilares da Nova Lei de Licitações (Lei nº 14.133/2021)."""
            fundamentos_textos.append(fundamento)

            pedidos_itens.append(
                f"- A imediata **retificação do Item {item_edital} do Edital**, adequando a exigência de {alert.tipo.lower()} aos parâmetros exatos do {alert.referencia_legal};"
            )

        pedidos_str = "\n".join(pedidos_itens)
        fundamentos_str = "\n\n".join(fundamentos_textos)

        minuta = f"""# ILUSTRÍSSIMO(A) SENHOR(A) AGENTE DE CONTRATAÇÃO / PREGOEIRO(A)
**ÓRGÃO:** {orgao}
**EDITAL:** {edital_numero}

---

**{razao_social}**, pessoa jurídica de direito privado, inscrita no CNPJ sob o nº **{cnpj}**, com sede em seu endereço comercial, por meio de seu representante legal adiante assinado, vem, tempestivamente e com o devido respeito perante Vossa Senhoria, com fulcro no **Artigo 164 da Lei Federal nº 14.133/2021**, interpor a presente:

## IMPUGNAÇÃO AO EDITAL

em face das disposições do edital do certame epigrafado, consoante as razões fáticas e jurídicas que passa a expor:

---

## 1. DA TEMPESTIVIDADE E LEGITIMIDADE ATIVA

O Art. 164 da Lei Federal nº 14.133/2021 assegura que *“qualquer pessoa é parte legítima para impugnar edital de licitação por irregularidade na aplicação desta Lei ou para solicitar esclarecimento sobre os seus termos, devendo protocolar o pedido até 3 (três) dias úteis antes da data de abertura do certame”*.

Tendo a presente petição sido protocolada no interstício legalmente assegurado, resta demonstrada a sua inconteste tempestividade e a plena legitimidade da Impugnante para pugnar pela legalidade do procedimento.

---

## 2. DOS FATOS E DOS FUNDAMENTOS JURÍDICOS

{fundamentos_str}

---

## 3. DOS PEDIDOS

Ante todo o exposto, demonstrada a incompatibilidade de itens do edital com a Nova Lei de Licitações e a jurisprudência dominante, requer-se a Vossa Senhoria:

1. O **recebimento, processamento e total acolhimento** da presente Impugnação;
{pedidos_str}
3. A consequente **reabertura dos prazos para envio de propostas**, nos termos do **Art. 55, § 1º da Lei nº 14.133/2021**, caso a alteração do instrumento convocatório afete a formulação das propostas de preços;
4. A devida publicidade da decisão motivada a todos os interessados no certame.

Termos em que,
Pede e espera deferimento.

Local e Data: {data_hoje}.

___________________________________________________
**{razao_social}**
CNPJ: {cnpj}
Representante Legal
"""
        return minuta.strip()
