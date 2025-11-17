"""
DefereIndefereService (Automação)
Regras para mapear DNNR_DEC em 'Nego Provimento' ou 'Dou Provimento'.
"""

class DefereIndefereService:
    def decidir(self, valor_dnnr: str | None) -> str | None:
        if not valor_dnnr:
            return None
        v = (valor_dnnr or '').strip().lower()
        if any(k in v for k in ['indeferimento', 'arquivamento', 'manutenção']):
            return 'Nego Provimento'
        if any(k in v for k in ['reconsideração', 'reconsidera']):
            return 'Dou Provimento'
        return None
