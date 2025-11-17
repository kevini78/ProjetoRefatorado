"""Camada Service - Regras de negócio para naturalização definitiva (modular).

Esta versão não depende mais da pasta ``Definitiva``. Toda a lógica de
análise é consumida via módulos em ``automation.services``:

- ``definitiva_pipeline.analisar_processo_definitiva``
- ``definitiva_elegibilidade_simples.AnalisadorElegibilidadeSimples``
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from automation.actions.definitiva_action import DefinitivaAction
from .definitiva_pipeline import analisar_processo_definitiva as _analisar_processo_definitiva
from .definitiva_elegibilidade_simples import AnalisadorElegibilidadeSimples


class DefinitivaService:
    """Service responsável por orquestrar a análise da Definitiva.

    A responsabilidade principal aqui é encapsular a chamada ao
    pipeline legado (`analisar_processo_definitiva`) e oferecer um
    ponto único para futuras extensões (ex.: geração de planilha).
    """

    def __init__(self, lecom_action: DefinitivaAction) -> None:
        self.lecom_action = lecom_action

    def analisar_processo(self, codigo_processo: str, timeout_global_minutos: Optional[int] = None) -> Dict[str, Any]:
        """Executa o fluxo completo de análise da Definitiva.

        A lógica é implementada no pipeline modular
        ``automation.services.definitiva_pipeline``.
        """
        return _analisar_processo_definitiva(
            self.lecom_action,
            codigo_processo,
            timeout_global_minutos,
        )

    def analisar_documentos(self, documentos: Dict[str, str], dados_formulario: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Atalho para análise isolada de documentos (sem navegação Selenium).

        Útil para testes unitários ou cenários em que os textos já
        foram extraídos previamente.
        """
        analisador = AnalisadorElegibilidadeSimples()
        return analisador.analisar_elegibilidade(documentos, dados_formulario)


__all__ = ["DefinitivaService"]
