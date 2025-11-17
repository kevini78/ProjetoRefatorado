import os
import pandas as pd
from datetime import datetime

# Stubs mínimos
class FakeLecomAction:
    def __init__(self):
        self.numero_processo_limpo = '580183'
        # Mantém formato textual como no exemplo do usuário
        self.data_inicial_processo = '15 de Abr de 2024'
        # Atributos esperados pelo repository
        self.driver = None
        self.wait = None

class FakeDocumentAction:
    pass

from automation.repositories.ordinaria_repository import OrdinariaRepository

repo = OrdinariaRepository(FakeLecomAction(), FakeDocumentAction())

numero_processo = '580.183'

resultado_elegibilidade = {
    'elegibilidade_final': 'indeferimento',
    'requisitos_nao_atendidos': [
        'Art. 65, inciso II da Lei nº 13.445/2017',
        'Art. 65, inciso III da Lei nº 13.445/2017',
        'Art. 65, inciso IV da Lei nº 13.445/2017',
    ],
    'motivos_indeferimento': [
        'Art. 65, inciso II da Lei nº 13.445/2017',
        'Art. 65, inciso III da Lei nº 13.445/2017',
        'Art. 65, inciso IV da Lei nº 13.445/2017',
    ],
    'requisito_i_capacidade_civil': {
        'atendido': True,
        'motivo': 'Possui 30 anos (≥ 18 anos)',
        'idade': 30,
        'avaliado': True
    },
    'requisito_ii_residencia_minima': {
        'atendido': False,
        'motivo': 'Tempo insuficiente: 1.50 anos < 4.00 anos',
        'tem_reducao': False,
        'prazo_requerido': 4,
        'tempo_comprovado': 1.5,
        'avaliado': True
    },
    'requisito_iii_comunicacao_portugues': {
        'atendido': False,
        'motivo': 'Não anexou item 13 - Comprovante de comunicação em português',
        'avaliado': True
    },
    'requisito_iv_antecedentes_criminais': {
        'atendido': False,
        'motivo': 'Antecedentes criminais do Brasil não anexado',
        'avaliado': True
    },
    'documentos_complementares': {
        'atendido': False,
        'documentos_validos': 0,
        'total_documentos': 4,
        'percentual_completude': 0.0,
        'documentos_faltantes': ['Não anexou item 3', 'Não anexou item 2'],
        'avaliado': True
    },
    'documentos_faltantes': ['Não anexou item 3', 'Não anexou item 2'],
    'dados_pessoais': {
        'nome': 'N/A',
        'nome_completo': 'N/A'
    },
    'data_inicial_processo': '15 de Abr de 2024',
    'parecer_pf': {
        'parecer_texto': '',
        'proposta_pf': 'Não encontrado',
        'excedeu_ausencia': False,
        'problema_portugues': False,
        'alertas': []
    },
}

resultado_decisao = {
    'status': 'INDEFERIMENTO',
    'tipo_decisao': 'INDEFERIMENTO',
    'despacho_completo': 'Processo indeferido por não atender aos requisitos',
    'motivos_indeferimento': resultado_elegibilidade['requisitos_nao_atendidos'],
    'fundamentos_legais': resultado_elegibilidade['requisitos_nao_atendidos'],
    'resumo_analise': 'Não atendeu 3 requisito(s)'
}

resumo_executivo = {'resumo': 'Resumo executivo de teste'}

res = repo.gerar_planilha_resultado_ordinaria(
    numero_processo,
    resultado_elegibilidade,
    resultado_decisao,
    resumo_executivo=resumo_executivo,
)

print('[OK] Caminho planilha:', res.get('caminho'))

# Mostrar a última linha registrada para conferência
caminho = res.get('caminho')
df = pd.read_excel(caminho)
print('\n[ULTIMA LINHA GERADA]')
print(df.tail(1).to_string(index=False))
