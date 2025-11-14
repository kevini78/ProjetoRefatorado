"""
Módulo para exportação de resultados de análise provisória
Gera planilha Excel com estrutura específica para processos provisórios
"""

import pandas as pd
from datetime import datetime
from typing import Dict, Any, List
import os

class ExportadorProvisoria:
    """
    Exportador específico para resultados de análise provisória
    Gera planilha Excel conforme especificação
    """
    
    def __init__(self):
        """Inicializa o exportador"""
        self.colunas_planilha = [
            'Codigo',
            'Data_Processamento',
            'Decisao_Final',
            'Percentual_Elegibilidade',
            'Observacoes',
            'Parecer_PF',
            'Documentos_Processados'
        ]
    
    def mascarar_dados_sensiveis(self, dados: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mascara dados sensíveis conforme LGPD
        
        Args:
            dados: Dados originais
            
        Returns:
            Dados mascarados
        """
        dados_mascarados = {}
        
        # Mascarar nome completo
        nome_completo = dados.get('nome_completo', '')
        if nome_completo:
            partes = nome_completo.split()
            if len(partes) >= 2:
                # Formato: "FER**** BAPT****"
                primeiro_nome = partes[0][:3] if len(partes[0]) >= 3 else partes[0]
                ultimo_nome = partes[-1][:4] if len(partes[-1]) >= 4 else partes[-1]
                nome_mascarado = f"{primeiro_nome}**** {ultimo_nome}****"
            else:
                primeiro_nome = nome_completo[:3] if len(nome_completo) >= 3 else nome_completo
                nome_mascarado = f"{primeiro_nome}****"
            dados_mascarados['nome_mascarado'] = nome_mascarado
        else:
            dados_mascarados['nome_mascarado'] = 'N/A'
        
        # Mascarar data de nascimento
        data_nasc = dados.get('data_nascimento', '')
        if data_nasc:
            # Formato: "**/06/2013"
            try:
                dia, mes, ano = data_nasc.split('/')
                data_mascarada = f"**/{mes}/{ano}"
            except:
                data_mascarada = "**/**/****"
            dados_mascarados['data_nascimento_mascarada'] = data_mascarada
        else:
            dados_mascarados['data_nascimento_mascarada'] = 'N/A'
        
        return dados_mascarados
    
    def extrair_status_documentos(self, documentos: Dict[str, Any]) -> Dict[str, str]:
        """
        Extrai status dos documentos obrigatórios
        
        Args:
            documentos: Dicionário com documentos
            
        Returns:
            Dict com status de cada documento
        """
        status = {}
        
        # Status do representante legal
        rep_legal = documentos.get('representante_legal', {})
        status['representante_legal'] = rep_legal.get('status', 'N/A')
        
        # Status do CRNM do naturalizando
        crnm_nat = documentos.get('crnm_naturalizando', {})
        status['crnm_naturalizando'] = crnm_nat.get('status', 'N/A')
        
        # Status do comprovante de residência
        comp_res = documentos.get('comprovante_residencia', {})
        status['comprovante_residencia'] = comp_res.get('status', 'N/A')
        
        # Status do documento de viagem
        doc_viagem = documentos.get('documento_viagem', {})
        status['documento_viagem'] = 'Sim' if doc_viagem.get('anexado') else 'Não'
        
        return status
    
    def determinar_resultado_final(self, resultado_analise: Dict[str, Any]) -> Dict[str, Any]:
        """
        Determina o resultado final baseado na análise
        
        Args:
            resultado_analise: Resultado da análise
            
        Returns:
            Dict com resultado final e motivo
        """
        decisao = resultado_analise.get('decisao', 'indeterminada')
        motivo = resultado_analise.get('motivo', '')
        
        if decisao == 'indeferimento':
            return {
                'resultado_final': 'Indeferimento',
                'motivo_resultado': motivo
            }
        elif decisao == 'deferimento':
            return {
                'resultado_final': 'Deferimento',
                'motivo_resultado': motivo
            }
        elif decisao == 'elegivel_com_ressalva':
            return {
                'resultado_final': 'Elegível com Ressalva',
                'motivo_resultado': motivo
            }
        else:
            return {
                'resultado_final': 'Indeterminado',
                'motivo_resultado': motivo or 'Análise inconclusiva'
            }
    
    def criar_linha_planilha(self, numero_processo: str, dados_pessoais: Dict[str, Any], 
                            resultado_analise: Dict[str, Any], data_inicial_processo: str) -> Dict[str, Any]:
        """
        Cria uma linha da planilha com todos os dados
        
        Args:
            numero_processo: Número do processo
            dados_pessoais: Dados pessoais extraídos
            resultado_analise: Resultado da análise
            data_inicial_processo: Data inicial do processo
            
        Returns:
            Dict com dados da linha
        """
        # Mascarar dados sensíveis
        dados_mascarados = self.mascarar_dados_sensiveis(dados_pessoais)
        
        # Extrair análise de elegibilidade
        analise_eleg = resultado_analise.get('analise_elegibilidade', {})
        
        # Calcular idade
        idade_calculada = 'N/A'
        if dados_pessoais.get('data_nascimento') and data_inicial_processo:
            try:
                from datetime import datetime
                nasc = datetime.strptime(dados_pessoais['data_nascimento'], "%d/%m/%Y")
                inicial = datetime.strptime(data_inicial_processo, "%d/%m/%Y")
                idade = inicial.year - nasc.year
                if inicial.month < nasc.month or (inicial.month == nasc.month and inicial.day < nasc.day):
                    idade -= 1
                idade_calculada = idade
            except:
                idade_calculada = 'Erro'
        
        # Status da residência antes dos 10 anos
        parecer_pf = analise_eleg.get('parecer_pf', {})
        residencia_antes_10 = parecer_pf.get('residencia_antes_10_anos', False)
        residencia_texto = 'Sim' if residencia_antes_10 else 'Não'
        
        # Status dos documentos
        documentos = analise_eleg.get('documentos', {})
        status_docs = self.extrair_status_documentos(documentos)
        
        # Indícios de falsidade
        indicios_falsidade = parecer_pf.get('indicios_falsidade', False)
        indicios_texto = 'Sim' if indicios_falsidade else 'Não'
        
        # Resultado final
        resultado_final = self.determinar_resultado_final(resultado_analise)
        
        # Extrair decisão final e percentual
        elegibilidade_final = analise_eleg.get('elegibilidade_final', 'indeterminada')
        percentual_final = analise_eleg.get('percentual_final', 0)
        
        # [DEBUG] CORREÇÃO: Extrair percentual de múltiplas fontes
        if percentual_final == 0:
            # Tentar extrair do documentos.percentual_elegibilidade
            documentos = analise_eleg.get('documentos', {})
            percentual_elegibilidade = documentos.get('percentual_elegibilidade', 0)
            if percentual_elegibilidade > 0:
                percentual_final = percentual_elegibilidade
            
            # Se ainda for 0, tentar extrair das observações do resultado_analise
            if percentual_final == 0:
                observacoes_texto = resultado_analise.get('observacoes', '')
                motivo_final = analise_eleg.get('motivo_final', '')
                # Procurar percentual nas observações
                import re
                for texto in [observacoes_texto, motivo_final]:
                    if texto:
                        match = re.search(r'(\d+)%', texto)
                        if match:
                            percentual_final = int(match.group(1))
                            break
            
            # Se ainda for 0 e for elegível com ressalva, usar 90% como padrão
            if percentual_final == 0 and elegibilidade_final == 'elegivel_com_ressalva':
                percentual_final = 90
        
        # Mapear decisão final para texto claro
        if elegibilidade_final == 'deferimento':
            decisao_final = "DEFERIMENTO"
        elif elegibilidade_final == 'elegivel_com_ressalva':
            decisao_final = "ELEGÍVEL COM RESSALVA"
        elif elegibilidade_final == 'elegibilidade_comprometida':
            decisao_final = "ELEGIBILIDADE COMPROMETIDA"
        elif elegibilidade_final == 'indeferimento_automatico':
            decisao_final = "INDEFERIMENTO AUTOMÁTICO"
        elif elegibilidade_final == 'requer_analise_manual':
            decisao_final = "REQUER ANÁLISE MANUAL"
        elif elegibilidade_final == 'nao_elegivel':
            decisao_final = "NÃO ELEGÍVEL"
        else:
            decisao_final = "INDETERMINADO"
        
        # Criar linha da planilha (colunas completas)
        # [DEBUG] CORREÇÃO: Usar timestamp do resultado se disponível, senão atual
        data_processamento = resultado_analise.get('data_processamento')
        if not data_processamento:
            data_processamento = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        linha = {
            'Codigo': numero_processo,
            'Data_Processamento': data_processamento,
            'Decisao_Final': decisao_final,
            'Percentual_Elegibilidade': f"{percentual_final}%",
            'Observacoes': self._gerar_observacoes_simplificadas(analise_eleg, resultado_analise),
            'Parecer_PF': self._extrair_parecer_pf(analise_eleg),
            'Documentos_Processados': self._contar_documentos_processados(analise_eleg)
        }
        
        return linha
    
    def _gerar_observacoes(self, resultado_analise: Dict[str, Any], analise_eleg: Dict[str, Any]) -> str:
        """
        Gera observações detalhadas para a planilha
        
        Args:
            resultado_analise: Resultado da análise
            analise_eleg: Análise de elegibilidade
            
        Returns:
            String com observações
        """
        observacoes = []
        
        # Adicionar observações baseadas na elegibilidade
        elegibilidade_final = analise_eleg.get('elegibilidade_final', '')
        if elegibilidade_final == 'deferimento':
            observacoes.append("100% elegível - deferimento")
        elif elegibilidade_final == 'elegivel_com_ressalva':
            observacoes.append("Elegível com ressalvas identificadas")
        elif elegibilidade_final == 'elegibilidade_comprometida':
            observacoes.append("Elegibilidade comprometida")
        elif elegibilidade_final == 'indeferimento_automatico':
            observacoes.append("Indeferimento automático aplicado")
        elif elegibilidade_final == 'requer_analise_manual':
            observacoes.append("Requer análise manual")
        elif elegibilidade_final == 'nao_elegivel':
            observacoes.append("Não elegível")
        
        # Adicionar observações sobre documentos
        documentos = analise_eleg.get('documentos', {})
        for nome_doc, doc in documentos.items():
            if doc.get('status') in ['Falta', 'Inválido', 'Erro']:
                nome_formatado = nome_doc.replace('_', ' ').title()
                observacoes.append(f"Problema com {nome_formatado}: {doc.get('status')}")
        
        # Adicionar observações sobre parecer PF
        parecer_pf = analise_eleg.get('parecer_pf', {})
        if parecer_pf.get('indicios_falsidade'):
            observacoes.append("Indícios de falsidade documental detectados")
        
        if not observacoes:
            observacoes.append("Análise concluída sem observações especiais")
        
        return "; ".join(observacoes)
    
    def _gerar_observacoes_simplificadas(self, analise_eleg: Dict[str, Any], resultado_analise: Dict[str, Any]) -> str:
        """
        Gera observações simplificadas para a planilha
        
        Args:
            analise_eleg: Análise de elegibilidade
            resultado_analise: Resultado da análise
            
        Returns:
            String com observações simplificadas
        """
        observacoes = []
        
        # Elegibilidade final e percentual
        elegibilidade_final = analise_eleg.get('elegibilidade_final', '')
        percentual_final = analise_eleg.get('percentual_final', 0)
        
        # [DEBUG] CORREÇÃO: Extrair percentual de múltiplas fontes
        if percentual_final == 0:
            # Tentar extrair do documentos.percentual_elegibilidade
            documentos = analise_eleg.get('documentos', {})
            percentual_elegibilidade = documentos.get('percentual_elegibilidade', 0)
            if percentual_elegibilidade > 0:
                percentual_final = percentual_elegibilidade
            
            # Se ainda for 0, tentar extrair das observações do resultado_analise
            if percentual_final == 0:
                observacoes_texto = resultado_analise.get('observacoes', '')
                motivo_final = analise_eleg.get('motivo_final', '')
                # Procurar percentual nas observações
                import re
                for texto in [observacoes_texto, motivo_final]:
                    if texto:
                        match = re.search(r'(\d+)%', texto)
                        if match:
                            percentual_final = int(match.group(1))
                            break
            
            # Se ainda for 0 e for elegível com ressalva, usar 90% como padrão
            if percentual_final == 0 and elegibilidade_final == 'elegivel_com_ressalva':
                percentual_final = 90
        
        if elegibilidade_final == 'deferimento':
            observacoes.append("100% elegível (Deferimento)")
        elif elegibilidade_final == 'elegivel_com_ressalva':
            # [DEBUG] CORREÇÃO: Adicionar informação sobre documento faltante
            motivo_final = analise_eleg.get('motivo_final', '')
            if 'problemas de documentos' in motivo_final.lower():
                # Tentar extrair qual documento está com problema
                documentos = analise_eleg.get('documentos', {})
                doc_com_problema = None
                for nome_doc, info_doc in documentos.items():
                    if isinstance(info_doc, dict) and info_doc.get('status') != 'OK':
                        # Simplificar nome do documento
                        doc_simples = nome_doc.replace('Documento de identificação do representante legal', 'Rep. Legal')
                        doc_simples = doc_simples.replace('Carteira de Registro Nacional Migratório', 'CRNM')
                        doc_simples = doc_simples.replace('Comprovante de tempo de residência', 'Residência')
                        doc_simples = doc_simples.replace('Documento de viagem internacional', 'Viagem')
                        doc_com_problema = doc_simples
                        break
                
                if doc_com_problema:
                    observacoes.append(f"Elegível com ressalvas - {percentual_final}% (Falta: {doc_com_problema})")
                else:
                    observacoes.append(f"Elegível com ressalvas - {percentual_final}%")
            else:
                observacoes.append(f"Elegível com ressalvas - {percentual_final}%")
        elif elegibilidade_final == 'elegibilidade_comprometida':
            observacoes.append(f"Elegibilidade comprometida - {percentual_final}%")
        elif elegibilidade_final == 'indeferimento_automatico':
            observacoes.append("Indeferimento automático")
        elif elegibilidade_final == 'requer_analise_manual':
            observacoes.append("Requer análise manual")
        elif elegibilidade_final == 'nao_elegivel':
            observacoes.append("Não elegível")
        
        # Percentual de elegibilidade
        documentos = analise_eleg.get('documentos', {})
        if isinstance(documentos, dict) and 'percentual_elegibilidade' in documentos:
            percentual = documentos['percentual_elegibilidade']
            observacoes.append(f"Elegibilidade: {percentual}%")
        
        # Status dos documentos
        if isinstance(documentos, dict):
            docs_ok = sum(1 for doc in documentos.values() if isinstance(doc, dict) and doc.get('status') == 'OK')
            total_docs = len([doc for doc in documentos.values() if isinstance(doc, dict) and doc.get('status') != 'Erro'])
            if total_docs > 0:
                observacoes.append(f"Documentos: {docs_ok}/{total_docs} OK")
        
        if not observacoes:
            observacoes.append("Análise concluída")
        
        return " | ".join(observacoes)
    
    def _contar_documentos_processados(self, analise_eleg: Dict[str, Any]) -> str:
        """
        Conta documentos processados para a planilha
        
        Args:
            analise_eleg: Análise de elegibilidade
            
        Returns:
            String com contagem de documentos
        """
        # [DEBUG] CORREÇÃO: Verificar estrutura de documentos correta
        documentos_obrigatorios = analise_eleg.get('documentos_obrigatorios', {})
        if not documentos_obrigatorios:
            # Fallback para estrutura antiga
            documentos = analise_eleg.get('documentos', {})
            if not documentos:
                return "0/4"  # Total padrão provisória: 4 documentos
            
            # [DEBUG] CORREÇÃO: Contar documentos válidos corretamente
            # Usar apenas os 4 documentos principais esperados para provisória
            docs_esperados = [
                'Documento de identificação do representante legal',
                'Carteira de Registro Nacional Migratório', 
                'Comprovante de tempo de residência',
                'Documento de viagem internacional'
            ]
            
            docs_processados = 0
            docs_faltantes = []
            
            for doc_nome in docs_esperados:
                if doc_nome in documentos:
                    doc_info = documentos[doc_nome]
                    if isinstance(doc_info, dict):
                        # [DEBUG] CORREÇÃO: Considera processado se presente=True e status for 'OK'
                        # NÃO considera como processado se status for 'Falta', 'Erro', etc.
                        presente = doc_info.get('presente', False)
                        status = doc_info.get('status', '')
                        
                        if presente and status == 'OK':
                            docs_processados += 1
                        else:
                            docs_faltantes.append(doc_nome)
                            print(f"DEBUG: {doc_nome} NÃO contado - presente: {presente}, status: {status}")
                else:
                    docs_faltantes.append(doc_nome)
            
            # Se há documentos faltantes, adicionar informação nas observações
            contagem = f"{docs_processados}/{len(docs_esperados)}"
            if docs_faltantes:
                # Adicionar informação sobre documentos faltantes (simplificado)
                doc_faltante_simples = docs_faltantes[0].replace('Documento de identificação do representante legal', 'Rep. Legal')
                doc_faltante_simples = doc_faltante_simples.replace('Carteira de Registro Nacional Migratório', 'CRNM')
                doc_faltante_simples = doc_faltante_simples.replace('Comprovante de tempo de residência', 'Residência')
                doc_faltante_simples = doc_faltante_simples.replace('Documento de viagem internacional', 'Viagem')
                contagem += f" (Falta: {doc_faltante_simples})"
            
            return contagem
        
        # Lista padrão de documentos obrigatórios para provisória
        docs_esperados = [
            'Documento de identificação do representante legal',
            'Carteira de Registro Nacional Migratório', 
            'Comprovante de tempo de residência',
            'Documento de viagem internacional'
        ]
        
        total_documentos = len(docs_esperados)
        documentos_validos = 0
        
        docs_faltantes = []
        
        for doc_nome in docs_esperados:
            doc_info = documentos_obrigatorios.get(doc_nome, {})
            
            if isinstance(doc_info, dict):
                status = doc_info.get('status', '')
                # [DEBUG] CORREÇÃO: Considerar válido apenas se encontrado
                # NÃO contar 'nao_baixado', 'erro' como válidos
                if status == 'encontrado':
                    documentos_validos += 1
                else:
                    docs_faltantes.append(doc_nome)
            else:
                docs_faltantes.append(doc_nome)
        
        # Se há documentos faltantes, adicionar informação
        contagem = f"{documentos_validos}/{total_documentos}"
        if docs_faltantes:
            # Adicionar informação sobre documentos faltantes (simplificado)
            doc_faltante_simples = docs_faltantes[0].replace('Documento de identificação do representante legal', 'Rep. Legal')
            doc_faltante_simples = doc_faltante_simples.replace('Carteira de Registro Nacional Migratório', 'CRNM')
            doc_faltante_simples = doc_faltante_simples.replace('Comprovante de tempo de residência', 'Residência')
            doc_faltante_simples = doc_faltante_simples.replace('Documento de viagem internacional', 'Viagem')
            contagem += f" (Falta: {doc_faltante_simples})"
        
        return contagem
    
    def _extrair_parecer_pf(self, analise_eleg: Dict[str, Any]) -> str:
        """
        Extrai o parecer da PF para a planilha
        
        Args:
            analise_eleg: Análise de elegibilidade
            
        Returns:
            String com resumo do parecer
        """
        parecer_pf = analise_eleg.get('parecer_pf', {})
        
        if not parecer_pf:
            return "N/A"
        
        resumo = []
        
        # Residência antes dos 10 anos
        if parecer_pf.get('residencia_antes_10_anos'):
            resumo.append("Residência antes dos 10 anos: SIM")
        else:
            resumo.append("Residência antes dos 10 anos: NÃO")
        
        # Residência por prazo indeterminado
        if parecer_pf.get('residencia_prazo_indeterminado'):
            resumo.append("Residência indeterminada: SIM")
        else:
            resumo.append("Residência indeterminada: NÃO")
        
        # Opinião favorável
        if parecer_pf.get('opiniao_favoravel'):
            resumo.append("Opinião: FAVORÁVEL")
        else:
            resumo.append("Opinião: NÃO FAVORÁVEL")
        
        # Indícios de falsidade
        if parecer_pf.get('indicios_falsidade'):
            resumo.append("Indícios de falsidade: SIM")
        else:
            resumo.append("Indícios de falsidade: NÃO")
        
        return " | ".join(resumo)
    
    def _extrair_percentual_elegibilidade(self, analise_eleg: Dict[str, Any]) -> str:
        """
        Extrai o percentual de elegibilidade para a planilha
        
        Args:
            analise_eleg: Análise de elegibilidade
            
        Returns:
            String com percentual
        """
        documentos = analise_eleg.get('documentos', {})
        percentual = documentos.get('percentual_elegibilidade', 100)
        return f"{percentual}%"
    
    def exportar_para_excel(self, resultados: List[Dict[str, Any]], 
                           caminho_saida: str = None) -> str:
        """
        Exporta resultados para planilha Excel
        
        Args:
            resultados: Lista de resultados para exportar
            caminho_saida: Caminho do arquivo de saída (opcional)
            
        Returns:
            Caminho do arquivo gerado
        """
        if not resultados:
            raise ValueError("Lista de resultados vazia")
        
        # Criar DataFrame
        df = pd.DataFrame(resultados)
        
        # Reordenar colunas conforme especificação
        colunas_ordenadas = [col for col in self.colunas_planilha if col in df.columns]
        df = df[colunas_ordenadas]
        
        # Definir caminho de saída
        if not caminho_saida:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            caminho_saida = f"analise_provisoria_resultados_{timestamp}.xlsx"
        
        # Criar diretório se não existir
        diretorio = os.path.dirname(caminho_saida)
        if diretorio and not os.path.exists(diretorio):
            os.makedirs(diretorio)
        
        # Exportar para Excel
        with pd.ExcelWriter(caminho_saida, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Resultados_Provisoria', index=False)
            
            # Ajustar largura das colunas
            worksheet = writer.sheets['Resultados_Provisoria']
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        print(f"[OK] Planilha exportada com sucesso: {caminho_saida}")
        print(f"[DADOS] Total de processos analisados: {len(resultados)}")
        
        return caminho_saida
    
    def gerar_relatorio_resumo(self, resultados: List[Dict[str, Any]]) -> str:
        """
        Gera relatório resumo dos resultados
        
        Args:
            resultados: Lista de resultados
            
        Returns:
            String com relatório resumo
        """
        if not resultados:
            return "Nenhum resultado para gerar relatório"
        
        total_processos = len(resultados)
        
        # Contar resultados finais
        resultados_finais = {}
        for resultado in resultados:
            resultado_final = resultado.get('Resultado_Final', 'Indeterminado')
            resultados_finais[resultado_final] = resultados_finais.get(resultado_final, 0) + 1
        
        # Contar problemas com documentos
        problemas_documentos = 0
        for resultado in resultados:
            if (resultado.get('Status_Representante_Legal') in ['Falta', 'Inválido', 'Erro'] or
                resultado.get('Status_CRNM_Naturalizando') in ['Falta', 'Inválido', 'Erro'] or
                resultado.get('Status_Comprovante_Residencia') in ['Falta', 'Inválido', 'Erro']):
                problemas_documentos += 1
        
        # Contar indícios de falsidade
        indicios_falsidade = sum(1 for r in resultados if r.get('Indicios_Falsidade') == 'Sim')
        
        relatorio = f"""
=== RELATÓRIO RESUMO - ANÁLISE PROVISÓRIA ===
Data: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

[DADOS] ESTATÍSTICAS GERAIS:
• Total de processos analisados: {total_processos}

[TARGET] RESULTADOS FINAIS:
"""
        
        for resultado, quantidade in resultados_finais.items():
            relatorio += f"• {resultado}: {quantidade} ({quantidade/total_processos*100:.1f}%)\n"
        
        relatorio += f"""
[DOC] PROBLEMAS IDENTIFICADOS:
• Processos com problemas de documentos: {problemas_documentos} ({problemas_documentos/total_processos*100:.1f}%)
• Processos com indícios de falsidade: {indicios_falsidade} ({indicios_falsidade/total_processos*100:.1f}%)

[BUSCA] OBSERVAÇÕES:
• Análise específica para naturalização provisória
• Regras de elegibilidade aplicadas conforme especificação
• Dados sensíveis mascarados conforme LGPD
• Exportação em formato Excel para análise detalhada
"""
        
        return relatorio

# Função de conveniência para uso direto
def exportar_resultados_provisoria(resultados: List[Dict[str, Any]], 
                                 caminho_saida: str = None) -> str:
    """
    Função de conveniência para exportar resultados provisórios
    
    Args:
        resultados: Lista de resultados para exportar
        caminho_saida: Caminho do arquivo de saída (opcional)
        
    Returns:
        Caminho do arquivo gerado
    """
    exportador = ExportadorProvisoria()
    return exportador.exportar_para_excel(resultados, caminho_saida) 