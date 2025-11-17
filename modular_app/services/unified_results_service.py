"""
Serviço Unificado de Resultados
Consolida geração de planilhas para Parecer do Analista e Ordinária em um único local
"""
import os
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Optional


class UnifiedResultsService:
    """
    Serviço centralizado para gerar e consolidar planilhas de resultados
    de diferentes tipos de análise em um único diretório (planilhas/)
    """
    
    def __init__(self, base_dir: Optional[str] = None):
        """
        Inicializa o serviço
        
        Args:
            base_dir: Diretório base (padrão: diretório atual)
        """
        self.base_dir = base_dir or os.getcwd()
        self.planilhas_dir = os.path.join(self.base_dir, 'planilhas')
        os.makedirs(self.planilhas_dir, exist_ok=True)
        
        # Nome do arquivo consolidado único
        self.consolidated_file = 'resultados_consolidados.xlsx'
        self.consolidated_path = os.path.join(self.planilhas_dir, self.consolidated_file)
    
    def salvar_resultado_parecer_analista(self, resultados: List[Dict[str, Any]], 
                                         timestamp: Optional[str] = None) -> str:
        """
        Salva resultados do Parecer do Analista (aprovação de recurso)
        
        Args:
            resultados: Lista de dicionários com resultados
            timestamp: Timestamp opcional para nome do arquivo
            
        Returns:
            Caminho do arquivo salvo
        """
        ts = timestamp or datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Normalizar dados para formato unificado
        rows_normalized = []
        for r in resultados:
            row = {
                'Número do Processo': r.get('codigo', 'N/A'),
                'Código do Processo': r.get('codigo', 'N/A'),
                'Tipo de Análise': 'Parecer do Analista',
                'Status': r.get('status', 'N/A'),
                'Decisão': r.get('decisao', 'N/A'),
                'Decisão Enviada': 'Sim' if r.get('decisao_enviada') else 'Não',
                'Erro': r.get('erro', ''),
                'Data da Análise': datetime.now().strftime('%d/%m/%Y'),
                'Hora da Análise': datetime.now().strftime('%H:%M:%S'),
            }
            rows_normalized.append(row)
        
        df = pd.DataFrame(rows_normalized)
        
        # Salvar arquivo individual com timestamp
        individual_file = f'resultados_parecer_analista_{ts}.xlsx'
        individual_path = os.path.join(self.planilhas_dir, individual_file)
        df.to_excel(individual_path, index=False)
        
        # Adicionar ao consolidado
        self._append_to_consolidated(df)
        
        return individual_path
    
    def salvar_resultado_ordinaria(self, resultado: Dict[str, Any],
                                   numero_processo: str,
                                   timestamp: Optional[str] = None) -> str:
        """
        Salva resultado de Análise Ordinária no formato unificado
        
        Args:
            resultado: Dicionário com resultado completo
            numero_processo: Número do processo
            timestamp: Timestamp opcional
            
        Returns:
            Caminho do arquivo consolidado
        """
        ts = timestamp or datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Normalizar dados para formato unificado
        elegibilidade = resultado.get('resultado_elegibilidade', {})
        dados_pessoais = elegibilidade.get('dados_pessoais', {})
        
        row = {
            'Número do Processo': numero_processo,
            'Código do Processo': numero_processo,
            'Nome': dados_pessoais.get('nome') or dados_pessoais.get('nome_completo', 'N/A'),
            'Tipo de Análise': 'Naturalização Ordinária',
            'Status': resultado.get('status', 'N/A'),
            'Elegibilidade Final': resultado.get('elegibilidade_final', 'N/A'),
            'Percentual Final': elegibilidade.get('percentual_final', 0),
            'Motivo Final': elegibilidade.get('motivo_final', ''),
            'Motivos Indeferimento': '; '.join(resultado.get('motivos_indeferimento', [])),
            'Documentos Faltantes': '; '.join(resultado.get('documentos_faltantes', [])),
            'Data da Análise': datetime.now().strftime('%d/%m/%Y'),
            'Hora da Análise': datetime.now().strftime('%H:%M:%S'),
            'Erro': resultado.get('erro', ''),
        }
        
        df = pd.DataFrame([row])
        
        # Adicionar ao consolidado
        self._append_to_consolidated(df)
        
        return self.consolidated_path
    
    def salvar_lote_ordinaria(self, resultados: List[Dict[str, Any]],
                             timestamp: Optional[str] = None) -> str:
        """
        Salva múltiplos resultados de Análise Ordinária
        
        Args:
            resultados: Lista de resultados
            timestamp: Timestamp opcional
            
        Returns:
            Caminho do arquivo salvo
        """
        ts = timestamp or datetime.now().strftime('%Y%m%d_%H%M%S')
        
        rows_normalized = []
        for r in resultados:
            row = {
                'Código do Processo': r.get('codigo', 'N/A'),
                'Tipo de Análise': 'Naturalização Ordinária',
                'Status': r.get('status', 'N/A'),
                'Elegibilidade Final': r.get('elegibilidade_final', 'N/A'),
                'Percentual Final': r.get('percentual_final', 0),
                'Motivo Final': r.get('motivo_final', ''),
                'Motivos Indeferimento': '; '.join(r.get('motivos_indeferimento', []) if isinstance(r.get('motivos_indeferimento'), list) else []),
                'Documentos Faltantes': '; '.join(r.get('documentos_faltantes', []) if isinstance(r.get('documentos_faltantes'), list) else []),
                'Data da Análise': datetime.now().strftime('%d/%m/%Y'),
                'Hora da Análise': datetime.now().strftime('%H:%M:%S'),
                'Erro': r.get('erro', ''),
            }
            rows_normalized.append(row)
        
        df = pd.DataFrame(rows_normalized)
        
        # Salvar arquivo individual com timestamp
        individual_file = f'resultados_ordinaria_{ts}.xlsx'
        individual_path = os.path.join(self.planilhas_dir, individual_file)
        df.to_excel(individual_path, index=False)
        
        # Adicionar ao consolidado
        self._append_to_consolidated(df)
        
        return individual_path
    
    def _append_to_consolidated(self, df_new: pd.DataFrame) -> None:
        """
        Adiciona novos resultados ao arquivo consolidado
        
        Args:
            df_new: DataFrame com novos resultados
        """
        try:
            # Se arquivo consolidado existe, carregar e concatenar
            if os.path.exists(self.consolidated_path):
                df_existing = pd.read_excel(self.consolidated_path)
                
                # Garantir que todas as colunas existem em ambos DataFrames
                all_columns = list(set(df_existing.columns) | set(df_new.columns))
                for col in all_columns:
                    if col not in df_existing.columns:
                        df_existing[col] = ''
                    if col not in df_new.columns:
                        df_new[col] = ''
                
                # Concatenar
                df_consolidated = pd.concat([df_existing, df_new], ignore_index=True)
                
                # Remover duplicatas por Código do Processo, mantendo o último
                if 'Código do Processo' in df_consolidated.columns:
                    df_consolidated = df_consolidated.drop_duplicates(
                        subset=['Código do Processo'], 
                        keep='last'
                    )
            else:
                df_consolidated = df_new
            
            # Salvar consolidado
            df_consolidated.to_excel(self.consolidated_path, index=False)
            
        except Exception as e:
            print(f"[AVISO] Erro ao atualizar consolidado: {e}")
    
    def get_consolidated_path(self) -> str:
        """Retorna o caminho do arquivo consolidado"""
        return self.consolidated_path
    
    def get_planilhas_dir(self) -> str:
        """Retorna o diretório de planilhas"""
        return self.planilhas_dir
