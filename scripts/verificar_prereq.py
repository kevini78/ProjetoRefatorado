"""
Script de Verificação de Pré-requisitos
========================================

Verifica se todos os requisitos estão atendidos antes de executar os testes.

Uso:
    python scripts/verificar_prereq.py
"""

import os
import sys
import subprocess


def verificar_python():
    """Verifica versão do Python"""
    print("\n[1/6] Verificando Python...")
    
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"✅ Python {version.major}.{version.minor}.{version.micro} (OK)")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor}.{version.micro} (Requer 3.8+)")
        return False


def verificar_arquivo_env():
    """Verifica se arquivo .env existe"""
    print("\n[2/6] Verificando arquivo .env...")
    
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    
    if os.path.exists(env_path):
        print("✅ Arquivo .env encontrado")
        
        # Verificar variáveis necessárias
        from dotenv import load_dotenv
        load_dotenv(env_path)
        
        vars_necessarias = ['LECOM_USER', 'LECOM_PASSWORD', 'MISTRAL_API_KEY']
        vars_faltando = []
        
        for var in vars_necessarias:
            if not os.getenv(var):
                vars_faltando.append(var)
        
        if vars_faltando:
            print(f"⚠️  Variáveis faltando no .env: {', '.join(vars_faltando)}")
            return False
        else:
            print("✅ Todas as variáveis necessárias estão configuradas")
            return True
    else:
        print("❌ Arquivo .env não encontrado")
        print("   Crie o arquivo .env na raiz do projeto com:")
        print("   LECOM_USER=seu_usuario")
        print("   LECOM_PASSWORD=sua_senha")
        print("   MISTRAL_API_KEY=sua_chave_api")
        return False


def verificar_dependencias():
    """Verifica se dependências estão instaladas"""
    print("\n[3/6] Verificando dependências Python...")
    
    dependencias = [
        'selenium',
        'mistralai',
        'opencv-python',
        'pytesseract',
        'Pillow',
        'pymupdf',
        'openpyxl',
        'pandas',
        'python-dotenv'
    ]
    
    faltando = []
    
    for dep in dependencias:
        try:
            __import__(dep.replace('-', '_'))
            print(f"   ✅ {dep}")
        except ImportError:
            print(f"   ❌ {dep}")
            faltando.append(dep)
    
    if faltando:
        print(f"\n⚠️  Dependências faltando: {len(faltando)}")
        print("   Instale com: pip install " + " ".join(faltando))
        return False
    else:
        print("\n✅ Todas as dependências instaladas")
        return True


def verificar_chrome():
    """Verifica se Chrome/Chromium está instalado"""
    print("\n[4/6] Verificando Chrome/Chromium...")
    
    # Tentar localizar Chrome
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\Application\\chrome.exe")
    ]
    
    chrome_encontrado = False
    for path in chrome_paths:
        if os.path.exists(path):
            print(f"✅ Chrome encontrado: {path}")
            chrome_encontrado = True
            break
    
    if not chrome_encontrado:
        print("⚠️  Chrome não encontrado nos locais padrão")
        print("   Certifique-se de que o Chrome está instalado")
        return False
    
    return True


def verificar_estrutura_projeto():
    """Verifica estrutura de diretórios do projeto"""
    print("\n[5/6] Verificando estrutura do projeto...")
    
    diretorios_necessarios = [
        'automation',
        'automation/actions',
        'automation/services',
        'automation/repositories',
        'automation/ocr',
        'scripts',
        'uploads'
    ]
    
    root = os.path.dirname(os.path.dirname(__file__))
    
    faltando = []
    for diretorio in diretorios_necessarios:
        path = os.path.join(root, diretorio)
        if os.path.exists(path):
            print(f"   ✅ {diretorio}")
        else:
            print(f"   ❌ {diretorio}")
            faltando.append(diretorio)
    
    if faltando:
        print(f"\n❌ Diretórios faltando: {len(faltando)}")
        return False
    else:
        print("\n✅ Estrutura do projeto OK")
        return True


def verificar_scripts_teste():
    """Verifica se scripts de teste existem"""
    print("\n[6/6] Verificando scripts de teste...")
    
    scripts_necessarios = [
        'test_documentos_especificos.py',
        'run_testes_documentos.py',
        'run_testes.bat'
    ]
    
    scripts_dir = os.path.dirname(__file__)
    
    faltando = []
    for script in scripts_necessarios:
        path = os.path.join(scripts_dir, script)
        if os.path.exists(path):
            print(f"   ✅ {script}")
        else:
            print(f"   ❌ {script}")
            faltando.append(script)
    
    if faltando:
        print(f"\n❌ Scripts faltando: {len(faltando)}")
        return False
    else:
        print("\n✅ Todos os scripts de teste presentes")
        return True


def imprimir_resumo(resultados):
    """Imprime resumo final"""
    print("\n" + "="*80)
    print("RESUMO DA VERIFICAÇÃO")
    print("="*80)
    
    total = len(resultados)
    passou = sum(resultados.values())
    
    print(f"\nVerificações realizadas: {total}")
    print(f"Verificações OK: {passou}")
    print(f"Verificações falhas: {total - passou}")
    
    if passou == total:
        print("\n" + "="*80)
        print("✅ TODOS OS PRÉ-REQUISITOS ATENDIDOS")
        print("="*80)
        print("\nVocê pode executar os testes com:")
        print("  - scripts\\run_testes.bat")
        print("  - python scripts/test_documentos_especificos.py")
        print("\n")
        return True
    else:
        print("\n" + "="*80)
        print("❌ ALGUNS PRÉ-REQUISITOS NÃO FORAM ATENDIDOS")
        print("="*80)
        print("\nCorrija os problemas acima antes de executar os testes.")
        print("\n")
        return False


def main():
    """Função principal"""
    print("="*80)
    print("VERIFICAÇÃO DE PRÉ-REQUISITOS - TESTES DE DOCUMENTOS")
    print("="*80)
    print("\nVerificando se o ambiente está pronto para executar os testes...")
    
    resultados = {
        'python': verificar_python(),
        'env': verificar_arquivo_env(),
        'dependencias': verificar_dependencias(),
        'chrome': verificar_chrome(),
        'estrutura': verificar_estrutura_projeto(),
        'scripts': verificar_scripts_teste()
    }
    
    sucesso = imprimir_resumo(resultados)
    
    return 0 if sucesso else 1


if __name__ == '__main__':
    sys.exit(main())
