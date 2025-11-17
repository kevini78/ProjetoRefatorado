"""
LoteService (Automação)
Regras de negócio para mapear a análise do MJ em uma decisão do aprovador em lote.
"""

import logging

logger = logging.getLogger(__name__)


class LoteService:
    """Service com regras de decisão para aprovação em lote."""

    def determinar_decisao(self, analise_mj: str | None) -> str | None:
        """Mapeia o texto de análise do MJ para a decisão a ser escolhida no formulário.

        Mantém a lógica original do método AprovacaoLote.determinar_decisao.
        """
        if not analise_mj:
            return None

        texto = analise_mj.lower().strip()

        if "propor deferimento" in texto:
            return "Aprovo o parecer pelo Deferimento"
        if "propor indeferimento" in texto:
            return "Aprovo o parecer pelo Indeferimento"
        if "propor arquivamento" in texto:
            return (
                "Não aprovo o parecer pelo Deferimento e Arquivo (Fundamentação a seguir)"
            )

        logger.warning(f"[AVISO] Análise MJ não reconhecida: {analise_mj}")
        return None
