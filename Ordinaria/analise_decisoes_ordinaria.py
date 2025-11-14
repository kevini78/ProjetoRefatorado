"""
Módulo para análise de decisões de naturalização ordinária
Gera decisões automáticas baseadas nos requisitos do Art. 65 da Lei nº 13.445/2017
"""

from typing import Dict, Any, List
from datetime import datetime

class AnaliseDecisoesOrdinaria:
    """
    Gerador de decisões automáticas para naturalização ordinária
    """
    
    def __init__(self):
        """
        Inicializa o analisador de decisões
        """
        self.fundamentos_legais = {
            'capacidade_civil': "Art. 65, inciso I da Lei nº 13.445/2017",
            'residencia_minima': "Art. 65, inciso II da Lei nº 13.445/2017", 
            'comunicacao_portugues': "Art. 65, inciso III da Lei nº 13.445/2017",
            'antecedentes_criminais': "Art. 65, inciso IV da Lei nº 13.445/2017",
            'documentos_obrigatorios': "Anexo I da Portaria 623/2020"
        }
    
    def gerar_decisao_automatica(self, resultado_elegibilidade: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gera decisão automática baseada no resultado da análise de elegibilidade
        
        Args:
            resultado_elegibilidade: Resultado da análise de elegibilidade
            
        Returns:
            Dict com a decisão gerada
        """
        print("\n" + "="*80)
        print("[DECISAO] GERAÇÃO DE DECISÃO AUTOMÁTICA")
        print("Naturalização Ordinária - Art. 65 da Lei nº 13.445/2017")
        print("="*80)
        
        decisao = {
            'tipo_decisao': '',
            'despacho_completo': '',
            'motivos_indeferimento': [],
            'fundamentos_legais': [],
            'resumo_analise': '',
            'data_decisao': datetime.now().strftime("%d/%m/%Y"),
            'percentual_atendimento': 0
        }
        
        # Determinar tipo de decisão
        elegibilidade_final = resultado_elegibilidade.get('elegibilidade_final', '')
        
        if elegibilidade_final == 'deferimento':
            decisao['tipo_decisao'] = 'DEFERIMENTO'
            decisao = self._gerar_despacho_deferimento(decisao, resultado_elegibilidade)
        else:
            decisao['tipo_decisao'] = 'INDEFERIMENTO'
            decisao = self._gerar_despacho_indeferimento(decisao, resultado_elegibilidade)
        
        print(f"[INFO] Tipo de decisão: {decisao['tipo_decisao']}")
        print(f"[DOC] Despacho gerado com {len(decisao['despacho_completo'])} caracteres")
        
        return decisao
    
    def _gerar_despacho_deferimento(self, decisao: Dict[str, Any], resultado: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gera despacho de deferimento
        """
        print("[OK] Gerando despacho de DEFERIMENTO...")
        
        # Texto do despacho de deferimento
        despacho = self._criar_cabecalho_despacho()
        despacho += "\n\nDECISÃO: DEFERIMENTO\n\n"
        
        # Fundamentação
        despacho += "FUNDAMENTAÇÃO:\n\n"
        despacho += "Após análise dos documentos apresentados e verificação dos requisitos legais, "
        despacho += "constato que o interessado atende a todos os requisitos estabelecidos no "
        despacho += "Art. 65 da Lei nº 13.445/2017 para concessão da naturalização ordinária:\n\n"
        
        # Listar requisitos atendidos
        requisitos = resultado.get('requisitos_atendidos', {})
        
        if requisitos.get('capacidade_civil', {}).get('atendido'):
            idade = requisitos['capacidade_civil'].get('idade', 'N/A')
            despacho += f"I - CAPACIDADE CIVIL: Atendido. O interessado possui {idade} anos, "
            despacho += "sendo maior de 18 anos conforme exigido pelo Art. 65, inciso I.\n\n"
        
        if requisitos.get('residencia_minima', {}).get('atendido'):
            req_residencia = requisitos['residencia_minima']
            prazo = req_residencia.get('prazo_requerido', 4)
            tem_reducao = req_residencia.get('tem_reducao', False)
            despacho += f"II - RESIDÊNCIA MÍNIMA: Atendido. Comprovou {prazo} ano(s) de residência "
            despacho += "indeterminada" if tem_reducao else "indeterminada ou permanente"
            despacho += f" no Brasil conforme Art. 65, inciso II"
            if tem_reducao:
                despacho += " (com redução de prazo)"
            despacho += ".\n\n"
        
        if requisitos.get('comunicacao_portugues', {}).get('atendido'):
            despacho += "III - COMUNICAÇÃO EM LÍNGUA PORTUGUESA: Atendido. Apresentou comprovante "
            despacho += "válido de comunicação em língua portuguesa conforme Art. 65, inciso III.\n\n"
        
        if requisitos.get('antecedentes_criminais', {}).get('atendido'):
            despacho += "IV - ANTECEDENTES CRIMINAIS: Atendido. Apresentou certidões de antecedentes "
            despacho += "criminais do Brasil e de outros países sem condenações pendentes, ou com "
            despacho += "comprovante de reabilitação, conforme Art. 65, inciso IV.\n\n"
        
        # Documentos obrigatórios
        docs = resultado.get('documentos_obrigatorios', {})
        if docs.get('percentual_completude', 0) == 100:
            despacho += "DOCUMENTOS OBRIGATÓRIOS: Todos os documentos exigidos pelo Anexo I da "
            despacho += "Portaria 623/2020 foram devidamente apresentados.\n\n"
        
        # Conclusão
        despacho += "CONCLUSÃO:\n\n"
        despacho += "Diante do exposto, tendo o interessado atendido a todos os requisitos "
        despacho += "estabelecidos no Art. 65 da Lei nº 13.445/2017 e apresentado toda a "
        despacho += "documentação exigida, DEFIRO o pedido de naturalização ordinária.\n\n"
        
        # Rodapé
        despacho += self._criar_rodape_despacho()
        
        decisao['despacho_completo'] = despacho
        decisao['resumo_analise'] = "Todos os requisitos atendidos - Deferimento"
        decisao['percentual_atendimento'] = 100
        decisao['fundamentos_legais'] = [
            self.fundamentos_legais['capacidade_civil'],
            self.fundamentos_legais['residencia_minima'],
            self.fundamentos_legais['comunicacao_portugues'],
            self.fundamentos_legais['antecedentes_criminais'],
            self.fundamentos_legais['documentos_obrigatorios']
        ]
        
        return decisao
    
    def _gerar_despacho_indeferimento(self, decisao: Dict[str, Any], resultado: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gera despacho de indeferimento
        """
        print("[ERRO] Gerando despacho de INDEFERIMENTO...")
        
        # Texto do despacho de indeferimento
        despacho = self._criar_cabecalho_despacho()
        despacho += "\n\nDECISÃO: INDEFERIMENTO\n\n"
        
        # Fundamentação
        despacho += "FUNDAMENTAÇÃO:\n\n"
        despacho += "Após análise dos documentos apresentados e verificação dos requisitos legais, "
        despacho += "constato que o interessado NÃO atende aos requisitos estabelecidos no "
        despacho += "Art. 65 da Lei nº 13.445/2017 para concessão da naturalização ordinária "
        despacho += "pelos seguintes motivos:\n\n"
        
        # Analisar e listar motivos específicos
        motivos = []
        fundamentos = []
        requisitos = resultado.get('requisitos_atendidos', {})
        
        # Verificar cada requisito
        if not requisitos.get('capacidade_civil', {}).get('atendido', True):
            req = requisitos.get('capacidade_civil', {})
            idade = req.get('idade', 'N/A')
            motivos.append(f"I - CAPACIDADE CIVIL: Não atendido. O interessado possui {idade} anos, "
                          f"sendo menor de 18 anos. {req.get('motivo', '')}")
            fundamentos.append(self.fundamentos_legais['capacidade_civil'])
        
        if not requisitos.get('residencia_minima', {}).get('atendido', True):
            req = requisitos.get('residencia_minima', {})
            prazo = req.get('prazo_requerido', 4)
            motivos.append(f"II - RESIDÊNCIA MÍNIMA: Não atendido. {req.get('motivo', '')} "
                          f"Exigido: {prazo} ano(s) de residência.")
            fundamentos.append(self.fundamentos_legais['residencia_minima'])
        
        if not requisitos.get('comunicacao_portugues', {}).get('atendido', True):
            req = requisitos.get('comunicacao_portugues', {})
            motivos.append(f"III - COMUNICAÇÃO EM LÍNGUA PORTUGUESA: Não atendido. {req.get('motivo', '')}")
            fundamentos.append(self.fundamentos_legais['comunicacao_portugues'])
        
        if not requisitos.get('antecedentes_criminais', {}).get('atendido', True):
            req = requisitos.get('antecedentes_criminais', {})
            motivos.append(f"IV - ANTECEDENTES CRIMINAIS: Não atendido. {req.get('motivo', '')}")
            fundamentos.append(self.fundamentos_legais['antecedentes_criminais'])
        
        # Verificar documentos obrigatórios
        docs = resultado.get('documentos_obrigatorios', {})
        docs_faltantes = docs.get('documentos_faltantes', [])
        docs_invalidos = docs.get('documentos_invalidos', [])
        
        if docs_faltantes or docs_invalidos:
            motivo_docs = "DOCUMENTOS OBRIGATÓRIOS: "
            if docs_faltantes:
                itens_faltantes = []
                for doc in docs_faltantes:
                    item_num = self._obter_numero_item_anexo(doc)
                    itens_faltantes.append(f"item {item_num}")
                motivo_docs += f"Não anexou {', '.join(itens_faltantes)}. "
            
            if docs_invalidos:
                motivo_docs += f"Documentos inválidos: {', '.join(docs_invalidos)}. "
            
            motivos.append(motivo_docs)
            fundamentos.append(self.fundamentos_legais['documentos_obrigatorios'])
        
        # Adicionar motivos ao despacho
        for i, motivo in enumerate(motivos, 1):
            despacho += f"{motivo}\n\n"
        
        # Conclusão
        despacho += "CONCLUSÃO:\n\n"
        despacho += "Diante do exposto, tendo o interessado NÃO atendido aos requisitos "
        despacho += "estabelecidos no Art. 65 da Lei nº 13.445/2017, INDEFIRO o pedido "
        despacho += "de naturalização ordinária.\n\n"
        
        # Rodapé
        despacho += self._criar_rodape_despacho()
        
        decisao['despacho_completo'] = despacho
        decisao['motivos_indeferimento'] = motivos
        decisao['fundamentos_legais'] = fundamentos
        decisao['resumo_analise'] = f"{len(motivos)} requisito(s) não atendido(s) - Indeferimento"
        
        # Calcular percentual de atendimento
        total_requisitos = 4  # 4 requisitos principais
        requisitos_atendidos = sum([
            1 if requisitos.get('capacidade_civil', {}).get('atendido') else 0,
            1 if requisitos.get('residencia_minima', {}).get('atendido') else 0,
            1 if requisitos.get('comunicacao_portugues', {}).get('atendido') else 0,
            1 if requisitos.get('antecedentes_criminais', {}).get('atendido') else 0
        ])
        
        decisao['percentual_atendimento'] = int((requisitos_atendidos / total_requisitos) * 100)
        
        return decisao
    
    def _criar_cabecalho_despacho(self) -> str:
        """
        Cria cabeçalho padrão do despacho
        """
        data_atual = datetime.now().strftime("%d/%m/%Y")
        
        cabecalho = f"""MINISTÉRIO DA JUSTIÇA E SEGURANÇA PÚBLICA
SECRETARIA NACIONAL DE JUSTIÇA
DEPARTAMENTO DE MIGRAÇÕES

DESPACHO DECISÓRIO
Data: {data_atual}

ASSUNTO: Pedido de Naturalização Ordinária
FUNDAMENTO LEGAL: Art. 65 da Lei nº 13.445/2017"""
        
        return cabecalho
    
    def _criar_rodape_despacho(self) -> str:
        """
        Cria rodapé padrão do despacho
        """
        data_atual = datetime.now().strftime("%d/%m/%Y")
        
        rodape = f"""
Brasília, {data_atual}.

[NOME DO SERVIDOR]
[CARGO]
Departamento de Migrações
Secretaria Nacional de Justiça
Ministério da Justiça e Segurança Pública"""
        
        return rodape
    
    def _obter_numero_item_anexo(self, nome_documento: str) -> str:
        """
        Obtém o número do item no Anexo I da Portaria 623/2020
        """
        mapeamento_itens = {
            'Carteira de Registro Nacional Migratório': '3',
            'Comprovante da situação cadastral do CPF': '4',
            'Comprovante de tempo de residência': '8',
            'Comprovante de comunicação em português': '13',
            'Certidão de antecedentes criminais (Brasil)': '9',
            'Atestado antecedentes criminais (país de origem)': '10',
            'Documento de viagem internacional': '2',
            'Comprovante de reabilitação': '11',
            'Comprovante de redução de prazo': '12'
        }
        
        return mapeamento_itens.get(nome_documento, '?')
    
    def gerar_resumo_executivo(self, resultado_elegibilidade: Dict[str, Any], decisao: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gera resumo executivo da análise e decisão
        
        Args:
            resultado_elegibilidade: Resultado da análise de elegibilidade
            decisao: Decisão gerada
            
        Returns:
            Dict com resumo executivo
        """
        print("\n[DADOS] Gerando resumo executivo...")
        
        requisitos = resultado_elegibilidade.get('requisitos_atendidos', {})
        
        resumo = {
            'data_analise': datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            'tipo_naturalizacao': 'Ordinária',
            'resultado_final': decisao['tipo_decisao'],
            'percentual_atendimento': decisao['percentual_atendimento'],
            'requisitos_verificados': {
                'capacidade_civil': {
                    'status': '[OK] Atendido' if requisitos.get('capacidade_civil', {}).get('atendido') else '[ERRO] Não Atendido',
                    'detalhes': requisitos.get('capacidade_civil', {}).get('motivo', 'N/A')
                },
                'residencia_minima': {
                    'status': '[OK] Atendido' if requisitos.get('residencia_minima', {}).get('atendido') else '[ERRO] Não Atendido',
                    'detalhes': requisitos.get('residencia_minima', {}).get('motivo', 'N/A')
                },
                'comunicacao_portugues': {
                    'status': '[OK] Atendido' if requisitos.get('comunicacao_portugues', {}).get('atendido') else '[ERRO] Não Atendido',
                    'detalhes': requisitos.get('comunicacao_portugues', {}).get('motivo', 'N/A')
                },
                'antecedentes_criminais': {
                    'status': '[OK] Atendido' if requisitos.get('antecedentes_criminais', {}).get('atendido') else '[ERRO] Não Atendido',
                    'detalhes': requisitos.get('antecedentes_criminais', {}).get('motivo', 'N/A')
                }
            },
            'documentos_status': {
                'completude': resultado_elegibilidade.get('documentos_obrigatorios', {}).get('percentual_completude', 0),
                'faltantes': resultado_elegibilidade.get('documentos_obrigatorios', {}).get('documentos_faltantes', []),
                'invalidos': resultado_elegibilidade.get('documentos_obrigatorios', {}).get('documentos_invalidos', [])
            },
            'fundamentos_legais': decisao.get('fundamentos_legais', []),
            'observacoes': self._gerar_observacoes(resultado_elegibilidade, decisao)
        }
        
        print("[OK] Resumo executivo gerado")
        return resumo
    
    def _gerar_observacoes(self, resultado_elegibilidade: Dict[str, Any], decisao: Dict[str, Any]) -> List[str]:
        """
        Gera observações relevantes para o caso
        """
        observacoes = []
        
        # Observações sobre idade
        requisitos = resultado_elegibilidade.get('requisitos_atendidos', {})
        cap_civil = requisitos.get('capacidade_civil', {})
        if cap_civil.get('idade'):
            idade = cap_civil['idade']
            if idade < 18:
                observacoes.append(f"Interessado possui {idade} anos (menor de idade)")
            elif idade >= 65:
                observacoes.append(f"Interessado possui {idade} anos (pessoa idosa)")
        
        # Observações sobre residência
        res_min = requisitos.get('residencia_minima', {})
        if res_min.get('tem_reducao'):
            observacoes.append("Caso com redução de prazo de residência")
        
        # Observações sobre antecedentes
        antec = requisitos.get('antecedentes_criminais', {})
        if 'reabilitação' in antec.get('motivo', '').lower():
            observacoes.append("Caso com antecedentes criminais reabilitados")
        
        # Observações sobre documentos
        docs = resultado_elegibilidade.get('documentos_obrigatorios', {})
        completude = docs.get('percentual_completude', 100)
        if completude < 100:
            observacoes.append(f"Documentação incompleta ({completude}%)")
        
        # Observação sobre tipo de decisão
        if decisao['tipo_decisao'] == 'DEFERIMENTO':
            observacoes.append("Processo elegível para deferimento automático")
        else:
            observacoes.append("Processo com impedimentos legais identificados")
        
        return observacoes
    
    def salvar_decisao_arquivo(self, decisao: Dict[str, Any], numero_processo: str, pasta_destino: str = "decisoes") -> str:
        """
        Salva a decisão em arquivo de texto
        
        Args:
            decisao: Decisão gerada
            numero_processo: Número do processo
            pasta_destino: Pasta onde salvar o arquivo
            
        Returns:
            Caminho do arquivo salvo
        """
        import os
        from datetime import datetime
        
        # Criar pasta se não existir
        os.makedirs(pasta_destino, exist_ok=True)
        
        # Nome do arquivo
        data_atual = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = f"decisao_ordinaria_{numero_processo}_{data_atual}.txt"
        caminho_arquivo = os.path.join(pasta_destino, nome_arquivo)
        
        # Salvar arquivo
        with open(caminho_arquivo, 'w', encoding='utf-8') as f:
            f.write(decisao['despacho_completo'])
        
        print(f"[DOC] Decisão salva em: {caminho_arquivo}")
        return caminho_arquivo


# Função de conveniência para uso direto
def gerar_decisao_ordinaria(resultado_elegibilidade: Dict[str, Any]) -> Dict[str, Any]:
    """
    Função de conveniência para geração de decisão ordinária
    
    Args:
        resultado_elegibilidade: Resultado da análise de elegibilidade
        
    Returns:
        Dict com a decisão gerada
    """
    analisador = AnaliseDecisoesOrdinaria()
    return analisador.gerar_decisao_automatica(resultado_elegibilidade)
