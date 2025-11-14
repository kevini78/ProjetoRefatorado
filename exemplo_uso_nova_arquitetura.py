"""
Exemplo de uso da nova arquitetura refatorada
Demonstra como usar as camadas Service/Repository/Action
"""

from app.services.ordinaria_processor import OrdinariaProcessor, processar_processo_ordinaria
from app.adapters.navegacao_ordinaria_adapter import NavegacaoOrdinaria


def exemplo_uso_direto():
    """
    Exemplo usando diretamente o OrdinariaProcessor
    """
    print("=== EXEMPLO: Uso direto do OrdinariaProcessor ===")
    
    # Usar context manager para garantir limpeza de recursos
    with OrdinariaProcessor() as processor:
        # Processar um processo
        numero_processo = "12345678901234567890"
        resultado = processor.processar_processo(numero_processo)
        
        if resultado.get('sucesso'):
            print(f"✅ Processo {numero_processo} processado com sucesso!")
            print(f"Status: {resultado.get('status')}")
            print(f"Elegibilidade: {resultado.get('elegibilidade_final')}")
        else:
            print(f"❌ Erro no processamento: {resultado.get('erro')}")


def exemplo_uso_funcao_conveniencia():
    """
    Exemplo usando função de conveniência
    """
    print("\n=== EXEMPLO: Uso da função de conveniência ===")
    
    numero_processo = "12345678901234567890"
    resultado = processar_processo_ordinaria(numero_processo)
    
    if resultado.get('sucesso'):
        print(f"✅ Processo {numero_processo} processado com sucesso!")
        print(f"Status: {resultado.get('status')}")
    else:
        print(f"❌ Erro no processamento: {resultado.get('erro')}")


def exemplo_uso_adaptador_compatibilidade():
    """
    Exemplo usando o adaptador para compatibilidade com código existente
    """
    print("\n=== EXEMPLO: Uso do adaptador (compatibilidade) ===")
    
    # Usar o adaptador que mantém a interface original
    with NavegacaoOrdinaria() as nav:
        # Login
        if nav.login():
            print("✅ Login realizado")
            
            # Processar processo (interface compatível)
            numero_processo = "12345678901234567890"
            resultado = nav.processar_processo(numero_processo)
            
            if resultado.get('sucesso'):
                print(f"✅ Processo {numero_processo} processado!")
                print(f"Dados pessoais extraídos: {len(nav.dados_pessoais_extraidos)} campos")
            else:
                print(f"❌ Erro: {resultado.get('erro')}")
        else:
            print("❌ Falha no login")


def exemplo_uso_camadas_separadas():
    """
    Exemplo usando as camadas separadamente (uso avançado)
    """
    print("\n=== EXEMPLO: Uso das camadas separadamente ===")
    
    from app.actions.lecom_action import LecomAction
    from app.actions.document_action import DocumentAction
    from app.repositories.ordinaria_repository import OrdinariaRepository
    from app.services.ordinaria_service import OrdinariaService
    
    # Inicializar camadas
    lecom_action = LecomAction()
    document_action = DocumentAction(lecom_action.driver, lecom_action.wait)
    repository = OrdinariaRepository(lecom_action, document_action)
    service = OrdinariaService(lecom_action, document_action, repository)
    
    try:
        # Login
        if lecom_action.login():
            print("✅ Login realizado")
            
            # Navegar para processo
            numero_processo = "12345678901234567890"
            resultado_nav = lecom_action.navegar_para_processo(numero_processo)
            
            if resultado_nav.get('status') == 'navegacao_concluida':
                print("✅ Navegação concluída")
                
                # Extrair dados
                dados_pessoais = repository.obter_dados_pessoais_formulario()
                documentos_ocr = repository.obter_documentos_processo()
                
                # Análise de elegibilidade
                resultado_elegibilidade = service.analisar_elegibilidade_completa(
                    dados_pessoais, documentos_ocr
                )
                
                # Gerar decisão
                resultado_decisao = service.gerar_decisao_automatica(resultado_elegibilidade)
                
                print(f"✅ Análise concluída: {resultado_elegibilidade.get('elegibilidade_final')}")
                print(f"✅ Decisão: {resultado_decisao.get('tipo_decisao')}")
                
            else:
                print(f"❌ Erro na navegação: {resultado_nav.get('mensagem')}")
        else:
            print("❌ Falha no login")
            
    finally:
        # Limpar recursos
        lecom_action.fechar_driver()


if __name__ == "__main__":
    print("🔄 EXEMPLOS DE USO DA NOVA ARQUITETURA REFATORADA")
    print("=" * 60)
    
    # Executar exemplos
    try:
        exemplo_uso_direto()
        exemplo_uso_funcao_conveniencia()
        exemplo_uso_adaptador_compatibilidade()
        exemplo_uso_camadas_separadas()
        
        print("\n✅ Todos os exemplos executados!")
        
    except Exception as e:
        print(f"\n❌ Erro nos exemplos: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("📋 RESUMO DA NOVA ARQUITETURA:")
    print("• Action: Interações externas (Selenium, OCR, downloads)")
    print("• Repository: Acesso a dados (extrair, salvar, planilhas)")
    print("• Service: Regras de negócio (elegibilidade, decisões)")
    print("• Processor: Façade que orquestra tudo")
    print("• Adapter: Compatibilidade com código existente")
    print("=" * 60)
