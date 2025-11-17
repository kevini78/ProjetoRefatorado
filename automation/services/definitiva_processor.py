"""\
Façade para processamento de naturalização definitiva.

Orquestra o fluxo Selenium (login + navegação) e delega a análise
para o pipeline existente em `Definitiva/analise_processos.py` via
`DefinitivaService`, de forma análoga ao `OrdinariaProcessor`.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from automation.actions.definitiva_action import DefinitivaAction
from .definitiva_service import DefinitivaService


class DefinitivaProcessor:
    """Façade que orquestra o processamento completo da Definitiva."""

    def __init__(self, driver: Optional[Any] = None, timeout_global_minutos: Optional[int] = None) -> None:
        self.lecom_action = DefinitivaAction(driver)
        self.service = DefinitivaService(self.lecom_action)
        self._timeout_default = timeout_global_minutos

    def processar_processo(self, codigo_processo: str, timeout_global_minutos: Optional[int] = None) -> Dict[str, Any]:
        """Processa um processo de naturalização definitiva.

        Preserva a lógica existente de `analisar_processo_definitiva`,
        apenas centralizando login/navegação aqui.
        """
        # Login se necessário
        if not getattr(self.lecom_action, "ja_logado", False):
            print("[DefinitivaProcessor] Realizando login no LECOM...")
            if not self.lecom_action.login():
                return {
                    "status": "Erro",
                    "erro": "Falha no login no LECOM (Definitiva)",
                    "codigo": codigo_processo,
                }

        # Navegação para o processo (usa fluxo novo da Ordinária)
        print(f"[DefinitivaProcessor] Navegando para processo {codigo_processo}...")
        nav_result = self.lecom_action.navegar_para_processo(codigo_processo)
        if isinstance(nav_result, dict) and nav_result.get("status") == "erro":
            return {
                "status": "Erro",
                "erro": f"Erro na navegação: {nav_result.get('mensagem')}",
                "codigo": codigo_processo,
            }

        effective_timeout = timeout_global_minutos
        if effective_timeout is None:
            effective_timeout = self._timeout_default

        # Chama o pipeline legado via service
        resultado = self.service.analisar_processo(codigo_processo, timeout_global_minutos=effective_timeout)

        # Garantir identificadores mínimos no resultado
        resultado.setdefault("codigo", codigo_processo)
        resultado.setdefault("numero_processo", codigo_processo)
        return resultado

    def fechar(self) -> None:
        """Libera recursos (fecha navegador)."""
        self.lecom_action.fechar()

    # Suporte a context manager
    def __enter__(self) -> "DefinitivaProcessor":  # type: ignore[name-defined]
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.fechar()


def processar_processo_definitiva(
    codigo_processo: str,
    driver: Optional[Any] = None,
    timeout_global_minutos: Optional[int] = None,
) -> Dict[str, Any]:
    """Função de conveniência para compatibilidade.

    Exemplo:

        from automation.services.definitiva_processor import processar_processo_definitiva
        resultado = processar_processo_definitiva("12345678901234567890")
    """
    with DefinitivaProcessor(driver=driver, timeout_global_minutos=timeout_global_minutos) as proc:
        return proc.processar_processo(codigo_processo, timeout_global_minutos=timeout_global_minutos)
