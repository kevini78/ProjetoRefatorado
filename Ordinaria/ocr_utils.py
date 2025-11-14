import re
import unicodedata

def extrair_nome_completo(texto):
    linhas = texto.splitlines()
    nome, sobrenome = '', ''
    for i, linha in enumerate(linhas):
        if re.search(r'NOME:', linha, re.IGNORECASE):
            nome = linha.split(':', 1)[-1].strip().upper()
        if re.search(r'SOBRENOME:', linha, re.IGNORECASE):
            sobrenome = linha.split(':', 1)[-1].strip().upper()
    if nome and sobrenome:
        return f'{nome} {sobrenome}'.strip(), nome, sobrenome
    # fallback antigo
    nome_idx, sobrenome_idx = -1, -1
    for i, linha in enumerate(linhas):
        if re.search(r'NOME', linha, re.IGNORECASE) and nome_idx == -1:
            nome_idx = i
        if re.search(r'SOBRENOME', linha, re.IGNORECASE) and sobrenome_idx == -1:
            sobrenome_idx = i
    if nome_idx != -1 and sobrenome_idx != -1:
        nome_val = linhas[nome_idx+1].strip().upper() if nome_idx+1 < len(linhas) else ''
        sobrenome_val = linhas[sobrenome_idx+1].strip().upper() if sobrenome_idx+1 < len(linhas) else ''
        if nome_val and sobrenome_val:
            return f'{nome_val} {sobrenome_val}'.strip(), nome_val, sobrenome_val
    return (nome or sobrenome).strip(), nome, sobrenome

def extrair_filiação_limpa(texto):
    linhas = texto.splitlines()
    nomes = []
    for i, linha in enumerate(linhas):
        if re.search(r'FILIA', linha, re.IGNORECASE):
            j = 1
            while len(nomes) < 2 and i+j < len(linhas):
                nome = linhas[i+j].strip()
                # Ignora linhas que são só o rótulo ou muito curtas
                if nome and len(nome) > 3 and not re.search(r'FILIA', nome, re.IGNORECASE):
                    nome = re.sub(r'\b(O|ma|de|do|da|e)\b', '', nome).strip()
                    nomes.append(nome)
                j += 1
            break
    # Se só houver um nome, considera como mãe
    if len(nomes) == 1:
        return ['', nomes[0]]
    return nomes

def extrair_pai_mae_da_filiacao_lista(nomes):
    pai = nomes[0] if len(nomes) > 0 else ''
    mae = nomes[1] if len(nomes) > 1 else ''
    return pai, mae

def extrair_nascimento_ajustado(texto):
    # Aceita datas como 02/07/1998, 2/7/1998, 1º de julho de 2025, etc.
    linhas = texto.splitlines()
    # 1. Busca padrão dd/mm/aaaa ou d/m/aaaa
    for i, linha in enumerate(linhas):
        if re.search(r'NASC', linha, re.IGNORECASE):
            match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', linha)
            if match:
                return match.group(1)
            if i+1 < len(linhas):
                prox = linhas[i+1]
                match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', prox)
                if match:
                    return match.group(1)
    # 2. Busca por extenso: "1º de julho de 2025"
    match = re.search(r'(\d{1,2}|1º) de [a-zç]+ de \d{4}', texto, re.IGNORECASE)
    if match:
        return match.group(0)
    # 3. Fallback: qualquer data
    match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', texto)
    if match:
        return match.group(1)
    return ''

def extrair_rnm_robusto(texto):
    # Procura linha que contenha apenas 'RNM' e pega a próxima linha
    linhas = texto.splitlines()
    for i, linha in enumerate(linhas):
        if re.match(r'^RNM\s*$', linha.strip(), re.IGNORECASE):
            if i+1 < len(linhas):
                rnm = linhas[i+1].strip().replace(' ', '').replace('-', '').upper()
                if rnm:
                    return rnm
    # Procura padrão RNM: XXXXXXXX-X
    match = re.search(r'RNM[:\s-]*([A-Z0-9-]+)', texto, re.IGNORECASE)
    if match:
        return match.group(1).strip().replace(' ', '').upper()
    # Busca padrão F209738-R, F209738R, etc.
    match = re.search(r'([A-Z][0-9]{6,}-?[A-Z0-9]?)', texto)
    if match:
        return match.group(1).strip().replace(' ', '').upper()
    return ''

