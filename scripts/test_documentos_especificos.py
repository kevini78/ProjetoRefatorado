"""
Testes para validação de documentos específicos
================================================

Este script testa o download, OCR e validação dos seguintes documentos:
1. Documento do representante legal
2. Carteira de Registro Nacional Migratorio
3. Comprovante de tempo de residência
4. Documento de viagem internacional

Os testes simulam o mesmo fluxo que ocorre quando uma planilha é enviada na interface web.
"""

import sys
import os
import time
from typing import Dict, Any, List

# Garantir que a raiz do projeto esteja no sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from automation.actions.lecom_ordinaria_action import LecomAction
from automation.actions.document_ordinaria_action import DocumentAction


class TestadorDocumentosEspecificos:
    """Classe para testar download, OCR e validação de documentos específicos"""
    
    # Documentos que devem ser testados
    DOCUMENTOS_OBRIGATORIOS = [
        'Documento de identificação do representante legal',
        'Carteira de Registro Nacional Migratório',
        'Comprovante de tempo de residência',
        'Documento de viagem internacional'
    ]
    
    def __init__(self, processos_teste: List[str] = None):
        """
        Inicializa o testador
        
        Args:
            processos_teste: Lista de números de processos para testar (ex: ['743961', '784408'])
        """
        self.processos_teste = processos_teste or ['743961']
        self.lecom_action = None
        self.document_action = None
        self.resultados_testes = []
        
    def inicializar_acoes(self) -> bool:
        """Inicializa as actions necessárias"""
        try:
            print("\n" + "="*80)
            print("INICIALIZANDO TESTADOR DE DOCUMENTOS ESPECÍFICOS")
            print("="*80)
            
            print("\n[1/2] Inicializando LecomAction...")
            self.lecom_action = LecomAction()
            
            print("[2/2] Inicializando DocumentAction...")
            self.document_action = DocumentAction(
                driver=self.lecom_action.driver,
                wait=self.lecom_action.wait
            )
            
            print("\n✅ Actions inicializadas com sucesso!")
            return True
            
        except Exception as e:
            print(f"\n❌ ERRO ao inicializar actions: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def fazer_login(self) -> bool:
        """Realiza login no sistema"""
        try:
            print("\n" + "="*80)
            print("FAZENDO LOGIN NO SISTEMA")
            print("="*80)
            
            if not self.lecom_action.login():
                print("❌ Login falhou")
                return False
                
            print("✅ Login realizado com sucesso!")
            
            # Navegar para workspace
            try:
                self.lecom_action.driver.get('https://justica.servicos.gov.br/workspace')
                time.sleep(2)
                print("✅ Navegação para workspace concluída")
            except Exception:
                pass
                
            return True
            
        except Exception as e:
            print(f"❌ ERRO no login: {e}")
            return False
    
    def aplicar_filtros_processo(self, numero_processo: str) -> bool:
        """
        Aplica filtros para localizar o processo
        
        Args:
            numero_processo: Número do processo a ser localizado
        """
        try:
            print(f"\n[FILTROS] Aplicando filtros para processo {numero_processo}...")
            
            if not self.lecom_action.aplicar_filtros(numero_processo):
                print(f"❌ Falha ao aplicar filtros para {numero_processo}")
                return False
            
            print(f"✅ Filtros aplicados com sucesso para {numero_processo}")
            
            # Aguardar carregamento
            time.sleep(3)
            
            # Garantir que temos a data inicial do processo
            if hasattr(self.lecom_action, 'data_inicial_processo'):
                print(f"[INFO] Data inicial do processo: {self.lecom_action.data_inicial_processo}")
            else:
                print("[AVISO] Data inicial do processo não encontrada")
            
            return True
            
        except Exception as e:
            print(f"❌ ERRO ao aplicar filtros: {e}")
            return False
    
    def testar_documento_individual(self, nome_documento: str, numero_processo: str) -> Dict[str, Any]:
        """
        Testa download, OCR e validação de um documento específico
        
        Args:
            nome_documento: Nome do documento a ser testado
            numero_processo: Número do processo sendo testado
            
        Returns:
            Dict com resultados do teste
        """
        print("\n" + "="*80)
        print(f"TESTANDO: {nome_documento}")
        print(f"Processo: {numero_processo}")
        print("="*80)
        
        resultado_teste = {
            'documento': nome_documento,
            'processo': numero_processo,
            'download_sucesso': False,
            'ocr_executado': False,
            'validacao_sucesso': False,
            'texto_extraido_tamanho': 0,
            'erros': [],
            'tempo_total_segundos': 0
        }
        
        tempo_inicio = time.time()
        
        try:
            # Executar download, OCR e validação usando o método integrado
            print(f"\n[TESTE] Iniciando teste completo para: {nome_documento}")
            print("[TESTE] Etapas: Download → OCR → Validação")
            
            sucesso = self.document_action.baixar_e_validar_documento_individual(nome_documento)
            
            resultado_teste['download_sucesso'] = sucesso
            resultado_teste['ocr_executado'] = sucesso  # Se passou, OCR foi executado
            resultado_teste['validacao_sucesso'] = sucesso
            
            # Verificar logs de download para mais detalhes
            if hasattr(self.document_action, 'logs_download'):
                logs = self.document_action.logs_download
                
                if nome_documento in logs.get('sucessos', []):
                    print(f"✅ SUCESSO COMPLETO: {nome_documento}")
                    print("   ✅ Download realizado")
                    print("   ✅ OCR executado")
                    print("   ✅ Validação aprovada")
                    
                elif nome_documento in [f.split(':')[0] for f in logs.get('falhas', [])]:
                    falhas = [f for f in logs.get('falhas', []) if nome_documento in f]
                    motivo = falhas[0].split(':', 1)[1].strip() if falhas else 'Motivo desconhecido'
                    print(f"❌ FALHA: {nome_documento}")
                    print(f"   Motivo: {motivo}")
                    resultado_teste['erros'].append(motivo)
                    
                elif nome_documento in [e.split(':')[0] for e in logs.get('erros', [])]:
                    erros = [e for e in logs.get('erros', []) if nome_documento in e]
                    motivo_erro = erros[0].split(':', 1)[1].strip() if erros else 'Erro desconhecido'
                    print(f"❌ ERRO: {nome_documento}")
                    print(f"   Erro: {motivo_erro}")
                    resultado_teste['erros'].append(motivo_erro)
            
            # Tentar recuperar informações do OCR
            if hasattr(self.document_action, 'documentos_ocr'):
                texto_ocr = self.document_action.documentos_ocr.get(nome_documento, '')
                if texto_ocr:
                    resultado_teste['texto_extraido_tamanho'] = len(texto_ocr)
                    print(f"[OCR] Texto extraído: {len(texto_ocr)} caracteres")
                    
                    # Mostrar preview do texto extraído
                    preview = texto_ocr[:200].replace('\n', ' ')
                    print(f"[OCR] Preview: {preview}...")
            
        except Exception as e:
            print(f"❌ ERRO DURANTE TESTE: {e}")
            resultado_teste['erros'].append(str(e))
            import traceback
            traceback.print_exc()
        
        resultado_teste['tempo_total_segundos'] = time.time() - tempo_inicio
        print(f"\n[TEMPO] Teste concluído em {resultado_teste['tempo_total_segundos']:.2f} segundos")
        
        return resultado_teste
    
    def testar_processo_completo(self, numero_processo: str) -> Dict[str, Any]:
        """
        Testa todos os documentos obrigatórios para um processo
        
        Args:
            numero_processo: Número do processo a ser testado
            
        Returns:
            Dict com resultados do teste do processo
        """
        print("\n" + "="*80)
        print(f"TESTANDO PROCESSO: {numero_processo}")
        print("="*80)
        print(f"Documentos a testar: {len(self.DOCUMENTOS_OBRIGATORIOS)}")
        for i, doc in enumerate(self.DOCUMENTOS_OBRIGATORIOS, 1):
            print(f"  {i}. {doc}")
        
        resultado_processo = {
            'numero_processo': numero_processo,
            'total_documentos': len(self.DOCUMENTOS_OBRIGATORIOS),
            'documentos_sucesso': 0,
            'documentos_falha': 0,
            'documentos_erro': 0,
            'resultados_documentos': [],
            'tempo_total_segundos': 0
        }
        
        tempo_inicio = time.time()
        
        # Aplicar filtros para o processo
        if not self.aplicar_filtros_processo(numero_processo):
            print(f"❌ Não foi possível localizar processo {numero_processo}")
            return resultado_processo
        
        # Testar cada documento
        for i, nome_documento in enumerate(self.DOCUMENTOS_OBRIGATORIOS, 1):
            print(f"\n[PROGRESSO] Testando documento {i}/{len(self.DOCUMENTOS_OBRIGATORIOS)}")
            
            resultado_doc = self.testar_documento_individual(nome_documento, numero_processo)
            resultado_processo['resultados_documentos'].append(resultado_doc)
            
            if resultado_doc['validacao_sucesso']:
                resultado_processo['documentos_sucesso'] += 1
            elif resultado_doc['erros']:
                resultado_processo['documentos_erro'] += 1
            else:
                resultado_processo['documentos_falha'] += 1
            
            # Aguardar entre testes para evitar sobrecarga
            if i < len(self.DOCUMENTOS_OBRIGATORIOS):
                print(f"[AGUARDANDO] Pausa de 2 segundos antes do próximo documento...")
                time.sleep(2)
        
        resultado_processo['tempo_total_segundos'] = time.time() - tempo_inicio
        
        # Imprimir resumo do processo
        self._imprimir_resumo_processo(resultado_processo)
        
        return resultado_processo
    
    def _imprimir_resumo_processo(self, resultado: Dict[str, Any]):
        """Imprime resumo dos testes de um processo"""
        print("\n" + "="*80)
        print(f"RESUMO DO PROCESSO: {resultado['numero_processo']}")
        print("="*80)
        print(f"Total de documentos testados: {resultado['total_documentos']}")
        print(f"✅ Sucessos: {resultado['documentos_sucesso']}")
        print(f"❌ Falhas: {resultado['documentos_falha']}")
        print(f"⚠️  Erros: {resultado['documentos_erro']}")
        print(f"⏱️  Tempo total: {resultado['tempo_total_segundos']:.2f} segundos")
        
        # Detalhes por documento
        print("\nDETALHES POR DOCUMENTO:")
        print("-" * 80)
        for resultado_doc in resultado['resultados_documentos']:
            status = "✅" if resultado_doc['validacao_sucesso'] else "❌"
            print(f"{status} {resultado_doc['documento']}")
            print(f"   Download: {'✅' if resultado_doc['download_sucesso'] else '❌'}")
            print(f"   OCR: {'✅' if resultado_doc['ocr_executado'] else '❌'}")
            print(f"   Validação: {'✅' if resultado_doc['validacao_sucesso'] else '❌'}")
            
            if resultado_doc['texto_extraido_tamanho'] > 0:
                print(f"   Texto extraído: {resultado_doc['texto_extraido_tamanho']} caracteres")
            
            if resultado_doc['erros']:
                print(f"   Erros: {', '.join(resultado_doc['erros'])}")
            
            print(f"   Tempo: {resultado_doc['tempo_total_segundos']:.2f}s")
            print()
    
    def executar_testes_completos(self) -> bool:
        """
        Executa todos os testes para os processos configurados
        
        Returns:
            True se todos os testes passaram, False caso contrário
        """
        print("\n" + "="*80)
        print("INICIANDO TESTES DE DOCUMENTOS ESPECÍFICOS")
        print("="*80)
        print(f"Processos a testar: {len(self.processos_teste)}")
        for i, proc in enumerate(self.processos_teste, 1):
            print(f"  {i}. {proc}")
        
        tempo_inicio_total = time.time()
        
        try:
            # Inicializar actions
            if not self.inicializar_acoes():
                return False
            
            # Fazer login
            if not self.fazer_login():
                return False
            
            # Testar cada processo
            todos_sucesso = True
            for i, numero_processo in enumerate(self.processos_teste, 1):
                print(f"\n{'='*80}")
                print(f"PROCESSO {i}/{len(self.processos_teste)}: {numero_processo}")
                print(f"{'='*80}")
                
                resultado_processo = self.testar_processo_completo(numero_processo)
                self.resultados_testes.append(resultado_processo)
                
                # Verificar se todos os documentos passaram
                if resultado_processo['documentos_sucesso'] != resultado_processo['total_documentos']:
                    todos_sucesso = False
                
                # Aguardar entre processos
                if i < len(self.processos_teste):
                    print(f"\n[AGUARDANDO] Pausa de 5 segundos antes do próximo processo...")
                    time.sleep(5)
            
            # Imprimir resumo final
            self._imprimir_resumo_final(tempo_inicio_total)
            
            return todos_sucesso
            
        except Exception as e:
            print(f"\n❌ ERRO DURANTE EXECUÇÃO DOS TESTES: {e}")
            import traceback
            traceback.print_exc()
            return False
            
        finally:
            self._finalizar()
    
    def _imprimir_resumo_final(self, tempo_inicio: float):
        """Imprime resumo final de todos os testes"""
        tempo_total = time.time() - tempo_inicio
        
        print("\n\n" + "="*80)
        print("RESUMO FINAL DE TODOS OS TESTES")
        print("="*80)
        
        total_processos = len(self.resultados_testes)
        total_documentos = sum(r['total_documentos'] for r in self.resultados_testes)
        total_sucessos = sum(r['documentos_sucesso'] for r in self.resultados_testes)
        total_falhas = sum(r['documentos_falha'] for r in self.resultados_testes)
        total_erros = sum(r['documentos_erro'] for r in self.resultados_testes)
        
        print(f"Processos testados: {total_processos}")
        print(f"Total de documentos testados: {total_documentos}")
        print(f"✅ Sucessos: {total_sucessos} ({total_sucessos/total_documentos*100:.1f}%)")
        print(f"❌ Falhas: {total_falhas} ({total_falhas/total_documentos*100:.1f}%)")
        print(f"⚠️  Erros: {total_erros} ({total_erros/total_documentos*100:.1f}%)")
        print(f"⏱️  Tempo total: {tempo_total:.2f} segundos")
        
        # Status final
        if total_sucessos == total_documentos:
            print("\n" + "="*80)
            print("🎉 TODOS OS TESTES PASSARAM COM SUCESSO! 🎉")
            print("="*80)
        else:
            print("\n" + "="*80)
            print("⚠️  ALGUNS TESTES FALHARAM ⚠️")
            print("="*80)
            
            # Listar falhas
            print("\nFALHAS IDENTIFICADAS:")
            for resultado_processo in self.resultados_testes:
                for resultado_doc in resultado_processo['resultados_documentos']:
                    if not resultado_doc['validacao_sucesso']:
                        print(f"  ❌ Processo {resultado_processo['numero_processo']}: {resultado_doc['documento']}")
                        if resultado_doc['erros']:
                            for erro in resultado_doc['erros']:
                                print(f"     → {erro}")
    
    def _finalizar(self):
        """Finaliza o testador e fecha recursos"""
        try:
            print("\n[FINALIZANDO] Fechando recursos...")
            if self.lecom_action:
                self.lecom_action.fechar()
            print("✅ Recursos fechados")
        except Exception as e:
            print(f"[AVISO] Erro ao fechar recursos: {e}")


def main():
    """Função principal"""
    import sys
    
    # Processos de teste (podem ser passados como argumentos)
    processos_teste = sys.argv[1:] if len(sys.argv) > 1 else ['743961']
    
    print("\n" + "="*80)
    print("TESTE DE DOCUMENTOS ESPECÍFICOS")
    print("Documentos testados:")
    print("  1. Documento do representante legal")
    print("  2. Carteira de Registro Nacional Migratorio")
    print("  3. Comprovante de tempo de residência")
    print("  4. Documento de viagem internacional")
    print("="*80)
    
    testador = TestadorDocumentosEspecificos(processos_teste=processos_teste)
    sucesso = testador.executar_testes_completos()
    
    # Retornar código de saída apropriado
    sys.exit(0 if sucesso else 1)


if __name__ == '__main__':
    main()
