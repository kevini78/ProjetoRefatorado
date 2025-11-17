"""\
Camada Action para Naturalização Definitiva

Fornece uma interface de "lecom_instance" compatível com o módulo
`Definitiva/analise_processos.py`, reutilizando a nova navegação
(LecomAction) e o novo pipeline de download/OCR (DocumentAction).

A ideia é a mesma da refatoração da Ordinária: separar responsabilidades
em Action/Service/Processor, mas mantendo 100% da lógica de análise
em `Definitiva/analise_processos.py`.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import os
import sys

from selenium.webdriver.support.ui import WebDriverWait  # apenas para type hints

# Garantir que os módulos legados estejam no path (padrão usado na Ordinária)
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from automation.actions.lecom_ordinaria_action import LecomAction
from automation.actions.document_ordinaria_action import DocumentAction
from automation.repositories.ordinaria_repository import OrdinariaRepository


class DefinitivaAction:
    """Wrapper que expõe a interface esperada por `analisar_processo_definitiva`.

    Este objeto é passado como `lecom_instance` para o módulo em
    `Definitiva/analise_processos.py`. Ele precisa oferecer, no mínimo:

    - `.driver` (Selenium WebDriver)
    - `.documentos_para_baixar` (lista de documentos)
    - `.textos_ja_extraidos` (cache de textos OCR)
    - `.extrair_dados_pessoais_formulario()`
    - `.baixar_documento_e_ocr(nome_documento, max_paginas=None)`

    Internamente ele usa:
    - `LecomAction` para login e navegação
    - `DocumentAction` para download/OCR/validação
    - `OrdinariaRepository` para extrair dados do formulário
    """

    # Conjunto de documentos relevantes para a Definitiva (tipo atual):
    # - Comprovante de tempo de residência
    # - Certidão de antecedentes criminais (Brasil)
    # - Documento oficial de identidade
    #
    # RNM e CPF não são exigidos neste tipo específico, então foram
    # removidos da lista para evitar falsos "NÃO ANEXADO".
    _DOCUMENTOS_PADRAO = [
        "Comprovante de tempo de residência",
        "Certidão de antecedentes criminais (Brasil)",
        "Documento oficial de identidade",
    ]

    def __init__(self, driver: Optional[Any] = None) -> None:
        self._lecom = LecomAction(driver)
        self.driver = self._lecom.driver
        # Apenas para type hints/consistência; não usamos diretamente aqui
        self.wait: WebDriverWait = self._lecom.wait  # type: ignore[assignment]

        self._document_action = DocumentAction(self._lecom.driver, self._lecom.wait)
        self._repository = OrdinariaRepository(self._lecom, self._document_action)

        # Cache simples de textos (compatível com analise_processos)
        self._textos_ja_extraidos: Dict[str, str] = {}

        # Flag usada pelo fluxo de Definitiva (naturalização confirmada via banco)
        self._naturalizacao_confirmada_via_banco: bool = False

        # Propriedades de compatibilidade
        self.ja_logado: bool = False
        self.numero_processo_limpo: Optional[str] = None
        self.data_inicial_processo: Optional[str] = None

    # ------------------------------------------------------------------
    # Propriedades esperadas pelo módulo Definitiva
    # ------------------------------------------------------------------
    @property
    def documentos_para_baixar(self) -> list[str]:
        return list(self._DOCUMENTOS_PADRAO)

    @documentos_para_baixar.setter
    def documentos_para_baixar(self, value: Any) -> None:
        """Setter apenas para compatibilidade; não altera a lista padrão.

        O fluxo de Definitiva costuma fazer `documentos_para_baixar.copy()`,
        então manter a lista padrão aqui é suficiente e evita efeitos colaterais.
        """
        # Aceita a atribuição mas ignora, para evitar inconsistências.
        return None

    @property
    def textos_ja_extraidos(self) -> Dict[str, str]:
        return self._textos_ja_extraidos

    @textos_ja_extraidos.setter
    def textos_ja_extraidos(self, value: Dict[str, str]) -> None:
        self._textos_ja_extraidos = value or {}

    @property
    def naturalizacao_confirmada_via_banco(self) -> bool:
        return self._naturalizacao_confirmada_via_banco

    @naturalizacao_confirmada_via_banco.setter
    def naturalizacao_confirmada_via_banco(self, value: bool) -> None:
        # O módulo Definitiva usa esta flag para decidir se baixa ou não portaria;
        # aqui apenas armazenamos o valor para logs/integrações futuras.
        self._naturalizacao_confirmada_via_banco = bool(value)

    # ------------------------------------------------------------------
    # Métodos de navegação / login
    # ------------------------------------------------------------------
    def login(self) -> bool:
        ok = self._lecom.login()
        self.ja_logado = ok
        return ok

    def navegar_para_processo(self, numero_processo: str) -> Dict[str, Any]:
        """Navega até o processo no LECOM usando o fluxo novo da Ordinária."""
        resultado = self._lecom.navegar_para_processo(numero_processo)
        self.numero_processo_limpo = getattr(self._lecom, "numero_processo_limpo", None)
        self.data_inicial_processo = getattr(self._lecom, "data_inicial_processo", None)
        return resultado

    # ------------------------------------------------------------------
    # Métodos usados diretamente por `analisar_processo_definitiva`
    # ------------------------------------------------------------------
    def extrair_dados_pessoais_formulario(self) -> Dict[str, Any]:
        """Extrai apenas os dados pessoais necessários para a Definitiva.

        Usa o mecanismo robusto do `OrdinariaRepository`, mas filtra o
        dicionário retornado para evitar carregar todos os campos do
        formulário (mantendo compatibilidade com LGPD e com o código
        legado da Definitiva).
        """
        try:
            dados_completos = self._repository.obter_dados_pessoais_formulario() or {}

            # Campos mínimos necessários para a Definitiva hoje
            chaves_interesse = {
                "nome_completo",
                "nome",
                "nome_mae",
                "nome_pai",
                "pai",
                "mae",
                "data_nascimento",
            }

            dados_filtrados: Dict[str, Any] = {}
            for chave in chaves_interesse:
                if chave in dados_completos and dados_completos[chave]:
                    dados_filtrados[chave] = dados_completos[chave]

            # Expor apenas as chaves para debug, sem prints extensos de PII
            print(f"[DefinitivaAction] Dados pessoais extraídos (chaves): {list(dados_filtrados.keys())}")

            return dados_filtrados
        except Exception as e:  # pragma: no cover - defensivo
            print(f"[DefinitivaAction] Erro ao extrair dados pessoais: {e}")
            return {}

    def baixar_documento_e_ocr(self, nome_documento: str, max_paginas: Optional[int] = None) -> str:
        """Baixa um documento específico e retorna o texto OCR.

        Implementado em cima de `DocumentAction.baixar_e_validar_documento_individual`,
        reaproveitando o cache `ultimo_texto_ocr` para obter o texto bruto.

        O parâmetro `max_paginas` é aceito apenas por compatibilidade; o
        controle de páginas é feito internamente pelo `DocumentAction`.
        """
        try:
            # Se já temos texto cacheado, reutilizar
            if nome_documento in self._textos_ja_extraidos:
                return self._textos_ja_extraidos[nome_documento]

            sucesso = self._document_action.baixar_e_validar_documento_individual(nome_documento)
            if not sucesso:
                return ""

            texto = (self._document_action.ultimo_texto_ocr or {}).get(nome_documento, "")
            if texto:
                self._textos_ja_extraidos[nome_documento] = texto
            return texto or ""
        except Exception as e:  # pragma: no cover - defensivo
            print(f"[DefinitivaAction] Erro ao baixar/OCR de '{nome_documento}': {e}")
            return ""

    # ------------------------------------------------------------------
    # Utilidades / compatibilidade
    # ------------------------------------------------------------------
    def navegar_para_iframe_form_app(self) -> bool:
        return self._lecom.navegar_para_iframe_form_app()

    def voltar_do_iframe(self) -> None:
        self._lecom.voltar_do_iframe()

    def fechar(self) -> None:
        """Fecha o driver do navegador."""
        try:
            self._lecom.fechar_driver()
        except Exception:
            pass

    # Alias para compatibilidade com padrões antigos
    close = fechar


__all__ = ["DefinitivaAction"]
