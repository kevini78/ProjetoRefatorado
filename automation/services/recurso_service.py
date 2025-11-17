"""
RecursoService (Automação)
Regras de negócio para mapear o valor de DNNR_DEC em uma decisão clicável.
"""

class RecursoService:
    def decidir_por_dnnr(self, valor_dnnr: str | None) -> str | None:
        if not valor_dnnr:
            return None
        v = valor_dnnr.strip()
        if 'Propor Manutenção do Indeferimento/Arquivamento' in v:
            return 'Nego Provimento'
        if 'Propor Reconsideração' in v:
            return 'Dou Provimento'
        return None
