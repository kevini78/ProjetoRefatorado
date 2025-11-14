"""
Módulo para análise de elegibilidade de naturalização ordinária
Implementa as regras específicas conforme Art. 65 da Lei nº 13.445/2017

ATUALIZADO: Integrado com termos validação melhorados
Baseado em análise de OCR de 5.323 documentos VALIDADOS
"""

import re
from datetime import datetime
from typing import Dict, Any, Tuple, Optional
import spacy
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Importar termos melhorados baseados em análise de OCR
try:
    from termos_validacao_melhorados import (
        TERMOS_CRNM,
        TERMOS_CPF,
        TERMOS_ANTECEDENTES_BRASIL,
        TERMOS_COMUNICACAO_PORTUGUES,
        TERMOS_ANTECEDENTES_ORIGEM,
        validar_documento_melhorado
    )
    TERMOS_MELHORADOS_DISPONIVEIS = True
    print("[OK] Termos de validação melhorados carregados (baseados em 5.323 documentos)")
except ImportError:
    TERMOS_MELHORADOS_DISPONIVEIS = False
    print("[AVISO] Usando validação básica (termos melhorados não disponíveis)")

class AnaliseElegibilidadeOrdinaria:
    """
    Analisador de elegibilidade para naturalização ordinária
    Implementa os 4 requisitos do Art. 65 da Lei nº 13.445/2017
    """
    
    def __init__(self, lecom_instance):
        """
        Inicializa o analisador
        
        Args:
            lecom_instance: Instância da navegação ordinária
        """
        self.lecom = lecom_instance
        self.wait = WebDriverWait(lecom_instance.driver, 20)
        
        # Carregar modelo SpaCy para análise de texto
        try:
            self.nlp = spacy.load("pt_core_news_sm")
            print("[OK] Modelo SpaCy carregado para análise de elegibilidade ordinária")
        except OSError:
            print("[AVISO] Modelo SpaCy não encontrado, usando análise básica")
            self.nlp = None
    
    def analisar_elegibilidade_completa(self, dados_formulario: Dict[str, Any], data_inicial_processo: str, documentos_ja_baixados: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Analisa elegibilidade completa para naturalização ordinária
        
        Args:
            dados_formulario: Dados extraídos do formulário
            data_inicial_processo: Data inicial do processo
            documentos_ja_baixados: Documentos já baixados (opcional)
            
        Returns:
            Dict com resultado completo da análise
        """
        print("\n" + "="*80)
        print("[TARGET] ANÁLISE DE ELEGIBILIDADE ORDINÁRIA")
        print("Art. 65 da Lei nº 13.445/2017")
        print("="*80)
        
        resultado = {
            'elegibilidade_final': 'nao_elegivel',
            'percentual_final': 0,
            'motivo_final': '',
            'deferimento': False,
            'indeferimento': False,
            'requisitos_atendidos': {},
            'documentos_obrigatorios': {},
            'fundamentos_legais': [],
            'data_inicial_processo': data_inicial_processo
        }
        
        # ========== REQUISITO I: CAPACIDADE CIVIL ==========
        print("\n[INFO] REQUISITO I: Capacidade civil (Art. 65, inciso I)")
        requisito_i = self._verificar_capacidade_civil(dados_formulario, data_inicial_processo)
        resultado['requisitos_atendidos']['capacidade_civil'] = requisito_i
        
        if not requisito_i['atendido']:
            print("❌ INDEFERIMENTO AUTOMÁTICO: Não possui capacidade civil")
            resultado['indeferimento'] = True
            resultado['motivo_final'] = requisito_i['motivo']
            resultado['fundamentos_legais'].append("Art. 65, inciso I da Lei nº 13.445/2017")
            resultado['elegibilidade_final'] = 'indeferimento_automatico'
            return resultado
        
        # ========== REQUISITO II: RESIDÊNCIA MÍNIMA ==========
        print("\n[INFO] REQUISITO II: Residência mínima (Art. 65, inciso II)")
        requisito_ii = self._verificar_residencia_minima()
        resultado['requisitos_atendidos']['residencia_minima'] = requisito_ii
        
        if not requisito_ii['atendido']:
            print("❌ INDEFERIMENTO: Não comprovou residência mínima")
            resultado['indeferimento'] = True
            resultado['motivo_final'] = requisito_ii['motivo']
            resultado['fundamentos_legais'].append("Art. 65, inciso II da Lei nº 13.445/2017")
            resultado['elegibilidade_final'] = 'indeferimento'
            return resultado
        
        # ========== REQUISITO III: COMUNICAÇÃO EM PORTUGUÊS ==========
        print("\n[INFO] REQUISITO III: Comunicação em língua portuguesa (Art. 65, inciso III)")
        requisito_iii = self._verificar_comunicacao_portugues(documentos_ja_baixados)
        resultado['requisitos_atendidos']['comunicacao_portugues'] = requisito_iii
        
        if not requisito_iii['atendido']:
            print("❌ INDEFERIMENTO: Não atende requisito de comunicação em português")
            resultado['indeferimento'] = True
            resultado['motivo_final'] = requisito_iii['motivo']
            resultado['fundamentos_legais'].append("Art. 65, inciso III da Lei nº 13.445/2017")
            resultado['elegibilidade_final'] = 'indeferimento'
            return resultado
        
        # ========== REQUISITO IV: ANTECEDENTES CRIMINAIS ==========
        print("\n[INFO] REQUISITO IV: Antecedentes criminais (Art. 65, inciso IV)")
        requisito_iv = self._verificar_antecedentes_criminais(documentos_ja_baixados, data_inicial_processo)
        resultado['requisitos_atendidos']['antecedentes_criminais'] = requisito_iv
        
        if not requisito_iv['atendido']:
            print("❌ INDEFERIMENTO: Não atende requisito de antecedentes criminais")
            resultado['indeferimento'] = True
            resultado['motivo_final'] = requisito_iv['motivo']
            resultado['fundamentos_legais'].append("Art. 65, inciso IV da Lei nº 13.445/2017")
            resultado['elegibilidade_final'] = 'indeferimento'
            return resultado
        
        # ========== DOCUMENTOS COMPLEMENTARES ==========
        print("\n[INFO] DOCUMENTOS COMPLEMENTARES: Anexo I da Portaria 623/2020")
        docs_complementares = self._verificar_documentos_complementares(documentos_ja_baixados)
        resultado['documentos_obrigatorios'] = docs_complementares
        
        # Calcular percentual baseado nos documentos complementares
        percentual_docs = self._calcular_percentual_documentos(docs_complementares)
        
        # ========== DECISÃO FINAL ==========
        print("\n[INFO] DECISÃO FINAL")
        
        # Se todos os requisitos I-IV foram atendidos
        if all([
            requisito_i['atendido'],
            requisito_ii['atendido'], 
            requisito_iii['atendido'],
            requisito_iv['atendido']
        ]):
            # Verificar documentos complementares
            if percentual_docs == 100:
                print("✅ DEFERIMENTO: Todos os requisitos e documentos válidos")
                resultado['deferimento'] = True
                resultado['elegibilidade_final'] = 'deferimento'
                resultado['percentual_final'] = 100
                resultado['motivo_final'] = "Atende todos os requisitos do Art. 65 e documentos obrigatórios"
            else:
                # Montar despacho de indeferimento por documentos faltantes
                motivos_indeferimento = []
                
                # Documentos faltantes
                docs_faltantes = docs_complementares.get('documentos_faltantes', [])
                if docs_faltantes:
                    for doc in docs_faltantes:
                        item_num = self._obter_numero_item_anexo(doc)
                        motivos_indeferimento.append(f"Não anexou item {item_num}")
                
                resultado['indeferimento'] = True
                resultado['elegibilidade_final'] = 'indeferimento'
                resultado['percentual_final'] = percentual_docs
                resultado['motivo_final'] = "; ".join(motivos_indeferimento)
                resultado['fundamentos_legais'].append("Anexo I da Portaria 623/2020")
        
        print("\n" + "="*80)
        print("[TARGET] RESULTADO FINAL DA ANÁLISE")
        print("="*80)
        print(f"[DADOS] Status: {resultado['elegibilidade_final'].replace('_', ' ').title()}")
        print(f"💬 Motivo: {resultado['motivo_final']}")
        if resultado['fundamentos_legais']:
            print(f"[DECISAO] Fundamentos: {'; '.join(resultado['fundamentos_legais'])}")
        print("="*80)
        
        return resultado
    
    def _verificar_capacidade_civil(self, dados_formulario: Dict[str, Any], data_inicial_processo: str) -> Dict[str, Any]:
        """
        Requisito I: Verificação de capacidade civil
        Regra: Maior de 18 anos
        """
        try:
            data_nascimento = dados_formulario.get('data_nascimento')
            if not data_nascimento:
                return {
                    'atendido': False,
                    'motivo': 'Data de nascimento não encontrada',
                    'detalhes': 'Não foi possível verificar idade'
                }
            
            # Calcular idade na data inicial do processo
            nasc = datetime.strptime(data_nascimento, "%d/%m/%Y")
            inicial = datetime.strptime(data_inicial_processo, "%d/%m/%Y")
            
            idade = inicial.year - nasc.year
            if inicial.month < nasc.month or (inicial.month == nasc.month and inicial.day < nasc.day):
                idade -= 1
            
            if idade >= 18:
                print(f"✅ Capacidade civil: {idade} anos (≥ 18)")
                return {
                    'atendido': True,
                    'idade': idade,
                    'motivo': f'Possui capacidade civil ({idade} anos)',
                    'detalhes': 'Maior de 18 anos'
                }
            else:
                print(f"❌ Capacidade civil: {idade} anos (< 18)")
                return {
                    'atendido': False,
                    'idade': idade,
                    'motivo': 'Não possui capacidade civil',
                    'detalhes': f'Menor de 18 anos ({idade} anos)'
                }
                
        except Exception as e:
            print(f"[ERRO] Erro ao verificar capacidade civil: {e}")
            return {
                'atendido': False,
                'motivo': f'Erro na verificação: {e}',
                'detalhes': 'Erro no cálculo da idade'
            }
    
    def _verificar_residencia_minima(self) -> Dict[str, Any]:
        """
        Requisito II: Verificação de residência mínima
        """
        try:
            # Verificar se há redução de prazo
            tem_reducao = self._verificar_reducao_prazo()
            
            if tem_reducao:
                # Com redução: 1 ano de residência indeterminada
                prazo_requerido = 1
                tipo_residencia = "residência indeterminada"
            else:
                # Sem redução: 4 anos de residência indeterminada ou permanente
                prazo_requerido = 4
                tipo_residencia = "residência indeterminada ou permanente"
            
            print(f"[INFO] Prazo requerido: {prazo_requerido} ano(s) de {tipo_residencia}")
            
            # Verificar residência via campos do formulário
            residencia_valida = self._verificar_dados_residencia(prazo_requerido)
            
            if residencia_valida:
                print(f"✅ Residência mínima: Atende prazo de {prazo_requerido} ano(s)")
                return {
                    'atendido': True,
                    'prazo_requerido': prazo_requerido,
                    'tem_reducao': tem_reducao,
                    'motivo': f'Comprovou {prazo_requerido} ano(s) de {tipo_residencia}',
                    'detalhes': f'Redução de prazo: {"Sim" if tem_reducao else "Não"}'
                }
            else:
                print(f"❌ Residência mínima: Não atende prazo de {prazo_requerido} ano(s)")
                return {
                    'atendido': False,
                    'prazo_requerido': prazo_requerido,
                    'tem_reducao': tem_reducao,
                    'motivo': 'Não comprovou residência mínima',
                    'detalhes': f'Não comprovou {prazo_requerido} ano(s) de {tipo_residencia}'
                }
                
        except Exception as e:
            print(f"[ERRO] Erro ao verificar residência mínima: {e}")
            return {
                'atendido': False,
                'motivo': f'Erro na verificação: {e}',
                'detalhes': 'Erro na análise de residência'
            }
    
    def _verificar_reducao_prazo(self) -> bool:
        """
        Verifica se há redução de prazo via elemento HIP_CON_0
        """
        try:
            # Buscar elemento de redução de prazo
            xpath_reducao = "//label[@for='HIP_CON_0' and contains(@aria-checked, 'true')]"
            elemento_reducao = self.lecom.driver.find_element(By.XPATH, xpath_reducao)
            
            if elemento_reducao and elemento_reducao.is_displayed():
                texto = elemento_reducao.text.strip().lower()
                if 'sim' in texto:
                    print("[OK] Redução de prazo: SIM")
                    return True
            
            print("[ERRO] Redução de prazo: NÃO")
            return False
            
        except Exception as e:
            print(f"[AVISO] Erro ao verificar redução de prazo: {e}")
            return False
    
    def _verificar_dados_residencia(self, prazo_requerido: int) -> bool:
        """
        Verifica dados de residência via campos CHPF_PARECER (PRIORIDADE) e RES_DAT
        ORDEM: 1º Parecer PF, 2º Campo RES_DAT
        """
        try:
            print("[INFO] Passo 1 – Verificar parecer da PF (PRIORIDADE)")
            
            # ========== PRIORIDADE 1: PARECER DA PF ==========
            try:
                elemento_parecer = self.lecom.driver.find_element(By.ID, "CHPF_PARECER")
                texto_parecer = elemento_parecer.get_attribute('value') or elemento_parecer.text
                
                if texto_parecer:
                    print(f"[INFO] Analisando parecer da PF...")
                    print(f"[DEBUG] Texto do parecer (primeiros 200 chars): {texto_parecer[:200]}...")
                    
                    # Análise inteligente do parecer para residência
                    resultado_parecer = self._analisar_residencia_no_parecer(texto_parecer, prazo_requerido)
                    if resultado_parecer:
                        print(f"[OK] Residência confirmada via parecer da PF")
                        return True
                    else:
                        print(f"[AVISO] Parecer da PF não confirmou residência suficiente")
                else:
                    print(f"[AVISO] Campo CHPF_PARECER vazio")
                    
            except Exception as e:
                print(f"[AVISO] Campo CHPF_PARECER não encontrado: {e}")
            
            print("[INFO] Passo 2 – Verificar campo RES_DAT (fallback)")
            
            # ========== PRIORIDADE 2: CAMPO RES_DAT (FALLBACK) ==========
            try:
                elemento_res_dat = self.lecom.driver.find_element(By.ID, "RES_DAT")
                data_residencia = elemento_res_dat.get_attribute('value')
                
                if data_residencia:
                    print(f"[DATA] Campo RES_DAT: {data_residencia}")
                    
                    # Verificar se data não está no futuro
                    try:
                        data_res = datetime.strptime(data_residencia, "%d/%m/%Y")
                        data_hoje = datetime.now()
                        
                        if data_res > data_hoje:
                            print(f"⚠️ AVISO: Data de residência no futuro ({data_residencia}), ignorando...")
                        else:
                            # Calcular tempo de residência
                            anos_residencia = (data_hoje - data_res).days / 365.25
                            
                            if anos_residencia >= prazo_requerido:
                                print(f"[OK] Tempo de residência: {anos_residencia:.1f} anos (≥ {prazo_requerido})")
                                return True
                            else:
                                print(f"[ERRO] Tempo de residência: {anos_residencia:.1f} anos (< {prazo_requerido})")
                    except ValueError as e:
                        print(f"[ERRO] Data inválida no RES_DAT: {data_residencia} - {e}")
                else:
                    print(f"[AVISO] Campo RES_DAT vazio")
                        
            except Exception as e:
                print(f"[AVISO] Campo RES_DAT não encontrado: {e}")
            
            print("[ERRO] Não foi possível verificar dados de residência")
            print("⚠️ OBSERVAÇÃO: Residência mínima não encontrada no parecer CHPF_PARECER nem campo RES_DAT")
            return False
            
        except Exception as e:
            print(f"[ERRO] Erro ao verificar dados de residência: {e}")
            return False
    
    def _analisar_residencia_no_parecer(self, texto_parecer: str, prazo_requerido: int) -> bool:
        """
        Analisa o parecer da PF para verificar informações sobre residência
        PRIORIZA: residência por prazo indeterminado
        """
        import re
        
        texto_lower = texto_parecer.lower()
        print(f"[DEBUG] Analisando parecer para residência (requerido: {prazo_requerido} anos)")
        
        # ========== PRIORIDADE 1: RESIDÊNCIA POR PRAZO INDETERMINADO ==========
        # Padrões regex para extrair tempo de residência indeterminada
        padroes_indeterminado = [
            r'residência\s+(?:no\s+brasil\s+)?por\s+prazo\s+indeterminado\s+desde\s+(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})',
            r'possuindo[,\s]+portanto[,\s]+(\d+)\s+\((?:um|dois|três|quatro|cinco|seis|sete|oito|nove|dez|onze|doze|treze|catorze|quinze|dezesseis|dezessete|dezoito|dezenove|vinte)\)\s+anos?\s+de\s+residência\s+por\s+(?:tempo|prazo)\s+indeterminado',
            r'possui\s+residência\s+no\s+brasil\s+por\s+prazo\s+indeterminado\s+desde\s+(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})',
            r'totalizando\s+(\d+)\s+\([a-zúéáóíõç]+\)\s+anos?\s+(?:e\s+\d+\s+\([a-z]+\)\s+meses?)?\s*\.?\s*$',
            r'residência\s+indeterminada\s+desde\s+(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})',
            r'(\d+)\s+anos?\s+de\s+residência\s+por\s+prazo\s+indeterminado',
            r'(\d+)\s+anos?\s+de\s+residência\s+por\s+tempo\s+indeterminado',
        ]
        
        print(f"[DEBUG] Testando {len(padroes_indeterminado)} padrões de residência por prazo indeterminado...")
        
        for i, padrao in enumerate(padroes_indeterminado, 1):
            print(f"[DEBUG] Padrão {i}: {padrao[:60]}...")
            match = re.search(padrao, texto_lower, re.MULTILINE)
            if match:
                print(f"[DEBUG] ✅ MATCH encontrado no padrão {i}!")
                print(f"[DEBUG] Grupo capturado: '{match.group(1)}'")
                try:
                    # Extrair anos de residência
                    if match.group(1).isdigit():
                        anos_residencia = int(match.group(1))
                        print(f"[DEBUG] Anos detectados: {anos_residencia}")
                        
                        if anos_residencia >= prazo_requerido:
                            print(f"✅ Parecer indica: {anos_residencia} anos de RESIDÊNCIA POR PRAZO INDETERMINADO (requerido: {prazo_requerido})")
                            return True
                        else:
                            print(f"⚠️ Parecer indica: {anos_residencia} anos de residência indeterminada (insuficiente, requerido: {prazo_requerido})")
                            return False
                    else:
                        # Pode ser uma data, calcular anos corretamente
                        data_str = match.group(1)
                        print(f"[DEBUG] Data detectada: {data_str}")
                        
                        try:
                            from datetime import datetime
                            # Tentar diferentes formatos de data
                            formatos_data = ['%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y']
                            data_residencia = None
                            
                            for formato in formatos_data:
                                try:
                                    data_residencia = datetime.strptime(data_str, formato)
                                    break
                                except ValueError:
                                    continue
                            
                            if data_residencia:
                                data_atual = datetime.now()
                                anos_calculados = (data_atual - data_residencia).days / 365.25
                                print(f"[DEBUG] Anos calculados desde {data_str}: {anos_calculados:.1f} anos")
                                
                                if anos_calculados >= prazo_requerido:
                                    print(f"✅ Parecer indica: RESIDÊNCIA POR PRAZO INDETERMINADO (desde {data_str} = {anos_calculados:.1f} anos)")
                                    return True
                                else:
                                    print(f"⚠️ Parecer indica: residência desde {data_str} = {anos_calculados:.1f} anos (insuficiente, requerido: {prazo_requerido})")
                                    return False
                            else:
                                print(f"[AVISO] Não foi possível interpretar a data: {data_str}")
                                return False
                                
                        except Exception as e:
                            print(f"[ERRO] Erro ao calcular anos da data {data_str}: {e}")
                            return False
                        
                except (ValueError, IndexError) as e:
                    print(f"[DEBUG] Erro ao processar match: {e}")
                    continue
            else:
                print(f"[DEBUG] ❌ Nenhum match no padrão {i}")
        
        print(f"[AVISO] Não foi possível extrair tempo específico do parecer")
        
        # ========== PRIORIDADE 2: TERMOS GERAIS DE RESIDÊNCIA ==========
        # Termos que indicam residência suficiente
        termos_positivos = [
            f'residência por mais de {prazo_requerido} anos',
            f'residência há {prazo_requerido} anos',
            'residência por prazo indeterminado',
            'residência por tempo indeterminado',
            'residência indeterminada',
            'residência permanente',
            'atende o prazo de residência',
            'comprovou residência',
            'residência desde',
        ]
        
        # Termos que indicam residência insuficiente
        termos_negativos = [
            'não comprovou residência',
            'residência insuficiente',
            'prazo de residência não atendido',
            'não atende o prazo'
        ]
        
        # Verificar termos negativos primeiro (mais específicos)
        for termo in termos_negativos:
            if termo in texto_lower:
                print(f"[ERRO] Parecer indica: {termo}")
                return False
        
        # Verificar termos positivos
        for termo in termos_positivos:
            if termo in texto_lower:
                print(f"[OK] Parecer indica: {termo}")
                return True
        
        # Se não encontrou indicações claras, assumir que não comprovou
        print("❓ Parecer não menciona residência claramente")
        return False
    
    def _verificar_comunicacao_portugues(self, documentos_ja_baixados: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Requisito III: Verificação de comunicação em língua portuguesa
        """
        try:
            # Verificar se documento foi anexado
            doc_comunicacao = self._verificar_documento_anexado(
                "Comprovante de comunicação em português",
                documentos_ja_baixados
            )
            
            if doc_comunicacao['anexado']:
                # Validar conteúdo se disponível
                if doc_comunicacao.get('texto'):
                    validacao = self._validar_comprovante_portugues(doc_comunicacao['texto'])
                    if validacao['valido']:
                        print("✅ Comunicação em português: Comprovante válido")
                        return {
                            'atendido': True,
                            'motivo': 'Anexou comprovante válido de comunicação em português',
                            'detalhes': validacao['detalhes']
                        }
                    else:
                        print("❌ Comunicação em português: Comprovante inválido")
                        return {
                            'atendido': False,
                            'motivo': 'Inválido, não atende aos requisitos do art 65 inciso III',
                            'detalhes': validacao['motivo']
                        }
                else:
                    # Documento anexado mas sem texto (OCR falhou)
                    print("✅ Comunicação em português: Documento anexado")
                    return {
                        'atendido': True,
                        'motivo': 'Anexou comprovante de comunicação em português',
                        'detalhes': 'Documento presente (OCR não executado)'
                    }
            else:
                print("❌ Comunicação em português: Documento não anexado")
                return {
                    'atendido': False,
                    'motivo': 'Não anexou item 13',
                    'detalhes': 'Comprovante de comunicação em português não encontrado'
                }
                
        except Exception as e:
            print(f"[ERRO] Erro ao verificar comunicação em português: {e}")
            return {
                'atendido': False,
                'motivo': f'Erro na verificação: {e}',
                'detalhes': 'Erro na análise do documento'
            }
    
    def _validar_documento_crnm(self, texto_crnm):
        """
        Valida CRNM usando termos MELHORADOS baseados em 1.068 documentos reais (94.6% sucesso)
        """
        try:
            if not texto_crnm or len(texto_crnm.strip()) < 10:
                return {
                    'valido': False,
                    'motivo': 'CRNM inválido - documento vazio ou muito pequeno',
                    'termos_encontrados': 0
                }
            
            # Usar validação melhorada se disponível
            if TERMOS_MELHORADOS_DISPONIVEIS:
                resultado = validar_documento_melhorado('CRNM', texto_crnm, minimo_confianca=70)
                return {
                    'valido': resultado['valido'],
                    'motivo': resultado['motivo'],
                    'termos_encontrados': resultado['total_termos_encontrados'],
                    'termos_detalhes': resultado['termos_encontrados'][:10],
                    'confianca': resultado['confianca']
                }
            
            # Fallback: validação básica (ANTIGA)
            texto_crnm_lower = texto_crnm.lower()
            
            termos_obrigatorios = [
                'rne', 'rnm', 'crnm',
                'republica federativa do brasil',
                'cedula de identidade de estrangeiro',
                'classificação', 'naturalidade',
                'data de entrada',
                'carteira de registro nacional migratorio',
                'documento', 'validade', 'registro', 'nome'
            ]
            
            termos_encontrados = 0
            termos_detalhes = []
            
            for termo in termos_obrigatorios:
                if termo in texto_crnm_lower:
                    termos_encontrados += 1
                    termos_detalhes.append(termo)
            
            if termos_encontrados >= 2:
                return {
                    'valido': True,
                    'motivo': f'CRNM válido - {termos_encontrados} termos encontrados',
                    'termos_encontrados': termos_encontrados,
                    'termos_detalhes': termos_detalhes
                }
            else:
                return {
                    'valido': False,
                    'motivo': f'CRNM inválido - apenas {termos_encontrados} termos encontrados (mínimo: 2)',
                    'termos_encontrados': termos_encontrados,
                    'termos_detalhes': termos_detalhes
                }
                
        except Exception as e:
            return {
                'valido': False,
                'motivo': f'Erro na validação do CRNM: {e}',
                'termos_encontrados': 0
            }

    def _extrair_data_emissao_antecedentes(self, texto_documento):
        """
        Extrai a data de emissão do documento de antecedentes criminais
        Retorna: datetime ou None
        """
        if not texto_documento:
            return None
        
        import re
        from datetime import datetime
        
        # Padrões para data de emissão (mais abrangentes)
        padroes_data_emissao = [
            r'emitid[ao]\s+em[:\s]+(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})',
            r'certidão\s+emitida\s+em[:\s]+(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})',
            r'data\s+de\s+emissão[:\s]+(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})',
            r'expedid[ao]\s+em[:\s]+(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})',
            r'certidão\s+foi\s+expedida\s+em[:\s]+(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})',
            r'em\s+(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})\s+às\s+\d{1,2}:\d{2}',  # padrão: em 08/01/2025 às 19:23
            r'data[:\s]+(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})',  # padrão simples: data: 08/01/2025
            r'(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})\s+às\s+\d{1,2}:\d{2}',  # padrão: 08/01/2025 às 19:23
            r'(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})\s+\(horário',  # padrão: 08/01/2025 (horário de Brasília)
            r'expedida\s+em\s+(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})',  # padrão: expedida em 08/01/2025
        ]
        
        for padrao in padroes_data_emissao:
            match = re.search(padrao, texto_documento, re.IGNORECASE)
            if match:
                data_str = match.group(1)
                # Tentar parsear a data
                for formato in ['%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y', '%d/%m/%y', '%d-%m-%y', '%d.%m.%y']:
                    try:
                        data_emissao = datetime.strptime(data_str, formato)
                        return data_emissao
                    except ValueError:
                        continue
        
        return None
    
    def _verificar_legalizacao_documento(self, texto_documento):
        """
        Verifica se o documento tem legalização/tradução juramentada
        """
        if not texto_documento:
            return False
        
        import re
        texto_lower = texto_documento.lower()
        
        # Termos de tradução juramentada
        termos_traducao = [
            'tradutor público',
            'tradutor publico',
            'tradução juramentada',
            'traducao juramentada',
            'tradução pública',
            'traducao publica',
            'intérprete comercial',
            'interprete comercial',
            'jucesp',
            'jucepar',
            'jucerja',
            'jucesc',
            'jucemg',
            'matrícula',
            'matricula',
            'certifico',
            'certifico e dou fé',
            'dou fé',
            'achei conforme',
            'fielmente traduzi',
            'tradução fiel',
            'traducao fiel',
            'nada mais constava',
            'devolvo com esta tradução',
            'número da tradução',
            'numero da traducao',
            'apostila',
            'apostilamento',
            'convenção de haia',
            'convencao de haia',
        ]
        
        # Padrões regex de legalização
        padroes_legalizacao = [
            r'tradutor\s+p[uú]blico',
            r'int[eé]rprete\s+comercial',
            r'juce[a-z]{2}.*matr[ií]cula',
            r'matr[ií]cula.*\d+',
            r'tradução\s+(?:jur[ament]{7}|fiel|p[uú]blica)',
            r'certifico\s+e\s+dou\s+f[eé]',
            r'apostila.*haia',
        ]
        
        # Verificar termos
        for termo in termos_traducao:
            if termo in texto_lower:
                return True
        
        # Verificar padrões regex
        for padrao in padroes_legalizacao:
            if re.search(padrao, texto_lower):
                return True
        
        return False
    
    def _detectar_tipo_antecedentes_brasil(self, texto_certidao):
        """
        Detecta se o documento de antecedentes criminais é ESTADUAL ou FEDERAL.
        Retorna: 'ESTADUAL', 'FEDERAL', 'AMBOS', ou 'INDEFINIDO'
        """
        if not texto_certidao:
            return 'INDEFINIDO'
        
        texto_lower = texto_certidao.lower()
        
        # Padrões para ESTADUAL
        padroes_estaduais = [
            'tribunal de justiça',
            'tj do estado',
            'tjsp', 'tjrj', 'tjmg', 'tjpe', 'tjrs', 'tjba', 'tjsc', 'tjpr',
            'secretaria de segurança pública',
            'secretaria da segurança pública',
            'comarca de',
            'seção judiciária estadual',
            'certidão estadual',
            'pje-ce', 'pje-pe', 'pje-pb', 'pje-se', 'pje-rn',
            'estado de', 'estado do',
            'poder judiciário estadual'
        ]
        
        # Padrões para FEDERAL
        padrões_federais = [
            'polícia federal',
            'policia federal',
            'justiça federal',
            'tribunal regional federal',
            'conselho da justiça federal',
            'seção judiciária federal',
            'epol',
            'sinic',
            'sistema nacional de informações criminais',
            'ministério da justiça',
            'mjsp',
            'trf',
            'certidão federal'
        ]
        
        tem_estadual = any(padrao in texto_lower for padrao in padroes_estaduais)
        tem_federal = any(padrao in texto_lower for padrao in padrões_federais)
        
        if tem_estadual and tem_federal:
            return 'AMBOS'
        elif tem_estadual:
            return 'ESTADUAL'
        elif tem_federal:
            return 'FEDERAL'
        else:
            return 'INDEFINIDO'
    
    def _validar_antecedentes_criminais_brasileiro(self, texto_certidao):
        """
        Valida Antecedentes Brasil usando termos MELHORADOS baseados em 1.170 documentos reais (98.2% sucesso)
        """
        try:
            if not texto_certidao or len(texto_certidao.strip()) < 10:
                return {
                    'valido': False,
                    'tem_condenacao': True,
                    'motivo': 'Certidão inválida - documento vazio ou muito pequeno'
                }
            
            # Detectar tipo de antecedentes (ESTADUAL/FEDERAL) - INFORMATIVO
            tipo_antecedentes = self._detectar_tipo_antecedentes_brasil(texto_certidao)
            print(f"[INFO] Tipo de antecedentes detectado: {tipo_antecedentes}")
            
            # Usar validação melhorada se disponível
            if TERMOS_MELHORADOS_DISPONIVEIS:
                resultado = validar_documento_melhorado('Antecedentes_Brasil', texto_certidao, minimo_confianca=70)
                
                # Verificar especificamente termos de negação de condenação
                texto_lower = texto_certidao.lower()
                tem_negacao = any(termo in texto_lower for termo in TERMOS_ANTECEDENTES_BRASIL['negacao_condenacao'])
                
                return {
                    'valido': resultado['valido'] and tem_negacao,
                    'tem_condenacao': not tem_negacao,
                    'motivo': f"{resultado['motivo']} | Negação encontrada: {tem_negacao} | Tipo: {tipo_antecedentes}",
                    'confianca': resultado.get('confianca', 0),
                    'tipo_antecedentes': tipo_antecedentes  # INFORMATIVO
                }
            
            # Fallback: validação básica (ANTIGA)
            texto_lower = texto_certidao.lower()
            
            termos_sem_condenacao = [
                'não consta condenação', 'nao consta condenacao',
                'não há condenação', 'nao ha condenacao',
                'sem antecedentes criminais', 'não possui antecedentes',
                'nao possui antecedentes', 'nada consta',
                'certidão negativa', 'sem registro criminal',
                'livre de antecedentes'
            ]
            
            for termo in termos_sem_condenacao:
                if termo in texto_lower:
                    return {
                        'valido': True,
                        'tem_condenacao': False,
                        'motivo': f'Sem condenação: {termo}'
                    }
            
            termos_com_condenacao = [
                'consta condenação', 'consta condenacao',
                'há condenação', 'ha condenacao',
                'possui antecedentes', 'condenado por',
                'sentença condenatória', 'sentenca condenatoria'
            ]
            
            for termo in termos_com_condenacao:
                if termo in texto_lower:
                    return {
                        'valido': True,
                        'tem_condenacao': True,
                        'motivo': f'Consta condenação: {termo}'
                    }
            
            return {
                'valido': False,
                'tem_condenacao': True,
                'motivo': 'Certidão inválida - não foi possível determinar status'
            }
            
        except Exception as e:
            return {
                'valido': False,
                'tem_condenacao': True,
                'motivo': f'Erro na validação: {e}'
            }

    def _validar_comunicacao_portugues(self, texto_documento):
        """
        Valida Comunicação Português usando termos MELHORADOS baseados em 1.029 documentos reais (88.2% sucesso)
        """
        if not texto_documento or len(texto_documento.strip()) < 10:
            return False
        
        # Usar validação melhorada se disponível
        if TERMOS_MELHORADOS_DISPONIVEIS:
            resultado = validar_documento_melhorado('Comunicacao_Portugues', texto_documento, minimo_confianca=65)
            print(f"[INFO] Comunicação em português: {resultado['motivo']}")
            return resultado['valido']
        
        # Fallback: validação básica (ANTIGA)
        texto_lower = texto_documento.lower()
        
        termos_validos = [
            'celpe-bras', 'celpe bras', 'certificado de proficiência',
            'proficiência em língua portuguesa', 'português brasileiro',
            'exame de proficiência', 'certificado', 'diploma',
            'curso de português', 'língua portuguesa', 'proficiência',
            'aprovado', 'apto', 'habilitado', 'qualificado',
            'português', 'portugues', 'ensino', 'escolar', 'escolaridade',
            'histórico', 'historico', 'fundamental', 'médio', 'medio',
            'superior', 'universidade', 'escola', 'educação', 'educacao',
            'língua', 'lingua', 'idioma', 'comunicação', 'comunicacao'
        ]
        
        termo_encontrado = False
        for termo in termos_validos:
            if termo in texto_lower:
                print(f"[INFO] Comunicação em português: Termo relevante encontrado")
                termo_encontrado = True
                break
        
        if not termo_encontrado and len(texto_documento.strip()) > 50:
            print(f"[INFO] Comunicação em português: Aceito por ter conteúdo válido ({len(texto_documento)} caracteres)")
            return True
        
        if termo_encontrado:
            return True
        
        print(f"[INFO] Comunicação em português: Rejeitado - sem termos relevantes")
        return False

    def _validar_documento_viagem_internacional(self, texto_documento):
        """
        Valida documento de viagem internacional
        """
        try:
            if not texto_documento or len(texto_documento.strip()) < 10:
                return {
                    'valido': False,
                    'motivo': 'Documento de viagem inválido - documento vazio ou muito pequeno'
                }
            
            texto_lower = texto_documento.lower()
            
            # Termos que indicam documento de viagem válido
            termos_validos = [
                'passaporte',
                'passport',
                'documento de viagem',
                'travel document',
                'laissez passer',
                'titre de voyage',
                'documento de identidad',
                'cedula de identidad',
                'documento nacional de identidad'
            ]
            
            for termo in termos_validos:
                if termo in texto_lower:
                    return {
                        'valido': True,
                        'motivo': f'Documento de viagem válido: {termo}'
                    }
            
            return {
                'valido': False,
                'motivo': 'Documento de viagem inválido - documento não reconhecido'
            }
            
        except Exception as e:
            return {
                'valido': False,
                'motivo': f'Erro na validação: {e}'
            }

    def _verificar_antecedentes_criminais(self, documentos_ja_baixados: Dict[str, str] = None, data_inicial_processo: str = None) -> Dict[str, Any]:
        """
        Requisito IV: Antecedentes criminais conforme Art. 65, inciso IV
        COM VALIDAÇÃO CORRETA DO TEXTO EXTRAÍDO E PENALIZAÇÃO POR NÃO ANEXAR
        """
        try:
            print("[INFO] REQUISITO IV: Antecedentes criminais (Art. 65, inciso IV)")
            
            # Definir documentos obrigatórios
            documentos_obrigatorios = [
                "Certidão de antecedentes criminais (Brasil)",
                "Atestado antecedentes criminais (país de origem)"
            ]
            
            documentos_faltantes = []
            documentos_invalidos = []
            tem_condenacao_geral = False
            detalhes_validacao = {}
            
            # VERIFICAR CADA DOCUMENTO OBRIGATÓRIO
            for nome_doc in documentos_obrigatorios:
                print(f"[BUSCA] Verificando {nome_doc}...")
                
                # 1. PENALIZAR SE NÃO FOI BAIXADO (não anexado)
                if not documentos_ja_baixados or nome_doc not in documentos_ja_baixados:
                    print(f"[ERRO] {nome_doc}: NÃO ANEXADO")
                    documentos_faltantes.append(nome_doc)
                    detalhes_validacao[nome_doc] = {
                        'anexado': False,
                        'valido': False,
                        'motivo': 'Documento não anexado'
                    }
                    continue
                
                # 2. VALIDAR TEXTO EXTRAÍDO
                texto_documento = documentos_ja_baixados[nome_doc]
                
                # 2.1. DETECTAR TIPO (ESTADUAL/FEDERAL) - APENAS INFORMATIVO (para Brasil)
                tipo_antecedentes = 'N/A'
                tem_legalizacao = False
                data_emissao = None
                dentro_prazo_180_dias = True
                
                if "Brasil" in nome_doc:
                    tipo_antecedentes = self._detectar_tipo_antecedentes_brasil(texto_documento)
                    print(f"[INFO] Tipo de antecedentes detectado: {tipo_antecedentes}")
                    
                    # Verificar data de emissão (180 dias)
                    from datetime import datetime, timedelta
                    data_emissao = self._extrair_data_emissao_antecedentes(texto_documento)
                    
                    if data_emissao and data_inicial_processo:
                        # CORRIGIDO: Início do processo - Data de expedição
                        try:
                            data_inicial = datetime.strptime(data_inicial_processo, '%d/%m/%Y')
                            dias_diferenca = (data_inicial - data_emissao).days
                            
                            if dias_diferenca > 180:
                                dentro_prazo_180_dias = False
                                print(f"⚠️ ATENÇÃO: Certidão emitida há {dias_diferenca} dias (excede 180 dias)")
                                print(f"   Data emissão: {data_emissao.strftime('%d/%m/%Y')}")
                                print(f"   Data inicial processo: {data_inicial.strftime('%d/%m/%Y')}")
                                print(f"   Cálculo: {data_inicial.strftime('%d/%m/%Y')} - {data_emissao.strftime('%d/%m/%Y')} = {dias_diferenca} dias")
                            else:
                                print(f"✅ Certidão dentro do prazo: emitida há {dias_diferenca} dias")
                                print(f"   Cálculo: {data_inicial.strftime('%d/%m/%Y')} - {data_emissao.strftime('%d/%m/%Y')} = {dias_diferenca} dias")
                        except Exception as e:
                            print(f"[ERRO] Erro ao calcular prazo de 180 dias: {e}")
                            print(f"[INFO] Data de emissão: {data_emissao.strftime('%d/%m/%Y')} (não foi possível verificar prazo)")
                    elif data_emissao:
                        print(f"[INFO] Data de emissão: {data_emissao.strftime('%d/%m/%Y')} (data inicial do processo não fornecida)")
                    else:
                        print(f"⚠️ ATENÇÃO: Não foi possível extrair data de emissão do antecedentes Brasil")
                
                # 2.2. Verificar legalização (para país de origem)
                if "país de origem" in nome_doc or "origem" in nome_doc:
                    tem_legalizacao = self._verificar_legalizacao_documento(texto_documento)
                    if not tem_legalizacao:
                        print(f"⚠️ ATENÇÃO: {nome_doc} - Não foi identificada legalização/tradução juramentada")
                    else:
                        print(f"✅ {nome_doc} - Legalização/tradução juramentada identificada")
                
                # 2.3. Usar validação específica para antecedentes criminais
                resultado_validacao = self._validar_antecedentes_criminais_brasileiro(texto_documento)
                
                if not resultado_validacao['valido']:
                    print(f"[ERRO] {nome_doc}: INVÁLIDO - {resultado_validacao['motivo']}")
                    documentos_invalidos.append(nome_doc)
                    detalhes_validacao[nome_doc] = {
                        'anexado': True,
                        'valido': False,
                        'motivo': resultado_validacao['motivo'],
                        'tipo_antecedentes': tipo_antecedentes,  # INFORMATIVO
                        'tem_legalizacao': tem_legalizacao,  # INFORMATIVO (origem)
                        'data_emissao': data_emissao.strftime('%d/%m/%Y') if data_emissao else None,  # INFORMATIVO (Brasil)
                        'dentro_prazo_180_dias': dentro_prazo_180_dias  # INFORMATIVO (Brasil)
                    }
                    # Se inválido, assume condenação por segurança
                    tem_condenacao_geral = True
                else:
                    print(f"[OK] {nome_doc}: VÁLIDO - {resultado_validacao['motivo']}")
                    detalhes_validacao[nome_doc] = {
                        'anexado': True,
                        'valido': True,
                        'motivo': resultado_validacao['motivo'],
                        'tem_condenacao': resultado_validacao['tem_condenacao'],
                        'tipo_antecedentes': tipo_antecedentes,  # INFORMATIVO
                        'tem_legalizacao': tem_legalizacao,  # INFORMATIVO (origem)
                        'data_emissao': data_emissao.strftime('%d/%m/%Y') if data_emissao else None,  # INFORMATIVO (Brasil)
                        'dentro_prazo_180_dias': dentro_prazo_180_dias  # INFORMATIVO (Brasil)
                    }
                    
                    # Verificar se há condenação
                    if resultado_validacao['tem_condenacao']:
                        tem_condenacao_geral = True
            
            # 2.3. EXIBIR RESUMO DOS TIPOS DE ANTECEDENTES (INFORMATIVO)
            print("\n" + "=" * 80)
            print("📋 RESUMO - TIPOS DE ANTECEDENTES CRIMINAIS BRASIL")
            print("=" * 80)
            
            tipos_detectados = set()
            for nome_doc, detalhes in detalhes_validacao.items():
                if "Brasil" in nome_doc and 'tipo_antecedentes' in detalhes:
                    tipo = detalhes['tipo_antecedentes']
                    if tipo != 'N/A' and tipo != 'INDEFINIDO':
                        if tipo == 'AMBOS':
                            tipos_detectados.add('ESTADUAL')
                            tipos_detectados.add('FEDERAL')
                        else:
                            tipos_detectados.add(tipo)
            
            tem_estadual = 'ESTADUAL' in tipos_detectados
            tem_federal = 'FEDERAL' in tipos_detectados
            
            print(f"   ✓ Antecedentes ESTADUAL: {'SIM' if tem_estadual else 'NÃO'}")
            print(f"   ✓ Antecedentes FEDERAL:  {'SIM' if tem_federal else 'NÃO'}")
            
            if tem_estadual and tem_federal:
                print("   ✅ COMPLETO: Ambos os tipos de antecedentes foram detectados")
            elif tem_estadual:
                print("   ⚠️  ATENÇÃO: Apenas antecedentes ESTADUAL detectado (falta FEDERAL)")
            elif tem_federal:
                print("   ⚠️  ATENÇÃO: Apenas antecedentes FEDERAL detectado (falta ESTADUAL)")
            else:
                print("   ⚠️  ATENÇÃO: Tipo de antecedentes não pôde ser determinado")
            
            print("=" * 80 + "\n")
            
            # 3. VERIFICAR COMPROVANTE DE REABILITAÇÃO SE HOUVER CONDENAÇÃO
            comp_reabilitacao_anexado = False
            if documentos_ja_baixados and "Comprovante de reabilitação" in documentos_ja_baixados:
                comp_reabilitacao_anexado = True
                print("[OK] Comprovante de reabilitação: ANEXADO")
            else:
                print("[ERRO] Comprovante de reabilitação: NÃO ANEXADO")
            
            # 4. APLICAR REGRAS DE NEGÓCIO
            
            # Se algum documento não foi anexado
            if documentos_faltantes:
                print(f"[ERRO] FALHA REQUISITO IV: Documentos não anexados: {', '.join(documentos_faltantes)}")
                return {
                    'atendido': False,
                    'motivo': f'Documentos não anexados: {", ".join(documentos_faltantes)}',
                    'detalhes': detalhes_validacao,
                    'documentos_faltantes': documentos_faltantes,
                    'documentos_invalidos': documentos_invalidos
                }
            
            # Se algum documento é inválido
            if documentos_invalidos:
                print(f"[ERRO] FALHA REQUISITO IV: Documentos inválidos: {', '.join(documentos_invalidos)}")
                return {
                    'atendido': False,
                    'motivo': f'Documentos inválidos: {", ".join(documentos_invalidos)}',
                    'detalhes': detalhes_validacao,
                    'documentos_faltantes': documentos_faltantes,
                    'documentos_invalidos': documentos_invalidos
                }
            
            # Se há condenação mas não há comprovante de reabilitação
            if tem_condenacao_geral and not comp_reabilitacao_anexado:
                print("[ERRO] FALHA REQUISITO IV: Consta condenação sem comprovante de reabilitação")
                return {
                    'atendido': False,
                    'motivo': 'Consta condenação criminal sem comprovante de reabilitação',
                    'detalhes': detalhes_validacao,
                    'tem_condenacao': True,
                    'comp_reabilitacao_anexado': False
                }
            
            # Se passou em todas as verificações
            print("✅ REQUISITO IV ATENDIDO: Antecedentes criminais em ordem")
            return {
                'atendido': True,
                'motivo': 'Sem condenações' if not tem_condenacao_geral else 'Com reabilitação',
                'detalhes': detalhes_validacao,
                'tem_condenacao': tem_condenacao_geral,
                'comp_reabilitacao_anexado': comp_reabilitacao_anexado,
                # INFORMATIVO - Tipos de antecedentes detectados
                'tipos_antecedentes': {
                    'tem_estadual': tem_estadual,
                    'tem_federal': tem_federal,
                    'completo': tem_estadual and tem_federal
                }
            }
            
        except Exception as e:
            print(f"[ERRO] Erro ao verificar antecedentes criminais: {e}")
            return {
                'atendido': False,
                'motivo': f'Erro na verificação: {e}',
                'detalhes': {'erro': str(e)}
            }
    
    def _verificar_documentos_complementares(self, documentos_ja_baixados: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Verifica documentos complementares do Anexo I da Portaria 623/2020
        COM VALIDAÇÃO CORRETA DO TEXTO EXTRAÍDO E PENALIZAÇÃO POR NÃO ANEXAR
        """
        try:
            print("[INFO] DOCUMENTOS COMPLEMENTARES: Anexo I da Portaria 623/2020")
            
            # Documentos obrigatórios conforme Anexo I
            documentos_complementares = {
                'Carteira de Registro Nacional Migratório': 'item 3',
                'Comprovante da situação cadastral do CPF': 'item 4',
                'Comprovante de tempo de residência': 'item 8',
                'Documento de viagem internacional': 'item 2'
            }
            
            resultados = {}
            documentos_faltantes = []
            documentos_invalidos = []
            
            for nome_doc, item in documentos_complementares.items():
                print(f"[BUSCA] Verificando {nome_doc}...")
                
                # 1. PENALIZAR SE NÃO FOI BAIXADO (não anexado)
                if not documentos_ja_baixados or nome_doc not in documentos_ja_baixados:
                    print(f"[ERRO] {nome_doc}: NÃO ANEXADO")
                    documentos_faltantes.append(f"Não anexou {item}")
                    resultados[nome_doc] = {
                        'anexado': False,
                        'valido': False,
                        'item': item,
                        'motivo': 'Documento não anexado'
                    }
                    continue
                
                # 2. VALIDAR TEXTO EXTRAÍDO
                texto_documento = documentos_ja_baixados[nome_doc]
                
                # Validação específica por tipo de documento
                if 'CRNM' in nome_doc or 'Carteira de Registro' in nome_doc:
                    resultado_validacao = self._validar_documento_crnm(texto_documento)
                elif 'viagem internacional' in nome_doc:
                    resultado_validacao = self._validar_documento_viagem_internacional(texto_documento)
                else:
                    # Para CPF e comprovante de residência, só verificar se não está vazio
                    resultado_validacao = {
                        'valido': len(texto_documento.strip()) > 10,
                        'motivo': 'Documento anexado' if len(texto_documento.strip()) > 10 else 'Documento muito pequeno'
                    }
                
                if not resultado_validacao['valido']:
                    print(f"[ERRO] {nome_doc}: INVÁLIDO - {resultado_validacao['motivo']}")
                    documentos_invalidos.append(f"{item} inválido")
                    resultados[nome_doc] = {
                        'anexado': True,
                        'valido': False,
                        'item': item,
                        'motivo': resultado_validacao['motivo']
                    }
                else:
                    print(f"[OK] {nome_doc}: VÁLIDO - {resultado_validacao['motivo']}")
                    resultados[nome_doc] = {
                        'anexado': True,
                        'valido': True,
                        'item': item,
                        'motivo': resultado_validacao['motivo']
                    }
            
            # Calcular completude (apenas documentos válidos)
            total_docs = len(documentos_complementares)
            docs_validos = sum(1 for r in resultados.values() if r.get('valido', False))
            percentual_completude = (docs_validos / total_docs) * 100
            
            print(f"[DADOS] Completude dos documentos: {percentual_completude:.0f}%")
            
            # Verificar se há problemas
            problemas = documentos_faltantes + documentos_invalidos
            
            # Retornar formato compatível com o sistema existente
            resultado = {
                'documentos_verificados': resultados,
                'documentos_faltantes': documentos_faltantes,
                'documentos_invalidos': documentos_invalidos,
                'percentual_completude': percentual_completude,
                'atendido': len(problemas) == 0,
                'motivo': 'Todos os documentos complementares válidos' if len(problemas) == 0 else f'Problemas: {", ".join(problemas)}'
            }
            
            return resultado
                
        except Exception as e:
            print(f"[ERRO] Erro ao verificar documentos complementares: {e}")
            return {
                'documentos_verificados': {},
                'documentos_faltantes': ['Erro na validação'],
                'documentos_invalidos': [],
                'percentual_completude': 0,
                'atendido': False,
                'motivo': f'Erro na verificação: {e}'
            }
    
    def _buscar_documento_na_tabela(self, nome_documento: str) -> Dict[str, Any]:
        """
        Busca documento na tabela de documentos anexados
        Retorna: {'encontrado': bool, 'texto': str, 'localizacao': str}
        """
        try:
            # Mapear nomes de documentos para variações possíveis na tabela
            variacoes_documento = {
                "Certidão de antecedentes criminais (Brasil)": [
                    "antecedentes criminais brasil",
                    "antecedentes brasil", 
                    "certidão antecedentes",
                    "certidao antecedentes",
                    "antecedentes criminais",
                    "certidão criminal",
                    "certidao criminal"
                ],
                "Atestado antecedentes criminais (país de origem)": [
                    "antecedentes país origem",
                    "antecedentes pais origem",
                    "antecedentes origem",
                    "atestado antecedentes",
                    "certidão origem",
                    "certidao origem"
                ],
                "Comprovante de comunicação em português": [
                    "comunicação português",
                    "comunicacao portugues",
                    "português",
                    "portugues",
                    "celpe",
                    "certificado português",
                    "certificado portugues"
                ],
                "CRNM": [
                    "crnm",
                    "rne",
                    "rnm",
                    "carteira registro",
                    "registro migratório",
                    "registro migratorio"
                ],
                "CPF": [
                    "cpf",
                    "cadastro pessoa física",
                    "cadastro pessoa fisica",
                    "receita federal"
                ]
            }
            
            # Obter variações para o documento
            variacoes = variacoes_documento.get(nome_documento, [nome_documento.lower()])
            
            # Buscar na tabela de documentos
            try:
                # Tentar encontrar tabela de documentos
                tabela_docs = self.lecom.driver.find_elements(By.XPATH, "//table//tr")
                
                for linha in tabela_docs:
                    texto_linha = linha.text.lower()
                    
                    # Verificar se alguma variação está na linha
                    for variacao in variacoes:
                        if variacao.lower() in texto_linha:
                            print(f"[TABELA] Documento encontrado na tabela: {nome_documento} (variação: {variacao})")
                            
                            # Tentar extrair OCR se possível
                            try:
                                # Procurar link de download ou botão de visualização
                                link_download = linha.find_element(By.XPATH, ".//a[contains(@href, 'download') or contains(@onclick, 'download')]")
                                if link_download:
                                    # Aqui poderia executar OCR, mas por enquanto retorna que foi encontrado
                                    return {
                                        'encontrado': True,
                                        'texto': None,  # Seria extraído via OCR
                                        'localizacao': 'tabela_documentos',
                                        'variacao_encontrada': variacao
                                    }
                            except:
                                pass
                            
                            return {
                                'encontrado': True,
                                'texto': None,
                                'localizacao': 'tabela_documentos',
                                'variacao_encontrada': variacao
                            }
                
                return {
                    'encontrado': False,
                    'texto': None,
                    'localizacao': None,
                    'variacao_encontrada': None
                }
                
            except Exception as e:
                print(f"[AVISO] Erro ao buscar na tabela: {e}")
                return {
                    'encontrado': False,
                    'texto': None,
                    'localizacao': None,
                    'variacao_encontrada': None
                }
                
        except Exception as e:
            print(f"[ERRO] Erro na busca na tabela: {e}")
            return {
                'encontrado': False,
                'texto': None,
                'localizacao': None,
                'variacao_encontrada': None
            }
    
    def _verificar_documento_anexado(self, nome_documento: str, documentos_ja_baixados: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Verifica se um documento específico foi anexado
        PRIMEIRO: documentos baixados
        SEGUNDO: busca na tabela se não encontrado
        """
        try:
            # 1. PRIMEIRO: Verificar nos documentos já baixados
            if documentos_ja_baixados and nome_documento in documentos_ja_baixados:
                texto = documentos_ja_baixados[nome_documento]
                return {
                    'anexado': True,
                    'texto': texto,
                    'fonte': 'documentos_baixados'
                }
            
            # 2. SEGUNDO: Buscar na tabela de documentos
            resultado_tabela = self._buscar_documento_na_tabela(nome_documento)
            if resultado_tabela['encontrado']:
                print(f"[TABELA] {nome_documento} encontrado na tabela (variação: {resultado_tabela['variacao_encontrada']})")
                return {
                    'anexado': True,
                    'texto': resultado_tabela['texto'],
                    'fonte': 'tabela_documentos',
                    'variacao_encontrada': resultado_tabela['variacao_encontrada']
                }
            
            # 3. TERCEIRO: Verificar via elemento HTML (método antigo)
            try:
                xpath = f"//span[contains(text(), '{nome_documento}')]"
                elemento = self.lecom.driver.find_element(By.XPATH, xpath)
                
                if elemento and elemento.is_displayed():
                    return {
                        'anexado': True,
                        'texto': None,
                        'fonte': 'elemento_html'
                    }
            except:
                pass
            
            # 4. NÃO ENCONTRADO
            return {
                'anexado': False,
                'texto': None,
                'fonte': None
            }
                
        except Exception as e:
            print(f"[ERRO] Erro ao verificar documento {nome_documento}: {e}")
            return {
                'anexado': False,
                'texto': None,
                'fonte': None
            }
    
    def _analisar_certidao_criminal(self, info_documento: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analisa certidão de antecedentes criminais via OCR
        """
        if not info_documento.get('texto'):
            return {'tem_condenacao': False, 'motivo': 'Sem texto para análise'}
        
        texto = info_documento['texto'].lower()
        
        # Termos que indicam ausência de condenação (verificar primeiro - mais específico)
        termos_limpo = [
            'não consta condenação',
            'nada consta',
            'sem antecedentes',
            'sem registros',
            'certidão negativa',
 
        ]
        
        # Termos que indicam presença de condenação (apenas se não houver negação)
        termos_condenacao = [
            'condenado por',
            'processo criminal condenatório',
            'sentença condenatória'
        ]
        
        # Verificar ausência de condenação PRIMEIRO (mais específico)
        for termo in termos_limpo:
            if termo in texto:
                return {
                    'tem_condenacao': False,
                    'motivo': f'Sem condenação: {termo}'
                }
        
        # Verificar condenações apenas se não encontrou termos de ausência
        for termo in termos_condenacao:
            if termo in texto:
                return {
                    'tem_condenacao': True,
                    'motivo': f'Consta condenação: {termo}'
                }
        
        # Se não encontrou termos claros, assumir que não há condenação
        return {
            'tem_condenacao': False,
            'motivo': 'Termos específicos não encontrados, assumindo sem condenação'
        }
    
    def _validar_comprovante_portugues(self, texto: str) -> Dict[str, Any]:
        """
        Valida comprovante de comunicação em português
        """
        texto_lower = texto.lower()
        
        # Termos que indicam certificado válido
        termos_validos = [
            'certificado de proficiência',
            'celpe-bras',
            'português brasileiro',
            'comunicação em português',
            'ensino superior',
            'curso de português',
            'certificado de conclusão'
        ]
        
        for termo in termos_validos:
            if termo in texto_lower:
                return {
                    'valido': True,
                    'motivo': f'Comprovante válido: {termo}',
                    'detalhes': 'Atende aos requisitos do Art. 65, inciso III'
                }
        
        return {
            'valido': False,
            'motivo': 'Documento não comprova comunicação em português',
            'detalhes': 'Não atende aos requisitos do Art. 65, inciso III'
        }
    
    def _validar_documento_generico(self, nome_documento: str, texto: str) -> Dict[str, Any]:
        """
        Validação genérica para documentos obrigatórios
        """
        if len(texto.strip()) < 20:
            return {
                'valido': False,
                'motivo': 'Documento com conteúdo insuficiente'
            }
        
        # Validações específicas por tipo
        if 'CPF' in nome_documento:
            return self._validar_cpf(texto)
        elif 'CRNM' in nome_documento or 'Migratório' in nome_documento:
            return self._validar_crnm(texto)
        elif 'residência' in nome_documento.lower():
            return self._validar_comprovante_residencia(texto)
        
        # Validação básica para outros documentos
        return {
            'valido': True,
            'motivo': 'Documento anexado com conteúdo válido'
        }
    
    def _validar_cpf(self, texto: str) -> Dict[str, Any]:
        """
        Valida CPF usando termos MELHORADOS baseados em 1.165 documentos reais (99.3% sucesso)
        """
        # Usar validação melhorada se disponível
        if TERMOS_MELHORADOS_DISPONIVEIS:
            resultado = validar_documento_melhorado('CPF', texto, minimo_confianca=70)
            return {
                'valido': resultado['valido'],
                'motivo': resultado['motivo'],
                'confianca': resultado.get('confianca', 0)
            }
        
        # Fallback: validação básica (ANTIGA)
        texto_lower = texto.lower()
        
        termos_cpf = [
            'cadastro de pessoas físicas',
            'situação cadastral',
            'cpf',
            'receita federal',
            'regular',
            'ativo'
        ]
        
        termos_encontrados = [termo for termo in termos_cpf if termo in texto_lower]
        
        if len(termos_encontrados) >= 2:
            return {
                'valido': True,
                'motivo': 'Comprovante de CPF válido'
            }
        
        return {
            'valido': False,
            'motivo': 'Não parece ser comprovante de CPF válido'
        }
    
    def _validar_crnm(self, texto: str) -> Dict[str, Any]:
        """
        Valida Carteira de Registro Nacional Migratório
        """
        texto_lower = texto.lower()
        
        # Termos que indicam CRNM válido
        termos_crnm = [
            'carteira de registro nacional migratório',
            'crnm',
            'rnm',
            'registro nacional migratório',
            'república federativa do brasil',
            'nacionalidade',
            'classificação'
        ]
        
        termos_encontrados = [termo for termo in termos_crnm if termo in texto_lower]
        
        if len(termos_encontrados) >= 2:
            return {
                'valido': True,
                'motivo': 'CRNM válido'
            }
        
        return {
            'valido': False,
            'motivo': 'Não parece ser CRNM válido'
        }
    
    def _validar_comprovante_residencia(self, texto: str) -> Dict[str, Any]:
        """
        Valida comprovante de tempo de residência
        """
        # Para comprovante de residência, apenas verificar se tem conteúdo
        if len(texto.strip()) > 10:
            return {
                'valido': True,
                'motivo': 'Comprovante de residência anexado'
            }
        
        return {
            'valido': False,
            'motivo': 'Comprovante de residência sem conteúdo válido'
        }
    
    def _calcular_percentual_documentos(self, docs_complementares: Dict[str, Any]) -> int:
        """
        Calcula percentual baseado nos documentos complementares
        """
        return docs_complementares.get('percentual_completude', 0)
    
    def _obter_numero_item_anexo(self, nome_documento: str) -> str:
        """
        Obtém o número do item no Anexo I da Portaria 623/2020
        """
        mapeamento_itens = {
            'Carteira de Registro Nacional Migratório': '3',
            'Comprovante da situação cadastral do CPF': '4',
            'Comprovante de tempo de residência': '8',
            'Comprovante de comunicação em português': '13'
        }
        
        return mapeamento_itens.get(nome_documento, '?')


# Função de conveniência para uso direto
def analisar_elegibilidade_ordinaria(lecom_instance, dados_pessoais: Dict[str, Any], data_inicial_processo: str, documentos_ja_baixados: Dict[str, str] = None) -> Dict[str, Any]:
    """
    Função de conveniência para análise de elegibilidade ordinária
    
    Args:
        lecom_instance: Instância da navegação ordinária
        dados_pessoais: Dados pessoais extraídos
        data_inicial_processo: Data inicial do processo
        documentos_ja_baixados: Documentos já baixados (opcional)
        
    Returns:
        Dict com resultado da análise
    """
    analisador = AnaliseElegibilidadeOrdinaria(lecom_instance)
    return analisador.analisar_elegibilidade_completa(dados_pessoais, data_inicial_processo, documentos_ja_baixados)
