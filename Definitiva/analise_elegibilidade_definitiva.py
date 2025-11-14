"""
Módulo para análise de elegibilidade para naturalização definitiva
Analisa documentos OCR para determinar se atendem às condições legais
"""

import re
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AnalisadorElegibilidadeDefinitiva:
    """
    Analisador especializado para determinar elegibilidade para naturalização definitiva
    baseado em condições legais específicas
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
                    r'não\s+consta.*condenação.*trânsito.*julgado'
                ],
                'padroes_negativos': [
                    r'(?<!não\s)consta\s+condenação',  # Não captura se precedido por "não"
                    r'possui\s+antecedentes',
                    r'com\s+antecedentes',
                    r'condenado',
                    r'processo\s+criminal'
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
                    r'provisório'
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
            'antecedentes_criminais': {
                'descricao': 'Presença de antecedentes criminais',
                'peso': -5.0,  # Peso negativo alto
                'padroes': [
                    r'consta\s+condenação',
                    r'possui\s+antecedentes',
                    r'processo\s+criminal',
                    r'condenado',
                    r'pena\s+privativa'
                ]
            },
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
    
    def analisar_elegibilidade(self, documentos: Dict[str, str]) -> Dict:
        """
        Analisa a elegibilidade para naturalização definitiva baseada nos documentos
        
        Args:
            documentos (Dict[str, str]): Dicionário com nome do documento e texto OCR
        
        Returns:
            Dict: Resultado da análise de elegibilidade
        """
        logger.info("Iniciando análise de elegibilidade para naturalização definitiva")
        
        # Análise de cada condição obrigatória
        resultados_condicoes = {}
        score_total = 0.0
        condicoes_atendidas = 0
        condicoes_nao_atendidas = 0
        
        for nome_condicao, config in self.condicoes_obrigatorias.items():
            resultado = self._verificar_condicao(nome_condicao, config, documentos)
            resultados_condicoes[nome_condicao] = resultado
            
            if resultado['atendida']:
                condicoes_atendidas += 1
                score_total += resultado['score'] * config['peso']
            else:
                condicoes_nao_atendidas += 1
                score_total += resultado['score'] * config['peso']
        
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
            'recomendacao': self._gerar_recomendacao(elegibilidade, resultados_condicoes),
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info(f"Análise concluída: {elegibilidade} (Confiança: {confianca:.1%})")
        return resultado_final
    
    def _verificar_condicao(self, nome_condicao: str, config: Dict, documentos: Dict[str, str]) -> Dict:
        """Verifica se uma condição obrigatória foi atendida"""
        texto_completo = " ".join(documentos.values()).lower()
        
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
            # Se encontrou "não consta condenação", é positivo, mesmo que encontre "consta condenação" em outro contexto
            if any('não consta' in padrao for padrao in padroes_positivos_encontrados):
                # Remover qualquer padrão negativo que possa ser falso positivo
                padroes_negativos_encontrados = [p for p in padroes_negativos_encontrados 
                                               if not ('consta' in p and 'não' not in p)]
        
        # Lógica especial para idade
        elif nome_condicao == 'idade_processo':
            # Se encontrou uma data de nascimento, calcular a idade real
            texto_completo = " ".join(documentos.values()).lower()
            match_data = re.search(r'data\s+de\s+nascimento[:\s]*(\d{2}/\d{2}/\d{4})', texto_completo, re.IGNORECASE)
            if match_data:
                try:
                    from datetime import datetime
                    data_nasc = datetime.strptime(match_data.group(1), '%d/%m/%Y')
                    data_atual = datetime.now()
                    idade = data_atual.year - data_nasc.year
                    if data_atual.month < data_nasc.month or (data_atual.month == data_nasc.month and data_atual.day < data_nasc.day):
                        idade -= 1
                    
                    # Se a idade está fora da faixa 18-20, forçar como não atendida
                    if idade < 18 or idade > 20:
                        padroes_positivos_encontrados = []
                        padroes_negativos_encontrados = ['idade_inadequada']
                        print(f"DEBUG: Idade calculada: {idade} anos - fora da faixa 18-20")
                except Exception as e:
                    print(f"DEBUG: Erro ao calcular idade: {e}")
        
        # Determinar se a condição foi atendida
        atendida = len(padroes_positivos_encontrados) > 0 and len(padroes_negativos_encontrados) == 0
        
        # Calcular score
        score = len(padroes_positivos_encontrados) - len(padroes_negativos_encontrados)
        
        return {
            'atendida': atendida,
            'score': score,
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
        
        # Se todas as condições obrigatórias foram atendidas
        if condicoes_nao_atendidas == 0:
            if score_total >= 15.0:  # Score alto
                return 'elegivel_alta_probabilidade'
            elif score_total >= 10.0:  # Score médio
                return 'elegivel_probabilidade_media'
            else:
                return 'elegivel_probabilidade_baixa'
        
        # Se algumas condições não foram atendidas
        elif condicoes_nao_atendidas <= 1:  # Máximo 1 condição não atendida
            if score_total >= 12.0:
                return 'elegivel_com_ressalvas'
            else:
                return 'elegibilidade_incerta'
        
        # Se muitas condições não foram atendidas
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
            confianca_base += 0.1
        
        if condicoes_desqualificadoras > 0:
            confianca_base -= 0.2
        
        # Limitar entre 0.0 e 1.0
        return max(0.0, min(1.0, confianca_base))
    
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
        
        else:
            return "❓ STATUS INDETERMINADO: Análise inconclusiva"
    
    def analisar_documento_especifico(self, nome_documento: str, texto: str) -> Dict:
        """Analisa um documento específico para extrair informações relevantes"""
        
        resultado = {
            'nome_documento': nome_documento,
            'tipo_documento': self._identificar_tipo_documento(nome_documento, texto),
            'informacoes_extraidas': self._extrair_informacoes_documento(texto),
            'relevancia': self._avaliar_relevancia_documento(nome_documento, texto)
        }
        
        return resultado
    
    def _identificar_tipo_documento(self, nome_documento: str, texto: str) -> str:
        """Identifica o tipo de documento baseado no nome e conteúdo"""
        
        nome_lower = nome_documento.lower()
        texto_lower = texto.lower()
        
        if 'antecedentes' in nome_lower or 'criminal' in nome_lower:
            return 'certidao_antecedentes_criminais'
        
        elif 'naturalização' in nome_lower or 'provisória' in nome_lower:
            return 'certificado_naturalizacao_provisoria'
        
        elif 'identidade' in nome_lower or 'rg' in nome_lower:
            return 'documento_identidade'
        
        elif 'residência' in nome_lower or 'tempo' in nome_lower:
            return 'comprovante_residencia'
        
        elif 'viagem' in nome_lower or 'passaporte' in nome_lower:
            return 'documento_viagem'
        
        else:
            return 'documento_geral'
    
    def _extrair_informacoes_documento(self, texto: str) -> Dict:
        """Extrai informações específicas do documento"""
        
        informacoes = {}
        
        # Extrair data de nascimento
        match_nascimento = re.search(r'data\s+de\s+nascimento[:\s]*(\d{2}/\d{2}/\d{4})', texto, re.IGNORECASE)
        if match_nascimento:
            informacoes['data_nascimento'] = match_nascimento.group(1)
            
            # Calcular idade
            try:
                data_nasc = datetime.strptime(match_nascimento.group(1), '%d/%m/%Y')
                data_atual = datetime.now()
                idade = data_atual.year - data_nasc.year
                if data_atual.month < data_nasc.month or (data_atual.month == data_nasc.month and data_atual.day < data_nasc.day):
                    idade -= 1
                informacoes['idade'] = idade
            except:
                pass
        
        # Extrair nacionalidade
        match_nacionalidade = re.search(r'origem[:\s]*([^,\n]+)', texto, re.IGNORECASE)
        if match_nacionalidade:
            informacoes['nacionalidade_origem'] = match_nacionalidade.group(1).strip()
        
        # Extrair validade
        match_validade = re.search(r'validade[:\s]*(\d{2}/\d{2}/\d{4})', texto, re.IGNORECASE)
        if match_validade:
            informacoes['validade'] = match_validade.group(1)
        
        # Extrair número do processo
        match_processo = re.search(r'processo\s*n[º°o]*[:\s]*([\d\.\-/]+)', texto, re.IGNORECASE)
        if match_processo:
            informacoes['numero_processo'] = match_processo.group(1)
        
        return informacoes
    
    def _avaliar_relevancia_documento(self, nome_documento: str, texto: str) -> str:
        """Avalia a relevância do documento para a análise de elegibilidade"""
        
        nome_lower = nome_documento.lower()
        texto_lower = texto.lower()
        
        # Documentos altamente relevantes
        if any(termo in nome_lower for termo in ['antecedentes', 'naturalização', 'provisória']):
            return 'alta'
        
        # Documentos relevantes
        elif any(termo in nome_lower for termo in ['identidade', 'residência', 'viagem']):
            return 'media'
        
        # Documentos pouco relevantes
        else:
            return 'baixa'


# Funções de conveniência
def analisar_elegibilidade_definitiva(documentos: Dict[str, str]) -> Dict:
    """
    Função de conveniência para análise de elegibilidade
    
    Args:
        documentos (Dict[str, str]): Dicionário com nome do documento e texto
    
    Returns:
        Dict: Resultado da análise de elegibilidade
    """
    analisador = AnalisadorElegibilidadeDefinitiva()
    return analisador.analisar_elegibilidade(documentos)


def analisar_documento_especifico(nome_documento: str, texto: str) -> Dict:
    """
    Função de conveniência para análise de documento específico
    
    Args:
        nome_documento (str): Nome do documento
        texto (str): Texto extraído do documento
    
    Returns:
        Dict: Análise do documento específico
    """
    analisador = AnalisadorElegibilidadeDefinitiva()
    return analisador.analisar_documento_especifico(nome_documento, texto)


if __name__ == "__main__":
    # Teste do módulo
    print("[TESTE] TESTANDO ANALISADOR DE ELEGIBILIDADE")
    print("=" * 50)
    
    # Exemplo de uso com os documentos reais
    documentos_teste = {
        'Documento oficial de identidade': """
        REPÚBLICA FEDERATIVA DO BRASIL
        ESTADO DE SÃO PAULO
        ORGÃO DEMISSOR: POLÍCIA CIVIL
        NÚMERO DO DOCUMENTO: *******
        NOME:  *******
        DATA DE NASCIMENTO:  *******
        SEXO: MASCULINO
        COR: BRANCA
        ESTADO CIVIL: CASADO
        PROFISSÃO: OUTRA
        ORIGEM: CHINA/TAIWAN
        ENDEREÇO: RUA
        NÚMERO: 123
        BAIRRO: CENTRO
        CIDADE: SÃO PAULO
        CEP:  *******
        ISSUE: 01/01/2015
        VALIDADE:  *******
        """,
        
        'Certidão de antecedentes criminais': """
        Ministério da Justiça e Segurança Pública
        Secretaria Nacional de Segurança Pública
        
        e-Pol - SINIC
        Sistema Nacional de Informações Criminais
        Certidão de Antecedentes Criminais
        
        A Polícia Federal CERTIFICA, após pesquisa no Sistema Nacional de Informações Criminais - SINIC, 
        que, até a presente data, NÃO CONSTA condenação com trânsito em julgado em nome de  *******, 
        país de nacionalidade Taiwan, filiação(a)  *******, nascido(a) aos *******, 
        natural de Kaoshuung-Kaoshuung, 
        
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
    analisador = AnalisadorElegibilidadeDefinitiva()
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