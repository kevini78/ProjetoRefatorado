"""
Camada Repository - Acesso a dados para naturalização ordinária
Responsável por obter e persistir dados do processo
"""

import os
import json
import pandas as pd
import re
from datetime import datetime
from typing import Dict, Any, Optional, List
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Importar utilitários de OCR da camada modular
from automation.ocr.ocr_utils import (
    extrair_nome_completo,
    extrair_filiação_limpa,
    extrair_pai_mae_da_filiacao_lista,
    extrair_nascimento_ajustado,
    extrair_rnm_robusto,
    extrair_cpf,
    extrair_classificacao,
    extrair_prazo_residencia,
    extrair_nacionalidade_validade_linha,
    comparar_campos,
    extrair_data_nasc_texto,
)


class OrdinariaRepository:
    """
    Repository responsável por acesso a dados de naturalização ordinária
    """
    
    def __init__(self, lecom_action, document_action):
        """
        Inicializa o repository
        
        Args:
            lecom_action: Instância da LecomAction
            document_action: Instância da DocumentAction
        """
        self.lecom_action = lecom_action
        self.document_action = document_action
        self.driver = lecom_action.driver
        self.wait = lecom_action.wait
        
        # Lista de documentos para naturalização ordinária
        self.documentos_para_baixar = [
            'Carteira de Registro Nacional Migratório',
            'Comprovante da situação cadastral do CPF',
            'Comprovante de tempo de residência',
            'Comprovante de comunicação em português',
            'Certidão de antecedentes criminais (Brasil)',
            'Atestado antecedentes criminais (país de origem)',
            'Documento de viagem internacional',
            'Comprovante de redução de prazo',
            'Comprovante de reabilitação'
        ]
    
    def obter_dados_pessoais_formulario(self) -> Dict[str, Any]:
        """
        Extrai dados pessoais do formulário
        
        Returns:
            Dict com dados pessoais extraídos
        """
        try:
            print("[DADOS] Extraindo dados pessoais do formulário...")
            
            dados_pessoais = {}
            
            # Extrair dados básicos do formulário
            dados_basicos = self._extrair_dados_basicos_formulario()
            dados_pessoais.update(dados_basicos)
            
            # Extrair dados do form-web se disponível
            dados_form_web = self._extrair_dados_do_formulario_form_web()
            if dados_form_web:
                dados_pessoais.update(dados_form_web)
            
            print(f"[OK] Dados pessoais extraídos: {len(dados_pessoais)} campos")
            return dados_pessoais
            
        except Exception as e:
            print(f"[ERRO] Erro ao extrair dados pessoais: {e}")
            return {}
    
    def _extrair_dados_basicos_formulario(self) -> Dict[str, Any]:
        """Extrai dados básicos do formulário (baseado no código original)"""
        dados = {}
        
        try:
            print("[INFO] Extraindo dados básicos do formulário...")
            
            # Aguardar página carregar
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Usar JavaScript para extrair todos os campos disponíveis
            script_dados = """
            var dados = {};
            
            // Buscar todos os inputs, selects e textareas
            var elementos = document.querySelectorAll('input, select, textarea, span[id], div[id]');
            
            elementos.forEach(function(elemento) {
                var valor = '';
                var id = elemento.id || elemento.name || '';
                
                if (elemento.tagName === 'INPUT' || elemento.tagName === 'TEXTAREA') {
                    valor = elemento.value;
                } else if (elemento.tagName === 'SELECT') {
                    valor = elemento.options[elemento.selectedIndex] ? elemento.options[elemento.selectedIndex].text : '';
                } else {
                    valor = elemento.textContent || elemento.innerText;
                }
                
                if (id && valor && valor.trim().length > 0) {
                    dados[id] = valor.trim();
                }
            });
            
            return dados;
            """
            
            dados_js = self.driver.execute_script(script_dados)
            print(f"[DEBUG] Dados JavaScript extraídos: {len(dados_js)} campos")
            
            # Processar e mapear dados
            for id_campo, valor in dados_js.items():
                if valor and len(str(valor).strip()) > 0:
                    valor_str = str(valor).strip()
                    nome_campo = self._mapear_id_para_nome(id_campo)

                    # Evitar sobrescrever pai/mãe com textos de rótulo (ex.: "Filho de (nome do pai)")
                    if nome_campo in ["pai", "mae"]:
                        valor_lower = valor_str.lower()
                        if any(
                            padrao in valor_lower
                            for padrao in [
                                "filho de (nome do pai)",
                                "filho de (nome da mãe)",
                                "filha de (nome do pai)",
                                "filha de (nome da mãe)",
                                "nome do pai",
                                "nome da mãe",
                            ]
                        ):
                            # Ignora rótulos; mantém eventual valor já capturado com o nome real
                            continue
                        # Se já havia um valor mais longo (provavelmente o nome completo), não substituir por algo menor
                        valor_existente = dados.get(nome_campo)
                        if valor_existente and len(valor_existente) > len(valor_str):
                            continue

                    dados[nome_campo] = valor_str
                    
                    # Log apenas campos importantes para debug (removido CPF)
                    if nome_campo in ['data_nascimento', 'nome', 'rnm', 'pai', 'mae']:
                        print(f"[OK] {nome_campo}: {valor_str}")
            
            # Tentar seletores específicos se não encontrou dados suficientes
            if len(dados) < 3:
                print("[INFO] Poucos dados encontrados, tentando seletores específicos...")
                
                # Mapeamento de campos comuns
                campos_formulario = {
                    'nome': ['#NOME', '[name="nome"]', '[id*="nome"]', 'input[placeholder*="nome"]'],
                    'sobrenome': ['#SOBRENOME', '[name="sobrenome"]', '[id*="sobrenome"]'],
                    'data_nascimento': ['#DATA_NASC', '[name="data_nascimento"]', '[id*="nascimento"]', 'input[placeholder*="nascimento"]'],
                    'nacionalidade': ['#NACIONALIDADE', '[name="nacionalidade"]', '[id*="nacionalidade"]'],
                    'rnm': ['#RNM', '[name="rnm"]', '[id*="rnm"]'],
                    'pai': ['#PAI', '[name="pai"]', '[id*="pai"]'],
                    'mae': ['#MAE', '[name="mae"]', '[id*="mae"]']
                }
                
                for campo, seletores in campos_formulario.items():
                    if campo not in dados:
                        valor = self._extrair_valor_campo(seletores)
                        if valor:
                            dados[campo] = valor
                            print(f"[OK] {campo} (seletor específico): {valor}")
            
            print(f"[DADOS] Total de dados básicos extraídos: {len(dados)}")
            return dados
            
        except Exception as e:
            print(f"[ERRO] Erro ao extrair dados básicos: {e}")
            return {}
    
    def _extrair_dados_do_formulario_form_web(self) -> Dict[str, Any]:
        """Extrai dados específicos do form-web (baseado no código original)"""
        try:
            dados_extraidos = {}
            
            print('[INFO] Extraindo dados específicos do form-web...')
            
            # Aguardar formulário carregar
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Extrair nome completo
            seletores_nome = [
                "input[name*='nome']",
                "input[name*='name']", 
                "input[id*='nome']",
                "input[id*='name']",
                "span[id*='nome']",
                "span[id*='name']"
            ]
            
            for seletor in seletores_nome:
                try:
                    elementos = self.driver.find_elements(By.CSS_SELECTOR, seletor)
                    for elemento in elementos:
                        valor = elemento.get_attribute('value') or elemento.text
                        if valor and len(valor) > 3 and valor.lower() not in ['nome', 'name', '']:
                            dados_extraidos['nome_completo'] = valor
                            print(f'[OK] Nome completo encontrado: {valor}')
                            break
                    if 'nome_completo' in dados_extraidos:
                        break
                except:
                    continue
            
            # Extrair data de nascimento
            seletores_data_nasc = [
                "input[name*='nascimento']",
                "input[name*='birth']",
                "input[id*='nascimento']", 
                "input[id*='birth']",
                "span[id*='nascimento']",
                "span[id*='birth']"
            ]
            
            for seletor in seletores_data_nasc:
                try:
                    elementos = self.driver.find_elements(By.CSS_SELECTOR, seletor)
                    for elemento in elementos:
                        valor = elemento.get_attribute('value') or elemento.text
                        if valor and ('/' in valor or len(valor) >= 8):
                            dados_extraidos['data_nascimento'] = valor
                            print(f'[OK] Data de nascimento encontrada: {valor}')
                            break
                    if 'data_nascimento' in dados_extraidos:
                        break
                except:
                    continue
            
            # Extrair nacionalidade
            seletores_nacionalidade = [
                "input[name*='nacionalidade']",
                "input[name*='pais']",
                "select[name*='nacionalidade']",
                "select[name*='pais']",
                "input[name*='country']",
                "select[name*='country']",
                "input[id*='nacionalidade']",
                "input[id*='pais']"
            ]
            
            for seletor in seletores_nacionalidade:
                try:
                    elementos = self.driver.find_elements(By.CSS_SELECTOR, seletor)
                    for elemento in elementos:
                        if elemento.tag_name.lower() == 'select':
                            # Para select, pegar o texto da opção selecionada
                            from selenium.webdriver.support.ui import Select
                            select_obj = Select(elemento)
                            try:
                                valor = select_obj.first_selected_option.text
                            except:
                                continue
                        else:
                            valor = elemento.get_attribute('value')
                        
                        if valor and len(valor) > 2 and valor.lower() not in ['selecione', 'escolha', '']:
                            dados_extraidos['nacionalidade'] = valor
                            print(f'[OK] Nacionalidade encontrada: {valor}')
                            break
                    if 'nacionalidade' in dados_extraidos:
                        break
                except:
                    continue
            
            # Tentar extrair outros campos úteis
            print('[INFO] Procurando outros campos do formulário...')
            
            # CPF/Documento
            seletores_documento = [
                "input[name*='cpf']",
                "input[name*='documento']",
                "input[id*='cpf']",
                "input[id*='documento']"
            ]
            
            for seletor in seletores_documento:
                try:
                    elementos = self.driver.find_elements(By.CSS_SELECTOR, seletor)
                    for elemento in elementos:
                        valor = elemento.get_attribute('value')
                        if valor and len(valor) >= 10:
                            dados_extraidos['documento'] = valor
                            print(f'[OK] Documento encontrado: {valor}')
                            break
                    if 'documento' in dados_extraidos:
                        break
                except:
                    continue
            
            print(f'[DADOS] Total de dados extraídos do form-web: {len(dados_extraidos)}')
            for chave, valor in dados_extraidos.items():
                print(f'  - {chave}: {valor}')
                
            return dados_extraidos
            
        except Exception as e:
            print(f"[ERRO] Erro ao extrair dados do form-web: {e}")
            return {}
    
    def _extrair_valor_campo(self, seletores: List[str]) -> Optional[str]:
        """Extrai valor de um campo usando múltiplos seletores"""
        for seletor in seletores:
            try:
                elementos = self.driver.find_elements(By.CSS_SELECTOR, seletor)
                for elemento in elementos:
                    valor = elemento.get_attribute('value') or elemento.text
                    if valor and valor.strip():
                        return valor.strip()
            except Exception:
                continue
        return None
    
    def _mapear_id_para_nome(self, id_campo: str) -> str:
        """Mapeia IDs de campos para nomes mais legíveis usando heurísticas.

        - Normaliza IDs variados para chaves canônicas (nome, nome_completo, pai, mae, data_nascimento, etc.)
        - Evita confundir "pais" (country) com "pai" (filiation)
        """
        id_lower = (id_campo or "").strip().lower()

        # Mapeamento direto conhecido
        mapeamento_direto = {
            'ord_nome': 'nome',
            'ord_sobrenome': 'sobrenome',
            'ord_nas': 'data_nascimento',
            'ord_nac': 'nacionalidade',
            'ord_cpf': 'cpf',
            'ord_rnm': 'rnm',
            'ord_pai': 'pai',
            'ord_mae': 'mae',
            'ord_sexo': 'sexo',
            'ord_estado_civil': 'estado_civil',
            'ord_fi1': 'pai',
            'ord_fi2': 'mae',
            'num_rnm': 'rnm',
            'ord_natu': 'pais_nascimento',
            'ord_nom_completo': 'nome_completo',
            'ord_ema': 'email',
            'ord_cel': 'telefone',
            'ord_end': 'endereco',
            'ord_bairro': 'bairro',
            'ord_cidade': 'cidade',
            'ord_uf': 'uf',
            'ord_cep': 'cep',
            'data_nascimento': 'data_nascimento',
        }
        if id_lower in mapeamento_direto:
            return mapeamento_direto[id_lower]

        # Nome completo
        if any(p in id_lower for p in ['nome_completo', 'nomecompleto', 'fullname', 'nome_naturalizado']):
            return 'nome_completo'

        # Nome e sobrenome (evita confundir "usuario")
        if 'sobrenome' in id_lower:
            return 'sobrenome'
        if 'nome' in id_lower and 'usuario' not in id_lower:
            return 'nome'

        # Filiação (garantir que 'pais' país não dispare)
        if ('pai' in id_lower or 'filiacao1' in id_lower or 'fi1' in id_lower or 'father' in id_lower) and 'pais' not in id_lower:
            return 'pai'
        if ('mae' in id_lower or 'filiacao2' in id_lower or 'fi2' in id_lower or 'mother' in id_lower):
            return 'mae'

        # Datas de nascimento
        if any(p in id_lower for p in ['nascimento', 'nasc', 'birth', 'data_nas']):
            return 'data_nascimento'

        # RNM/RNE
        if 'rnm' in id_lower or 'rne' in id_lower:
            return 'rnm'

        # CPF
        if 'cpf' in id_lower:
            return 'cpf'

        # Nacionalidade/pais
        if 'nacionalidade' in id_lower or 'nationality' in id_lower:
            return 'nacionalidade'
        if 'pais' in id_lower and 'nascimento' in id_lower:
            return 'pais_nascimento'
        if 'pais' in id_lower:
            return 'nacionalidade'

        # Fallback: id original em lowercase
        return id_lower
    
    def obter_documentos_processo(self) -> Dict[str, str]:
        """
        Baixa e processa todos os documentos do processo
        
        Returns:
            Dict com textos OCR dos documentos
        """
        try:
            print("[DOCUMENTOS] Iniciando download e processamento de documentos...")
            
            documentos_processados = {}
            documentos_validos = 0
            documentos_faltantes = []
            
            for documento in self.documentos_para_baixar:
                print(f"\n[DOC] Processando: {documento}")
                
                try:
                    # Baixar e validar documento
                    sucesso = self.document_action.baixar_e_validar_documento_individual(documento)
                    
                    if sucesso:
                        documentos_validos += 1
                        # Obter texto OCR do documento (se disponível)
                        texto_ocr = self._obter_texto_ocr_documento(documento)
                        if texto_ocr:
                            documentos_processados[documento] = texto_ocr
                    else:
                        documentos_faltantes.append(documento)
                        
                except Exception as e:
                    print(f"[ERRO] Erro ao processar {documento}: {e}")
                    documentos_faltantes.append(documento)
            
            print(f"\n[RESUMO] Documentos processados: {documentos_validos}/{len(self.documentos_para_baixar)}")
            print(f"[RESUMO] Documentos faltantes: {len(documentos_faltantes)}")
            
            # Adicionar informações de resumo
            documentos_processados['_resumo'] = {
                'total_documentos': len(self.documentos_para_baixar),
                'documentos_validos': documentos_validos,
                'documentos_faltantes': documentos_faltantes,
                'percentual_completude': (documentos_validos / len(self.documentos_para_baixar)) * 100
            }
            
            return documentos_processados
            
        except Exception as e:
            print(f"[ERRO] Erro ao obter documentos: {e}")
            return {}
    
    def _obter_texto_ocr_documento(self, nome_documento: str) -> Optional[str]:
        """Obtém texto OCR de um documento específico"""
        try:
            # Verificar se já temos o texto no cache
            if nome_documento in self.document_action.textos_ja_extraidos:
                return self.document_action.textos_ja_extraidos[nome_documento]
            
            # Se não tiver no cache, retornar None (documento foi validado mas texto não foi salvo)
            return None
            
        except Exception as e:
            print(f"[ERRO] Erro ao obter texto OCR de {nome_documento}: {e}")
            return None
    
    def extrair_parecer_pf(self) -> Dict[str, Any]:
        """
        Extrai e analisa o parecer da Polícia Federal
        (preserva lógica original dos padrões de alerta da PF)
        """
        try:
            elemento_parecer = self.driver.find_element(By.ID, "CHPF_PARECER")
            parecer_texto = elemento_parecer.get_attribute("value") or elemento_parecer.text
            
            if not parecer_texto:
                return {
                    'parecer_texto': '',
                    'proposta_pf': 'Não encontrado',
                    'excedeu_ausencia': False,
                    'problema_portugues': False,
                    'alertas': []
                }
            
            alertas = []
            
            # PADRÕES DE ALERTA DA PF (preserva lógica original)
            
            # 1. Verificar excesso de ausência
            padroes_ausencia = [
                r'excedeu.*ausência',
                r'ausente.*por.*mais.*de.*\d+.*dias',
                r'período.*ausência.*superior',
                r'ultrapassou.*limite.*ausência',
                r'ausência.*prolongada'
            ]
            
            excedeu_ausencia = False
            for padrao in padroes_ausencia:
                if re.search(padrao, parecer_texto, re.IGNORECASE):
                    excedeu_ausencia = True
                    alertas.append("Excedeu limite de ausência do país")
                    break
            
            # 2. Verificar problemas com português
            padroes_portugues = [
                r'não.*consegue.*comunicar.*português',
                r'dificuldade.*comunicação.*português',
                r'não.*domina.*língua.*portuguesa',
                r'comunicação.*português.*inadequada',
                r'não.*atende.*requisito.*português'
            ]
            
            problema_portugues = False
            for padrao in padroes_portugues:
                if re.search(padrao, parecer_texto, re.IGNORECASE):
                    problema_portugues = True
                    alertas.append("Problema na comunicação em português identificado pela PF")
                    break
            
            # 3. Extrair proposta da PF
            proposta_pf = 'Indeferimento'  # Default
            
            padroes_deferimento = [
                r'proposta.*deferimento',
                r'recomenda.*deferimento',
                r'sugere.*deferimento',
                r'favorável.*ao.*pedido'
            ]
            
            for padrao in padroes_deferimento:
                if re.search(padrao, parecer_texto, re.IGNORECASE):
                    proposta_pf = 'Deferimento'
                    break
            
            return {
                'parecer_texto': parecer_texto,
                'proposta_pf': proposta_pf,
                'excedeu_ausencia': excedeu_ausencia,
                'problema_portugues': problema_portugues,
                'alertas': alertas
            }
            
        except Exception as e:
            print(f"[ERRO] Erro ao extrair parecer PF: {e}")
            return {
                'parecer_texto': '',
                'proposta_pf': 'Erro na extração',
                'excedeu_ausencia': False,
                'problema_portugues': False,
                'alertas': [f'Erro na extração: {e}']
            }
    
    def _montar_snapshot_legacy(self, numero_processo: str, resultado_elegibilidade: Dict[str, Any],
                                resultado_decisao: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Replica o payload legado utilizado no exportador global."""

        dados_pessoais = resultado_elegibilidade.get('dados_pessoais', {}) or {}
        parecer_pf = resultado_elegibilidade.get('parecer_pf', {}) or {}
        documentos_complementares = resultado_elegibilidade.get('documentos_complementares', {}) or {}

        return {
                'numero_processo': numero_processo,
                'codigo_processo': getattr(self.lecom_action, 'numero_processo_limpo', numero_processo),
                'tipo_analise': 'Naturalização Ordinária',
                'data_analise': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
                'nome': dados_pessoais.get('nome') or dados_pessoais.get('nome_completo', 'N/A'),
                'protocolo': dados_pessoais.get('protocolo', 'N/A'),
                'data_inicial': resultado_elegibilidade.get('data_inicial_processo') or self.lecom_action.data_inicial_processo,
                'resultado_final': 'DEFERIMENTO' if resultado_elegibilidade.get('elegibilidade_final') == 'deferimento' else 'INDEFERIMENTO',
                'motivos_indeferimento': resultado_elegibilidade.get('requisitos_nao_atendidos', []),
                'requisitos': {
                    'capacidade_civil': resultado_elegibilidade.get('requisito_i_capacidade_civil', {}).get('atendido', False),
                    'residencia_minima': resultado_elegibilidade.get('requisito_ii_residencia_minima', {}).get('atendido', False),
                    'comunicacao_portugues': resultado_elegibilidade.get('requisito_iii_comunicacao_portugues', {}).get('atendido', False),
                    'antecedentes_criminais': resultado_elegibilidade.get('requisito_iv_antecedentes_criminais', {}).get('atendido', False)
                },
                'documentos_complementares': {
                    'percentual_completude': documentos_complementares.get('percentual_completude', 0),
                    'documentos_faltantes': documentos_complementares.get('documentos_faltantes', [])
                },
                'despacho': ((resultado_decisao or {}).get('despacho') or (resultado_decisao or {}).get('despacho_completo') or 'N/A'),
                'resumo': ((resultado_decisao or {}).get('resumo') or (resultado_decisao or {}).get('resumo_analise') or 'N/A'),
                'parecer_pf': parecer_pf,
            }

    def _salvar_snapshot_individual(self, snapshot: Dict[str, Any]) -> None:
        """Persiste snapshot em arquivo próprio para depuração."""

        try:
            diretorio_exportacao = os.path.join(
                os.path.dirname(__file__), '..', '..', 'dados_exportacao_ordinaria'
            )
            os.makedirs(diretorio_exportacao, exist_ok=True)

            nome_arquivo = f"ordinaria_{snapshot['numero_processo']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            caminho_arquivo = os.path.join(diretorio_exportacao, nome_arquivo)

            with open(caminho_arquivo, 'w', encoding='utf-8') as f:
                json.dump(snapshot, f, ensure_ascii=False, indent=2)

            print(f"[SALVO] Dados exportados para: {nome_arquivo}")

        except Exception as e:
            print(f"[ERRO] Erro ao salvar snapshot individual: {e}")

    def _atualizar_json_global(self, snapshot: Dict[str, Any]) -> None:
        """Atualiza o arquivo global mantendo o layout legado (compatível com nome antigo e novo)."""

        try:
            def _atualizar_arquivo(arquivo_global: str):
                if os.path.exists(arquivo_global):
                    try:
                        with open(arquivo_global, 'r', encoding='utf-8') as f:
                            dados_existentes = json.load(f)
                        if not isinstance(dados_existentes, list):
                            print('[AVISO] Estrutura inesperada no JSON global, recriando lista.')
                            dados_existentes = []
                    except Exception as leitura_erro:
                        print(f"[AVISO] Falha ao carregar JSON global, recriando arquivo: {leitura_erro}")
                        dados_existentes = []
                else:
                    dados_existentes = []

                dados_existentes.append(snapshot)

                with open(arquivo_global, 'w', encoding='utf-8') as f:
                    json.dump(dados_existentes, f, ensure_ascii=False, indent=2)

                print(f"[DADOS] Resultado adicionado ao arquivo global: {arquivo_global}")

            base_dir = os.getcwd()
            # Compatível com formato antigo (underscores) e o nome citado (com pontos)
            arquivos_globais = [
                os.path.join(base_dir, 'resultados_ordinaria_global.json'),
                os.path.join(base_dir, 'resultados.ordinaria.global'),
            ]

            for caminho in arquivos_globais:
                _atualizar_arquivo(caminho)

        except Exception as e:
            print(f"[ERRO] Erro ao atualizar arquivo global de resultados: {e}")

    def salvar_dados_para_exportacao(self, numero_processo: str, resultado_elegibilidade: Dict, resultado_decisao: Optional[Dict]):
        """Gera snapshot legado, salva em arquivo individual e atualiza JSON global."""

        snapshot = self._montar_snapshot_legacy(numero_processo, resultado_elegibilidade, resultado_decisao)
        self._salvar_snapshot_individual(snapshot)
        self._atualizar_json_global(snapshot)
    
    def gerar_planilha_resultado_ordinaria(self, numero_processo: str, resultado_elegibilidade: Dict,
                                           resultado_decisao: Dict, processos_especificos: Optional[List] = None,
                                           resumo_executivo: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Gera planilha consolidada com os resultados completos da análise"""
        try:
            print("[PLANILHA] Gerando planilha de resultados consolidada...")

            dados_pessoais = resultado_elegibilidade.get('dados_pessoais', {})
            parecer_pf = resultado_elegibilidade.get('parecer_pf', {})
            documentos_complementares = resultado_elegibilidade.get('documentos_complementares', {})

            data_analise = datetime.now()

            # Resultado final e motivos
            resultado_status = resultado_decisao.get('status', '').title() or 'Indefinido'
            motivos_requisitos = resultado_elegibilidade.get('requisitos_nao_atendidos', [])
            if not motivos_requisitos:
                motivos_requisitos = resultado_elegibilidade.get('motivos_indeferimento', [])
            motivos_documentos = resultado_elegibilidade.get('documentos_faltantes', [])
            # Fallback: se vazio, tentar extrair do bloco de documentos_complementares
            if not motivos_documentos and isinstance(documentos_complementares, dict):
                motivos_documentos = documentos_complementares.get('documentos_faltantes', []) or []
            motivos_totais = (motivos_requisitos or []) + (motivos_documentos or [])
            motivo_indeferimento = '; '.join(motivos_totais) if motivos_totais else 'N/A'

            # Requisitos principais
            requisito_i = resultado_elegibilidade.get('requisito_i_capacidade_civil', {})
            requisito_ii = resultado_elegibilidade.get('requisito_ii_residencia_minima', {})
            requisito_iii = resultado_elegibilidade.get('requisito_iii_comunicacao_portugues', {})
            requisito_iv = resultado_elegibilidade.get('requisito_iv_antecedentes_criminais', {})

            def _formatar_requisito(requisito: Dict[str, Any], nome: str) -> str:
                if requisito.get('atendido'):
                    return '✅ ATENDIDO'
                motivo = requisito.get('motivo', f'{nome} não atendido')
                return f'❌ NÃO ATENDIDO - {motivo}'

            requisito_iv_formatado = '✅ ATENDIDO'
            if not requisito_iv.get('atendido'):
                motivo_iv = (requisito_iv.get('motivo') or '').strip()
                motivo_iv_lower = motivo_iv.lower()
                if 'brasil' in motivo_iv_lower:
                    requisito_iv_formatado = '❌ NÃO ATENDIDO (BRASIL)'
                elif any(p in motivo_iv_lower for p in ['país', 'origem']):
                    requisito_iv_formatado = '❌ NÃO ATENDIDO (PAÍS DE ORIGEM)'
                else:
                    # Evitar duplicar "❌ NÃO ATENDIDO" quando já está no motivo
                    if 'não atendido' in motivo_iv_lower or '❌' in motivo_iv:
                        requisito_iv_formatado = '❌ NÃO ATENDIDO'
                    else:
                        requisito_iv_formatado = f'❌ NÃO ATENDIDO - {motivo_iv or "Sem detalhe"}'

            # Documentos complementares
            docs_validos = int(documentos_complementares.get('documentos_validos', 0))
            docs_total = int(documentos_complementares.get('total_documentos', 0)) or 0
            percentual_docs_complementares = documentos_complementares.get('percentual_completude', 0.0)
            documentos_complementares_texto = 'N/A'
            if docs_total > 0:
                documentos_complementares_texto = f"✅ {percentual_docs_complementares:.0f}% ({docs_validos}/{docs_total})"

            # Totais de documentos
            requisitos_validos = sum(1 for req in [requisito_i, requisito_ii, requisito_iii, requisito_iv] if req.get('atendido'))
            requisitos_total = 4
            total_documentos = requisitos_total + docs_total
            total_documentos_validados = requisitos_validos + docs_validos
            percentual_documentos = f"{(total_documentos_validados / total_documentos * 100):.1f}%" if total_documentos > 0 else '0.0%'

            total_documentos_texto = f"{total_documentos_validados}/{total_documentos}" if total_documentos > 0 else '0/0'

            # Dados principais
            codigo_processo = getattr(self.lecom_action, 'numero_processo_limpo', numero_processo)
            nome_requerente = dados_pessoais.get('nome_completo') or dados_pessoais.get('nome') or 'N/A'
            data_inicial = resultado_elegibilidade.get('data_inicial_processo') or self.lecom_action.data_inicial_processo or 'N/A'

            # PF
            decisao_pf = parecer_pf.get('proposta_pf', 'Não encontrado')
            alertas_pf = ' | '.join(parecer_pf.get('alertas', [])) if parecer_pf.get('alertas') else 'Nenhum'
            parecer_texto = (parecer_pf.get('parecer_texto') or 'N/A')
            if len(parecer_texto) > 500:
                parecer_texto = parecer_texto[:500] + '...'

            # Observações e despacho
            despacho_automatico = resultado_decisao.get('despacho_completo', 'Não gerado')
            observacoes = resultado_decisao.get('resumo_analise')
            if not observacoes and resumo_executivo:
                observacoes = resumo_executivo.get('resumo')
            observacoes = observacoes or 'N/A'

            dados_linha = {
                'Número do Processo': numero_processo,
                'Código do Processo': codigo_processo,
                'Nome': nome_requerente,
                'Data Inicial': data_inicial,
                'Tipo de Análise': 'Naturalização Ordinária',
                'Resultado': resultado_status,
                'Motivo do Indeferimento': motivo_indeferimento,
                'Decisão PF': decisao_pf,
                'Alertas PF': alertas_pf,
                'Despacho Automático': despacho_automatico,
                'Requisito I (Capacidade Civil)': _formatar_requisito(requisito_i, 'Capacidade Civil'),
                'Requisito II (Residência Mínima)': _formatar_requisito(requisito_ii, 'Residência Mínima'),
                'Requisito III (Comunicação Português)': _formatar_requisito(requisito_iii, 'Comunicação Português'),
                'Requisito IV (Antecedentes Criminais)': requisito_iv_formatado,
                'Documentos Complementares': documentos_complementares_texto,
                'Total de Documentos Validados': total_documentos_texto,
                'Percentual de Documentos Validados': percentual_documentos,
                'Data da Análise': data_analise.strftime('%d/%m/%Y'),
                'Hora da Análise': data_analise.strftime('%H:%M:%S'),
                'Parecer PF': parecer_texto,
                'Observações': observacoes
            }

            colunas_planilha = [
                'Número do Processo',
                'Código do Processo',
                'Nome',
                'Data Inicial',
                'Tipo de Análise',
                'Resultado',
                'Motivo do Indeferimento',
                'Decisão PF',
                'Alertas PF',
                'Despacho Automático',
                'Requisito I (Capacidade Civil)',
                'Requisito II (Residência Mínima)',
                'Requisito III (Comunicação Português)',
                'Requisito IV (Antecedentes Criminais)',
                'Documentos Complementares',
                'Total de Documentos Validados',
                'Percentual de Documentos Validados',
                'Data da Análise',
                'Hora da Análise',
                'Parecer PF',
                'Observações'
            ]

            df_novo = pd.DataFrame([dados_linha], columns=colunas_planilha)

            diretorio_planilhas = os.path.join(os.getcwd(), 'planilhas')
            os.makedirs(diretorio_planilhas, exist_ok=True)

            if processos_especificos:
                nome_arquivo = f"analise_ordinaria_especifica_{data_analise.strftime('%Y%m%d_%H%M%S')}.xlsx"
            else:
                nome_arquivo = 'analise_ordinaria_consolidada.xlsx'

            caminho_arquivo = os.path.join(diretorio_planilhas, nome_arquivo)

            if os.path.exists(caminho_arquivo) and not processos_especificos:
                df_existente = pd.read_excel(caminho_arquivo)
                for coluna in colunas_planilha:
                    if coluna not in df_existente.columns:
                        df_existente[coluna] = ''
                df = pd.concat([df_existente, df_novo], ignore_index=True)
                df = df[colunas_planilha]
                if 'Número do Processo' in df.columns:
                    tamanho_antes = len(df)
                    df = df.drop_duplicates(subset=['Número do Processo'], keep='last')
                    tamanho_depois = len(df)
                    if tamanho_depois < tamanho_antes:
                        print(f"[PLANILHA] Removidas {tamanho_antes - tamanho_depois} duplicata(s) por Número do Processo")
            else:
                df = df_novo

            df.to_excel(caminho_arquivo, index=False)

            print(f"[OK] Planilha atualizada: {caminho_arquivo}")

            return {
                'sucesso': True,
                'arquivo': nome_arquivo,
                'caminho': caminho_arquivo,
                'dados': dados_linha
            }

        except Exception as e:
            print(f"[ERRO] Erro ao gerar planilha: {e}")
            return {
                'sucesso': False,
                'erro': str(e),
                'dados': None
            }
