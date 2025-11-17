"""
RecursoRepository (Automação)
Leitura de planilhas de códigos para Aprovação do Conteúdo de Recurso.
"""
import logging
import pandas as pd

logger = logging.getLogger(__name__)


class RecursoRepository:
    def ler_planilha_codigos(self, caminho_planilha: str, nome_coluna_codigo: str = 'codigo') -> list[str]:
        try:
            if caminho_planilha.lower().endswith('.csv'):
                df = pd.read_csv(caminho_planilha)
            else:
                df = pd.read_excel(caminho_planilha)
            # coluna alvo (case-insensitive)
            col_map = {str(c).strip().lower(): c for c in df.columns}
            alvo = (nome_coluna_codigo or 'codigo').strip().lower()
            real = None
            for cand in [alvo, 'codigo', 'código']:
                if cand in col_map:
                    real = col_map[cand]
                    break
            if not real:
                for low, orig in col_map.items():
                    if 'codigo' in low or 'código' in low:
                        real = orig
                        break
            if not real:
                logger.error(f"Coluna de código não encontrada na planilha: {list(df.columns)}")
                return []
            serie = df[real].dropna().astype(str).map(lambda s: s.strip()).replace({'': None})
            # normalizar 770.033 -> 770033
            serie = serie.str.replace('.', '', regex=False).str.replace(',', '', regex=False)
            codigos = [s for s in serie.tolist() if s]
            logger.info(f"[OK] {len(codigos)} códigos lidos da planilha")
            return codigos
        except Exception as e:
            logger.error(f"[ERRO] ler_planilha_codigos: {e}")
            return []
