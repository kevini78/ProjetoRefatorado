"""
Script de execução automatizada de testes de documentos
========================================================

Este script executa testes automatizados para validação de documentos específicos
em múltiplos processos de teste, gerando relatórios detalhados.

Uso:
    python run_testes_documentos.py                    # Usa processo padrão (743961)
    python run_testes_documentos.py 743961 784408     # Testa múltiplos processos
"""

import sys
import os
import json
from datetime import datetime

# Garantir que a raiz do projeto esteja no sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from test_documentos_especificos import TestadorDocumentosEspecificos


def gerar_relatorio_json(testador: TestadorDocumentosEspecificos, caminho_arquivo: str):
    """
    Gera relatório JSON com os resultados dos testes
    
    Args:
        testador: Instância do testador com resultados
        caminho_arquivo: Caminho do arquivo JSON a ser gerado
    """
    print(f"\n[RELATÓRIO] Gerando relatório JSON: {caminho_arquivo}")
    
    relatorio = {
        'data_execucao': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_processos': len(testador.resultados_testes),
        'processos': []
    }
    
    for resultado in testador.resultados_testes:
        processo_info = {
            'numero_processo': resultado['numero_processo'],
            'total_documentos': resultado['total_documentos'],
            'documentos_sucesso': resultado['documentos_sucesso'],
            'documentos_falha': resultado['documentos_falha'],
            'documentos_erro': resultado['documentos_erro'],
            'percentual_sucesso': (resultado['documentos_sucesso'] / resultado['total_documentos'] * 100) if resultado['total_documentos'] > 0 else 0,
            'tempo_total_segundos': resultado['tempo_total_segundos'],
            'documentos': []
        }
        
        for doc in resultado['resultados_documentos']:
            doc_info = {
                'nome': doc['documento'],
                'download_sucesso': doc['download_sucesso'],
                'ocr_executado': doc['ocr_executado'],
                'validacao_sucesso': doc['validacao_sucesso'],
                'texto_extraido_tamanho': doc['texto_extraido_tamanho'],
                'erros': doc['erros'],
                'tempo_segundos': doc['tempo_total_segundos']
            }
            processo_info['documentos'].append(doc_info)
        
        relatorio['processos'].append(processo_info)
    
    # Adicionar estatísticas globais
    total_docs = sum(r['total_documentos'] for r in testador.resultados_testes)
    total_sucesso = sum(r['documentos_sucesso'] for r in testador.resultados_testes)
    total_falha = sum(r['documentos_falha'] for r in testador.resultados_testes)
    total_erro = sum(r['documentos_erro'] for r in testador.resultados_testes)
    
    relatorio['estatisticas_globais'] = {
        'total_documentos_testados': total_docs,
        'total_sucessos': total_sucesso,
        'total_falhas': total_falha,
        'total_erros': total_erro,
        'percentual_sucesso_geral': (total_sucesso / total_docs * 100) if total_docs > 0 else 0
    }
    
    # Salvar arquivo
    with open(caminho_arquivo, 'w', encoding='utf-8') as f:
        json.dump(relatorio, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Relatório JSON gerado: {caminho_arquivo}")


def gerar_relatorio_markdown(testador: TestadorDocumentosEspecificos, caminho_arquivo: str):
    """
    Gera relatório Markdown com os resultados dos testes
    
    Args:
        testador: Instância do testador com resultados
        caminho_arquivo: Caminho do arquivo Markdown a ser gerado
    """
    print(f"\n[RELATÓRIO] Gerando relatório Markdown: {caminho_arquivo}")
    
    with open(caminho_arquivo, 'w', encoding='utf-8') as f:
        # Cabeçalho
        f.write("# Relatório de Testes de Documentos Específicos\n\n")
        f.write(f"**Data de Execução:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n")
        
        # Estatísticas gerais
        total_docs = sum(r['total_documentos'] for r in testador.resultados_testes)
        total_sucesso = sum(r['documentos_sucesso'] for r in testador.resultados_testes)
        total_falha = sum(r['documentos_falha'] for r in testador.resultados_testes)
        total_erro = sum(r['documentos_erro'] for r in testador.resultados_testes)
        
        f.write("## Estatísticas Gerais\n\n")
        f.write(f"- **Processos Testados:** {len(testador.resultados_testes)}\n")
        f.write(f"- **Total de Documentos:** {total_docs}\n")
        f.write(f"- **Sucessos:** {total_sucesso} ({total_sucesso/total_docs*100:.1f}%)\n")
        f.write(f"- **Falhas:** {total_falha} ({total_falha/total_docs*100:.1f}%)\n")
        f.write(f"- **Erros:** {total_erro} ({total_erro/total_docs*100:.1f}%)\n\n")
        
        # Status geral
        if total_sucesso == total_docs:
            f.write("### ✅ Status: TODOS OS TESTES PASSARAM\n\n")
        else:
            f.write("### ⚠️ Status: ALGUNS TESTES FALHARAM\n\n")
        
        # Detalhes por processo
        f.write("## Detalhes por Processo\n\n")
        
        for resultado in testador.resultados_testes:
            f.write(f"### Processo {resultado['numero_processo']}\n\n")
            
            percentual = (resultado['documentos_sucesso'] / resultado['total_documentos'] * 100) if resultado['total_documentos'] > 0 else 0
            f.write(f"- **Documentos Testados:** {resultado['total_documentos']}\n")
            f.write(f"- **Sucessos:** {resultado['documentos_sucesso']} ({percentual:.1f}%)\n")
            f.write(f"- **Falhas:** {resultado['documentos_falha']}\n")
            f.write(f"- **Erros:** {resultado['documentos_erro']}\n")
            f.write(f"- **Tempo Total:** {resultado['tempo_total_segundos']:.2f}s\n\n")
            
            # Tabela de documentos
            f.write("| Documento | Download | OCR | Validação | Tamanho Texto | Tempo |\n")
            f.write("|-----------|----------|-----|-----------|---------------|-------|\n")
            
            for doc in resultado['resultados_documentos']:
                download_icon = "✅" if doc['download_sucesso'] else "❌"
                ocr_icon = "✅" if doc['ocr_executado'] else "❌"
                validacao_icon = "✅" if doc['validacao_sucesso'] else "❌"
                tamanho = f"{doc['texto_extraido_tamanho']} chars" if doc['texto_extraido_tamanho'] > 0 else "-"
                tempo = f"{doc['tempo_total_segundos']:.2f}s"
                
                f.write(f"| {doc['documento']} | {download_icon} | {ocr_icon} | {validacao_icon} | {tamanho} | {tempo} |\n")
            
            f.write("\n")
            
            # Erros encontrados
            erros_processo = []
            for doc in resultado['resultados_documentos']:
                if doc['erros']:
                    erros_processo.extend([(doc['documento'], erro) for erro in doc['erros']])
            
            if erros_processo:
                f.write("#### Erros Encontrados\n\n")
                for doc_nome, erro in erros_processo:
                    f.write(f"- **{doc_nome}:** {erro}\n")
                f.write("\n")
        
        # Documentos testados
        f.write("## Documentos Testados\n\n")
        f.write("Os seguintes documentos foram testados em cada processo:\n\n")
        for i, doc in enumerate(testador.DOCUMENTOS_OBRIGATORIOS, 1):
            f.write(f"{i}. {doc}\n")
        f.write("\n")
        
        # Fluxo de teste
        f.write("## Fluxo de Teste\n\n")
        f.write("Para cada documento, o teste executa as seguintes etapas:\n\n")
        f.write("1. **Download:** Localiza e baixa o documento do processo\n")
        f.write("2. **OCR:** Extrai texto do documento usando Mistral Vision OCR com pré-processamento\n")
        f.write("3. **Validação:** Valida o conteúdo extraído usando termos específicos\n\n")
    
    print(f"✅ Relatório Markdown gerado: {caminho_arquivo}")


def main():
    """Função principal"""
    # Processos de teste (podem ser passados como argumentos)
    processos_teste = sys.argv[1:] if len(sys.argv) > 1 else ['743961']
    
    print("\n" + "="*80)
    print("EXECUTANDO TESTES DE DOCUMENTOS ESPECÍFICOS")
    print("="*80)
    print("\nDocumentos testados:")
    print("  1. Documento do representante legal")
    print("  2. Carteira de Registro Nacional Migratorio")
    print("  3. Comprovante de tempo de residência")
    print("  4. Documento de viagem internacional")
    print("\nProcessos de teste:", ', '.join(processos_teste))
    print("="*80)
    
    # Executar testes
    testador = TestadorDocumentosEspecificos(processos_teste=processos_teste)
    sucesso = testador.executar_testes_completos()
    
    # Gerar relatórios
    if testador.resultados_testes:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Relatório JSON
        caminho_json = os.path.join(ROOT, f'relatorio_testes_documentos_{timestamp}.json')
        gerar_relatorio_json(testador, caminho_json)
        
        # Relatório Markdown
        caminho_md = os.path.join(ROOT, f'relatorio_testes_documentos_{timestamp}.md')
        gerar_relatorio_markdown(testador, caminho_md)
        
        print("\n" + "="*80)
        print("RELATÓRIOS GERADOS")
        print("="*80)
        print(f"JSON: {caminho_json}")
        print(f"Markdown: {caminho_md}")
    
    # Retornar código de saída apropriado
    sys.exit(0 if sucesso else 1)


if __name__ == '__main__':
    main()
