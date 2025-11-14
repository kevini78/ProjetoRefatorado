"""
Módulo para gerar planilha com resultados do OCR e análise do spaCy
"""

import pandas as pd
import os
from datetime import datetime
from typing import Dict, List, Any

class GeradorPlanilhaResultados:
    """
    Classe para gerar planilha com resultados do OCR e análise
    """
    
    def __init__(self):
        self.colunas_planilha = [
            'Codigo',  # Código do processo (da planilha original)
            'Texto_Portaria_Provisoria',  # Texto extraído da portaria
            'Texto_Identidade',  # Texto extraído do documento de identidade
            'Texto_Antecedentes_Criminais',  # Texto extraído dos antecedentes
            'Resultado_Analise',  # Deferimento ou Indeferimento
            'Data_Processamento',  # Data/hora do processamento
            'Status_Processamento',  # Status do processamento
            # NOVAS COLUNAS PARA ANÁLISE DETALHADA
            'Elegibilidade',  # elegivel_alta_probabilidade, deferimento_com_ressalvas, etc.
            'Confianca',  # Porcentagem de confiança (ex: 91.7%)
            'Score_Total',  # Score numérico da análise
            'Condicoes_Atendidas',  # Número de condições atendidas
            'Condicoes_Total',  # Total de condições obrigatórias
            'Documentos_Faltantes',  # Lista de documentos que geram ressalva
            'Condicoes_Criticas_Atendidas',  # Condições críticas atendidas
            'Condicoes_Criticas_Total',  # Total de condições críticas
            'Recomendacao',  # Recomendação detalhada da análise
            'Detalhes_Antecedentes',  # Status dos antecedentes criminais
            'Detalhes_Naturalizacao',  # Status da naturalização provisória
            'Detalhes_Idade',  # Status da verificação de idade
            'Detalhes_Residencia',  # Status do comprovante de residência
            'Detalhes_Identidade'  # Status do documento de identidade
        ]
    
    def modificar_planilha_original(self, 
                                   caminho_planilha_original: str,
                                   resultados_ocr: Dict[str, Dict],
                                   resultados_analise: Dict[str, str] = None) -> str:
        """
        Modifica a planilha original adicionando colunas com resultados do OCR e análise
        
        Args:
            caminho_planilha_original: Caminho da planilha original enviada
            resultados_ocr: Dicionário com resultados do OCR por processo
            resultados_analise: Dicionário com resultados da análise por processo
        
        Returns:
            str: Caminho da planilha modificada
        """
        print("[DADOS] MODIFICANDO PLANILHA ORIGINAL")
        print("=" * 50)
        
        try:
            # Carregar a planilha original
            print(f"Carregando planilha original: {caminho_planilha_original}")
            df_original = pd.read_excel(caminho_planilha_original)
            
            # Verificar se a planilha tem a coluna de código
            coluna_codigo = self._encontrar_coluna_codigo(df_original)
            if not coluna_codigo:
                raise ValueError("Coluna 'Codigo' não encontrada na planilha original")
            
            print(f"Coluna de código encontrada: '{coluna_codigo}'")
            print(f"Total de linhas na planilha: {len(df_original)}")
            
            # Normalizar códigos (remover .0, .00, etc.)
            df_original[coluna_codigo] = df_original[coluna_codigo].astype(str).str.replace('.0', '', regex=False)
            
            # Adicionar novas colunas se não existirem
            novas_colunas = {
                'Texto_Portaria_Provisoria': '',
                'Texto_Identidade': '',
                'Texto_Antecedentes_Criminais': '',
                'Resultado_Analise': 'Não analisado',
                'Data_Processamento': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
                'Status_Processamento': 'Não processado',
                # NOVAS COLUNAS PARA ANÁLISE DETALHADA
                'Elegibilidade': 'Não analisado',
                'Confianca': '0%',
                'Score_Total': 0,
                'Condicoes_Atendidas': 0,
                'Condicoes_Total': 0,
                'Documentos_Faltantes': 'Nenhum',
                'Condicoes_Criticas_Atendidas': 0,
                'Condicoes_Criticas_Total': 0,
                'Recomendacao': 'Não analisado',
                'Detalhes_Antecedentes': 'Não verificado',
                'Detalhes_Naturalizacao': 'Não verificado',
                'Detalhes_Idade': 'Não verificado',
                'Detalhes_Residencia': 'Não verificado',
                'Detalhes_Identidade': 'Não verificado'
            }
            
            for coluna, valor_padrao in novas_colunas.items():
                if coluna not in df_original.columns:
                    df_original[coluna] = valor_padrao
                    print(f"  [OK] Coluna '{coluna}' adicionada")
                else:
                    print(f"  [AVISO] Coluna '{coluna}' já existe")
            
            # Preencher dados para cada linha
            for idx, row in df_original.iterrows():
                codigo = str(row[coluna_codigo]).strip()
                print(f"Processando linha {idx+1}: código {codigo}")
                
                # Buscar resultados do OCR para este processo
                resultado_processo = resultados_ocr.get(codigo, {})
                
                # Extrair textos dos documentos
                texto_portaria = self._extrair_texto_documento(resultado_processo, 'Portaria de concessão da naturalização provisória')
                texto_identidade = self._extrair_texto_documento(resultado_processo, 'Documento oficial de identidade')
                texto_antecedentes = self._extrair_texto_documento(resultado_processo, 'Certidão de antecedentes criminais')
                
                # Resultado da análise (se disponível)
                resultado_analise_processo = resultados_analise.get(codigo, 'Não analisado') if resultados_analise else 'Não analisado'
                
                # Status do processamento
                status = self._determinar_status_processamento(resultado_processo)
                
                # EXTRAIR INFORMAÇÕES DETALHADAS DA ANÁLISE DE ELEGIBILIDADE
                info_detalhada = self._extrair_info_detalhada_analise(resultado_processo, resultado_analise_processo)
                
                # Atualizar a linha na planilha original
                df_original.at[idx, 'Texto_Portaria_Provisoria'] = texto_portaria
                df_original.at[idx, 'Texto_Identidade'] = texto_identidade
                df_original.at[idx, 'Texto_Antecedentes_Criminais'] = texto_antecedentes
                df_original.at[idx, 'Resultado_Analise'] = resultado_analise_processo
                df_original.at[idx, 'Status_Processamento'] = status
                df_original.at[idx, 'Data_Processamento'] = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                
                # PREENCHER COLUNAS DETALHADAS
                for coluna, valor in info_detalhada.items():
                    if coluna in df_original.columns:
                        df_original.at[idx, coluna] = valor
                
                print(f"  [OK] Portaria: {len(texto_portaria)} chars")
                print(f"  [OK] Identidade: {len(texto_identidade)} chars")
                print(f"  [OK] Antecedentes: {len(texto_antecedentes)} chars")
                print(f"  [OK] Resultado: {resultado_analise_processo}")
                print(f"  [OK] Status: {status}")
                print(f"  [OK] Elegibilidade: {info_detalhada.get('Elegibilidade', 'N/A')}")
                print(f"  [OK] Confiança: {info_detalhada.get('Confianca', 'N/A')}")
                print(f"  [OK] Documentos Faltantes: {info_detalhada.get('Documentos_Faltantes', 'N/A')}")
            
            # Gerar nome do arquivo modificado
            nome_base = os.path.splitext(os.path.basename(caminho_planilha_original))[0]
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            nome_arquivo_modificado = f'{nome_base}_MODIFICADA_{timestamp}.xlsx'
            
            # Caminho completo do arquivo modificado (na pasta uploads)
            uploads_dir = os.path.join(os.path.dirname(__file__), 'uploads')
            os.makedirs(uploads_dir, exist_ok=True)
            caminho_arquivo_modificado = os.path.join(uploads_dir, nome_arquivo_modificado)
            
            # Salvar planilha modificada
            with pd.ExcelWriter(caminho_arquivo_modificado, engine='openpyxl') as writer:
                # Planilha principal modificada
                df_original.to_excel(writer, sheet_name='Planilha_Modificada', index=False)
                
                # Planilha resumida (apenas códigos e resultados)
                df_resumo = df_original[[
                    coluna_codigo, 
                    'Resultado_Analise', 
                    'Status_Processamento',
                    'Elegibilidade',
                    'Confianca',
                    'Documentos_Faltantes',
                    'Condicoes_Criticas_Atendidas',
                    'Condicoes_Criticas_Total'
                ]].copy()
                df_resumo.to_excel(writer, sheet_name='Resumo', index=False)
                
                # Planilha de estatísticas
                self._criar_planilha_estatisticas(df_original, writer)
            
            print(f"\n[OK] Planilha modificada salva com sucesso: {caminho_arquivo_modificado}")
            print(f"   Total de processos processados: {len(df_original)}")
            print(f"   Planilhas criadas: Planilha_Modificada, Resumo, Estatisticas")
            
            return caminho_arquivo_modificado
            
        except Exception as e:
            print(f"[ERRO] Erro ao salvar planilha: {e}")
            raise
    
    def _extrair_texto_documento(self, resultado_processo: Dict, nome_documento: str) -> str:
        """
        Extrai texto de um documento específico
        
        Args:
            resultado_processo: Resultado do processamento do processo
            nome_documento: Nome do documento a extrair
        
        Returns:
            str: Texto extraído ou mensagem de erro
        """
        try:
            # Buscar pelo nome do documento
            for nome_doc, dados_doc in resultado_processo.items():
                if nome_documento.lower() in nome_doc.lower():
                    if dados_doc.get('sucesso', False):
                        texto = dados_doc.get('texto_completo', '')
                        if not texto:
                            texto = dados_doc.get('campos_ocr', {}).get('texto_bruto', '')
                        return texto if texto else 'Texto não extraído'
                    else:
                        erro = dados_doc.get('erro', 'Erro desconhecido')
                        return f'ERRO: {erro}'
            
            return 'Documento não encontrado'
            
        except Exception as e:
            return f'ERRO ao extrair: {str(e)}'
    
    def _determinar_status_processamento(self, resultado_processo: Dict) -> str:
        """
        Determina o status do processamento do processo
        
        Args:
            resultado_processo: Resultado do processamento
        
        Returns:
            str: Status do processamento
        """
        if not resultado_processo:
            return 'Não processado'
        
        # Contar documentos processados com sucesso
        sucessos = sum(1 for doc in resultado_processo.values() if doc.get('sucesso', False))
        total = len(resultado_processo)
        
        if sucessos == 0:
            return 'Falha total'
        elif sucessos == total:
            return 'Sucesso total'
        else:
            return f'Parcial ({sucessos}/{total})'
    
    def _criar_planilha_estatisticas(self, df: pd.DataFrame, writer: pd.ExcelWriter):
        """
        Cria planilha de estatísticas
        
        Args:
            df: DataFrame principal
            writer: ExcelWriter para salvar
        """
        # Estatísticas gerais
        stats_gerais = {
            'Métrica': [
                'Total de Processos',
                'Processados com Sucesso Total',
                'Processados com Sucesso Parcial',
                'Falhas Totais',
                'Não Processados'
            ],
            'Quantidade': [
                len(df),
                len(df[df['Status_Processamento'] == 'Sucesso total']),
                len(df[df['Status_Processamento'].str.contains('Parcial', na=False)]),
                len(df[df['Status_Processamento'] == 'Falha total']),
                len(df[df['Status_Processamento'] == 'Não processado'])
            ]
        }
        
        df_stats = pd.DataFrame(stats_gerais)
        df_stats.to_excel(writer, sheet_name='Estatisticas', index=False)
        
        # Estatísticas por resultado
        if 'Resultado_Analise' in df.columns:
            resultados = df['Resultado_Analise'].value_counts()
            df_resultados = pd.DataFrame({
                'Resultado': resultados.index,
                'Quantidade': resultados.values
            })
            df_resultados.to_excel(writer, sheet_name='Estatisticas', startrow=len(stats_gerais) + 3, index=False)
        
        # ESTATÍSTICAS DE ELEGIBILIDADE (NOVAS!)
        if 'Elegibilidade' in df.columns:
            # Estatísticas de elegibilidade
            elegibilidades = df['Elegibilidade'].value_counts()
            df_elegibilidades = pd.DataFrame({
                'Elegibilidade': elegibilidades.index,
                'Quantidade': elegibilidades.values
            })
            df_elegibilidades.to_excel(writer, sheet_name='Estatisticas', startrow=len(stats_gerais) + 6, index=False)
            
            # Estatísticas de confiança
            if 'Confianca' in df.columns:
                # Converter confiança para numérico para estatísticas
                confiancas = df['Confianca'].str.replace('%', '').astype(float)
                stats_confianca = {
                    'Métrica': ['Confiança Média', 'Confiança Mínima', 'Confiança Máxima'],
                    'Valor': [f"{confiancas.mean():.1f}%", f"{confiancas.min():.1f}%", f"{confiancas.max():.1f}%"]
                }
                df_confianca = pd.DataFrame(stats_confianca)
                df_confianca.to_excel(writer, sheet_name='Estatisticas', startrow=len(stats_gerais) + 9, index=False)
            
            # Estatísticas de documentos faltantes
            if 'Documentos_Faltantes' in df.columns:
                docs_faltantes = df[df['Documentos_Faltantes'] != 'Nenhum']['Documentos_Faltantes'].value_counts()
                if not docs_faltantes.empty:
                    df_docs_faltantes = pd.DataFrame({
                        'Documento Faltante': docs_faltantes.index,
                        'Quantidade': docs_faltantes.values
                    })
                    df_docs_faltantes.to_excel(writer, sheet_name='Estatisticas', startrow=len(stats_gerais) + 12, index=False)
    
    def _encontrar_coluna_codigo(self, df: pd.DataFrame) -> str:
        """
        Encontra a coluna de código na planilha
        
        Args:
            df: DataFrame da planilha
        
        Returns:
            str: Nome da coluna de código ou None se não encontrada
        """
        for col in df.columns:
            if 'codigo' in col.lower() or 'código' in col.lower():
                return col
        return None
    
    def carregar_planilha_codigos(self, caminho_arquivo: str) -> List[str]:
        """
        Carrega códigos de uma planilha
        
        Args:
            caminho_arquivo: Caminho da planilha
        
        Returns:
            List[str]: Lista de códigos
        """
        try:
            df = pd.read_excel(caminho_arquivo)
            
            # Procurar coluna de código
            coluna_codigo = self._encontrar_coluna_codigo(df)
            
            if coluna_codigo is None:
                raise ValueError("Coluna 'Codigo' não encontrada na planilha")
            
            # Converter códigos para string e remover .0
            codigos = df[coluna_codigo].astype(str).str.replace('.0', '', regex=False).tolist()
            
            print(f"[OK] {len(codigos)} códigos carregados da planilha")
            return codigos
            
        except Exception as e:
            print(f"[ERRO] Erro ao carregar planilha: {e}")
            raise

    def _extrair_info_detalhada_analise(self, resultado_processo: Dict, resultado_analise: str) -> Dict[str, Any]:
        """
        Extrai informações detalhadas da análise de elegibilidade
        
        Args:
            resultado_processo: Resultado do processamento do processo
            resultado_analise: Resultado da análise (string)
        
        Returns:
            Dict com informações detalhadas
        """
        try:
            # Buscar pela análise de elegibilidade nos resultados do processo
            analise_elegibilidade = None
            for nome_doc, dados_doc in resultado_processo.items():
                if 'analise_elegibilidade' in dados_doc:
                    analise_elegibilidade = dados_doc['analise_elegibilidade']
                    break
            
            if not analise_elegibilidade:
                return {
                    'Elegibilidade': 'Não analisado',
                    'Confianca': '0%',
                    'Score_Total': 0,
                    'Condicoes_Atendidas': 0,
                    'Condicoes_Total': 0,
                    'Documentos_Faltantes': 'Nenhum',
                    'Condicoes_Criticas_Atendidas': 0,
                    'Condicoes_Criticas_Total': 0,
                    'Recomendacao': 'Não analisado',
                    'Detalhes_Antecedentes': 'Não verificado',
                    'Detalhes_Naturalizacao': 'Não verificado',
                    'Detalhes_Idade': 'Não verificado',
                    'Detalhes_Residencia': 'Não verificado',
                    'Detalhes_Identidade': 'Não verificado'
                }
            
            # Extrair informações da análise
            elegibilidade = analise_elegibilidade.get('elegibilidade', 'Não determinado')
            confianca = f"{analise_elegibilidade.get('confianca', 0) * 100:.1f}%"
            score_total = analise_elegibilidade.get('score_total', 0)
            
            # Condições obrigatórias
            condicoes_obrig = analise_elegibilidade.get('condicoes_obrigatorias', {})
            condicoes_atendidas = condicoes_obrig.get('atendidas', 0)
            condicoes_total = condicoes_obrig.get('total', 0)
            
            # Documentos de ressalva
            docs_ressalva = analise_elegibilidade.get('documentos_ressalva', {})
            docs_faltantes = docs_ressalva.get('descricoes_faltantes', [])
            docs_faltantes_str = '; '.join(docs_faltantes) if docs_faltantes else 'Nenhum'
            
            # Condições críticas (total - documentos de ressalva)
            condicoes_criticas_total = condicoes_total - len(docs_ressalva.get('faltantes', []))
            condicoes_criticas_atendidas = condicoes_atendidas
            
            # Recomendação
            recomendacao = analise_elegibilidade.get('recomendacao', 'Não disponível')
            
            # Detalhes de cada condição
            detalhes_condicoes = condicoes_obrig.get('detalhes', {})
            
            detalhes_antecedentes = self._extrair_status_condicao(detalhes_condicoes, 'sem_antecedentes_criminais')
            detalhes_naturalizacao = self._extrair_status_condicao(detalhes_condicoes, 'naturalizacao_provisoria')
            detalhes_idade = self._extrair_status_condicao(detalhes_condicoes, 'idade_processo')
            detalhes_residencia = self._extrair_status_condicao(detalhes_condicoes, 'comprovante_residencia')
            detalhes_identidade = self._extrair_status_condicao(detalhes_condicoes, 'documento_identidade')
            
            return {
                'Elegibilidade': elegibilidade,
                'Confianca': confianca,
                'Score_Total': score_total,
                'Condicoes_Atendidas': condicoes_atendidas,
                'Condicoes_Total': condicoes_total,
                'Documentos_Faltantes': docs_faltantes_str,
                'Condicoes_Criticas_Atendidas': condicoes_criticas_atendidas,
                'Condicoes_Criticas_Total': condicoes_criticas_total,
                'Recomendacao': recomendacao,
                'Detalhes_Antecedentes': detalhes_antecedentes,
                'Detalhes_Naturalizacao': detalhes_naturalizacao,
                'Detalhes_Idade': detalhes_idade,
                'Detalhes_Residencia': detalhes_residencia,
                'Detalhes_Identidade': detalhes_identidade
            }
            
        except Exception as e:
            print(f"[AVISO] Erro ao extrair informações detalhadas: {e}")
            return {
                'Elegibilidade': 'Erro na extração',
                'Confianca': '0%',
                'Score_Total': 0,
                'Condicoes_Atendidas': 0,
                'Condicoes_Total': 0,
                'Documentos_Faltantes': 'Erro na extração',
                'Condicoes_Criticas_Atendidas': 0,
                'Condicoes_Criticas_Total': 0,
                'Recomendacao': 'Erro na extração',
                'Detalhes_Antecedentes': 'Erro na extração',
                'Detalhes_Naturalizacao': 'Erro na extração',
                'Detalhes_Idade': 'Erro na extração',
                'Detalhes_Residencia': 'Erro na extração',
                'Detalhes_Identidade': 'Erro na extração'
            }
    
    def _extrair_status_condicao(self, detalhes_condicoes: Dict, nome_condicao: str) -> str:
        """
        Extrai o status de uma condição específica
        
        Args:
            detalhes_condicoes: Dicionário com detalhes das condições
            nome_condicao: Nome da condição
        
        Returns:
            str: Status da condição
        """
        try:
            if nome_condicao in detalhes_condicoes:
                condicao = detalhes_condicoes[nome_condicao]
                atendida = condicao.get('atendida', False)
                motivo = condicao.get('motivo', 'Sem motivo')
                
                if atendida:
                    return f"[OK] ATENDIDA: {motivo}"
                else:
                    return f"[ERRO] NÃO ATENDIDA: {motivo}"
            else:
                return 'Não verificado'
        except Exception as e:
            return f'Erro: {str(e)}'

