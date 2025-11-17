"""
Script helper para inspecionar IDs de containers de documentos na Provisória.
Útil para descobrir os IDs corretos quando os documentos não são encontrados.
"""
import sys
import os
import time

# Adicionar raiz ao path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from automation.actions.provisoria_action import ProvisoriaAction
from selenium.webdriver.common.by import By


def inspecionar_containers(numero_processo: str):
    """Inspeciona todos os containers com botões de download no formulário."""
    
    print(f"\n{'='*80}")
    print(f"INSPEÇÃO DE CONTAINERS - PROCESSO {numero_processo}")
    print(f"{'='*80}\n")
    
    # Inicializar action
    print("[1/3] Inicializando driver...")
    action = ProvisoriaAction()
    
    try:
        # Login
        print("[2/3] Fazendo login...")
        if not action.login():
            print("[ERRO] Falha no login")
            return
        print("[OK] Login realizado com sucesso\n")
        
        # Navegar para o processo
        print(f"[3/3] Navegando para o processo {numero_processo}...")
        if not action.aplicar_filtros(numero_processo):
            print("[ERRO] Falha ao navegar para o processo")
            return
        print("[OK] Navegação bem-sucedida\n")
        
        time.sleep(3)  # Aguardar página carregar completamente
        
        # Tentar contexto principal primeiro
        print("="*80)
        print("BUSCANDO CONTAINERS COM BOTÕES DE DOWNLOAD")
        print("="*80 + "\n")
        
        # Voltar ao contexto principal
        try:
            action.driver.switch_to.default_content()
        except:
            pass
        
        # Tentar entrar no iframe se existir
        try:
            iframe = action.driver.find_element(By.ID, 'iframe-form-app')
            action.driver.switch_to.frame(iframe)
            print("[INFO] Contexto: iframe-form-app\n")
        except:
            print("[INFO] Contexto: página principal\n")
        
        # Buscar todos os divs com IDs que começam com "input__"
        try:
            # JavaScript para encontrar todos os elementos com IDs começando com "input__"
            script = """
            var elements = document.querySelectorAll('[id^="input__"]');
            var result = [];
            elements.forEach(function(el) {
                // Verificar se tem botão de download
                var downloadBtn = el.querySelector('i[type="cloud_download"]');
                if (downloadBtn) {
                    // Tentar pegar o label/tooltip
                    var label = el.querySelector('label');
                    var tooltip = el.querySelector('[aria-label]');
                    var text = '';
                    if (label) text = label.textContent || label.innerText;
                    else if (tooltip) text = tooltip.getAttribute('aria-label');
                    
                    result.push({
                        id: el.id,
                        label: text.trim(),
                        hasDownload: true
                    });
                }
            });
            return result;
            """
            
            containers = action.driver.execute_script(script)
            
            if containers:
                print(f"✓ Encontrados {len(containers)} container(s) com botão de download:\n")
                
                for i, container in enumerate(containers, 1):
                    print(f"  [{i}] ID: {container['id']}")
                    if container['label']:
                        print(f"      Label: {container['label']}")
                    print()
                
                print("\n" + "="*80)
                print("MAPEAMENTO SUGERIDO PARA DOCUMENT_ID_MAP")
                print("="*80 + "\n")
                
                for container in containers:
                    label = container['label'] if container['label'] else 'Documento sem label'
                    print(f"'{label}': ['{container['id']}'],")
                
                print("\n" + "="*80)
                
            else:
                print("⚠ Nenhum container com botão de download encontrado.")
                print("\nTentando busca alternativa por IDs conhecidos...\n")
                
                ids_conhecidos = [
                    'input__DOC_RNMREP',
                    'input__DOC_RNM',
                    'input__DOC_COMPRRESID',
                    'input__DOC_RESIDENCIA',
                    'input__DOC_RESID',
                    'input__DOC_VIAGEM',
                    'input__DOC_PASSAPORTE'
                ]
                
                for container_id in ids_conhecidos:
                    try:
                        element = action.driver.find_element(By.ID, container_id)
                        print(f"  ✓ Encontrado: {container_id}")
                        
                        # Verificar se tem botão de download
                        try:
                            download_btn = element.find_element(By.XPATH, ".//i[@type='cloud_download']")
                            print(f"    → TEM botão de download")
                        except:
                            print(f"    → NÃO TEM botão de download")
                    except:
                        print(f"  ✗ Não encontrado: {container_id}")
                
        except Exception as e:
            print(f"\n[ERRO] Erro na inspeção: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n\n[INFO] Inspeção concluída. Janela do navegador permanecerá aberta.")
        print("[INFO] Use DevTools (F12) para inspecionar manualmente os elementos.")
        print("[INFO] Procure por divs com id começando com 'input__DOC_'")
        
        # Aguardar input do usuário
        input("\nPressione ENTER para fechar...")
        
    except Exception as e:
        print(f"\n[ERRO] Exceção durante a inspeção: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        try:
            action.fechar()
        except:
            pass


def main():
    if len(sys.argv) < 2:
        print("Uso: python scripts/inspect_document_ids.py NUMERO_PROCESSO")
        print("\nExemplo: python scripts/inspect_document_ids.py 743961")
        sys.exit(1)
    
    numero_processo = sys.argv[1]
    
    try:
        inspecionar_containers(numero_processo)
    except KeyboardInterrupt:
        print("\n\n[INFO] Inspeção interrompida pelo usuário")
        sys.exit(130)


if __name__ == '__main__':
    main()
