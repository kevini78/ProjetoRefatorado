"""
Módulo para análise de decisões de naturalização provisória
Implementa regras específicas para processos provisórios
"""

import re
from datetime import datetime
from typing import Dict, Any, List
from analise_elegibilidade_provisoria import AnaliseElegibilidadeProvisoria

class AnaliseDecisoesProvisoria:
    """
    Analisador de decisões para naturalização provisória
    Implementa regras específicas conforme especificação
    """
    
    def __init__(self, lecom_instance):
        """
        Inicializa o analisador de decisões
        
        Args:
            lecom_instance: Instância da navegação provisória
        """
        self.lecom = lecom_instance
        self.analisador_elegibilidade = AnaliseElegibilidadeProvisoria(lecom_instance)
    
    def analisar_decisao_completa(self, dados_pessoais: Dict[str, Any], data_inicial_processo: str) -> Dict[str, Any]:
        """
        Análise completa de decisão para naturalização provisória
        
        Args:
            dados_pessoais: Dados pessoais extraídos
            data_inicial_processo: Data inicial do processo
            
        Returns:
            Dict com resultado da análise de decisão
        """
        print("[TARGET] INICIANDO ANÁLISE COMPLETA DE DECISÃO PROVISÓRIA")
        print("=" * 70)
        
        # 1. Análise de Elegibilidade
        print("\n1️⃣ ANALISANDO ELEGIBILIDADE...")
        resultado_elegibilidade = self.analisador_elegibilidade.analisar_elegibilidade_completa(
            dados_pessoais, data_inicial_processo
        )
        
        # 2. Análise de Decisão baseada na elegibilidade
        print("\n2️⃣ ANALISANDO DECISÃO...")
        resultado_decisao = self._analisar_decisao_baseada_elegibilidade(resultado_elegibilidade)
        
        # 3. Consolidação dos resultados
        resultado_final = {
            'tipo_analise': 'decisao_naturalizacao_provisoria',
            'data_analise': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'elegibilidade': resultado_elegibilidade,
            'decisao': resultado_decisao,
            'decisao_consolidada': resultado_decisao['decisao_final'],
            'confianca_consolidada': resultado_decisao['confianca_final'],
            'score_total_consolidado': resultado_decisao['score_final'],
            'motivo_consolidado': resultado_decisao['motivo_final']
        }
        
        print("\n" + "=" * 70)
        print(f"[TARGET] DECISÃO FINAL: {resultado_decisao['decisao_final'].replace('_', ' ').title()}")
        print(f"💬 Motivo: {resultado_decisao['motivo_final']}")
        print(f"[DADOS] Confiança: {resultado_decisao['confianca_final']:.1%}")
        print(f"[DESTAQUE] Score: {resultado_decisao['score_final']}")
        print("=" * 70)
        
        return resultado_final
    
    def _analisar_decisao_baseada_elegibilidade(self, resultado_elegibilidade: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analisa decisão baseada na elegibilidade
        """
        print("[BUSCA] Analisando decisão baseada na elegibilidade...")
        
        elegibilidade_final = resultado_elegibilidade.get('elegibilidade_final', 'indeterminada')
        percentual_final = resultado_elegibilidade.get('percentual_final', 0)
        
        # [DEBUG] CORREÇÃO: Alinhar confiança com elegibilidade
        if elegibilidade_final == 'deferimento' or percentual_final == 100:
            print("[TARGET] Elegibilidade 100% - aplicando checklist de documentos para deferimento")
            return self._decisao_deferimento_com_checklist(resultado_elegibilidade)
        elif elegibilidade_final == 'elegivel_com_ressalva' or percentual_final >= 80:
            print("[AVISO] Elegibilidade com ressalva - aplicando penalizações moderadas")
            return self._decisao_elegivel_com_ressalva(resultado_elegibilidade)
        elif elegibilidade_final == 'elegibilidade_comprometida' or percentual_final >= 60:
            print("🚨 Elegibilidade comprometida - aplicando penalizações severas")
            return self._decisao_elegibilidade_comprometida(resultado_elegibilidade)
        elif elegibilidade_final == 'requer_analise_manual':
            print("🚨 Requer análise manual - não aplicando decisão automática")
            return self._decisao_requer_analise_manual(resultado_elegibilidade)
        else:
            print("[ERRO] Não elegível - aplicando indeferimento")
            return self._decisao_nao_elegivel(resultado_elegibilidade)
    
    def _decisao_elegivel_com_ressalva(self, resultado_elegibilidade: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decisão para elegível com ressalva (80-99%)
        """
        print("[AVISO] Aplicando decisão para elegível com ressalva...")
        
        confianca_base = 0.8  # 80% base
        score_base = 80
        
        problemas_checklist = self._verificar_checklist_documentos(resultado_elegibilidade)
        
        if not problemas_checklist:
            return {
                'decisao_final': 'elegivel_com_ressalva',
                'confianca_final': round(confianca_base, 2),
                'score_final': score_base,
                'motivo_final': 'Elegível com ressalva - documentos em ordem',
                'tipo_decisao': 'elegivel_com_ressalva',
                'detalhes': {
                    'criterio': 'Elegibilidade total + checklist completo',
                    'motivo_especifico': 'Todos os critérios e documentos atendidos',
                    'recurso_possivel': True,
                    'condicoes_atendidas': 'Todas'
                }
            }
        
        # Aplicar penalizações moderadas
        penalidade_por_problema = 0.05  # -5% por problema
        penalidade_total = len(problemas_checklist) * penalidade_por_problema
        
        confianca_final = max(0.4, confianca_base - penalidade_total)
        score_final = max(40, score_base - (len(problemas_checklist) * 5))
        
        return {
            'decisao_final': 'elegivel_com_ressalva',
            'confianca_final': round(confianca_final, 2),
            'score_final': score_final,
            'motivo_final': f'Elegível com ressalva - {len(problemas_checklist)} problemas identificados',
            'tipo_decisao': 'elegivel_com_ressalva',
            'detalhes': {
                'criterio': 'Elegibilidade total com problemas no checklist',
                'motivo_especifico': f'{len(problemas_checklist)} problema(s) identificado(s)',
                'problemas_checklist': problemas_checklist,
                'recurso_possivel': True,
                'acao_recomendada': 'Corrigir problemas no checklist'
            }
        }
    
    def _decisao_elegibilidade_comprometida(self, resultado_elegibilidade: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decisão para elegibilidade comprometida (60-79%)
        """
        print("🚨 Aplicando decisão para elegibilidade comprometida...")
        
        confianca_base = 0.6  # 60% base
        score_base = 60
        
        problemas_checklist = self._verificar_checklist_documentos(resultado_elegibilidade)
        
        if not problemas_checklist:
            return {
                'decisao_final': 'elegibilidade_comprometida',
                'confianca_final': round(confianca_base, 2),
                'score_final': score_base,
                'motivo_final': 'Elegibilidade comprometida - documentos em ordem',
                'tipo_decisao': 'elegibilidade_comprometida',
                'detalhes': {
                    'criterio': 'Elegibilidade total + checklist completo',
                    'motivo_especifico': 'Todos os critérios e documentos atendidos',
                    'recurso_possivel': True,
                    'condicoes_atendidas': 'Todas'
                }
            }
        
        # Aplicar penalizações severas
        penalidade_por_problema = 0.08  # -8% por problema
        penalidade_total = len(problemas_checklist) * penalidade_por_problema
        
        confianca_final = max(0.3, confianca_base - penalidade_total)
        score_final = max(30, score_base - (len(problemas_checklist) * 8))
        
        return {
            'decisao_final': 'elegibilidade_comprometida',
            'confianca_final': round(confianca_final, 2),
            'score_final': score_final,
            'motivo_final': f'Elegibilidade comprometida - {len(problemas_checklist)} problemas identificados',
            'tipo_decisao': 'elegibilidade_comprometida',
            'detalhes': {
                'criterio': 'Elegibilidade total com problemas no checklist',
                'motivo_especifico': f'{len(problemas_checklist)} problema(s) identificado(s)',
                'problemas_checklist': problemas_checklist,
                'recurso_possivel': True,
                'acao_recomendada': 'Corrigir problemas no checklist'
            }
        }
    
    def _decisao_requer_analise_manual(self, resultado_elegibilidade: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decisão para requer análise manual
        """
        print("🚨 Aplicando decisão para requer análise manual...")
        
        return {
            'decisao_final': 'requer_analise_manual',
            'confianca_final': 0.3,  # Baixa confiança para análise manual
            'score_final': 30,
            'motivo_final': resultado_elegibilidade.get('motivo_final', 'Requer análise manual'),
            'tipo_decisao': 'requer_analise_manual',
            'detalhes': {
                'criterio': 'Decisão não identificada automaticamente',
                'motivo_especifico': resultado_elegibilidade.get('motivo_final', 'Requer análise manual'),
                'recurso_possivel': True,
                'acao_recomendada': 'Análise manual por servidor habilitado',
                'prioridade': 'Alta'
            }
        }
    
    def _decisao_nao_elegivel(self, resultado_elegibilidade: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decisão para não elegível
        """
        print("[ERRO] Aplicando decisão para não elegível...")
        
        return {
            'decisao_final': 'nao_elegivel',
            'confianca_final': 0.2,  # Muito baixa confiança para não elegível
            'score_final': 20,
            'motivo_final': resultado_elegibilidade.get('motivo_final', 'Não elegível'),
            'tipo_decisao': 'nao_elegivel',
            'detalhes': {
                'criterio': 'Não elegível',
                'motivo_especifico': resultado_elegibilidade.get('motivo_final', 'Não elegível'),
                'recurso_possivel': False,
                'acao_recomendada': 'Não aplicar decisão automática'
            }
        }
    
    def _decisao_indeferimento_automatico(self, resultado_elegibilidade: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decisão de indeferimento automático
        """
        motivo = resultado_elegibilidade.get('motivo_final', 'Indeferimento automático')
        
        return {
            'decisao_final': 'indeferimento',
            'confianca_final': 1.0,  # 100% de confiança
            'score_final': 0,  # Score mínimo
            'motivo_final': motivo,
            'tipo_decisao': 'indeferimento_automatico',
            'detalhes': {
                'criterio': 'Regra automática',
                'motivo_especifico': motivo,
                'recurso_possivel': False
            }
        }
    
    def _decisao_analise_manual(self, resultado_elegibilidade: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decisão de análise manual (quando não há decisão clara)
        """
        motivo = resultado_elegibilidade.get('motivo_final', 'Requer análise manual')
        
        return {
            'decisao_final': 'analise_manual',
            'confianca_final': 0.0,  # 0% de confiança - requer intervenção humana
            'score_final': 0,  # Score mínimo
            'motivo_final': motivo,
            'tipo_decisao': 'analise_manual',
            'detalhes': {
                'criterio': 'Decisão não identificada automaticamente',
                'motivo_especifico': motivo,
                'recurso_possivel': True,
                'acao_recomendada': 'Análise manual por servidor habilitado',
                'prioridade': 'Alta'
            }
        }
    
    def _decisao_deferimento(self, resultado_elegibilidade: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decisão de deferimento
        """
        return {
            'decisao_final': 'deferimento',
            'confianca_final': 1.0,  # 100% de confiança
            'score_final': 100,  # Score máximo
            'motivo_final': '100% elegível - deferimento recomendado',
            'tipo_decisao': 'deferimento',
            'detalhes': {
                'criterio': 'Elegibilidade total',
                'motivo_especifico': 'Todos os critérios atendidos',
                'recurso_possivel': False,
                'condicoes_atendidas': 'Todas'
            }
        }
    
    def _decisao_indeterminada(self, resultado_elegibilidade: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decisão indeterminada (quando não há dados suficientes)
        """
        return {
            'decisao_final': 'indeterminada',
            'confianca_final': 0.3,  # Baixa confiança
            'score_final': 30,  # Score baixo
            'motivo_final': 'Decisão indeterminada - dados insuficientes',
            'tipo_decisao': 'indeterminada',
            'detalhes': {
                'criterio': 'Dados insuficientes',
                'motivo_especifico': 'Não foi possível determinar elegibilidade',
                'recurso_possivel': True,
                'acao_recomendada': 'Coletar mais informações'
            }
        }
    
    def _decisao_deferimento_com_checklist(self, resultado_elegibilidade: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decisão de deferimento com verificação de checklist de documentos
        """
        print("[BUSCA] Aplicando checklist de documentos para deferimento...")
        
        confianca_base = 1.0  # 100% base
        score_base = 100
        
        problemas_checklist = self._verificar_checklist_documentos(resultado_elegibilidade)
        
        if not problemas_checklist:
            return {
                'decisao_final': 'deferimento',
                'confianca_final': 1.0,
                'score_final': 100,
                'motivo_final': '100% elegível - todos os documentos processados',
                'tipo_decisao': 'deferimento',
                'detalhes': {
                    'criterio': 'Elegibilidade total + checklist completo',
                    'motivo_especifico': 'Todos os critérios e documentos atendidos',
                    'recurso_possivel': False,
                    'condicoes_atendidas': 'Todas'
                }
            }
        
        # Aplicar penalizações baseadas no checklist
        penalidade_por_problema = 0.10  # -10% por problema
        penalidade_total = len(problemas_checklist) * penalidade_por_problema
        
        confianca_final = max(0.3, confianca_base - penalidade_total)
        score_final = max(30, score_base - (len(problemas_checklist) * 10))
        
        return {
            'decisao_final': 'deferimento_com_ressalva',
            'confianca_final': round(confianca_final, 2),
            'score_final': score_final,
            'motivo_final': f'Deferimento com ressalva - {len(problemas_checklist)} problema(s) no checklist',
            'tipo_decisao': 'deferimento_com_ressalva',
            'detalhes': {
                'criterio': 'Elegibilidade total com problemas no checklist',
                'motivo_especifico': f'{len(problemas_checklist)} problema(s) identificado(s)',
                'problemas_checklist': problemas_checklist,
                'recurso_possivel': True,
                'acao_recomendada': 'Corrigir problemas no checklist'
            }
        }
    
    def _verificar_checklist_documentos(self, resultado_elegibilidade: Dict[str, Any]) -> List[str]:
        """
        Verifica o checklist de documentos e identifica problemas
        
        Args:
            resultado_elegibilidade: Resultado da análise de elegibilidade
            
        Returns:
            Lista de problemas encontrados
        """
        problemas = []
        
        # Verificar se há resultado de documentos
        resultado_documentos = resultado_elegibilidade.get('resultado_documentos', {})
        if not resultado_documentos:
            problemas.append("Resultado de documentos não disponível")
            return problemas
        
        # Verificar documentos faltantes
        documentos_faltantes = resultado_documentos.get('documentos_faltantes', [])
        if documentos_faltantes:
            for doc in documentos_faltantes:
                problemas.append(f"Documento faltante: {doc}")
        
        # Verificar documentos com falha de download
        documentos_falharam_download = resultado_documentos.get('documentos_falharam_download', [])
        if documentos_falharam_download:
            for doc in documentos_falharam_download:
                problemas.append(f"Falha no download: {doc}")
        
        # Verificar percentual de elegibilidade dos documentos
        percentual_documentos = resultado_documentos.get('percentual_elegibilidade', 100)
        if percentual_documentos < 100:
            problemas.append(f"Percentual de documentos: {percentual_documentos}% (deveria ser 100%)")
        
        # Verificar status dos documentos
        status_documentos = resultado_documentos.get('status_documentos', '')
        if status_documentos != 'completo':
            problemas.append(f"Status dos documentos: {status_documentos} (deveria ser 'completo')")
        
        return problemas
    
    def _calcular_confianca_ressalva(self, resultado_elegibilidade: Dict[str, Any]) -> float:
        """
        Calcula confiança para casos com ressalva
        """
        confianca_base = 0.6  # Confiança base para ressalva
        
        # Ajustar baseado nos problemas encontrados
        problemas = self._identificar_problemas_ressalva(resultado_elegibilidade)
        
        if not problemas:
            return confianca_base
        
        # Reduzir confiança baseado no número e tipo de problemas
        reducao_por_problema = 0.1
        confianca_final = confianca_base - (len(problemas) * reducao_por_problema)
        
        return max(0.3, confianca_final)  # Mínimo de 30%
    
    def _calcular_score_ressalva(self, resultado_elegibilidade: Dict[str, Any]) -> int:
        """
        Calcula score para casos com ressalva
        """
        score_base = 60  # Score base para ressalva
        
        # Ajustar baseado nos problemas encontrados
        problemas = self._identificar_problemas_ressalva(resultado_elegibilidade)
        
        if not problemas:
            return score_base
        
        # Reduzir score baseado no número e tipo de problemas
        reducao_por_problema = 15
        score_final = score_base - (len(problemas) * reducao_por_problema)
        
        return max(20, score_final)  # Mínimo de 20
    
    def _identificar_problemas_ressalva(self, resultado_elegibilidade: Dict[str, Any]) -> List[str]:
        """
        Identifica problemas específicos que causaram ressalva
        """
        problemas = []
        
        # [DEBUG] CORREÇÃO: Verificar se resultado_elegibilidade é um dicionário válido
        if not isinstance(resultado_elegibilidade, dict):
            print(f"[AVISO] ERRO: resultado_elegibilidade não é um dicionário válido: {type(resultado_elegibilidade)}")
            return ["Erro na análise de elegibilidade"]
        
        # Verificar problemas de idade
        analise_idade = resultado_elegibilidade.get('analise_idade', {})
        if isinstance(analise_idade, dict) and analise_idade.get('erro'):
            problemas.append("Erro no cálculo de idade")
        
        # Verificar problemas no parecer PF
        parecer_pf = resultado_elegibilidade.get('parecer_pf', {})
        if isinstance(parecer_pf, dict):
            if parecer_pf.get('indicios_falsidade'):
                problemas.append("Indícios de falsidade documental")
            if parecer_pf.get('erro'):
                problemas.append("Erro na análise do parecer PF")
        
        # Verificar problemas nos documentos
        documentos = resultado_elegibilidade.get('documentos', {})
        if isinstance(documentos, dict):
            for nome_doc, doc in documentos.items():
                if isinstance(doc, dict) and doc.get('status') in ['Falta', 'Inválido', 'Erro']:
                    problemas.append(f"Problema com {nome_doc.replace('_', ' ').title()}")
        
        return problemas
    
    def gerar_relatorio_decisao(self, resultado_analise: Dict[str, Any]) -> str:
        """
        Gera relatório textual da decisão
        
        Args:
            resultado_analise: Resultado completo da análise
            
        Returns:
            String com relatório formatado
        """
        decisao = resultado_analise.get('decisao', {})
        elegibilidade = resultado_analise.get('elegibilidade', {})
        
        relatorio = f"""
=== RELATÓRIO DE DECISÃO - NATURALIZAÇÃO PROVISÓRIA ===
Data da Análise: {resultado_analise.get('data_analise', 'N/A')}

[TARGET] DECISÃO FINAL: {decisao.get('decisao_final', 'N/A').replace('_', ' ').title()}
💬 Motivo: {decisao.get('motivo_final', 'N/A')}
[DADOS] Confiança: {decisao.get('confianca_final', 0):.1%}
[DESTAQUE] Score: {decisao.get('score_final', 0)}

[INFO] DETALHES DA ELEGIBILIDADE:
• Status: {elegibilidade.get('elegibilidade_final', 'N/A').replace('_', ' ').title()}
• Motivo: {elegibilidade.get('motivo_final', 'N/A')}

[BUSCA] ANÁLISE DETALHADA:
"""
        
        # Adicionar análise de idade
        analise_idade = elegibilidade.get('analise_idade', {})
        if analise_idade:
            relatorio += f"• Idade: {analise_idade.get('idade_calculada', 'N/A')} anos\n"
            relatorio += f"• Elegível por idade: {'Sim' if analise_idade.get('elegivel_por_idade') else 'Não'}\n"
        
        # Adicionar análise do parecer PF
        parecer_pf = elegibilidade.get('parecer_pf', {})
        if parecer_pf:
            relatorio += f"• Parecer PF: {'Indícios de falsidade' if parecer_pf.get('indicios_falsidade') else 'Sem indícios'}\n"
            relatorio += f"• Residência antes dos 10 anos: {'Sim' if parecer_pf.get('residencia_antes_10_anos') else 'Não'}\n"
        
        # Adicionar status dos documentos
        documentos = elegibilidade.get('documentos', {})
        if documentos:
            relatorio += "\n[DOC] STATUS DOS DOCUMENTOS:\n"
            for nome_doc, doc in documentos.items():
                nome_formatado = nome_doc.replace('_', ' ').title()
                status = doc.get('status', 'N/A')
                relatorio += f"• {nome_formatado}: {status}\n"
        
        # Adicionar detalhes da decisão
        detalhes = decisao.get('detalhes', {})
        if detalhes:
            relatorio += f"\n[BUSCA] DETALHES DA DECISÃO:\n"
            relatorio += f"• Critério: {detalhes.get('criterio', 'N/A')}\n"
            relatorio += f"• Recurso possível: {'Sim' if detalhes.get('recurso_possivel') else 'Não'}\n"
        
        relatorio += "\n" + "=" * 70
        
        return relatorio

# Função de conveniência para uso direto
def analisar_decisao_provisoria(lecom_instance, dados_pessoais: Dict[str, Any], data_inicial_processo: str, resultado_elegibilidade_existente: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Analisa decisão de naturalização provisória
    
    Args:
        lecom_instance: Instância do LecomAutomation
        dados_pessoais: Dados pessoais do interessado
        data_inicial_processo: Data inicial do processo
        resultado_elegibilidade_existente: Resultado de elegibilidade já obtido (opcional)
        
    Returns:
        Dict com resultado da análise de decisão
    """
    analisador = AnaliseDecisoesProvisoria(lecom_instance)
    return analisador.analisar_decisao_completa(dados_pessoais, data_inicial_processo) 