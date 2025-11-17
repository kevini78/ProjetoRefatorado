"""
LecomLoteAction (Automação)
Ações de navegação/interação no LECOM para o fluxo
"Naturalizar-se - Aprovação em Lote".
"""

import logging
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException

from automation.adapters.navegacao_ordinaria_adapter import NavegacaoOrdinaria

logger = logging.getLogger(__name__)


class LecomLoteAction:
    """Camada de ações para o fluxo de Aprovação em Lote no LECOM."""

    def __init__(self, driver, wait_timeout: int = 10):
        self.driver = driver
        self.wait = WebDriverWait(self.driver, wait_timeout)
        self.url_workspace = "https://justica.servicos.gov.br/workspace/"
        self.ja_logado = False

        # Adaptador de navegação ordinária (reutiliza login automático existente)
        self.navegacao_ordinaria = NavegacaoOrdinaria(self.driver)

        self.seletores = {
            "menu_abrir": ".menu-top .ant-menu-item",
            "aprovacao_lote": ".container-category",
            "iframe_form_app": "#iframe-form-app",
            "etapa_dropdown": "#ETAPA",
            "etapa_list": "#ETAPA_list",
            "tabela_processos": ".table.striped",
            "botao_editar": ".edit-line-grid",
            "decisao_dropdown": "#NAT_DECISAO",
            "decisao_list": "#NAT_DECISAO_list",
            "botao_atualizar": "#UPDATE",
            "botao_avancar": "#aprovar",
        }

    # ===================== LOGIN & NAVEGAÇÃO PRINCIPAL =====================
    def fazer_login(self) -> bool:
        """Realiza login no sistema usando NavegacaoOrdinaria (compatível com fluxo atual)."""
        try:
            if not self.navegacao_ordinaria:
                logger.error("Módulo de navegação ordinária não inicializado")
                return False

            # Verificar se já está logado e ainda no domínio correto
            if self.ja_logado:
                try:
                    current_url = self.driver.current_url
                except Exception:
                    current_url = ""
                if "justica.servicos.gov.br" in (current_url or ""):
                    logger.info("[OK] Usuário já está logado - pulando processo de login")
                    return True
                logger.warning(
                    "[AVISO] Marcado como logado mas não está no domínio correto - fazendo login novamente"
                )
                self.ja_logado = False

            logger.info("Iniciando processo de login (NavegacaoOrdinaria)...")

            # Executar login (usa LecomAction.login por baixo dos panos)
            self.navegacao_ordinaria.login()
            time.sleep(2)

            try:
                current_url = self.driver.current_url
            except Exception:
                current_url = ""
            logger.info(f"URL atual após login: {current_url}")

            if "workspace" in current_url.lower():
                logger.info("[OK] Login realizado com sucesso - usuário está no workspace")
                self.ja_logado = True
                return True

            if "justica.servicos.gov.br" in current_url:
                logger.info("[OK] Login aparentemente bem-sucedido - está no domínio correto")
                self.ja_logado = True
                return True

            logger.error(f"[ERRO] Falha no login - URL não é do sistema esperado: {current_url}")
            self.ja_logado = False
            return False

        except Exception as e:
            logger.error(f"Erro durante o login: {str(e)}")
            self.ja_logado = False
            return False

    def navegar_para_workspace(self) -> bool:
        """Navega para a página inicial do workspace."""
        try:
            logger.info("Navegando para o workspace...")
            self.driver.get(self.url_workspace)
            time.sleep(2)
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            logger.info("[OK] Navegação para workspace concluída")
            return True
        except Exception as e:
            logger.error(f"Erro ao navegar para workspace: {str(e)}")
            return False

    def clicar_menu_abrir(self) -> bool:
        """Clica no menu 'Abrir'."""
        try:
            logger.info("Procurando menu 'Abrir'...")
            menu_abrir = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, self.seletores["menu_abrir"]))
            )
            if "Abrir" in (menu_abrir.text or ""):
                menu_abrir.click()
                logger.info("[OK] Menu 'Abrir' clicado com sucesso")
                time.sleep(1)
                return True
            logger.warning("Menu encontrado não contém texto 'Abrir'")
            return False
        except Exception as e:
            logger.error(f"Erro ao clicar no menu 'Abrir': {str(e)}")
            return False

    def clicar_aprovacao_lote(self) -> bool:
        """Clica na opção 'Naturalizar-se - Aprovação em Lote'."""
        try:
            logger.info("Procurando opção 'Aprovação em Lote'...")
            time.sleep(2)
            categorias = self.driver.find_elements(By.CSS_SELECTOR, self.seletores["aprovacao_lote"])
            for categoria in categorias:
                try:
                    nome_processo = categoria.find_element(
                        By.CSS_SELECTOR, ".name-process"
                    ).text
                    if "Naturalizar-se - Aprovação em Lote" in (nome_processo or ""):
                        categoria.click()
                        logger.info("[OK] Opção 'Aprovação em Lote' clicada com sucesso")
                        time.sleep(2)
                        return True
                except Exception:
                    continue
            logger.error("Opção 'Aprovação em Lote' não encontrada")
            return False
        except Exception as e:
            logger.error(f"Erro ao clicar em 'Aprovação em Lote': {str(e)}")
            return False

    def abrir_formulario_lote(self) -> bool:
        """Aguarda o iframe da tela de lote e navega para a URL interna (form-web)."""
        try:
            logger.info("Aguardando iframe aparecer...")
            iframe = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#iframe-form-app"))
            )
            iframe_src = iframe.get_attribute("src")
            logger.info(f"URL do iframe encontrada: {iframe_src}")
            if not iframe_src:
                logger.error("[ERRO] iframe-form-app encontrado, mas sem atributo src")
                return False
            self.driver.get(iframe_src)
            logger.info("[OK] Navegação para URL do formulário concluída")
            time.sleep(2)
            return True
        except Exception as e:
            logger.error(f"Erro ao processar iframe: {str(e)}")
            return False

    def selecionar_etapa_aprovacao_conteudo(self) -> bool:
        """Seleciona a etapa 'Aprovação do Conteúdo' no dropdown de etapa."""
        try:
            logger.info("Selecionando etapa 'Aprovação do Conteúdo'...")
            etapa_dropdown = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#ETAPA"))
            )
            etapa_dropdown.click()
            time.sleep(1)

            etapa_list = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#ETAPA_list"))
            )
            opcoes = etapa_list.find_elements(By.CSS_SELECTOR, ".input-autocomplete__option")
            for opcao in opcoes:
                try:
                    span = opcao.find_element(By.TAG_NAME, "span")
                    texto_opcao = span.get_attribute("title") or span.text or ""
                    if "Aprovação do Conteúdo" in texto_opcao:
                        opcao.click()
                        logger.info("[OK] Etapa 'Aprovação do Conteúdo' selecionada")
                        time.sleep(2)
                        return True
                except Exception:
                    continue
            logger.error("Opção 'Aprovação do Conteúdo' não encontrada")
            return False
        except Exception as e:
            logger.error(f"Erro ao selecionar etapa: {str(e)}")
            return False

    # ===================== AÇÕES SOBRE A TABELA =====================
    def abrir_edicao_processo(self, linha) -> bool:
        """Clica no botão de edição de uma linha da tabela."""
        try:
            botao_editar = linha.find_element(By.CSS_SELECTOR, ".edit-line-grid")
            botao_editar.click()
            time.sleep(1)
            return True
        except Exception as e:
            logger.error(f"Erro ao clicar em editar na linha: {str(e)}")
            return False

    def selecionar_decisao(self, decisao: str) -> bool:
        """Seleciona a decisão no dropdown da coluna NAT_DECISAO."""
        try:
            decisao_dropdown = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#NAT_DECISAO"))
            )
            decisao_dropdown.click()
            time.sleep(1)

            decisao_list = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#NAT_DECISAO_list"))
            )
            opcoes = decisao_list.find_elements(By.CSS_SELECTOR, ".input-autocomplete__option")
            for opcao in opcoes:
                try:
                    span = opcao.find_element(By.TAG_NAME, "span")
                    texto_opcao = span.get_attribute("title") or span.text or ""
                    if decisao in texto_opcao:
                        opcao.click()
                        logger.info(f"[OK] Decisão selecionada: {decisao}")
                        time.sleep(1)
                        return True
                except Exception:
                    continue
            logger.error(f"Decisão não encontrada no dropdown: {decisao}")
            return False
        except Exception as e:
            logger.error(f"Erro ao selecionar decisão: {str(e)}")
            return False

    def clicar_atualizar(self) -> bool:
        """Clica no botão 'Atualizar' para salvar a decisão."""
        try:
            botao_atualizar = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#UPDATE"))
            )
            botao_atualizar.click()
            logger.info("[OK] Botão 'Atualizar' clicado")
            time.sleep(2)
            return True
        except Exception as e:
            logger.error(f"Erro ao clicar em 'Atualizar': {str(e)}")
            return False

    def navegar_para_pagina_2(self) -> bool:
        """Navega explicitamente para a página 2 da tabela, se existir."""
        try:
            logger.info("Navegando para página 2...")
            try:
                pagina_2 = self.driver.find_element(By.XPATH, "//a[contains(text(), '2')]")
            except NoSuchElementException:
                logger.info("Página 2 não encontrada - provavelmente só existe uma página")
                return False
            pagina_2.click()
            logger.info("[OK] Navegação para página 2 concluída")
            time.sleep(2)
            return True
        except NoSuchElementException:
            logger.info("Página 2 não encontrada - provavelmente só existe uma página")
            return False
        except Exception as e:
            logger.error(f"Erro ao navegar para página 2: {str(e)}")
            return False

    def clicar_avancar(self) -> bool:
        """Clica no botão 'Avançar' para finalizar o lote."""
        try:
            logger.info("Clicando em 'Avançar' para finalizar...")
            botao_avancar = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#aprovar"))
            )
            botao_avancar.click()
            logger.info("[OK] Botão 'Avançar' clicado - aguardando conclusão...")
            time.sleep(10)
            logger.info("[OK] Processo finalizado após timeout de 10 segundos")
            return True
        except Exception as e:
            logger.error(f"Erro ao clicar em 'Avançar': {str(e)}")
            return False
