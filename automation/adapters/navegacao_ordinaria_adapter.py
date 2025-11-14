"""
Adaptador para manter compatibilidade com NavegacaoOrdinaria
Permite que módulos existentes continuem funcionando sem alterações
"""

from typing import Dict, Any, Optional
from ..services.ordinaria_processor import OrdinariaProcessor


class NavegacaoOrdinaria:
    """
    Adaptador que mantém a interface da classe NavegacaoOrdinaria original
    mas usa a nova arquitetura internamente
    """
    
    def __init__(self, driver=None):
        """
        Inicializa o adaptador
        
        Args:
            driver: WebDriver do Selenium (opcional)
        """
        self.processor = OrdinariaProcessor(driver)
        self.driver = self.processor.lecom_action.driver
        self.wait = self.processor.lecom_action.wait
        
        # Propriedades para compatibilidade
        self.ja_logado = False
        self.numero_processo_limpo = None
        self.data_inicial_processo = None
        self.dados_pessoais_extraidos = {}
        
        # Resultados dos requisitos (para compatibilidade)
        self.resultado_capacidade_civil = {}
        self.resultado_residencia_minima = {}
        self.resultado_comunicacao = {}
        
        print("[ADAPTADOR] NavegacaoOrdinaria inicializada com nova arquitetura")
    
    def login(self):
        """Realiza login no sistema"""
        sucesso = self.processor.lecom_action.login()
        self.ja_logado = sucesso
        return sucesso
    
    def aplicar_filtros(self, numero_processo: str) -> Dict[str, Any]:
        """
        Navega para um processo específico
        
        Args:
            numero_processo: Número do processo
            
        Returns:
            Dict com resultado da navegação
        """
        resultado = self.processor.lecom_action.navegar_para_processo(numero_processo)
        
        # Atualizar propriedades para compatibilidade
        self.numero_processo_limpo = self.processor.lecom_action.numero_processo_limpo
        self.data_inicial_processo = self.processor.lecom_action.data_inicial_processo
        
        return resultado
    
    def processar_processo(self, numero_processo: str, dados_texto=None) -> Dict[str, Any]:
        """
        Processa um processo completo de naturalização ordinária
        
        Args:
            numero_processo: Número do processo
            dados_texto: Dados de texto (mantido para compatibilidade)
            
        Returns:
            Dict com resultado do processamento
        """
        print(f"[ADAPTADOR] Processando processo {numero_processo} via nova arquitetura")
        
        try:
            # Usar o processor para fazer o processamento completo
            resultado = self.processor.processar_processo(numero_processo)
            
            # Atualizar propriedades para compatibilidade com código existente
            if resultado.get('sucesso'):
                self.dados_pessoais_extraidos = resultado.get('dados_pessoais', {})
                self.data_inicial_processo = resultado.get('data_inicial_processo')
                
                # Extrair resultados dos requisitos se disponíveis
                elegibilidade = resultado.get('resultado_elegibilidade', {})
                self.resultado_capacidade_civil = elegibilidade.get('requisito_i_capacidade_civil', {})
                self.resultado_residencia_minima = elegibilidade.get('requisito_ii_residencia_minima', {})
                self.resultado_comunicacao = elegibilidade.get('requisito_iii_comunicacao_portugues', {})
            
            return resultado
            
        except Exception as e:
            print(f"[ERRO ADAPTADOR] Erro no processamento: {e}")
            return {
                'numero_processo': numero_processo,
                'erro': str(e),
                'status': 'Erro',
                'sucesso': False
            }
    
    def navegar_para_iframe_form_app(self) -> bool:
        """Navega para o iframe do form-app"""
        return self.processor.lecom_action.navegar_para_iframe_form_app()
    
    def voltar_do_iframe(self):
        """Volta do iframe para a janela principal"""
        self.processor.lecom_action.voltar_do_iframe()
    
    def extrair_dados_pessoais_formulario(self) -> Dict[str, Any]:
        """Extrai dados pessoais do formulário"""
        return self.processor.repository.obter_dados_pessoais_formulario()
    
    def baixar_e_validar_documento_individual(self, nome_documento: str) -> bool:
        """Baixa e valida um documento específico"""
        return self.processor.document_action.baixar_e_validar_documento_individual(nome_documento)
    
    def fechar_driver(self):
        """Fecha o driver do navegador"""
        self.processor.fechar()
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.fechar_driver()


# Para compatibilidade total, criar alias
class NavegacaoOrdinariaAdapter(NavegacaoOrdinaria):
    """Alias para NavegacaoOrdinaria para máxima compatibilidade"""
    pass
