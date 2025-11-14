"""
Utilitários para normalização de datas (baseado no código original)
"""

import re

# Mapeamento de meses
MESES = {
    'janeiro': '01', 'jan': '01', 'fevereiro': '02', 'fev': '02', 'março': '03', 'marco': '03', 'mar': '03',
    'abril': '04', 'abr': '04', 'maio': '05', 'mai': '05', 'junho': '06', 'jun': '06',
    'julho': '07', 'jul': '07', 'agosto': '08', 'ago': '08', 'setembro': '09', 'set': '09', 'outubro': '10', 'out': '10', 
    'novembro': '11', 'nov': '11', 'dezembro': '12', 'dez': '12'
}

def normalizar_data_para_ddmmaaaa(data_str):
    """
    Normaliza data para formato dd/mm/yyyy
    Função utilitária para normalizar datas por extenso para dd/mm/yyyy
    """
    # Se já está no formato dd/mm/yyyy, retorna igual
    if re.match(r'\d{2}/\d{2}/\d{4}$', data_str.strip()):
        return data_str.strip()
    # Tenta converter de "19 de dezembro de 1992" ou "15 de Abr de 2024" para "19/12/1992"
    m = re.match(r'(\d{1,2}) de ([a-zç]{3,}) de (\d{4})', data_str.strip(), re.IGNORECASE)
    if m:
        dia = m.group(1).zfill(2)
        mes_nome = m.group(2).lower()
        mes = MESES.get(mes_nome, '01')
        ano = m.group(3)
        resultado = f'{dia}/{mes}/{ano}'
        print(f"[DEBUG] Data normalizada: '{data_str}' -> '{resultado}'")
        return resultado
    print(f"[DEBUG] Data não normalizada: '{data_str}'")
    return data_str.strip()
