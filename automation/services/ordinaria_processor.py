"""
Façade para processamento de naturalização ordinária
Orquestra todas as camadas (Action, Repository, Service)
"""

from typing import Dict, Any, Optional
from ..actions.lecom_ordinaria_action import LecomAction
from ..actions.document_ordinaria_action import DocumentAction
from ..repositories.ordinaria_repository import OrdinariaRepository
from .ordinaria_service import OrdinariaService


class OrdinariaProcessor:
    """
    Façade que orquestra o processamento completo de naturalização ordinária
    """
    
    def __init__(self, driver=None):
        """
        Inicializa o processor
        
        Args:
            driver: WebDriver do Selenium (opcional)
        """
        # Inicializar camadas
        self.lecom_action = LecomAction(driver)
        self.document_action = DocumentAction(self.lecom_action.driver, self.lecom_action.wait)
        self.repository = OrdinariaRepository(self.lecom_action, self.document_action)
        self.service = OrdinariaService(self.lecom_action, self.document_action, self.repository)
        
        print("[OK] OrdinariaProcessor inicializado com todas as camadas")
    
    def processar_processo(self, numero_processo: str) -> Dict[str, Any]:
        """
        Processa um processo de naturalização ordinária completo
        
        Args:
            numero_processo: Número do processo a ser processado
            
        Returns:
            Dict com resultado completo do processamento
        """
        print(f"=== INICIANDO PROCESSAMENTO DO PROCESSO {numero_processo} ===")
        
        try:
            # ETAPA 1: Login (se necessário)
            if not self.lecom_action.ja_logado:
                print("\n[ETAPA 1] Realizando login...")
                sucesso_login = self.lecom_action.login()
                if not sucesso_login:
                    return {
                        'numero_processo': numero_processo,
                        'erro': 'Falha no login',
                        'status': 'Erro'
                    }
                print("[OK] Login realizado com sucesso")
            else:
                print("[INFO] Já logado - pulando etapa de login")
            
            # ETAPA 2: Navegar para o processo
            print(f"\n[ETAPA 2] Navegando para processo {numero_processo}...")
            resultado_navegacao = self.lecom_action.navegar_para_processo(numero_processo)
            
            if resultado_navegacao.get('status') == 'erro':
                return {
                    'numero_processo': numero_processo,
                    'erro': f"Erro na navegação: {resultado_navegacao.get('mensagem')}",
                    'status': 'Erro'
                }
            
            print("[OK] Navegação para processo concluída")
            
            # Extrair data inicial do processo do resultado da navegação
            data_inicial_processo = resultado_navegacao.get('data_inicial', '')
            
            # ETAPA 3: Extrair dados pessoais
            print("\n[ETAPA 3] Extraindo dados pessoais...")
            
            # Extrair dados pessoais
            dados_pessoais = self.repository.obter_dados_pessoais_formulario()
            
            if not dados_pessoais:
                return {
                    'numero_processo': numero_processo,
                    'erro': 'Não foi possível extrair dados pessoais',
                    'status': 'Erro'
                }
            
            # Verificar se temos data de nascimento (obrigatória para capacidade civil)
            if not dados_pessoais.get('data_nascimento'):
                return {
                    'numero_processo': numero_processo,
                    'erro': 'Data de nascimento não encontrada no formulário',
                    'status': 'Erro'
                }
            
            print(f"[OK] Dados pessoais extraídos: {len(dados_pessoais)} campos")
            
            # ETAPA 4: Análise de elegibilidade (com downloads integrados)
            print("\n[ETAPA 4] Realizando análise de elegibilidade...")
            resultado_elegibilidade = self.service.analisar_elegibilidade(dados_pessoais, data_inicial_processo, {})
            
            if resultado_elegibilidade.get('elegibilidade_final') == 'erro':
                return {
                    'numero_processo': numero_processo,
                    'erro': resultado_elegibilidade.get('erro'),
                    'status': 'Erro'
                }
            
            print(f"[OK] Análise de elegibilidade concluída: {resultado_elegibilidade.get('elegibilidade_final')}")
            
            # ETAPA 5: Gerar decisão automática
            print("\n[ETAPA 5] Gerando decisão automática...")
            resultado_decisao = self.service.gerar_decisao_automatica(resultado_elegibilidade)
            print(f"[OK] Decisão gerada: {resultado_decisao.get('status', 'ERRO')}")
            
            # ETAPA 6: Gerar resumo executivo
            print("\n[ETAPA 6] Gerando resumo executivo...")
            resumo_executivo = self.service.gerar_resumo_executivo(resultado_elegibilidade, resultado_decisao)
            print("[OK] Resumo executivo gerado")
            
            # ETAPA 7: Salvar dados e gerar planilha
            print("\n[ETAPA 7] Salvando dados e gerando planilha...")
            resultado_planilha = self.service.salvar_dados_e_gerar_planilha(
                numero_processo, dados_pessoais, resultado_elegibilidade, 
                resultado_decisao, resumo_executivo
            )
            print("[OK] Dados salvos e planilha gerada")
            
            # ETAPA 8: Finalizar processamento
            print("\n[ETAPA 8] Finalizando processamento...")
            self.lecom_action.voltar_do_iframe()
            
            # Retornar para workspace para próximo processo
            try:
                self.lecom_action.driver.get('https://justica.servicos.gov.br/workspace/')
                print("[OK] Retornou para workspace")
            except Exception as e:
                print(f"[AVISO] Erro ao retornar para workspace: {e}")
            
            # RESULTADO FINAL
            status_final = 'Deferimento' if resultado_elegibilidade.get('elegibilidade_final') == 'deferimento' else 'Indeferimento'
            
            resultado_final = {
                'numero_processo': numero_processo,
                'dados_pessoais': dados_pessoais,
                'data_inicial_processo': self.lecom_action.data_inicial_processo,
                'resultado_elegibilidade': resultado_elegibilidade,
                'resultado_decisao': resultado_decisao,
                'resumo_executivo': resumo_executivo,
                'status': status_final,
                'elegibilidade_final': resultado_elegibilidade.get('elegibilidade_final'),
                'motivos_indeferimento': resultado_elegibilidade.get('requisitos_nao_atendidos', []),
                'documentos_faltantes': resultado_elegibilidade.get('documentos_faltantes', []),
                'exportado_para_planilha': resultado_planilha.get('sucesso', False),
                'dados_planilha': resultado_planilha.get('dados'),
                'sucesso': True
            }
            
            print(f"\n=== PROCESSAMENTO CONCLUÍDO: {status_final.upper()} ===")
            return resultado_final
            
        except Exception as e:
            print(f"\n[ERRO CRÍTICO] Erro no processamento: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                'numero_processo': numero_processo,
                'erro': f'Erro crítico no processamento: {e}',
                'status': 'Erro',
                'sucesso': False
            }
    
    def fechar(self):
        """Fecha o processor e libera recursos"""
        try:
            self.lecom_action.fechar_driver()
            print("[OK] OrdinariaProcessor fechado")
        except Exception as e:
            print(f"[ERRO] Erro ao fechar processor: {e}")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.fechar()


# Função de conveniência para compatibilidade com código existente
def processar_processo_ordinaria(numero_processo: str, driver=None) -> Dict[str, Any]:
    """
    Função de conveniência para processar um processo de naturalização ordinária
    
    Args:
        numero_processo: Número do processo
        driver: WebDriver do Selenium (opcional)
        
    Returns:
        Dict com resultado do processamento
    """
    with OrdinariaProcessor(driver) as processor:
        return processor.processar_processo(numero_processo)
