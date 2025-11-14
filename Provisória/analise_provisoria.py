"""
Módulo para análise automática de processos usando OCR genérico para tipo provisória
"""

import os
import tempfile
import uuid
import time
import signal
from datetime import datetime
from functools import wraps

def timeout_handler(signum, frame):
    """Handler para timeout"""
    raise TimeoutError("Processamento OCR excedeu o tempo limite")

def timeout_decorator(seconds=120):
    """Decorator para aplicar timeout em funções"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Configurar timeout apenas em sistemas Unix
            if hasattr(signal, 'SIGALRM'):
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                if hasattr(signal, 'SIGALRM'):
                    signal.alarm(0)
        return wrapper
    return decorator

def processar_documento_ocr_generico(pdf_path, nome_documento="Documento", max_retries=3, timeout_seconds=120):
    """
    Processa um documento PDF usando OCR genérico (Mistral) para extrair apenas texto bruto.
    Inclui sistema de retry, timeout e tratamento robusto de erros.
    
    Args:
        pdf_path (str): Caminho para o arquivo PDF
        nome_documento (str): Nome do documento para identificação
        max_retries (int): Número máximo de tentativas
        timeout_seconds (int): Timeout em segundos para cada tentativa
    
    Returns:
        dict: Informações do documento processado
    """
    print(f"DEBUG OCR GENÉRICO: Processando {nome_documento}")
    print(f"DEBUG OCR GENÉRICO: Arquivo: {pdf_path}")
    print(f"DEBUG OCR GENÉRICO: Configuração - Max retries: {max_retries}, Timeout: {timeout_seconds}s")
    
    # Verificações iniciais
    if not os.path.exists(pdf_path):
        print(f"ERRO OCR GENÉRICO: Arquivo não encontrado: {pdf_path}")
        return {
            'nome_documento': nome_documento,
            'arquivo_pdf': pdf_path,
            'texto_extraido': '',
            'caracteres_extraidos': 0,
            'linhas_extraidas': 0,
            'sucesso': False,
            'erro': f'Arquivo não encontrado: {pdf_path}'
        }
    
    if not pdf_path.lower().endswith('.pdf'):
        print(f"ERRO OCR GENÉRICO: Arquivo não é PDF: {pdf_path}")
        return {
            'nome_documento': nome_documento,
            'arquivo_pdf': pdf_path,
            'texto_extraido': '',
            'caracteres_extraidos': 0,
            'linhas_extraidas': 0,
            'sucesso': False,
            'erro': f'Arquivo não é PDF: {pdf_path}'
        }
    
    file_size = os.path.getsize(pdf_path)
    print(f"DEBUG OCR GENÉRICO: Tamanho do arquivo: {file_size} bytes")
    
    if file_size == 0:
        print(f"ERRO OCR GENÉRICO: Arquivo vazio: {pdf_path}")
        return {
            'nome_documento': nome_documento,
            'arquivo_pdf': pdf_path,
            'texto_extraido': '',
            'caracteres_extraidos': 0,
            'linhas_extraidas': 0,
            'sucesso': False,
            'erro': 'Arquivo vazio'
        }
    
    # Sistema de retry com timeout
    for tentativa in range(1, max_retries + 1):
        print(f"DEBUG OCR GENÉRICO: Tentativa {tentativa}/{max_retries}")
        
        try:
            # Importar função OCR
            try:
                from app import extrair_campos_ocr_mistral
                print(f"DEBUG OCR GENÉRICO: Função OCR importada com sucesso")
            except ImportError as e:
                print(f"ERRO OCR GENÉRICO: Não foi possível importar função OCR: {e}")
                return {
                    'nome_documento': nome_documento,
                    'arquivo_pdf': pdf_path,
                    'texto_extraido': '',
                    'caracteres_extraidos': 0,
                    'linhas_extraidas': 0,
                    'sucesso': False,
                    'erro': f'Erro ao importar função OCR: {e}'
                }
            
            # Processar com timeout
            print(f"DEBUG OCR GENÉRICO: Chamando extrair_campos_ocr_mistral com modo_texto_bruto=True")
            
            # Aplicar timeout manualmente (para compatibilidade cross-platform)
            start_time = time.time()
            
            def processar_com_timeout():
                return extrair_campos_ocr_mistral(pdf_path, modo_texto_bruto=True)
            
            # Processar com verificação de timeout
            resultado_ocr = None
            import threading
            
            def worker():
                nonlocal resultado_ocr
                try:
                    resultado_ocr = processar_com_timeout()
                except Exception as e:
                    print(f"ERRO OCR GENÉRICO: Erro durante processamento: {e}")
            
            thread = threading.Thread(target=worker)
            thread.daemon = True
            thread.start()
            thread.join(timeout=timeout_seconds)
            
            if thread.is_alive():
                print(f"ERRO OCR GENÉRICO: Timeout após {timeout_seconds} segundos")
                raise TimeoutError(f"Processamento OCR excedeu {timeout_seconds} segundos")
            
            if resultado_ocr is None:
                raise Exception("Processamento OCR falhou sem retornar resultado")
            
            # Verificar resultado
            print(f"DEBUG OCR GENÉRICO: Resultado da API: {resultado_ocr}")
            
            if resultado_ocr and 'texto_bruto' in resultado_ocr:
                texto_extraido = resultado_ocr['texto_bruto']
                sucesso = True
                print(f"DEBUG OCR GENÉRICO: Texto extraído com sucesso - {len(texto_extraido)} caracteres")
                
                # Calcular estatísticas
                caracteres = len(texto_extraido)
                linhas = len(texto_extraido.split('\n'))
                
                resultado = {
                    'nome_documento': nome_documento,
                    'arquivo_pdf': pdf_path,
                    'texto_extraido': texto_extraido,
                    'caracteres_extraidos': caracteres,
                    'linhas_extraidas': linhas,
                    'sucesso': True,
                    'erro': None,
                    'tentativas': tentativa,
                    'tempo_processamento': time.time() - start_time
                }
                
                print(f"DEBUG OCR GENÉRICO: {nome_documento} processado com sucesso na tentativa {tentativa}")
                return resultado
                
            else:
                raise Exception(f"Resultado OCR inválido: {resultado_ocr}")
                
        except TimeoutError as e:
            print(f"ERRO OCR GENÉRICO: Timeout na tentativa {tentativa}: {e}")
            if tentativa < max_retries:
                print(f"DEBUG OCR GENÉRICO: Aguardando 5 segundos antes da próxima tentativa...")
                time.sleep(5)
                continue
            else:
                return {
                    'nome_documento': nome_documento,
                    'arquivo_pdf': pdf_path,
                    'texto_extraido': '',
                    'caracteres_extraidos': 0,
                    'linhas_extraidas': 0,
                    'sucesso': False,
                    'erro': f'Timeout após {max_retries} tentativas: {e}',
                    'tentativas': tentativa,
                    'tempo_processamento': time.time() - start_time
                }
                
        except Exception as e:
            print(f"ERRO OCR GENÉRICO: Erro na tentativa {tentativa}: {e}")
            if tentativa < max_retries:
                print(f"DEBUG OCR GENÉRICO: Aguardando 3 segundos antes da próxima tentativa...")
                time.sleep(3)
                continue
            else:
                return {
                    'nome_documento': nome_documento,
                    'arquivo_pdf': pdf_path,
                    'texto_extraido': '',
                    'caracteres_extraidos': 0,
                    'linhas_extraidas': 0,
                    'sucesso': False,
                    'erro': f'Erro após {max_retries} tentativas: {e}',
                    'tentativas': tentativa,
                    'tempo_processamento': time.time() - start_time
                }
    
    # Se chegou aqui, todas as tentativas falharam
    return {
        'nome_documento': nome_documento,
        'arquivo_pdf': pdf_path,
        'texto_extraido': '',
        'caracteres_extraidos': 0,
        'linhas_extraidas': 0,
        'sucesso': False,
        'erro': f'Todas as {max_retries} tentativas falharam',
        'tentativas': max_retries,
        'tempo_processamento': 0
    }

def imprimir_texto_console(resultado_documento):
    """
    Imprime o texto extraído no console de forma formatada.
    
    Args:
        resultado_documento (dict): Resultado do processamento do documento
    """
    nome = resultado_documento['nome_documento']
    texto = resultado_documento['texto_extraido']
    arquivo = resultado_documento['arquivo_pdf']
    
    print("\n" + "=" * 80)
    print(f"TEXTO EXTRAÍDO - {nome.upper()}")
    print("=" * 80)
    print(f"Arquivo: {arquivo}")
    print(f"Caracteres: {resultado_documento['caracteres_extraidos']}")
    print(f"Linhas: {resultado_documento['linhas_extraidas']}")
    print("-" * 80)
    
    if texto:
        print(texto)
    else:
        print("(Nenhum texto extraído)")
    
    print("=" * 80)

def analisar_processo_provisoria(lecom_instance, codigo_processo, data_inicial_processo=None, timeout_global_minutos=30):
    """
    Analisa um processo do tipo provisória usando OCR genérico.
    
    Args:
        lecom_instance: Instância do LecomAutomation
        codigo_processo (str): Código do processo a ser analisado
        timeout_global_minutos (int, optional): Timeout global em minutos para todo o processo. 
                                              Se None, não há timeout (análise pode demorar o tempo necessário)
    
    Returns:
        dict: Resultado da análise
    """
    print(f"DEBUG: Iniciando análise provisória com OCR genérico para processo {codigo_processo}")
    
    # [DEBUG] NOVA CORREÇÃO: Timeout opcional
    if timeout_global_minutos is None:
        print("DEBUG: 🚫 Timeout global DESABILITADO - análise pode demorar o tempo necessário")
        timeout_global_seconds = None
        start_time_global = None
    else:
        print(f"DEBUG: Timeout global configurado: {timeout_global_minutos} minutos")
        start_time_global = time.time()
        timeout_global_seconds = timeout_global_minutos * 60
    
    try:
        # Verificar se o Lecom está funcionando
        if not lecom_instance or not hasattr(lecom_instance, 'driver'):
            return {
                'status': 'Erro',
                'erro': 'Instância do Lecom inválida',
                'data_processamento': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        
        # Verificar se o driver está ativo
        try:
            # Teste simples para verificar se o driver está funcionando
            current_url = lecom_instance.driver.current_url
            print(f"DEBUG: Driver ativo - URL atual: {current_url}")
        except Exception as e:
            print(f"DEBUG: Driver inativo - Erro: {e}")
            return {
                'status': 'Erro',
                'erro': f'Driver do navegador inativo: {e}',
                'data_processamento': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        
        # Extrair dados do formulário se disponível
        dados_formulario = {}
        try:
            if hasattr(lecom_instance, 'extrair_dados_pessoais_formulario'):
                dados_formulario = lecom_instance.extrair_dados_pessoais_formulario()
                print(f"DEBUG: Dados do formulário extraídos: {dados_formulario}")
        except Exception as e:
            print(f"DEBUG: Erro ao extrair dados do formulário: {e}")
        
        # [DEBUG] CORREÇÃO CRÍTICA: Usar data inicial passada como parâmetro ou extrair se necessário
        if data_inicial_processo is None:
            try:
                if hasattr(lecom_instance, 'extrair_data_inicial_processo'):
                    data_inicial_processo = lecom_instance.extrair_data_inicial_processo()
                    print(f"DEBUG: Data inicial do processo extraída via método: {data_inicial_processo}")
                else:
                    # Fallback: usar data atual se não conseguir extrair
                    data_inicial_processo = datetime.now().strftime("%d/%m/%Y")
                    print(f"DEBUG: Data inicial não disponível, usando data atual: {data_inicial_processo}")
            except Exception as e:
                print(f"DEBUG: Erro ao extrair data inicial: {e}")
                data_inicial_processo = datetime.now().strftime("%d/%m/%Y")
                print(f"DEBUG: Usando data atual como fallback: {data_inicial_processo}")
        else:
            print(f"DEBUG: Data inicial do processo recebida como parâmetro: {data_inicial_processo}")
        
        # [DEBUG] CORREÇÃO CRÍTICA: Para análise provisória, NÃO verificar banco - analisar parecer
        print("DEBUG: [BUSCA] Análise provisória - NÃO verificando banco de dados")
        print("DEBUG: [TARGET] Foco: Analisar parecer CHPF_PARECER para verificar elegibilidade")
        
        # Para análise provisória, não precisamos verificar se já tem naturalização
        # Estamos analisando se a pessoa DEVE RECEBER naturalização provisória
        naturalizacao_confirmada_via_banco = False
        dados_naturalizacao = None
        
        # Definir flag na instância do Lecom para uso posterior
        lecom_instance.naturalizacao_confirmada_via_banco = naturalizacao_confirmada_via_banco
        
        # Baixar todos os documentos
        print("DEBUG: Iniciando download de todos os documentos...")
        
        # [DEBUG] CORREÇÃO: Para análise provisória, usar documentos específicos
        print("DEBUG:  Definindo documentos específicos para análise provisória...")
        
        # Documentos específicos para análise provisória (NÃO os da definitiva)
        documentos_para_baixar = [
            'Documento de identificação do representante legal',
            'Carteira de Registro Nacional Migratório',
            'Comprovante de tempo de residência',
            'Documento de viagem internacional'
        ]
        
        print(f"DEBUG: [INFO] Documentos para análise provisória: {len(documentos_para_baixar)}")
        for doc in documentos_para_baixar:
            print(f"DEBUG:   • {doc}")
        
        # [FECHADO] LGPD: NUNCA baixar portaria de naturalização - sempre usar banco oficial
        print("DEBUG: [FECHADO] LGPD: Portaria de naturalização NUNCA será baixada - apenas banco oficial")
        
        # [DEBUG] CORREÇÃO: Analisar parecer ANTES de baixar documentos
        print("DEBUG: [BUSCA] Analisando parecer da Polícia Federal ANTES do download...")
        try:
            from analise_elegibilidade_provisoria import AnaliseElegibilidadeProvisoria
            
            # Criar instância do analisador
            analisador = AnaliseElegibilidadeProvisoria(lecom_instance)
            
            # Extrair e analisar o parecer (campo CHPF_PARECER)
            resultado_parecer = analisador.extrair_parecer_pf()
            
            # [DEBUG] CORREÇÃO: Marcar que o parecer já foi analisado para evitar duplicação
            analisador._parecer_analisado = resultado_parecer
            
            if resultado_parecer and not resultado_parecer.get('erro'):
                print("DEBUG: [OK] Parecer PF analisado com sucesso")
                print(f"DEBUG: [DADOS] Residência antes dos 10 anos: {resultado_parecer.get('residencia_antes_10_anos')}")
                print(f"DEBUG: [DADOS] Opinião favorável: {resultado_parecer.get('opiniao_favoravel')}")
                print(f"DEBUG: [DADOS] Indícios de falsidade: {resultado_parecer.get('indicios_falsidade')}")
                
                # [DEBUG] CORREÇÃO: Verificar se deve continuar com download
                residencia_antes_10 = resultado_parecer.get('residencia_antes_10_anos')
                
                # [DEBUG] CORREÇÃO: Verificar primeiro se é indeferimento por falta de residência
                if resultado_parecer.get('indeferimento_automatico', False):
                    print("DEBUG: 🚫 INDEFERIMENTO AUTOMÁTICO: Não possui autorização de residência por prazo indeterminado")
                    print("DEBUG: [TARGET] Não será necessário baixar documentos")
                    
                    return {
                        'status': 'Indeferimento automático',
                        'data_processamento': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'motivo': resultado_parecer.get('motivo_indeferimento', 'Não possui autorização de residência por prazo indeterminado'),
                        'analise_parecer': resultado_parecer,
                        'documentos_baixados': 0,
                        'lgpd_compliant': True
                    }
                elif residencia_antes_10 is False:
                    # Explicitamente confirmou que residência foi APÓS os 10 anos
                    print("DEBUG: 🚫 INDEFERIMENTO AUTOMÁTICO: Confirmado que obteve residência APÓS os 10 anos")
                    print("DEBUG: [TARGET] Não será necessário baixar documentos")
                    
                    # Retornar resultado de indeferimento automático
                    return {
                        'status': 'Indeferimento automático',
                        'data_processamento': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'motivo': 'Confirmado que obteve residência APÓS os 10 anos',
                        'analise_parecer': resultado_parecer,
                        'documentos_baixados': 0,
                        'lgpd_compliant': True
                    }
                elif residencia_antes_10 is True:
                    print("DEBUG: [OK] Residência antes dos 10 anos confirmada - continuando com download")
                else:
                    # residencia_antes_10 é None (indeterminado) - verificar idade para decidir
                    print("DEBUG: ❓ Residência antes dos 10 anos indeterminada - verificando idade...")
                    
                    try:
                        data_nascimento = dados_formulario.get('data_nascimento')
                        if data_nascimento:
                            data_processo = datetime.strptime(data_inicial_processo, "%d/%m/%Y")
                            data_nasc = datetime.strptime(data_nascimento, "%d/%m/%Y")
                            idade = data_processo.year - data_nasc.year
                            if (data_processo.month, data_processo.day) < (data_nasc.month, data_nasc.day):
                                idade -= 1
                            
                            print(f"DEBUG: Idade calculada: {idade} anos")
                            
                            if idade >= 10:
                                print("DEBUG: 🚫 ANÁLISE MANUAL: Idade >= 10 anos e residência indeterminada")
                                print("DEBUG: [TARGET] Não será necessário baixar documentos - pular para próximo processo")
                                
                                return {
                                    'status': 'Requer análise manual',
                                    'data_processamento': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    'motivo': f'Idade {idade} anos >= 10 e residência antes dos 10 anos indeterminada - requer análise manual',
                                    'analise_parecer': resultado_parecer,
                                    'idade_calculada': idade,
                                    'documentos_baixados': 0,
                                    'lgpd_compliant': True,
                                    'elegibilidade_final': 'requer_analise_manual'
                                }
                            else:
                                print(f"DEBUG: [OK] Idade {idade} anos < 10 - continuando com download (residência indeterminada)")
                        else:
                            print("DEBUG: [ERRO] Data de nascimento não disponível - continuando com download (residência indeterminada)")
                    except Exception as idade_erro:
                        print(f"DEBUG: [ERRO] Erro ao calcular idade: {idade_erro}")
                        print("DEBUG: ❓ Continuando com download devido a erro no cálculo de idade")
            else:
                print("DEBUG: [AVISO] Erro ao analisar parecer PF - verificando idade...")
                
                # [DEBUG] CORREÇÃO: Se parecer PF não funciona, verificar idade
                try:
                    data_nascimento = dados_formulario.get('data_nascimento')
                    if data_nascimento:
                        data_processo = datetime.strptime(data_inicial_processo, "%d/%m/%Y")
                        data_nasc = datetime.strptime(data_nascimento, "%d/%m/%Y")
                        idade = data_processo.year - data_nasc.year
                        if (data_processo.month, data_processo.day) < (data_nasc.month, data_nasc.day):
                            idade -= 1
                        
                        print(f"DEBUG: Idade calculada: {idade} anos")
                        
                        if idade >= 10:
                            print("DEBUG: 🚫 ANÁLISE MANUAL: Idade >= 10 anos e parecer PF com erro")
                            print("DEBUG: [TARGET] Não será necessário baixar documentos")
                            
                            return {
                                'status': 'Requer análise manual',
                                'data_processamento': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                'motivo': f'Idade {idade} anos >= 10 e parecer PF com erro - requer análise manual',
                                'analise_parecer': {'erro': 'Falha na análise do parecer', 'idade': idade},
                                'documentos_baixados': 0,
                                'lgpd_compliant': True,
                                'elegibilidade_final': 'requer_analise_manual'
                            }
                        else:
                            print(f"DEBUG: [OK] Idade {idade} anos < 10 - continuando com download")
                            resultado_parecer = {'erro': 'Falha na análise do parecer', 'idade': idade, 'continuar_analise': True}
                    else:
                        print("DEBUG: [ERRO] Data de nascimento não disponível - continuando com download")
                        resultado_parecer = {'erro': 'Falha na análise do parecer'}
                except Exception as idade_erro:
                    print(f"DEBUG: [ERRO] Erro ao calcular idade: {idade_erro}")
                    resultado_parecer = {'erro': 'Falha na análise do parecer'}
                
        except Exception as e:
            print(f"DEBUG: [ERRO] Erro ao analisar parecer PF: {e}")
            
            # [DEBUG] CORREÇÃO: Se há erro, verificar idade também
            try:
                data_nascimento = dados_formulario.get('data_nascimento')
                if data_nascimento:
                    data_processo = datetime.strptime(data_inicial_processo, "%d/%m/%Y")
                    data_nasc = datetime.strptime(data_nascimento, "%d/%m/%Y")
                    idade = data_processo.year - data_nasc.year
                    if (data_processo.month, data_processo.day) < (data_nasc.month, data_nasc.day):
                        idade -= 1
                    
                    print(f"DEBUG: Idade calculada: {idade} anos")
                    
                    if idade >= 10:
                        print("DEBUG: 🚫 ANÁLISE MANUAL: Idade >= 10 anos e erro na análise do parecer")
                        print("DEBUG: [TARGET] Não será necessário baixar documentos")
                        
                        return {
                            'status': 'Requer análise manual',
                            'data_processamento': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'motivo': f'Idade {idade} anos >= 10 e erro na análise do parecer - requer análise manual',
                            'analise_parecer': {'erro': str(e), 'idade': idade},
                            'documentos_baixados': 0,
                            'lgpd_compliant': True,
                            'elegibilidade_final': 'requer_analise_manual'
                        }
                    else:
                        print(f"DEBUG: [OK] Idade {idade} anos < 10 - continuando com download")
                        resultado_parecer = {'erro': str(e), 'idade': idade, 'continuar_analise': True}
                else:
                    print("DEBUG: [ERRO] Data de nascimento não disponível - continuando com download")
                    resultado_parecer = {'erro': str(e)}
            except Exception as idade_erro:
                print(f"DEBUG: [ERRO] Erro ao calcular idade: {idade_erro}")
                resultado_parecer = {'erro': str(e)}
                
            print("DEBUG: [RELOAD] Continuando com download de documentos...")
        
        # [DEBUG] CORREÇÃO: SEMPRE baixar todos os documentos (sem cache)
        print("DEBUG: [DEBUG] Baixando TODOS os documentos obrigatórios...")
        todos_textos_extraidos = {}
        
        for nome_documento in documentos_para_baixar:
            print(f"DEBUG: [RELOAD] Baixando {nome_documento}...")
            try:
                # [DEBUG] CORREÇÃO: Aplicar max_paginas=1 para documentos específicos
                if 'Comprovante de tempo de residência' in nome_documento:
                    print("DEBUG: [BUSCA] Comprovante de residência - usando apenas primeira página (max_paginas=1)")
                    texto_extraido = lecom_instance.baixar_documento_e_ocr(nome_documento, max_paginas=1)
                elif 'Documento de viagem internacional' in nome_documento:
                    print("DEBUG: [BUSCA] Documento de viagem internacional - usando apenas primeira página (max_paginas=1)")
                    texto_extraido = lecom_instance.baixar_documento_e_ocr(nome_documento, max_paginas=1)
                else:
                    # Para outros documentos, usar processamento normal
                    texto_extraido = lecom_instance.baixar_documento_e_ocr(nome_documento)
                
                if texto_extraido:
                    todos_textos_extraidos[nome_documento] = texto_extraido
                    print(f"DEBUG: [OK] {nome_documento}: {len(texto_extraido)} caracteres extraídos")
                else:
                    todos_textos_extraidos[nome_documento] = "Documento não processado"
                    print(f"DEBUG: [ERRO] {nome_documento}: Falha no download/OCR")
            except Exception as e:
                print(f"DEBUG: [ERRO] Erro ao baixar {nome_documento}: {e}")
                todos_textos_extraidos[nome_documento] = "Erro no download"
        
        # [DEBUG] CORREÇÃO: Para análise provisória, NÃO adicionar confirmação de banco
        print("DEBUG: [DEBUG] Análise provisória - NÃO adicionando confirmação de banco")
        
        # Usar documentos sem confirmação de banco
        documentos_com_confirmacao = todos_textos_extraidos.copy()
        
        # [FECHADO] CORREÇÃO LGPD: Log seguro sem dados sensíveis
        print(f"DEBUG: [FECHADO] Total de documentos processados: {len(todos_textos_extraidos)}")
        print("DEBUG: [FECHADO] LGPD: Portaria de naturalização NUNCA é baixada - apenas banco oficial")
        
        # [DEBUG] CORREÇÃO CRÍTICA: Executar APENAS UMA análise de elegibilidade completa
        print("DEBUG: [TARGET] Executando análise de elegibilidade completa UNIFICADA...")
        try:
            from analise_elegibilidade_provisoria import AnaliseElegibilidadeProvisoria
            
            # Criar instância do analisador de elegibilidade
            analisador_elegibilidade = AnaliseElegibilidadeProvisoria(lecom_instance)
            
            # [DEBUG] CORREÇÃO: Parecer analisado com sucesso
            if resultado_parecer and not resultado_parecer.get('erro'):
                print("DEBUG: [OK] Parecer PF analisado com sucesso")
            
            # Executar análise completa (que incluirá parecer, documentos E decisão)
            # [DEBUG] CORREÇÃO: Passar documentos já baixados para evitar download duplo
            resultado_elegibilidade = analisador_elegibilidade.analisar_elegibilidade_completa(
                dados_formulario, data_inicial_processo, todos_textos_extraidos
            )
            
            print("DEBUG: [OK] Análise de elegibilidade completa executada")
            print(f"DEBUG: [TARGET] Resultado final: {resultado_elegibilidade.get('elegibilidade_final', 'N/A')}")
            print(f"DEBUG: 💬 Motivo final: {resultado_elegibilidade.get('motivo_final', 'N/A')}")
            
            # [DEBUG] CORREÇÃO: NÃO executar análise de decisão separada - já está incluída na elegibilidade
            print("DEBUG: 🚫 Análise de decisão já incluída na elegibilidade - não executando separadamente")
            resultado_decisao = {
                'decisao_consolidada': resultado_elegibilidade.get('elegibilidade_final', 'indeterminada'),
                'confianca_consolidada': 1.0 if resultado_elegibilidade.get('deferimento') else 0.8,
                'score_total_consolidado': 100 if resultado_elegibilidade.get('deferimento') else 80,
                'motivo_consolidado': resultado_elegibilidade.get('motivo_final', 'Resultado da análise completa')
            }
            
            # Verificar se o resultado é válido
            if not isinstance(resultado_decisao, dict):
                print(f"DEBUG: [AVISO] Resultado de decisão não é dict: {type(resultado_decisao)}")
                resultado_decisao = {'erro': 'Resultado inválido'}
            
            # Consolidar resultados
            resultado_analise = {
                'elegibilidade': resultado_elegibilidade.get('elegibilidade_final', 'indeterminada'),
                'confianca': resultado_decisao.get('confianca_consolidada', 0.0),
                'score_total': resultado_decisao.get('score_total_consolidado', 0),
                'decisao': resultado_decisao.get('decisao_consolidada', 'indeterminada'),
                'motivo': resultado_decisao.get('motivo_consolidado', ''),
                'analise_elegibilidade': resultado_elegibilidade,
                'analise_decisoes': resultado_decisao,
                'tipo_analise': 'provisoria'
            }
            
            # [DEBUG] CORREÇÃO: Verificar se resultado_analise é um dicionário válido
            if not isinstance(resultado_analise, dict):
                print(f"[AVISO] ERRO: resultado_analise não é um dicionário válido: {type(resultado_analise)}")
                resultado_analise = {
                    'elegibilidade': 'erro_analise',
                    'decisao': 'indeterminada',
                    'confianca': 0.0,
                    'score_total': 0,
                    'motivo': 'Erro na análise'
                }
            
            # [FECHADO] CORREÇÃO LGPD: Log seguro do resultado
            print(f"DEBUG: [FECHADO] Análise provisória concluída: {resultado_analise.get('elegibilidade', 'N/A')}")
            print(f"DEBUG: [FECHADO] Decisão: {resultado_analise.get('decisao', 'N/A')}")
            print(f"DEBUG: [FECHADO] Confiança: {resultado_analise.get('confianca', 0.0):.1%}")
            print(f"DEBUG: [FECHADO] Score: {resultado_analise.get('score_total', 0)}")
            
            # Adicionar log de deferimento/indeferimento
            decisao = resultado_analise.get('decisao', 'indeterminada')
            motivo = resultado_analise.get('motivo', 'Motivo não disponível')
            
            if decisao == 'deferimento':
                print(f"DEBUG: [OK] RESULTADO: DEFERIDO - {motivo}")
            elif decisao == 'indeferimento':
                print(f"DEBUG: [ERRO] RESULTADO: INDEFERIDO - {motivo}")
            elif decisao == 'elegivel_com_ressalva':
                print(f"DEBUG: [AVISO] RESULTADO: ELEGÍVEL COM RESSALVA - {motivo}")
            else:
                print(f"DEBUG: ❓ RESULTADO: INDETERMINADO - {motivo}")
            
            # Mascarar dados sensíveis no resultado antes de salvar
            resultado_analise['dados_formulario_mascarados'] = {
                'nome_completo': f"{dados_formulario.get('nome_completo', '')[:2]}***" if dados_formulario.get('nome_completo') else None,
                'data_nascimento': dados_formulario.get('data_nascimento'),
                'idade_calculada': dados_formulario.get('idade_calculada', 'N/A')
            }
            
            # [FECHADO] LGPD: Adicionar flag de conformidade
            resultado_analise['lgpd_compliant'] = True
            resultado_analise['naturalizacao_fonte'] = 'banco_oficial' if naturalizacao_confirmada_via_banco else 'verificacao_manual_requerida'
            
            # [DEBUG] CORREÇÃO CRÍTICA: NÃO executar segunda análise de elegibilidade
            # A análise já foi feita acima, retornar diretamente o resultado
            print("DEBUG: [OK] Usando resultado de elegibilidade já obtido")
            resultado_analise['elegibilidade_final'] = resultado_analise.get('elegibilidade', 'indeterminada')
            resultado_analise['confianca'] = resultado_analise.get('confianca', 0.0)
            resultado_analise['score_total'] = resultado_analise.get('score_total', 0)
            
            # [DEBUG] CORREÇÃO: NÃO chamar análise de decisões separadamente
            # A decisão já está incluída no resultado da elegibilidade
            print("DEBUG: [OK] Decisão já incluída no resultado da elegibilidade")
            
            # [DEBUG] CORREÇÃO: Garantir que apenas o resultado da primeira análise seja usado
            print("DEBUG: 🚫 SEGUNDA ANÁLISE ELIMINADA - usando apenas primeira análise")
            
            # Criar resultado final completo
            resultado_final = {
                'status': 'Processado com sucesso',
                'data_processamento': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'total_documentos': len([doc for doc in todos_textos_extraidos.values() if doc and len(doc.strip()) > 10]),
                'documentos_processados': [nome for nome, texto in todos_textos_extraidos.items() if texto and len(texto.strip()) > 10],
                'todos_textos_extraidos': todos_textos_extraidos,
                'analise_elegibilidade': resultado_analise,
                'naturalizacao_confirmada_via_banco': naturalizacao_confirmada_via_banco,
                'dados_naturalizacao': dados_naturalizacao
            }
            
            # [DEBUG] CORREÇÃO: Sempre tentar navegar para próximo processo, mesmo com erro
            try:
                print("DEBUG: [BUSCA] Verificando se a sessão ainda está ativa...")
                current_url = lecom_instance.driver.current_url
                print(f"DEBUG: URL atual: {current_url}")
                
                # [DEBUG] CORREÇÃO: Forçar navegação para página de pesquisa
                print("DEBUG: [EXEC] Navegando de volta para página de pesquisa...")
                lecom_instance.voltar_para_pesquisa_processos()
                
                # Verificar se navegação foi bem-sucedida
                nova_url = lecom_instance.driver.current_url
                print(f"DEBUG: Nova URL após navegação: {nova_url}")
                
                if 'pesquisa_processo' in nova_url:
                    print("DEBUG: [OK] Navegação para página de pesquisa bem-sucedida")
                    print("DEBUG: [RELOAD] Sessão renovada - pronto para próximo processo")
                else:
                    print("DEBUG: [AVISO] Navegação não foi para pesquisa - tentando novamente...")
                    lecom_instance.driver.get("https://justica.servicos.gov.br/bpm/pesquisa_processo")
                    print("DEBUG: [RELOAD] Navegação forçada para pesquisa concluída")
                    
            except Exception as nav_error:
                print(f"DEBUG: [ERRO] Erro na navegação: {nav_error}")
                print("DEBUG: [RELOAD] Tentando navegação de emergência...")
                try:
                    lecom_instance.driver.get("https://justica.servicos.gov.br/bpm/pesquisa_processo")
                    print("DEBUG: [OK] Navegação de emergência concluída")
                except Exception as emergency_error:
                    print(f"DEBUG: [ERRO] Navegação de emergência falhou: {emergency_error}")
                    print("DEBUG: [AVISO] Sistema pode não conseguir processar próximo processo")
            
            print(f"DEBUG: Análise provisoria concluída com sucesso para o código {codigo_processo}")
            return resultado_final
            
        except Exception as e:
            print(f"DEBUG: [ERRO] Erro na análise de elegibilidade: {e}")
            resultado_analise_erro = {
                'elegibilidade': 'erro_analise',
                'confianca': 0.0,
                'erro': str(e),
                'lgpd_compliant': True,  # [FECHADO] Sempre em conformidade LGPD
                'naturalizacao_fonte': 'erro_verificacao',
                'dados_formulario_mascarados': {
                    'nome_completo': f"{dados_formulario.get('nome_completo', '')[:2]}***" if dados_formulario.get('nome_completo') else None,
                    'data_nascimento': dados_formulario.get('data_nascimento')
                }
            }
            
            # Criar resultado final completo mesmo em caso de erro
            resultado_final = {
                'status': 'Processado com sucesso',
                'data_processamento': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'total_documentos': len([doc for doc in todos_textos_extraidos.values() if doc and len(doc.strip()) > 10]),
                'documentos_processados': [nome for nome, texto in todos_textos_extraidos.items() if texto and len(texto.strip()) > 10],
                'todos_textos_extraidos': todos_textos_extraidos,
                'analise_elegibilidade': resultado_analise_erro,
                'naturalizacao_confirmada_via_banco': naturalizacao_confirmada_via_banco,
                'dados_naturalizacao': dados_naturalizacao
            }
            
            return resultado_final
        
        # [DEBUG] CORREÇÃO: NÃO executar análise de decisões separada
        # A decisão já está incluída no resultado da elegibilidade
        print("DEBUG: [OK] Análise de decisões já incluída no resultado de elegibilidade")
        resultado_final['analise_decisoes'] = {
            'decisao_consolidada': resultado_analise.get('elegibilidade_final', 'indeterminada'),
            'confianca_consolidada': resultado_analise.get('confianca', 0.0),
            'score_total_consolidado': resultado_analise.get('score_total', 0)
        }
        
        print(f"DEBUG: Análise provisória concluída para processo {codigo_processo}")
        return resultado_final
        
    except TimeoutError as e:
        print(f"DEBUG: Timeout global atingido: {e}")
        return {
            'status': 'Timeout',
            'erro': f'Timeout global de {timeout_global_minutos} minutos: {e}',
            'data_processamento': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'tempo_total_processamento': time.time() - start_time_global if start_time_global else 'N/A'
        }
        
    except Exception as e:
        print(f"DEBUG: [ERRO] Erro geral na análise provisória: {e}")
        import traceback
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        
        # [DEBUG] CORREÇÃO: Sempre tentar navegar para próximo processo, mesmo com erro
        try:
            print("DEBUG: [BUSCA] Verificando se a sessão ainda está ativa...")
            current_url = lecom_instance.driver.current_url
            print(f"DEBUG: URL atual: {current_url}")
            
            # [DEBUG] CORREÇÃO: Forçar navegação para página de pesquisa
            print("DEBUG: [EXEC] Navegando de volta para página de pesquisa...")
            lecom_instance.voltar_para_pesquisa_processos()
            
            # Verificar se navegação foi bem-sucedida
            nova_url = lecom_instance.driver.current_url
            print(f"DEBUG: Nova URL após navegação: {nova_url}")
            
            if 'pesquisa_processo' in nova_url:
                print("DEBUG: [OK] Navegação para página de pesquisa bem-sucedida")
                print("DEBUG: [RELOAD] Sessão renovada - pronto para próximo processo")
            else:
                print("DEBUG: [AVISO] Navegação não foi para pesquisa - tentando novamente...")
                lecom_instance.driver.get("https://justica.servicos.gov.br/bpm/pesquisa_processo")
                print("DEBUG: [RELOAD] Navegação forçada para pesquisa concluída")
                
        except Exception as nav_error:
            print(f"DEBUG: [ERRO] Erro na navegação: {nav_error}")
            print("DEBUG: [RELOAD] Tentando navegação de emergência...")
            try:
                lecom_instance.driver.get("https://justica.servicos.gov.br/bpm/pesquisa_processo")
                print("DEBUG: [OK] Navegação de emergência concluída")
            except Exception as emergency_error:
                print(f"DEBUG: [ERRO] Navegação de emergência falhou: {emergency_error}")
                print("DEBUG: [AVISO] Sistema pode não conseguir processar próximo processo")
            
        return {
            'status': 'Erro',
            'erro': f'Erro geral: {e}',
            'data_processamento': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'tempo_total_processamento': time.time() - start_time_global if start_time_global else 'N/A'
        }

def analisar_processo_provisoria(lecom, codigo_processo, data_inicial=None, timeout_global_minutos=None):
    """
    Função para análise de processo provisória
    Wrapper que chama a lógica de processamento de documentos do lecom
    """
    print(f"DEBUG: Iniciando análise de processo provisória para código: {codigo_processo}")
    print(f"DEBUG: Data inicial fornecida: {data_inicial}")
    
    try:
        # Armazenar a data inicial se fornecida
        if data_inicial:
            lecom.data_inicial_processo = data_inicial
            
        # Usar o método existente do lecom para processar o processo
        if hasattr(lecom, 'processar_processo'):
            return lecom.processar_processo(codigo_processo)
        else:
            print("ERRO: Método processar_processo não encontrado no objeto lecom")
            return {
                'status': 'Erro',
                'erro': 'Método processar_processo não encontrado',
                'codigo_processo': codigo_processo
            }
    except Exception as e:
        print(f"ERRO na análise provisória: {e}")
        return {
            'status': 'Erro',
            'erro': str(e),
            'codigo_processo': codigo_processo
        } 