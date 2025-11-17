"""
LoteProcessor (Automação)
Orquestra o fluxo "Naturalizar-se - Aprovação em Lote" reutilizando a arquitetura em camadas.
"""

import logging

from automation.actions.lecom_lote_action import LecomLoteAction
from automation.repositories.lote_repository import LoteRepository
from automation.services.lote_service import LoteService

logger = logging.getLogger(__name__)


class LoteProcessor:
    """Processor que coordena Action, Repository e Service para Aprovação em Lote."""

    def __init__(self, driver):
        self.lecom = LecomLoteAction(driver)
        self.repo = LoteRepository(driver)
        self.service = LoteService()

    def executar(self) -> bool:
        """Executa um ciclo completo de aprovação em lote.

        Retorna True se pelo menos um processo foi atualizado com sucesso.
        """
        try:
            logger.info(
                "[EXEC] Iniciando Processor de Aprovação em Lote (arquitetura modular)..."
            )

            # 1. Login (apenas se necessário)
            if not self.lecom.fazer_login():
                return False

            # 2. Ir para workspace
            if not self.lecom.navegar_para_workspace():
                return False

            # 3. Abrir menu > Aprovação em Lote
            if not self.lecom.clicar_menu_abrir():
                return False
            if not self.lecom.clicar_aprovacao_lote():
                return False

            # 4. Entrar na tela interna (iframe form-web)
            if not self.lecom.abrir_formulario_lote():
                return False

            # 5. Selecionar etapa "Aprovação do Conteúdo"
            if not self.lecom.selecionar_etapa_aprovacao_conteudo():
                return False

            total_processados = 0

            # 6. Processar página 1
            logger.info("[INFO] Processando página 1 da tabela de lote...")
            processados_p1 = self._processar_tabela_atual()
            if processados_p1 == 0:
                logger.warning("[AVISO] Nenhum processo processado na página 1")
            total_processados += processados_p1

            # 7. Tentar navegar para página 2 e processar (mantém comportamento atual)
            if self.lecom.navegar_para_pagina_2():
                logger.info("[INFO] Processando página 2 da tabela de lote...")
                processados_p2 = self._processar_tabela_atual()
                if processados_p2 == 0:
                    logger.warning("[AVISO] Nenhum processo processado na página 2")
                total_processados += processados_p2

            # 8. Finalizar clicando em "Avançar" (se houve pelo menos tentativa)
            if total_processados > 0:
                if not self.lecom.clicar_avancar():
                    return False

            # 9. Voltar para workspace para nova iteração
            if not self.lecom.navegar_para_workspace():
                return False

            logger.info(
                f"[OK] Processor de Aprovação em Lote concluído - "
                f"{total_processados} processos processados."
            )
            return total_processados > 0

        except Exception as e:
            logger.error(f"[ERRO] Erro durante execução do LoteProcessor: {str(e)}")
            return False

    # ===================== MÉTODOS AUXILIARES =====================
    def _processar_tabela_atual(self) -> int:
        """Processa todos os processos da tabela atualmente exibida."""
        try:
            linhas = self.repo.listar_linhas_tabela()
            if not linhas:
                logger.info("[INFO] Nenhuma linha encontrada na tabela atual")
                return 0

            processos_processados = 0
            for idx, linha in enumerate(linhas, start=1):
                logger.info(f"[PROC] Processando linha {idx}/{len(linhas)}...")
                if self._processar_linha(linha):
                    processos_processados += 1
            logger.info(
                f"[OK] Página processada: {processos_processados}/{len(linhas)} "
                f"processos atualizados"
            )
            return processos_processados
        except Exception as e:
            logger.error(f"[ERRO] Erro ao processar tabela atual: {str(e)}")
            return 0

    def _processar_linha(self, linha) -> bool:
        """Processa um processo individual da tabela (1 linha)."""
        try:
            dados = self.repo.extrair_dados_linha(linha) or {}
            numero_processo = dados.get("numero_processo") or "DESCONHECIDO"
            analise_mj = dados.get("analise_mj") or ""

            logger.info(
                f"Processando processo {numero_processo} com análise MJ: {analise_mj}"
            )

            decisao = self.service.determinar_decisao(analise_mj)
            if not decisao:
                logger.warning(
                    f"Não foi possível determinar decisão para análise MJ: {analise_mj}"
                )
                return False

            if not self.lecom.abrir_edicao_processo(linha):
                logger.error(f"Falha ao abrir edição para o processo {numero_processo}")
                return False

            if not self.lecom.selecionar_decisao(decisao):
                logger.error(f"Falha ao selecionar decisão para processo {numero_processo}")
                return False

            if not self.lecom.clicar_atualizar():
                logger.error(f"Falha ao atualizar processo {numero_processo}")
                return False

            logger.info(
                f"[OK] Processo {numero_processo} atualizado com decisão: {decisao}"
            )
            return True
        except Exception as e:
            logger.error(f"Erro ao processar linha da tabela: {str(e)}")
            return False