# Função de conveniência
def modificar_planilha_original(caminho_planilha_original: str,
                               resultados_ocr: Dict[str, Dict],
                               resultados_analise: Dict[str, str] = None) -> str:
    """
    Função de conveniência para modificar planilha original
    
    Args:
        caminho_planilha_original: Caminho da planilha original
        resultados_ocr: Dicionário com resultados do OCR por processo
        resultados_analise: Dicionário com resultados da análise por processo
    
    Returns:
        str: Caminho da planilha modificada
    """
    gerador = GeradorPlanilhaResultados()
    return gerador.modificar_planilha_original(
        caminho_planilha_original,
        resultados_ocr, 
        resultados_analise
    )

# Teste do módulo
if __name__ == "__main__":
    print("[TESTE] TESTANDO GERADOR DE PLANILHA DE RESULTADOS")
    print("=" * 60)
    
    # Dados de teste
    codigos_teste = ['679380', '686063', '576441']
    
    resultados_ocr_teste = {
        '679380': {
            'Portaria de concessão da naturalização provisória': {
                'sucesso': True,
                'texto_completo': 'Texto da portaria do processo 679380...',
                'campos_ocr': {'texto_bruto': 'Texto da portaria do processo 679380...'}
            },
            'Documento oficial de identidade': {
                'sucesso': True,
                'texto_completo': 'Texto da identidade do processo 679380...',
                'campos_ocr': {'texto_bruto': 'Texto da identidade do processo 679380...'}
            },
            'Certidão de antecedentes criminais': {
                'sucesso': True,
                'texto_completo': 'Texto dos antecedentes do processo 679380...',
                'campos_ocr': {'texto_bruto': 'Texto dos antecedentes do processo 679380...'}
            }
        }
    }
    
    resultados_analise_teste = {
        '679380': 'Deferimento'
    }
    
    try:
        # Testar geração da planilha
        gerador = GeradorPlanilhaResultados()
        
        # Testar carregamento de códigos
        print("[INFO] Testando carregamento de códigos...")
        codigos_carregados = gerador.carregar_planilha_codigos = lambda x: codigos_teste
        print(f"   Códigos carregados: {codigos_teste}")
        
        # Testar extração de texto
        print("\n[DOC] Testando extração de texto...")
        texto_portaria = gerador._extrair_texto_documento(
            resultados_ocr_teste['679380'], 
            'Portaria de concessão da naturalização provisória'
        )
        print(f"   Texto portaria: {len(texto_portaria)} chars")
        
        # Testar determinação de status
        print("\n[DADOS] Testando determinação de status...")
        status = gerador._determinar_status_processamento(resultados_ocr_teste['679380'])
        print(f"   Status: {status}")
        
        # Testar busca de coluna de código
        print("\n[BUSCA] Testando busca de coluna de código...")
        df_teste = pd.DataFrame({'Codigo': codigos_teste})
        coluna_encontrada = gerador._encontrar_coluna_codigo(df_teste)
        print(f"   Coluna encontrada: {coluna_encontrada}")
        
        print("\n[OK] Teste concluído com sucesso!")
        
    except Exception as e:
        print(f"[ERRO] Teste falhou: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}") 