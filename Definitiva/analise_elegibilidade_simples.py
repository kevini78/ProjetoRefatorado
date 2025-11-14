"""
Módulo simplificado para análise de elegibilidade para naturalização definitiva
Versão sem dependências do spaCy para evitar conflitos de versão
"""

import re
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AnalisadorElegibilidadeSimples:
    """
    Analisador simplificado para determinar elegibilidade para naturalização definitiva
    baseado em condições legais específicas - sem dependências do spaCy
    """
    
    def __init__(self):
        """Inicializa o analisador de elegibilidade"""
        
        # Condições para elegibilidade
        self.condicoes_obrigatorias = {
            'sem_antecedentes_criminais': {
                'descricao': 'Não possuir antecedentes criminais',
                'peso': 3.0,
                'padroes_positivos': [
                    r'não\s+consta\s+condenação',
                    r'não\s+consta\s+antecedentes',
                    r'sem\s+antecedentes',
                    r'nenhuma\s+condenação',
                    r'limpa\s+antecedentes',
                    r'certidão\s+negativa',
                    r'não\s+consta.*condenação.*trânsito.*julgado',
                    r'certidão.*negativa',
                    r'nada\s+constar',
                    r'não\s+constam.*processos.*criminais',
                    r'verificou\s+nada\s+constar',
                    r'certificamos.*não\s+constam'
                ],
                'padroes_negativos': [
                    r'(?<!não\s)consta\s+condenação',  # Não captura se precedido por "não"
                    r'possui\s+antecedentes',
                    r'com\s+antecedentes',
                    r'condenado',
                    r'processo\s+criminal',
                    r'antecedentes\s+criminais\s+positivos'
                ]
            },
            'naturalizacao_provisoria': {
                'descricao': 'Possuir naturalização provisória válida',
                'peso': 4.0,  # Peso maior por ser condição principal
                'padroes_positivos': [
                    r'naturalização\s+provisória',
                    r'certificado\s+provisório',
                    r'provisório.*naturalização',
                    r'portaria.*provisória',
                    r'naturalização.*provisória',
                    r'certificado.*provisório.*naturalização',
                    r'provisório',
                    r'naturalização\s+provisória\s+confirmada',
                    r'confirmada\s+via\s+banco',
                    r'portaria\s+ministerial\s+mj',
                    r'certificado\s+de\s+naturalização\s+provisório'
                ],
                'padroes_negativos': [
                    r'naturalização\s+definitiva',
                    r'certificado\s+definitivo',
                    r'revogação',
                    r'cancelação',
                    r'perda.*naturalização'
                ]
            },
            'idade_processo': {
                'descricao': 'Idade entre 18-20 anos na data de início do processo',
                'peso': 2.5,
                'padroes_positivos': [
                    r'nascido.*\d{2}/\d{2}/200[0-5]',  # Nascido entre 2000-2005 (18-20 anos em 2023-2025)
                    r'nascido.*\d{2}/\d{2}/199[8-9]',  # Nascido entre 1998-1999 (24-25 anos em 2023-2025)
                    r'idade.*1[8-9]\s*anos',  # 18-19 anos
                    r'idade.*20\s*anos',  # 20 anos
                    r'maior\s+de\s+18',
                    r'maior\s+de\s+dezoito'
                ],
                'padroes_negativos': [
                    r'nascido.*\d{2}/\d{2}/19[0-7]\d',  # Nascido antes de 1998
                    r'nascido.*\d{2}/\d{2}/200[6-9]',  # Nascido entre 2006-2009 (muito jovem)
                    r'idade.*\d{3,}\s*anos',  # Mais de 100 anos
                    r'idade.*[2-9]\d\s*anos',  # 20 anos ou mais
                    r'menor\s+de\s+18',
                    r'menor\s+de\s+dezoito'
                ]
            },
            'comprovante_residencia': {
                'descricao': 'Comprovante de tempo de residência (art. 56)',
                'peso': 2.0,
                'tipo_documento': 'obrigatorio_ressalva',  # Se faltar = ressalva, não indeferimento
                'padroes_positivos': [
                    # Tipos de comprovantes aceitos
                    r'comprovante.*residência',
                    r'comprovante.*tempo.*residência',
                    r'conta.*luz',
                    r'conta.*energia.*elétrica',
                    r'conta.*água',
                    r'conta.*telefone',
                    r'conta.*internet',
                    r'contrato.*aluguel',
                    r'contrato.*locação',
                    r'escritura.*imóvel',
                    r'iptu',
                    r'carnê.*iptu',
                    r'declaração.*residência',
                    r'atestado.*residência',
                    r'comprovante.*endereço',
                    r'fatura.*cartão.*crédito',
                    r'extrato.*bancário',
                    r'correspondência.*bancária',
                    # PADRÕES ESPECÍFICOS DO SISTEMA LECOM
                    r'comprovante.*tempo.*residência.*baixado',
                    r'comprovante.*tempo.*residência.*pdf',
                    r'span.*comprovante.*tempo.*residência.*encontrado',
                    r'debug.*comprovante.*tempo.*residência.*encontrado',
                    r'clique.*realizado.*comprovante.*tempo.*residência',
                    r'novo.*pdf.*detectado.*comprovante.*tempo.*residência',
                    r'arquivo.*baixado.*residência',
                    r'documento.*baixado.*residência',
                    # Padrões de conteúdo de comprovantes
                    r'endereço.*residencial',
                    r'residente.*em',
                    r'localizado.*na.*rua',
                    r'localizado.*na.*avenida',
                    r'cep.*\d{5}-?\d{3}',
                    r'município.*de',
                    r'estado.*de',
                    r'uf:',
                    r'número.*\d+.*complemento',
                    r'bairro.*\w+',
                    # Padrões de empresas de serviços
                    r'cpfl.*energia',
                    r'enel.*distribuição',
                    r'light.*energia',
                    r'cemig',
                    r'copel',
                    r'energisa',
                    r'sabesp',
                    r'cedae',
                    r'sanepar',
                    r'vivo.*telefonia',
                    r'claro.*telefonia',
                    r'tim.*telefonia',
                    r'oi.*telefonia'
                ],
                'padroes_negativos': [
                    r'comprovante.*não.*anexado',
                    r'documento.*não.*encontrado',
                    r'erro.*download.*residência',
                    r'falha.*baixar.*residência',
                    r'timeout.*comprovante.*tempo.*residência',
                    r'erro.*tentar.*baixar.*comprovante.*tempo.*residência'
                ]
            },
            'documento_identidade': {
                'descricao': 'Documento oficial de identidade',
                'peso': 2.0,
                'tipo_documento': 'obrigatorio_ressalva',  # Se faltar = ressalva, não indeferimento
                'padroes_positivos': [
                    # Tipos de identidade aceitos
                    r'documento.*oficial.*identidade',
                    r'carteira.*identidade',
                    r'rg',
                    r'registro.*geral',
                    r'cartão.*nacional.*identidade',
                    r'cni',
                    r'passaporte',
                    r'carteira.*trabalho',
                    r'ctps',
                    r'carteira.*motorista',
                    r'cnh',
                    r'identidade.*estrangeiro',
                    r'cie',
                    r'rne',
                    r'registro.*nacional.*estrangeiro',
                    # PADRÕES ESPECÍFICOS DO SISTEMA LECOM
                    r'documento.*oficial.*identidade.*baixado',
                    r'documento.*oficial.*identidade.*pdf',
                    r'span.*documento.*oficial.*identidade.*encontrado',
                    r'debug.*documento.*oficial.*identidade.*encontrado',
                    r'clique.*realizado.*documento.*oficial.*identidade',
                    r'novo.*pdf.*detectado.*documento.*oficial.*identidade',
                    r'documento.*identidade.*baixado',
                    r'span.*documento.*oficial.*identidade',
                    # Padrões de conteúdo de documentos de identidade
                    r'república.*federativa.*brasil',
                    r'estado.*de.*\w+',
                    r'organismo.*identificação',
                    r'secretaria.*segurança.*pública',
                    r'instituto.*identificação',
                    r'número.*documento.*\d+',
                    r'órgão.*expedidor',
                    r'orgão.*empressor',  # Possível erro de OCR
                    r'data.*expedição',
                    r'uf:.*\w{2}',
                    r'categoria.*identidade',
                    r'registro.*geral.*\d+',
                    r'nome.*completo.*\w+',
                    r'data.*nascimento.*\d{2}/\d{2}/\d{4}',
                    r'filiação.*\w+',
                    r'naturalidade.*\w+',
                    r'documento.*nacional.*identidade',
                    r'válido.*em.*todo.*território.*nacional',
                    # Padrões específicos para estrangeiros
                    r'identidade.*estrangeiro',
                    r'serviço.*público.*federal',
                    r'departamento.*federal.*segurança.*pública',
                    r'polícia.*federal',
                    r'origem.*\w+',
                    r'observação.*identidade.*estrangeiro'
                ],
                'padroes_negativos': [
                    r'identidade.*não.*anexada',
                    r'documento.*não.*encontrado',
                    r'erro.*download.*identidade',
                    r'falha.*baixar.*identidade',
                    r'timeout.*documento.*oficial.*identidade',
                    r'erro.*tentar.*baixar.*documento.*oficial.*identidade'
                ]
            }
        }
        
        # Condições adicionais que podem favorecer
        self.condicoes_favoraveis = {
            'tempo_residencia': {
                'descricao': 'Tempo adequado de residência no Brasil',
                'peso': 1.5,
                'padroes': [
                    r'residindo.*\d+\s*anos',
                    r'residência.*\d+\s*anos',
                    r'tempo.*residência',
                    r'permanência.*\d+\s*anos'
                ]
            },
            'documentacao_completa': {
                'descricao': 'Documentação completa e válida',
                'peso': 1.0,
                'padroes': [
                    r'certificado.*válido',
                    r'documento.*válido',
                    r'validade.*\d{4}',
                    r'vigente',
                    r'atualizado'
                ]
            }
        }
        
        # Condições que podem desqualificar
        self.condicoes_desqualificadoras = {
            # REMOVIDO: 'antecedentes_criminais' - conflita com 'sem_antecedentes_criminais'
            # A lógica de antecedentes é tratada exclusivamente em _verificar_condicao_sem_antecedentes_criminais()
            'naturalizacao_revogada': {
                'descricao': 'Naturalização revogada ou cancelada',
                'peso': -4.0,
                'padroes': [
                    r'revogação',
                    r'cancelação',
                    r'perda.*naturalização',
                    r'decisão.*negativa',
                    r'indeferimento'
                ]
            },
            'idade_inadequada': {
                'descricao': 'Idade inadequada para o processo',
                'peso': -3.0,
                'padroes': [
                    r'menor\s+de\s+18',
                    r'idade.*\d{1,2}\s*anos',  # Muito jovem
                    r'nascido.*\d{2}/\d{2}/20[1-9]\d'  # Muito novo
                ]
            }
        }
    
    def analisar_elegibilidade(self, documentos: Dict[str, str], dados_formulario: Dict = None) -> Dict:
        """
        Analisa a elegibilidade de um processo para naturalização definitiva
        
        Args:
            documentos: Dicionário com nome_documento -> texto_extraido
            dados_formulario: Dados extraídos do formulário (opcional)
            
        Returns:
            Dict com resultado da análise
        """
        logger.info("Iniciando análise de elegibilidade para naturalização definitiva")
        
        # Limpar lista de documentos faltantes de análise anterior
        if hasattr(self, 'documentos_faltantes_ressalva'):
            delattr(self, 'documentos_faltantes_ressalva')
        
        # Análise de cada condição obrigatória
        resultados_condicoes = {}
        score_total = 0.0
        condicoes_atendidas = 0
        condicoes_nao_atendidas = 0
        
        for nome_condicao, config in self.condicoes_obrigatorias.items():
            resultado = self._verificar_condicao(nome_condicao, config, documentos, dados_formulario)
            resultados_condicoes[nome_condicao] = resultado
            
            print(f"DEBUG: [INFO] CONDIÇÃO: {nome_condicao}")
            print(f"       Descrição: {config['descricao']}")
            print(f"       Atendida: {'[OK] SIM' if resultado['atendida'] else '[ERRO] NÃO'}")
            print(f"       Score: {resultado['score']:.2f}")
            print(f"       Motivo: {resultado['motivo']}")
            
            # Verificar se é um documento que gera ressalva em vez de indeferimento
            eh_documento_ressalva = config.get('tipo_documento') == 'obrigatorio_ressalva'
            
            if resultado['atendida']:
                condicoes_atendidas += 1
                score_total += resultado['score'] * config['peso']
                print(f"       Status: [OK] CONDIÇÃO ATENDIDA (+{resultado['score'] * config['peso']:.2f} pontos)")
            else:
                condicoes_nao_atendidas += 1
                score_total += resultado['score'] * config['peso']
                
                if eh_documento_ressalva:
                    print(f"       Status: [AVISO] DOCUMENTO AUSENTE - GERARÁ RESSALVA (+{resultado['score'] * config['peso']:.2f} pontos)")
                    # Adicionar à lista de documentos faltantes para ressalva
                    if not hasattr(self, 'documentos_faltantes_ressalva'):
                        self.documentos_faltantes_ressalva = []
                    self.documentos_faltantes_ressalva.append(nome_condicao)
                else:
                    print(f"       Status: [ERRO] CONDIÇÃO NÃO ATENDIDA (+{resultado['score'] * config['peso']:.2f} pontos)")
            print(f"       " + "="*50)
        
        # Análise de condições favoráveis
        condicoes_favoraveis_encontradas = 0
        for nome_condicao, config in self.condicoes_favoraveis.items():
            resultado = self._verificar_condicao_favoravel(nome_condicao, config, documentos)
            if resultado['encontrada']:
                condicoes_favoraveis_encontradas += 1
                score_total += resultado['score'] * config['peso']
        
        # Análise de condições desqualificadoras
        condicoes_desqualificadoras_encontradas = 0
        for nome_condicao, config in self.condicoes_desqualificadoras.items():
            resultado = self._verificar_condicao_desqualificadora(nome_condicao, config, documentos)
            if resultado['encontrada']:
                condicoes_desqualificadoras_encontradas += 1
                score_total += resultado['score'] * config['peso']
        
        # Determinar elegibilidade
        elegibilidade = self._determinar_elegibilidade(
            score_total, condicoes_atendidas, condicoes_nao_atendidas,
            condicoes_desqualificadoras_encontradas
        )
        
        # Calcular confiança
        confianca = self._calcular_confianca(
            condicoes_atendidas, condicoes_nao_atendidas,
            condicoes_favoraveis_encontradas, condicoes_desqualificadoras_encontradas
        )
        
        resultado_final = {
            'elegibilidade': elegibilidade,
            'confianca': confianca,
            'score_total': round(score_total, 2),
            'condicoes_obrigatorias': {
                'atendidas': condicoes_atendidas,
                'nao_atendidas': condicoes_nao_atendidas,
                'total': len(self.condicoes_obrigatorias),
                'detalhes': resultados_condicoes
            },
            'condicoes_favoraveis': {
                'encontradas': condicoes_favoraveis_encontradas,
                'total': len(self.condicoes_favoraveis)
            },
            'condicoes_desqualificadoras': {
                'encontradas': condicoes_desqualificadoras_encontradas,
                'total': len(self.condicoes_desqualificadoras)
            },
            'documentos_ressalva': {
                'faltantes': getattr(self, 'documentos_faltantes_ressalva', []),
                'total_faltantes': len(getattr(self, 'documentos_faltantes_ressalva', [])),
                'descricoes_faltantes': [
                    self.condicoes_obrigatorias[doc]['descricao'] 
                    for doc in getattr(self, 'documentos_faltantes_ressalva', [])
                ]
            },
            'recomendacao': self._gerar_recomendacao(elegibilidade, resultados_condicoes),
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info(f"Análise concluída: {elegibilidade} (Confiança: {confianca:.1%})")
        return resultado_final
    
    def _verificar_condicao(self, nome_condicao: str, config: Dict, documentos: Dict[str, str], dados_formulario: Dict = None) -> Dict:
        """Verifica se uma condição obrigatória foi atendida"""
        texto_completo = " ".join(documentos.values()).lower()
        
        # Inicializar variáveis de controle
        idade_calculada = None
        
        # Verificar padrões positivos
        padroes_positivos_encontrados = []
        for padrao in config['padroes_positivos']:
            if re.search(padrao, texto_completo, re.IGNORECASE):
                padroes_positivos_encontrados.append(padrao)
        
        # Verificar padrões negativos
        padroes_negativos_encontrados = []
        for padrao in config['padroes_negativos']:
            if re.search(padrao, texto_completo, re.IGNORECASE):
                padroes_negativos_encontrados.append(padrao)
        
        # Lógica especial para antecedentes criminais
        if nome_condicao == 'sem_antecedentes_criminais':
            # Verificar explicitamente por certidões negativas
            padroes_certidao_negativa = [
                r'não\s+consta\s+condenação',
                r'não\s+constam.*processos.*criminais',
                r'verificou\s+nada\s+constar',
                r'certificamos.*não\s+constam',
                r'nada\s+constar',
                r'certidão.*negativa',
                r'não\s+consta.*trânsito.*julgado',
                r'verificou\s+nada\s+constar.*contra',
                r'certificamos.*não\s+constam.*processos.*criminais'
            ]
            
            tem_certidao_negativa = False
            for padrao in padroes_certidao_negativa:
                if re.search(padrao, texto_completo, re.IGNORECASE):
                    tem_certidao_negativa = True
                    padroes_positivos_encontrados.append(f'certidao_negativa_{padrao}')
                    print(f"DEBUG: Certidão negativa detectada com padrão: {padrao}")
                    break
            
            # CORREÇÃO CRÍTICA: Verificar se há negação explícita antes de "consta condenação"
            # Padrões de negação que devem ser verificados ANTES de qualquer padrão positivo
            padroes_negacao_explicita = [
                r'não\s+consta\s+condenação',
                r'não\s+constam.*condenação',
                r'verificou\s+nada\s+constar.*condenação',
                r'não\s+consta.*trânsito.*julgado',
                r'não\s+consta.*processo.*criminal',
                r'não\s+consta.*antecedente',
                r'não\s+consta.*histórico.*criminal'
            ]
            
            # Verificar se há negação explícita
            tem_negacao_explicita = False
            for padrao_neg in padroes_negacao_explicita:
                if re.search(padrao_neg, texto_completo, re.IGNORECASE):
                    tem_negacao_explicita = True
                    padroes_positivos_encontrados.append(f'negacao_explicita_{padrao_neg}')
                    print(f"DEBUG: [OK] Negação explícita detectada: {padrao_neg}")
                    break
            
            # Se tem negação explícita, LIMPAR TODOS os padrões negativos e forçar como positiva
            if tem_negacao_explicita:
                print(f"DEBUG: 🚨 NEGAÇÃO EXPLÍCITA DETECTADA - limpando TODOS os padrões negativos")
                padroes_negativos_encontrados = []
                # Forçar score positivo alto
                padroes_positivos_encontrados.append('antecedentes_limpos_confirmados_negacao_explicita')
                print(f"DEBUG: [TARGET] Antecedentes limpos confirmados por negação explícita - score positivo alto")
                
                # Marcar como já processado e não continuar com outras verificações
                tem_certidao_negativa = True  # Usar flag existente
                print(f"DEBUG: [OK] Processamento de antecedentes concluído por negação explícita")
            else:
                # Se tem certidão negativa, limpar qualquer padrão negativo e forçar como positiva
                if tem_certidao_negativa:
                    print(f"DEBUG: Certidão negativa confirmada - limpando padrões negativos")
                    padroes_negativos_encontrados = []
                    # Forçar score positivo alto
                    padroes_positivos_encontrados.append('antecedentes_limpos_confirmados')
                    print(f"DEBUG: Antecedentes limpos confirmados - score positivo alto")
                
                # Verificar por padrões específicos de antecedentes limpos
                padroes_antecedentes_limpos = [
                    r'limpa\s+antecedentes',
                    r'sem\s+antecedentes',
                    r'nenhuma\s+condenação',
                    r'antecedentes\s+limpos',
                    r'histórico\s+limpo'
                ]
                
                for padrao in padroes_antecedentes_limpos:
                    if re.search(padrao, texto_completo, re.IGNORECASE):
                        padroes_positivos_encontrados.append(f'antecedentes_limpos_{padrao}')
                        print(f"DEBUG: Padrão de antecedentes limpos detectado: {padrao}")
                
                # Se encontrou múltiplos padrões positivos, aumentar score
                if len(padroes_positivos_encontrados) > 1:
                    padroes_positivos_encontrados.append('múltiplas_confirmações')
                    print(f"DEBUG: Múltiplas confirmações de antecedentes limpos")
        
        # Lógica especial para idade - USAR DADOS DO FORMULÁRIO PRIMEIRO
        elif nome_condicao == 'idade_processo':
            # PRIORIZAR dados do formulário se disponíveis
            if dados_formulario and dados_formulario.get('data_nascimento'):
                data_nascimento_formulario = dados_formulario['data_nascimento']
                print(f"DEBUG: Usando data de nascimento do formulário: {data_nascimento_formulario}")
                
                try:
                    # Normalizar formato da data do formulário
                    if '/' in data_nascimento_formulario:
                        data_nasc = datetime.strptime(data_nascimento_formulario, '%d/%m/%Y')
                    elif '-' in data_nascimento_formulario:
                        data_nasc = datetime.strptime(data_nascimento_formulario, '%d-%m-%Y')
                    else:
                        raise ValueError("Formato de data não reconhecido")
                    
                    data_atual = datetime.now()
                    idade_calculada = data_atual.year - data_nasc.year
                    if data_atual.month < data_nasc.month or (data_atual.month == data_nasc.month and data_atual.day < data_nasc.day):
                        idade_calculada -= 1
                    
                    print(f"DEBUG: Idade calculada do formulário: {idade_calculada} anos")
                    
                except Exception as e:
                    print(f"DEBUG: Erro ao calcular idade do formulário: {e}")
                    idade_calculada = None
            
            # Se não conseguiu calcular do formulário, tentar do OCR
            if idade_calculada is None:
                print(f"DEBUG: Tentando extrair data de nascimento do OCR...")
                padroes_data = [
                    r'data\s+de\s+nascimento[:\s]*(\d{2}/\d{2}/\d{4})',
                    r'data\s+de\s+nascimento[:\s]*(\d{2}-\d{2}-\d{4})',
                    r'nascimento[:\s]*(\d{2}/\d{2}/\d{4})',
                    r'nascimento[:\s]*(\d{2}-\d{2}-\d{4})',
                    r'nascido.*(\d{2}/\d{2}/\d{4})',
                    r'nascida.*(\d{2}/\d{2}/\d{4})'
                ]
                
                data_encontrada = None
                for padrao in padroes_data:
                    match_data = re.search(padrao, texto_completo, re.IGNORECASE)
                    if match_data:
                        data_encontrada = match_data.group(1)
                        break
                
                if data_encontrada:
                    try:
                        if '-' in data_encontrada:
                            data_nasc = datetime.strptime(data_encontrada, '%d-%m-%Y')
                        else:
                            data_nasc = datetime.strptime(data_encontrada, '%d/%m/%Y')
                        
                        data_atual = datetime.now()
                        idade_calculada = data_atual.year - data_nasc.year
                        if data_atual.month < data_nasc.month or (data_atual.month == data_nasc.month and data_atual.day < data_nasc.day):
                            idade_calculada -= 1
                        
                        print(f"DEBUG: Data encontrada no OCR: {data_encontrada}, Idade calculada: {idade_calculada} anos")
                        
                    except Exception as e:
                        print(f"DEBUG: Erro ao calcular idade do OCR: {e}")
            
            # Aplicar lógica de elegibilidade por idade
            if idade_calculada is not None:
                if idade_calculada < 18 or idade_calculada > 20:
                    padroes_positivos_encontrados = []
                    padroes_negativos_encontrados = ['idade_inadequada']
                    print(f"DEBUG: Idade calculada: {idade_calculada} anos - fora da faixa 18-20")
                else:
                    padroes_positivos_encontrados.append(f'idade_correta_{idade_calculada}_anos')
                    padroes_negativos_encontrados = []  # Limpar negativos
                    print(f"DEBUG: Idade calculada: {idade_calculada} anos - dentro da faixa 18-20")
            else:
                print(f"DEBUG: Não foi possível calcular a idade")
        
        # Lógica especial para naturalização provisória
        elif nome_condicao == 'naturalizacao_provisoria':
            print("DEBUG: [TARGET] Verificando naturalização provisória...")
            
            # [DEBUG] CORREÇÃO CRÍTICA: Priorizar confirmação via banco de dados sobre OCR
            # Verificar primeiro se há confirmação explícita via banco
            confirmacao_banco_encontrada = False
            for nome_doc, texto_doc in documentos.items():
                if 'confirmacao' in nome_doc.lower() and 'banco' in nome_doc.lower():
                    if 'naturalização provisória confirmada' in texto_doc.lower():
                        confirmacao_banco_encontrada = True
                        print("DEBUG: [OK] Naturalização provisória confirmada via banco de dados")
                        break
            
            # Se confirmada via banco, marcar como atendida SEM verificar OCR
            if confirmacao_banco_encontrada:
                padroes_positivos_encontrados.append('confirmacao_via_banco')
                print("DEBUG: [TARGET] Naturalização provisória CONFIRMADA via banco de dados")
                # Não continuar com verificação de OCR - já confirmada via banco
            else:
                # Se não confirmada via banco, verificar padrões nos documentos
                for padrao in config['padroes_positivos']:
                    if re.search(padrao, texto_completo, re.IGNORECASE):
                        padroes_positivos_encontrados.append(padrao)
                        print(f"DEBUG: [OK] Padrão de naturalização encontrado: {padrao}")
                
                # Se não encontrou nenhuma evidência
                if not padroes_positivos_encontrados:
                    print("DEBUG: [AVISO] NENHUMA evidência de naturalização provisória encontrada")
                    print(f"DEBUG: Texto verificado (primeiros 500 chars): {texto_completo[:500]}")
                    print("DEBUG: Verificando dados do formulário...")
                
                # Aplicar padrões padrões se não encontrou confirmação especial
                for padrao in config['padroes_positivos']:
                    if re.search(padrao, texto_completo, re.IGNORECASE):
                        padroes_positivos_encontrados.append(padrao)
                        print(f"DEBUG: Padrão padrão encontrado: {padrao}")
        
        elif nome_condicao == 'comprovante_residencia':
            print("DEBUG: 🏠 Verificando comprovante de residência...")
            
            # Verificar padrões positivos nos textos
            evidencias_positivas = []
            for padrao in config['padroes_positivos']:
                if re.search(padrao, texto_completo, re.IGNORECASE):
                    evidencias_positivas.append(padrao)
                    print(f"DEBUG: [OK] Padrão de residência encontrado: {padrao}")
            
            # Verificar também logs do sistema para downloads
            for nome_doc, texto_doc in documentos.items():
                if 'comprovante' in nome_doc.lower() and ('tempo' in nome_doc.lower() or 'residência' in nome_doc.lower()):
                    print(f"DEBUG: 🏠 Analisando documento: {nome_doc}")
                    # Se o documento foi baixado com sucesso
                    if len(texto_doc.strip()) > 100:  # Documento com conteúdo significativo
                        evidencias_positivas.append(f"documento_{nome_doc}_baixado_com_conteudo")
                        print(f"DEBUG: [OK] Documento de residência baixado com conteúdo: {len(texto_doc)} chars")
                        break
            
            if evidencias_positivas:
                resultado = {
                    'atendida': True,
                    'score': config['peso'],
                    'motivo': f"Comprovante de residência encontrado ({len(evidencias_positivas)} evidências)",
                    'padroes_positivos_encontrados': evidencias_positivas,
                    'padroes_negativos_encontrados': [],
                    'descricao': config['descricao'],
                    'peso': config['peso']
                }
            else:
                # Verificar se documento foi tentado mas falhou
                documento_tentado = False
                for nome_doc in documentos.keys():
                    if 'comprovante' in nome_doc.lower() and 'tempo' in nome_doc.lower():
                        documento_tentado = True
                        break
                
                # Se o documento é do tipo 'obrigatorio_ressalva', adicionar à lista de faltantes
                if config.get('tipo_documento') == 'obrigatorio_ressalva':
                    if not hasattr(self, 'documentos_faltantes_ressalva'):
                        self.documentos_faltantes_ressalva = []
                    self.documentos_faltantes_ressalva.append(nome_condicao)
                    print("DEBUG: [AVISO] Comprovante de residência NÃO encontrado - gerará ressalva")
                
                resultado = {
                    'atendida': False,
                    'score': 0,
                    'motivo': "Nenhuma evidência positiva encontrada nos documentos",
                    'padroes_positivos_encontrados': [],
                    'padroes_negativos_encontrados': [],
                    'descricao': config['descricao'],
                    'peso': config['peso']
                }
            
            # Retornar resultado customizado sem processar lógica padrão
            return resultado
        
        elif nome_condicao == 'documento_identidade':
            print("DEBUG: 🆔 Verificando documento de identidade...")
            
            # Verificar padrões positivos nos textos
            evidencias_positivas = []
            for padrao in config['padroes_positivos']:
                if re.search(padrao, texto_completo, re.IGNORECASE):
                    evidencias_positivas.append(padrao)
                    print(f"DEBUG: [OK] Padrão de identidade encontrado: {padrao}")
            
            # Verificar também logs do sistema para downloads
            for nome_doc, texto_doc in documentos.items():
                if 'identidade' in nome_doc.lower() or 'documento' in nome_doc.lower():
                    print(f"DEBUG: 🆔 Analisando documento: {nome_doc}")
                    # Se o documento foi baixado com sucesso
                    if len(texto_doc.strip()) > 100:  # Documento com conteúdo significativo
                        evidencias_positivas.append(f"documento_{nome_doc}_baixado_com_conteudo")
                        print(f"DEBUG: [OK] Documento de identidade baixado com conteúdo: {len(texto_doc)} chars")
                        break
            
            if evidencias_positivas:
                resultado = {
                    'atendida': True,
                    'score': config['peso'],
                    'motivo': f"Documento de identidade encontrado ({len(evidencias_positivas)} evidências)",
                    'padroes_positivos_encontrados': evidencias_positivas,
                    'padroes_negativos_encontrados': [],
                    'descricao': config['descricao'],
                    'peso': config['peso']
                }
            else:
                # Se o documento é do tipo 'obrigatorio_ressalva', adicionar à lista de faltantes
                if config.get('tipo_documento') == 'obrigatorio_ressalva':
                    if not hasattr(self, 'documentos_faltantes_ressalva'):
                        self.documentos_faltantes_ressalva = []
                    self.documentos_faltantes_ressalva.append(nome_condicao)
                    print("DEBUG: [AVISO] Documento de identidade NÃO encontrado - gerará ressalva")
                
                resultado = {
                    'atendida': False,
                    'score': 0,
                    'motivo': "Nenhuma evidência positiva encontrada nos documentos",
                    'padroes_positivos_encontrados': [],
                    'padroes_negativos_encontrados': [],
                    'descricao': config['descricao'],
                    'peso': config['peso']
                }
            
            # Retornar resultado customizado sem processar lógica padrão
            return resultado
        
        # Determinar se a condição foi atendida
        atendida = len(padroes_positivos_encontrados) > 0 and len(padroes_negativos_encontrados) == 0
        
        # Calcular score
        score = len(padroes_positivos_encontrados) - len(padroes_negativos_encontrados)
        
        # Gerar motivo explicativo
        if atendida:
            if nome_condicao == 'sem_antecedentes_criminais':
                motivo = f"Antecedentes limpos confirmados ({len(padroes_positivos_encontrados)} evidências)"
            elif nome_condicao == 'idade_processo':
                motivo = f"Idade adequada ({idade_calculada if idade_calculada is not None else 'verificada'} anos)"
            elif nome_condicao == 'naturalizacao_provisoria':
                motivo = f"Naturalização provisória confirmada ({len(padroes_positivos_encontrados)} evidências)"
            else:
                motivo = f"Condição atendida ({len(padroes_positivos_encontrados)} evidências positivas)"
        else:
            if len(padroes_negativos_encontrados) > 0:
                motivo = f"Evidências negativas encontradas: {padroes_negativos_encontrados}"
            elif len(padroes_positivos_encontrados) == 0:
                motivo = "Nenhuma evidência positiva encontrada nos documentos"
            else:
                motivo = f"Evidências mistas: {len(padroes_positivos_encontrados)} positivas, {len(padroes_negativos_encontrados)} negativas"
        
        return {
            'atendida': atendida,
            'score': score,
            'motivo': motivo,
            'padroes_positivos_encontrados': padroes_positivos_encontrados,
            'padroes_negativos_encontrados': padroes_negativos_encontrados,
            'descricao': config['descricao'],
            'peso': config['peso']
        }
    
    def _verificar_condicao_favoravel(self, nome_condicao: str, config: Dict, documentos: Dict[str, str]) -> Dict:
        """Verifica se uma condição favorável foi encontrada"""
        texto_completo = " ".join(documentos.values()).lower()
        
        padroes_encontrados = []
        for padrao in config['padroes']:
            if re.search(padrao, texto_completo, re.IGNORECASE):
                padroes_encontrados.append(padrao)
        
        # NOTA: Lógica especial para antecedentes criminais foi movida para o método específico
        # _verificar_condicao_sem_antecedentes_criminais() - não usar lógica genérica aqui
        
        encontrada = len(padroes_encontrados) > 0
        score = len(padroes_encontrados)
        
        return {
            'encontrada': encontrada,
            'score': score,
            'padroes_encontrados': padroes_encontrados,
            'descricao': config['descricao']
        }
    
    def _verificar_condicao_desqualificadora(self, nome_condicao: str, config: Dict, documentos: Dict[str, str]) -> Dict:
        """Verifica se uma condição desqualificadora foi encontrada"""
        texto_completo = " ".join(documentos.values()).lower()
        
        padroes_encontrados = []
        for padrao in config['padroes']:
            if re.search(padrao, texto_completo, re.IGNORECASE):
                padroes_encontrados.append(padrao)
        
        # NOTA: Lógica especial para antecedentes criminais foi removida
        # A detecção de antecedentes é tratada exclusivamente em _verificar_condicao_sem_antecedentes_criminais()
        
        encontrada = len(padroes_encontrados) > 0
        score = len(padroes_encontrados)
        
        return {
            'encontrada': encontrada,
            'score': score,
            'padroes_encontrados': padroes_encontrados,
            'descricao': config['descricao']
        }
    
    def _determinar_elegibilidade(self, score_total: float, condicoes_atendidas: int, 
                                condicoes_nao_atendidas: int, condicoes_desqualificadoras: int) -> str:
        """Determina a elegibilidade baseada nos resultados"""
        
        # Se há condições desqualificadoras, automaticamente não elegível
        if condicoes_desqualificadoras > 0:
            return 'não_elegivel'
        
        # Verificar se há documentos faltantes que geram ressalva
        documentos_faltantes = getattr(self, 'documentos_faltantes_ressalva', [])
        tem_documentos_faltantes = len(documentos_faltantes) > 0
        
        # Contar apenas condições críticas (não de ressalva) não atendidas
        condicoes_criticas_nao_atendidas = condicoes_nao_atendidas - len(documentos_faltantes)
        
        print(f"DEBUG: [DADOS] Análise de elegibilidade:")
        print(f"       Total condições não atendidas: {condicoes_nao_atendidas}")
        print(f"       Documentos faltantes (ressalva): {len(documentos_faltantes)} - {documentos_faltantes}")
        print(f"       Condições críticas não atendidas: {condicoes_criticas_nao_atendidas}")
        
        # Se todas as condições críticas foram atendidas
        if condicoes_criticas_nao_atendidas == 0:
            if tem_documentos_faltantes:
                # Tem documentos faltantes mas condições críticas OK = DEFERIMENTO COM RESSALVAS
                print(f"DEBUG: [OK] Condições críticas atendidas, mas faltam documentos: {documentos_faltantes}")
                return 'deferimento_com_ressalvas'
            else:
                # Tudo perfeito = elegibilidade baseada no score
                if score_total >= 15.0:
                    return 'elegivel_alta_probabilidade'
                elif score_total >= 10.0:
                    return 'elegivel_probabilidade_media'
                else:
                    return 'elegivel_probabilidade_baixa'
        
        # LÓGICA ESPECIAL: Se apenas condições críticas não foram atendidas (sem considerar documentos de ressalva)
        elif condicoes_criticas_nao_atendidas == 1:
            # Se tem score alto (antecedentes limpos + idade confirmados)
            if score_total >= 10.0:
                if tem_documentos_faltantes:
                    return 'deferimento_com_ressalvas'  # 1 condição crítica + docs faltantes
                else:
                    return 'elegivel_alta_probabilidade'  # Apenas 1 condição crítica
            elif score_total >= 8.0:
                if tem_documentos_faltantes:
                    return 'deferimento_com_ressalvas'
                else:
                    return 'elegivel_probabilidade_media'
            elif score_total >= 5.0:
                return 'elegivel_com_ressalvas'
            else:
                return 'elegibilidade_incerta'
        
        # Se muitas condições críticas não foram atendidas
        elif condicoes_criticas_nao_atendidas <= 2:  # Até 2 condições críticas não atendidas
            if score_total >= 8.0:
                return 'elegivel_com_ressalvas'
            elif score_total >= 5.0:
                return 'elegibilidade_incerta'
            else:
                return 'não_elegivel'
        else:
            return 'não_elegivel'
    
    def _calcular_confianca(self, condicoes_atendidas: int, condicoes_nao_atendidas: int,
                           condicoes_favoraveis: int, condicoes_desqualificadoras: int) -> float:
        """Calcula o nível de confiança da análise"""
        
        total_condicoes = condicoes_atendidas + condicoes_nao_atendidas
        
        if total_condicoes == 0:
            return 0.0
        
        # Base de confiança nas condições obrigatórias
        confianca_base = condicoes_atendidas / total_condicoes
        
        # Ajustes baseados em condições adicionais
        if condicoes_favoraveis > 0:
            confianca_base += 0.20  # Aumentado de 0.15 para 0.20
        
        if condicoes_desqualificadoras > 0:
            confianca_base -= 0.2
        
        # BONUS ESPECIAL: Se todas as condições obrigatórias foram atendidas
        if condicoes_nao_atendidas == 0:
            confianca_base += 0.25  # Aumentado de 0.20 para 0.25 - bônus de 25% para casos completos
        
        # BONUS ESPECIAL: Se tem antecedentes limpos confirmados E naturalização confirmada
        if condicoes_atendidas >= 2 and condicoes_nao_atendidas <= 1:
            confianca_base += 0.15  # Aumentado de 0.10 para 0.15 - bônus de 15% para casos com antecedentes limpos
        
        # BONUS EXTRA: Se tem 2 condições atendidas (idade + antecedentes limpos)
        if condicoes_atendidas >= 2:
            confianca_base += 0.10  # Bônus adicional de 10% para múltiplas condições atendidas
        
        # Limitar entre 0.0 e 1.0
        confianca_final = max(0.0, min(1.0, confianca_base))
        
        print(f"DEBUG: Cálculo de confiança:")
        print(f"  - Base inicial: {condicoes_atendidas}/{total_condicoes} = {condicoes_atendidas/total_condicoes:.3f}")
        print(f"  - Base final: {confianca_base:.3f}")
        print(f"  - Condições atendidas: {condicoes_atendidas}")
        print(f"  - Condições não atendidas: {condicoes_nao_atendidas}")
        print(f"  - Condições favoráveis: {condicoes_favoraveis}")
        print(f"  - Confiança final: {confianca_final:.3f} ({confianca_final*100:.1f}%)")
        
        return confianca_final
    
    def _gerar_recomendacao(self, elegibilidade: str, resultados_condicoes: Dict) -> str:
        """Gera uma recomendação baseada na elegibilidade"""
        
        if elegibilidade == 'elegivel_alta_probabilidade':
            return "[OK] RECOMENDADO: Processo elegível com alta probabilidade de aprovação"
        
        elif elegibilidade == 'elegivel_probabilidade_media':
            return "[OK] RECOMENDADO: Processo elegível com probabilidade média de aprovação"
        
        elif elegibilidade == 'elegivel_probabilidade_baixa':
            return "[AVISO] RECOMENDADO COM RESSALVAS: Processo elegível mas com baixa probabilidade"
        
        elif elegibilidade == 'elegivel_com_ressalvas':
            return "[AVISO] RECOMENDADO COM RESSALVAS: Processo elegível mas requer atenção especial"
        
        elif elegibilidade == 'elegibilidade_incerta':
            return "❓ ELEGIBILIDADE INCERTA: Mais informações necessárias para determinar"
        
        elif elegibilidade == 'não_elegivel':
            return "[ERRO] NÃO RECOMENDADO: Processo não elegível para naturalização definitiva"
        
        elif elegibilidade == 'deferimento_com_ressalvas':
            return "[OK] RECOMENDADO COM RESSALVAS: Processo elegível mas requer atenção especial"
        
        else:
            return "❓ STATUS INDETERMINADO: Análise inconclusiva"


# Funções de conveniência
def analisar_elegibilidade_definitiva(documentos: Dict[str, str], dados_formulario: Dict = None) -> Dict:
    """
    Função de conveniência para análise de elegibilidade
    
    Args:
        documentos (Dict[str, str]): Dicionário com nome do documento e texto
        dados_formulario (Dict): Dados extraídos do formulário (prioridade sobre OCR)
    
    Returns:
        Dict: Resultado da análise de elegibilidade
    """
    analisador = AnalisadorElegibilidadeSimples()
    return analisador.analisar_elegibilidade(documentos, dados_formulario)


def analisar_documento_especifico(nome_documento: str, texto: str) -> Dict:
    """
    Função de conveniência para análise de documento específico
    
    Args:
        nome_documento (str): Nome do documento
        texto (str): Texto extraído do documento
    
    Returns:
        Dict: Análise do documento específico
    """
    analisador = AnalisadorElegibilidadeSimples()
    return analisador.analisar_documento_especifico(nome_documento, texto)


if __name__ == "__main__":
    # Teste do módulo
    print("[TESTE] TESTANDO ANALISADOR SIMPLIFICADO")
    print("=" * 50)
    
    # Exemplo de uso com os documentos reais
    documentos_teste = {
        'Documento oficial de identidade': """
        REPÚBLICA FEDERATIVA DO BRASIL
        ESTADO DE SÃO PAULO
        ORGÃO DEMISSOR: POLÍCIA CIVIL
        NÚMERO DO DOCUMENTO: 25.101.2005
        NOME: HUANG PO CHANG
        DATA DE NASCIMENTO: 25/10/1983
        SEXO: MASCULINO
        COR: BRANCA
        ESTADO CIVIL: CASADO
        PROFISSÃO: OUTRA
        ORIGEM: CHINA/TAIWAN
        ENDEREÇO: RUA
        NÚMERO: 123
        BAIRRO: CENTRO
        CIDADE: SÃO PAULO
        CEP: XXXXX-XXX
        ISSUE: 01/01/2015
        VALIDADE: 31/12/2025
        """,
        
        'Certidão de antecedentes criminais': """
        Ministério da Justiça e Segurança Pública
        Secretaria Nacional de Segurança Pública
        
        e-Pol - SINIC
        Sistema Nacional de Informações Criminais
        Certidão de Antecedentes Criminais
        
        A Polícia Federal CERTIFICA, após pesquisa no Sistema Nacional de Informações Criminais - SINIC, 
        que, até a presente data, NÃO CONSTA condenação com trânsito em julgado em nome de HUANG PO CHIANG, 
        país de nacionalidade Taiwan, filiação(a) de HUANG YI TA e TSAI YU MEI, nascido(a) aos 25/01/2005, 
        natural de Kaoshuung-Kaoshuung, CI 609304805, Sexo: SF, CPF: XXX.XXX.XXX-XX.
        
        Esta certidão foi expedida em 25/11/2024 às 21:21 (horário de Brasília/DF GMT-3) 
        com base nos dados informados e somente será válida com a apresentação de documento 
        de identificação para confirmação dos dados.
        """,
        
        'Portaria de concessão da naturalização provisória': """
        SEI / MJ - 1228261 - Certificado de Naturalização
        
        MINISTÉRIO DA JUSTIÇA
        SECRETARIA NACIONAL DE JUSTIÇA
        DEPARTAMENTO DE ESTRANGEIROS
        
        CERTIFICADO DE NATURALIZAÇÃO
        PROVISÓRIO
        
        O SECRETÁRIO NACIONAL DE JUSTIÇA, DO MINISTÉRIO DA JUSTIÇA,
        em conformidade com o artigo 119 da Lei n° 6.815, de 19 de agosto de 1980, 
        com redação dada pela Lei n° 6.964, de 09 de dezembro de 1981, 
        combinado com o artigo 128 do Decreto n° 86.715, de 10 de dezembro de 1981.
        
        CERTIFICA que, pela Portaria n° 96, de 1 de junho de 2015, publicada no Diário Oficial 
        da União de 20 de julho de 2015, foi autorizada a emissão de Certificado Provisório 
        de Naturalização, nos termos do artigo 12, inciso II, alínea "a", da Constituição Federal 
        e dos artigos 111 e 116 da Lei n° 6.815/80, com redação dada pela Lei n° 6.964/81, 
        à HUANG PO CHIANG, natural da China (Taiwan), nascido em 25 de janeiro de 2005, 
        filho de Huang Yi Ta e de Tsai Yu Mei, residente no Estado de São Paulo, 
        a fim de que possa gozar dos direitos outorgados pela Constituição e leis do Brasil, 
        até 25 de janeiro de 2025.
        
        Processo n°: 08505.056813/2014-99
        """
    }
    
    # Analisar elegibilidade
    analisador = AnalisadorElegibilidadeSimples()
    resultado = analisador.analisar_elegibilidade(documentos_teste)
    
    print(f"[TARGET] ELEGIBILIDADE: {resultado['elegibilidade']}")
    print(f"[DADOS] CONFIANÇA: {resultado['confianca']:.1%}")
    print(f"🔢 SCORE TOTAL: {resultado['score_total']}")
    print(f"[OK] CONDIÇÕES ATENDIDAS: {resultado['condicoes_obrigatorias']['atendidas']}/{resultado['condicoes_obrigatorias']['total']}")
    print(f"[DICA] RECOMENDAÇÃO: {resultado['recomendacao']}")
    
    print("\n[INFO] DETALHES DAS CONDIÇÕES:")
    for nome_condicao, resultado_condicao in resultado['condicoes_obrigatorias']['detalhes'].items():
        status = "[OK]" if resultado_condicao['atendida'] else "[ERRO]"
        print(f"  {status} {resultado_condicao['descricao']}")
        print(f"     Score: {resultado_condicao['score']}, Peso: {resultado_condicao['peso']}")
    
    print(f"\n🌟 CONDIÇÕES FAVORÁVEIS: {resultado['condicoes_favoraveis']['encontradas']}")
    print(f"[AVISO]  CONDIÇÕES DESQUALIFICADORAS: {resultado['condicoes_desqualificadoras']['encontradas']}") 