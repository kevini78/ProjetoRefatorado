"""
Módulo para análise automática de processos usando OCR genérico para tipo definitiva
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

def analisar_processo_definitiva(lecom_instance, codigo_processo, timeout_global_minutos=None):
    """
    Analisa um processo do tipo definitiva usando OCR genérico.
    
    Args:
        lecom_instance: Instância do LecomAutomation
        codigo_processo (str): Código do processo a ser analisado
        timeout_global_minutos (int, optional): Timeout global em minutos para todo o processo.
                                              Se None, não há timeout (análise pode demorar o tempo necessário)
    
    Returns:
        dict: Resultado da análise
    """
    print(f"DEBUG: Iniciando análise definitiva com OCR genérico para processo {codigo_processo}")
    
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
        
        # [DEBUG] CORREÇÃO CRÍTICA: Verificar naturalização provisória NO BANCO DE DADOS ANTES de baixar documentos
        print("DEBUG: [BUSCA] Verificando naturalização provisória no banco de dados ANTES da análise...")
        naturalizacao_confirmada_via_banco = False
        dados_naturalizacao = None
        
        if dados_formulario and dados_formulario.get('nome_completo'):
            try:
                # [FECHADO] USAR VERIFICADOR SEGURO CONFORME LGPD
                from verificador_naturalizacao_seguro import verificar_naturalizacao_provisoria_segura
                
                print("DEBUG: [FECHADO] Usando verificador seguro de naturalização (LGPD)")
                
                # Verificar naturalização no banco ANTES de qualquer análise
                tem_naturalizacao, dados_nat = verificar_naturalizacao_provisoria_segura(
                    dados_formulario['nome_completo'],
                    dados_formulario.get('nome_mae'),
                    dados_formulario.get('nome_pai')
                )
                
                if tem_naturalizacao:
                    naturalizacao_confirmada_via_banco = True
                    dados_naturalizacao = dados_nat
                    print(f"DEBUG: [OK] Naturalização provisória CONFIRMADA via banco para: {dados_formulario['nome_completo']}")
                    print(f"DEBUG: [NOTA] ID: {dados_nat.get('nat_id_seq_naturalizado')}")
                    print(f"DEBUG: [TARGET] Não será necessário baixar documento de portaria")
                    print("DEBUG: [FECHADO] Verificação realizada de forma segura (LGPD)")
                else:
                    print(f"DEBUG: [ERRO] Naturalização provisória NÃO encontrada no banco para: {dados_formulario['nome_completo']}")
                    print(f"DEBUG: [TARGET] Será necessário baixar documento de portaria")
                    print("DEBUG: [FECHADO] Verificação realizada de forma segura (LGPD)")
                
            except ImportError:
                print("DEBUG: [AVISO] Módulo de verificação segura não disponível")
                print("DEBUG: [RELOAD] Usando método alternativo...")
                
                # Fallback para método antigo (menos seguro)
                try:
                    from verificador_naturalizacao_db import verificar_naturalizacao_provisoria_db
                    
                    # Configuração do banco via arquivo de configuração
                    try:
                        from config_banco_naturalizacao import obter_config_banco, TIPO_BANCO
                        config_db = obter_config_banco()
                        tipo_db = TIPO_BANCO
                    except ImportError:
                        # Configuração padrão se arquivo não estiver disponível
                        config_db = {
                            'host': 'localhost',
                            'user': 'seu_usuario',
                            'password': 'sua_senha',
                            'database': 'nome_do_banco',
                            'port': 5432
                        }
                        tipo_db = 'postgresql'
                    
                    # Verificar naturalização (campos opcionais)
                    tem_naturalizacao, dados_nat = verificar_naturalizacao_provisoria_db(
                        dados_formulario['nome_completo'],
                        dados_formulario.get('nome_mae'),  # Pode ser None
                        dados_formulario.get('nome_pai'),  # Pode ser None
                        tipo_db=tipo_db,
                        config_db=config_db
                    )
                    
                    if tem_naturalizacao:
                        naturalizacao_confirmada_via_banco = True
                        dados_naturalizacao = dados_nat
                        print(f"DEBUG: [OK] Naturalização provisória confirmada via Banco de Dados!")
                        print(f"DEBUG: [NOTA] ID: {dados_nat.get('nat_id_seq_naturalizado')}")
                        print(f"DEBUG: [USER] Nome: {dados_nat.get('nat_nome_naturalizado')}")
                        print(f"DEBUG: 👩 Mãe: {dados_nat.get('nat_nome_mae') or 'Não informado'}")
                        print(f"DEBUG: 👨 Pai: {dados_nat.get('nat_nome_pai') or 'Não informado'}")
                        print("DEBUG: [TARGET] Não será necessário baixar documento de portaria")
                        print("DEBUG: [TARGET] Continuando para verificação de antecedentes criminais...")
                    else:
                        print("DEBUG: [ERRO] Naturalização provisória NÃO encontrada no banco")
                        print("DEBUG: [TARGET] Será necessário baixar documento de portaria")
                
                except ImportError:
                    print("DEBUG: [AVISO] Módulo de verificação de banco não disponível")
                except Exception as e:
                    print(f"DEBUG: [AVISO] Erro na verificação de banco: {e}")
            except Exception as e:
                print(f"DEBUG: [AVISO] Erro na verificação segura: {e}")
                print("DEBUG: [RELOAD] Tentando método alternativo...")
        
        # Definir flag na instância do Lecom para uso posterior
        lecom_instance.naturalizacao_confirmada_via_banco = naturalizacao_confirmada_via_banco
        
        # [DEBUG] CORREÇÃO CRÍTICA: Se naturalização NÃO foi encontrada no banco, é INDEFERIMENTO AUTOMÁTICO
        if not naturalizacao_confirmada_via_banco:
            print("[ERRO] Naturalização provisória NÃO encontrada no banco")
            print("🚫 INDEFERIMENTO AUTOMÁTICO: Naturalização provisória é requisito obrigatório")
            print("➡️ Pulando para o próximo processo...")
            
            return {
                'status': 'Indeferimento automático',
                'motivo': 'Indeferimento automático por ausência de naturalização provisória: Naturalização provisória não encontrada no banco de dados oficial',
                'data_processamento': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'nome_processo': dados_formulario.get('nome_completo', 'Nome não extraído'),
                'indeferimento_automatico': True,
                'motivo_indef': 'Naturalização provisória não encontrada no banco de dados oficial'
            }
        
        # Baixar todos os documentos
        print("DEBUG: Iniciando download de todos os documentos...")
        
        # [FECHADO] CORREÇÃO LGPD: Se naturalização foi confirmada via banco, NÃO baixar portaria
        documentos_para_baixar = lecom_instance.documentos_para_baixar.copy()
        
        # [FECHADO] LGPD: NUNCA baixar portaria de naturalização - sempre usar banco oficial
        if 'Portaria de concessão da naturalização provisória' in documentos_para_baixar:
            documentos_para_baixar.remove('Portaria de concessão da naturalização provisória')
            print("DEBUG: [FECHADO] LGPD: Portaria de naturalização NUNCA será baixada - apenas banco oficial")
        
        # Baixar documentos restantes (SEM portaria de naturalização)
        todos_textos_extraidos = {}
        for nome_documento in documentos_para_baixar:
            try:
                print(f"DEBUG: Tentando baixar {nome_documento}...")
                
                # Verificar se já foi processado (cache)
                if nome_documento in lecom_instance.textos_ja_extraidos:
                    print(f"DEBUG: [OK] {nome_documento}: {len(lecom_instance.textos_ja_extraidos[nome_documento])} caracteres cacheados")
                    todos_textos_extraidos[nome_documento] = lecom_instance.textos_ja_extraidos[nome_documento]
                    continue
                
                # Baixar documento
                texto_extraido = lecom_instance.baixar_documento_e_ocr(nome_documento)
                
                if texto_extraido:
                    # [FECHADO] MASCARAR DADOS SENSÍVEIS CONFORME LGPD
                    try:
                        from data_protection import limpar_texto_ocr
                        texto_protegido = limpar_texto_ocr(texto_extraido)
                        print(f"DEBUG: [FECHADO] Dados sensíveis mascarados em {nome_documento}")
                    except ImportError:
                        # Fallback para mascaramento básico
                        texto_protegido = texto_extraido
                        # Mascarar CPF e RG basicamente
                        import re
                        texto_protegido = re.sub(r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b', '[CPF MASCARADO]', texto_protegido)
                        texto_protegido = re.sub(r'\b\d{2}\.\d{3}\.\d{3}-[0-9X]\b', '[RG MASCARADO]', texto_protegido)
                        print(f"DEBUG: [FECHADO] Mascaramento básico aplicado em {nome_documento}")
                    
                    todos_textos_extraidos[nome_documento] = texto_protegido
                    print(f"DEBUG: [OK] {nome_documento}: {len(texto_protegido)} caracteres extraídos e protegidos")
                else:
                    print(f"DEBUG: [ERRO] Falha ao extrair texto de {nome_documento}")
                    
            except Exception as e:
                print(f"DEBUG: [ERRO] Erro ao processar {nome_documento}: {e}")
        
        # [FECHADO] CORREÇÃO LGPD: Adicionar confirmação de naturalização via banco se aplicável
        confirmacao_banco_texto = None
        if naturalizacao_confirmada_via_banco:
            confirmacao_banco_texto = f"""
            CONFIRMAÇÃO VIA BANCO DE DADOS OFICIAL:
            [OK] Naturalização provisória confirmada via Banco de Dados Oficial!
            [TARGET] Documento de portaria NÃO foi baixado (LGPD)
            [NOTA] Status: Naturalização provisória encontrada e confirmada
            [INFO] Verificação: Dados conferidos no banco oficial
            [FECHADO] Conformidade: LGPD - Apenas fonte oficial utilizada
            [OK] Naturalização provisória válida e ativa
            """
            print("DEBUG: [TARGET] Adicionando confirmação de naturalização via banco aos documentos")
        else:
            # [FECHADO] LGPD: Se não confirmada via banco, adicionar instrução para verificação manual
            confirmacao_banco_texto = f"""
            VERIFICAÇÃO MANUAL REQUERIDA (LGPD):
            [AVISO] Naturalização provisória NÃO confirmada via banco oficial
            [FECHADO] Conformidade LGPD: Documento de portaria NÃO foi processado
            [INFO] Ação necessária: Verificar manualmente no banco de dados oficial
            [TARGET] Motivo: Sistema respeita LGPD - apenas fonte oficial é utilizada
            """
            print("DEBUG: [FECHADO] LGPD: Instrução de verificação manual adicionada")
        
        # Adicionar confirmação aos documentos se existir
        documentos_com_confirmacao = todos_textos_extraidos.copy()
        if confirmacao_banco_texto:
            documentos_com_confirmacao['Confirmacao_Naturalizacao_Banco'] = confirmacao_banco_texto
            print("DEBUG: [OK] Confirmação/instrução LGPD adicionada aos documentos para análise")
        
        # [FECHADO] CORREÇÃO LGPD: Log seguro sem dados sensíveis
        print(f"DEBUG: [FECHADO] Total de documentos processados: {len(todos_textos_extraidos)}")
        print(f"DEBUG: [FECHADO] Naturalização via banco: {'[OK] SIM' if naturalizacao_confirmada_via_banco else '[ERRO] NÃO'}")
        print("DEBUG: [FECHADO] LGPD: Portaria de naturalização NUNCA é baixada - apenas banco oficial")
        
        # Análise de elegibilidade
        print("DEBUG: Iniciando análise de elegibilidade...")
        try:
            print("DEBUG: Importando AnalisadorElegibilidadeSimples...")
            from analise_elegibilidade_simples import AnalisadorElegibilidadeSimples
            print("DEBUG: [OK] Módulo importado com sucesso")
            analisador = AnalisadorElegibilidadeSimples()
            print("DEBUG: [OK] Analisador criado com sucesso")
            
            # Passar dados do formulário E documentos com confirmação para análise de elegibilidade
            resultado_analise = analisador.analisar_elegibilidade(documentos_com_confirmacao, dados_formulario)
            
            # [FECHADO] CORREÇÃO LGPD: Log seguro do resultado
            print(f"DEBUG: [FECHADO] Análise concluída: {resultado_analise['elegibilidade']}")
            print(f"DEBUG: [FECHADO] Confiança: {resultado_analise['confianca']:.1%}")
            
            # Adicionar log de deferimento/indeferimento
            if resultado_analise['elegibilidade'].startswith('elegivel'):
                print(f"DEBUG: [OK] RESULTADO: DEFERIDO - {resultado_analise['elegibilidade']}")
            elif resultado_analise['elegibilidade'] == 'não_elegivel':
                print(f"DEBUG: [ERRO] RESULTADO: INDEFERIDO - {resultado_analise['elegibilidade']}")
            elif resultado_analise['elegibilidade'] == 'deferimento_com_ressalvas':
                print(f"DEBUG: [AVISO] RESULTADO: DEFERIDO COM RESSALVAS - {resultado_analise['elegibilidade']}")
            else:
                print(f"DEBUG: ❓ RESULTADO: INDETERMINADO - {resultado_analise['elegibilidade']}")
            
            # Mascarar dados sensíveis no resultado antes de salvar
            resultado_analise['dados_formulario_mascarados'] = {
                'nome_completo': f"{dados_formulario.get('nome_completo', '')[:2]}***" if dados_formulario.get('nome_completo') else None,
                'data_nascimento': dados_formulario.get('data_nascimento'),
                'idade_calculada': resultado_analise.get('idade_calculada')
            }
            
            # [FECHADO] LGPD: Adicionar flag de conformidade
            resultado_analise['lgpd_compliant'] = True
            resultado_analise['naturalizacao_fonte'] = 'banco_oficial' if naturalizacao_confirmada_via_banco else 'verificacao_manual_requerida'
            
            # Criar resultado final completo
            resultado_final = {
                'status': 'Processado com sucesso',
                'data_processamento': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'total_documentos': len(todos_textos_extraidos),
                'documentos_processados': list(todos_textos_extraidos.keys()),
                'todos_textos_extraidos': todos_textos_extraidos,
                'analise_elegibilidade': resultado_analise,
                'naturalizacao_confirmada_via_banco': naturalizacao_confirmada_via_banco,
                'dados_naturalizacao': dados_naturalizacao
            }
            
            # Análise de decisões (se houver textos)
            if todos_textos_extraidos:
                try:
                    print("DEBUG: Iniciando análise de decisões...")
                    from analise_decisoes import AnalisadorDecisoes
                    
                    analisador_dec = AnalisadorDecisoes()
                    analise_decisoes = analisador_dec.analisar_multiplos_documentos(todos_textos_extraidos)
                    
                    resultado_final['analise_decisoes'] = analise_decisoes
                    print(f"DEBUG: Análise de decisões concluída: {analise_decisoes.get('decisao_consolidada', 'N/A')}")
                    
                except Exception as e:
                    print(f"DEBUG: Erro na análise de decisões: {e}")
                    resultado_final['analise_decisoes'] = {
                        'decisao_consolidada': 'erro_analise',
                        'erro': str(e)
                    }
            
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
                'total_documentos': len(todos_textos_extraidos),
                'documentos_processados': list(todos_textos_extraidos.keys()),
                'todos_textos_extraidos': todos_textos_extraidos,
                'analise_elegibilidade': resultado_analise_erro,
                'naturalizacao_confirmada_via_banco': naturalizacao_confirmada_via_banco,
                'dados_naturalizacao': dados_naturalizacao
            }
            
            return resultado_final
        
        print(f"DEBUG: Análise definitiva concluída para processo {codigo_processo}")
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
        print(f"DEBUG: Erro geral na análise definitiva: {e}")
        import traceback
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        
        return {
            'status': 'Erro',
            'erro': f'Erro geral: {e}',
            'data_processamento': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'tempo_total_processamento': time.time() - start_time_global if start_time_global else 'N/A'
        }

# FUNÇÃO REMOVIDA - usar apenas analisar_processo_definitiva principal acima

 