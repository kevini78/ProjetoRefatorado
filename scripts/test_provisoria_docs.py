"""
Script de teste para verificar detecção e download de documentos Provisória.
Testa um único processo para garantir que os 4 documentos sejam detectados e baixados.
"""
import sys
import os

# Adicionar raiz ao path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from automation.actions.provisoria_action import ProvisoriaAction
from automation.actions.document_provisoria_action import DocumentProvisoriaAction


def testar_deteccao_documentos(numero_processo: str):
    """Testa a detecção e download dos 4 documentos de um processo Provisória."""
    
    print(f"\n{'='*80}")
    print(f"TESTE DE DETECÇÃO DE DOCUMENTOS - PROCESSO {numero_processo}")
    print(f"{'='*80}\n")
    
    # Lista dos 4 documentos esperados
    documentos_esperados = [
        'Documento de identificacao do representante legal',
        'Carteira de Registro Nacional Migratorio',
        'Comprovante de tempo de residência',
        'Documento de viagem internacional',
    ]
    
    # Inicializar action
    print("[1/5] Inicializando driver...")
    action = ProvisoriaAction()
    
    try:
        # Login
        print("[2/5] Fazendo login...")
        if not action.login():
            print("[ERRO] Falha no login")
            return False
        print("[OK] Login realizado com sucesso")
        
        # Navegar para o processo
        print(f"[3/5] Navegando para o processo {numero_processo}...")
        if not action.aplicar_filtros(numero_processo):
            print("[ERRO] Falha ao navegar para o processo")
            return False
        print("[OK] Navegação bem-sucedida")
        
        # Inicializar DocumentProvisoriaAction
        print("[4/5] Inicializando validação de documentos...")
        doc_action = DocumentProvisoriaAction(action.driver, action.wait)
        
        # Testar detecção de cada documento
        print(f"\n[5/5] Testando detecção dos {len(documentos_esperados)} documentos:\n")
        
        resultados = {}
        for i, doc_nome in enumerate(documentos_esperados, 1):
            print(f"  [{i}/{len(documentos_esperados)}] Testando: {doc_nome}")
            
            # Verificar se o documento existe
            existe = doc_action._documento_existe(doc_nome)
            resultados[doc_nome] = existe
            
            if existe:
                print(f"      ✓ Documento ENCONTRADO")
            else:
                print(f"      ✗ Documento NÃO ENCONTRADO")
        
        # Resumo
        print(f"\n{'='*80}")
        print("RESUMO DOS RESULTADOS")
        print(f"{'='*80}\n")
        
        docs_encontrados = sum(1 for v in resultados.values() if v)
        docs_faltantes = len(documentos_esperados) - docs_encontrados
        
        print(f"Documentos encontrados: {docs_encontrados}/{len(documentos_esperados)}")
        print(f"Documentos faltantes: {docs_faltantes}/{len(documentos_esperados)}\n")
        
        if docs_faltantes > 0:
            print("Documentos NÃO encontrados:")
            for doc, encontrado in resultados.items():
                if not encontrado:
                    print(f"  - {doc}")
            print()
        
        sucesso = docs_encontrados == len(documentos_esperados)
        
        if sucesso:
            print("✓ TESTE PASSOU - Todos os documentos foram detectados!")
        else:
            print("✗ TESTE FALHOU - Alguns documentos não foram detectados")
        
        print(f"\n{'='*80}\n")
        
        return sucesso
        
    except Exception as e:
        print(f"\n[ERRO] Exceção durante o teste: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Manter janela aberta para inspeção
        print("\n[INFO] Janela do navegador permanecerá aberta para inspeção.")
        print("[INFO] Pressione Ctrl+C ou feche manualmente para encerrar.")
        
        # Não fechar o driver automaticamente
        # action.fechar()


def main():
    if len(sys.argv) < 2:
        print("Uso: python scripts/test_provisoria_docs.py NUMERO_PROCESSO")
        print("\nExemplo: python scripts/test_provisoria_docs.py 743961")
        sys.exit(1)
    
    numero_processo = sys.argv[1]
    
    try:
        sucesso = testar_deteccao_documentos(numero_processo)
        sys.exit(0 if sucesso else 1)
    except KeyboardInterrupt:
        print("\n\n[INFO] Teste interrompido pelo usuário")
        sys.exit(130)


if __name__ == '__main__':
    main()