def comparar_campos(campos_ocr, campos_esperados):
    # Compara nome, pai, mae, rnm, data_nasc
    campos_interesse = ['nome', 'pai', 'mae', 'rnm', 'data_nasc']
    resultado = {}
    divergencias = []
    # Para filiação, extrai lista de nomes do OCR
    nomes_filiacao_ocr = []
    if 'filiação' in campos_ocr:
        if isinstance(campos_ocr['filiação'], list):
            nomes_filiacao_ocr = [n.strip().lower() for n in campos_ocr['filiação'] if n and isinstance(n, str)]
        elif isinstance(campos_ocr['filiação'], str):
            nomes_filiacao_ocr = [n.strip().lower() for n in campos_ocr['filiação'].split('/') if n.strip()]
    for campo in campos_interesse:
        valor_esperado = campos_esperados.get(campo, '').strip().lower()
        valor_ocr = campos_ocr.get(campo, '')
        valor_ocr_lower = valor_ocr.strip().lower() if isinstance(valor_ocr, str) else ''
        ok = False
        ocr_exibido = valor_ocr
        if campo in ['pai', 'mae']:
            # Se houver nomes na filiação extraída, compara com ambos
            if nomes_filiacao_ocr and valor_esperado:
                ok = any(valor_esperado in nome for nome in nomes_filiacao_ocr)
                idx = 0 if campo == 'pai' else 1
                if len(nomes_filiacao_ocr) > idx:
                    ocr_exibido = nomes_filiacao_ocr[idx].upper()
            else:
                ok = valor_esperado in valor_ocr_lower if valor_esperado else False
        else:
            ok = valor_esperado in valor_ocr_lower if valor_esperado else False
        resultado[campo] = {
            'esperado': campos_esperados.get(campo, ''),
            'ocr': ocr_exibido,
            'ok': ok
        }
        if valor_esperado and not ok:
            divergencias.append(campo)
    all_ok = all(v['ok'] for v in resultado.values() if v['esperado'])
    return {
        'resultado': 'DADOS CONFEREM!' if all_ok else 'DIVERGÊNCIA ENCONTRADA!',
        'campos': resultado,
        'divergencias': divergencias
    }

def extrair_cpf(texto):
    match = re.search(r'CPF[:\s-]*([0-9\.\-]{11,})', texto)
    if match:
        return match.group(1).strip()
    match = re.search(r'(\d{3}\.?\d{3}\.?\d{3}-?\d{2})', texto)
    if match:
        return match.group(1).strip()
    return ''

def extrair_classificacao(texto):
    match = re.search(r'CLASSIFICA[ÇC][AÃ]O[:\s-]*([A-Z ]+)', texto, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ''

def extrair_prazo_residencia(texto):
    match = re.search(r'PRAZO DE RESID[ÊE]NCIA[:\s-]*([A-Za-z ]+)', texto, re.IGNORECASE)
    if match:
        return match.group(1).strip().upper()
    return ''

def extrair_nacionalidade_validade_linha(texto):
    linhas = texto.splitlines()
    for i, linha in enumerate(linhas):
        if re.search(r'NACIONAL.*VALIDADE', linha, re.IGNORECASE):
            if i+1 < len(linhas):
                prox = linhas[i+1]
                match = re.search(r'([A-ZÁ-Úa-zá-ú]+)[^0-9]*(\d{2}/\d{2}/\d{4})', prox)
                if match:
                    return match.group(1), match.group(2)
    return '', ''

def extrair_data_nasc_texto(texto, nome):
    meses = {
        'janeiro': '01', 'fevereiro': '02', 'março': '03', 'marco': '03', 'abril': '04', 'maio': '05', 'junho': '06',
        'julho': '07', 'agosto': '08', 'setembro': '09', 'outubro': '10', 'novembro': '11', 'dezembro': '12'
    }
    # Normaliza texto e nome para facilitar regex
    texto_norm = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII').lower()
    nome_norm = unicodedata.normalize('NFKD', nome).encode('ASCII', 'ignore').decode('ASCII').lower()
    # Busca o bloco da pessoa pelo nome (linha que começa com o nome)
    padrao_bloco = re.compile(rf'({re.escape(nome_norm)}.*?)(?:;|\n|$)', re.IGNORECASE)
    match_bloco = padrao_bloco.search(texto_norm)
    bloco = ''
    if match_bloco:
        bloco = match_bloco.group(1)
    else:
        bloco = texto_norm
    # Busca qualquer 'nascid... em ...' no bloco
    padrao_data = re.compile(r'nascid[oa]?\(?a?\)? em (\d{1,2}) de ([a-z]+) de (\d{4})', re.IGNORECASE)
    match_data = padrao_data.search(bloco)
    if not match_data:
        # Se não achou no bloco, busca no texto inteiro
        match_data = padrao_data.search(texto_norm)
    if match_data:
        dia = match_data.group(1).zfill(2)
        mes = meses.get(match_data.group(2).lower(), '01')
        ano = match_data.group(3)
        return f'{dia}/{mes}/{ano}'
    return '' 