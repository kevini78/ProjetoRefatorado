"""
TERMOS DE VALIDAÇÃO MELHORADOS
Baseado na análise de OCR de 5.323 documentos VALIDADOS

Este módulo contém os termos otimizados para cada tipo de documento,
identificados através da análise estatística de documentos reais.
"""

# ============================================================================
# CRNM - Baseado em 1.068 documentos válidos (94.6% de sucesso)
# ============================================================================

TERMOS_CRNM = {
    'obrigatorios_alta_prioridade': [
        # Presentes em 100% dos documentos válidos
        'data',                  # 8.220x
        'validade',             # 3.458x  
        'documento',            # 3.160x
        'número',              # 2.813x
        'emissão',             # 2.104x
        'expedição',           # 2.050x
        'registro',            # 2.042x
        'nome',                # 1.981x
    ],
    
    'obrigatorios_media_prioridade': [
        # Presentes em 78-100% dos documentos válidos
        'orgão',               # 1.921x
        'nascimento',          # 1.745x
        'identificação',       # 1.735x
        'serviços',            # 1.481x
        'brasil',              # 1.474x
        'públicos',            # 1.428x
        'cartão',              # 1.357x
        'estado',              # 1.319x
        'república',           # 1.203x
        'residente',           # 1.177x
        'endereço',            # 1.167x
        'federativa',          # 1.134x
    ],
    
    'especificos': [
        # Termos específicos de CRNM
        'filiação',            # 990x
        'nacionalidade',       # 956x
        'acesso',              # 910x
        'classificação',       # 818x
        'migratório',          # 752x
        'rnm',
        'rne',
        'crnm',
        'carteira de registro nacional migratório',
        'registro nacional migratório',
        'cédula de identidade de estrangeiro',
        'cedula de identidade de estrangeiro',
        'naturalidade',
        'data de entrada',
        'permanente',
        'temporário',
        'provisório',
        'refugiado',
    ],
    
    'minimo_termos': 5,  # Deve conter pelo menos 5 termos obrigatórios
}

# ============================================================================
# CPF - Baseado em 1.165 documentos válidos (99.3% de sucesso)
# ============================================================================

TERMOS_CPF = {
    'obrigatorios_alta_prioridade': [
        # Presentes em quase 100% dos documentos válidos
        'cpf',                          # ~3.000x
        'federal',                      # ~2.500x
        'receita',                      # ~2.500x
        'brasil',                       # ~2.000x
        'cadastro',                     # ~1.800x
        'situação',                     # ~1.500x
        'nome',                         # ~1.200x
        'nascimento',                   # ~1.200x
    ],
    
    'obrigatorios_media_prioridade': [
        # Presentes em 80-100% dos documentos válidos
        'regular',                      # ~1.000x
        'ativa',                        # ~1.000x
        'cadastral',                    # ~1.000x
        'emissão',                      # ~900x
        'número',                       # ~900x
        'data',                         # ~800x
    ],
    
    'especificos': [
        # Termos específicos de CPF
        'cadastro de pessoas físicas',
        'cadastro de pessoa física',
        'situação cadastral',
        'receita federal do brasil',
        'receita federal',
        'república federativa do brasil',
        'ministério da economia',
        'governo federal',
        'ativo',
        'regular',
        'suspensa',
        'cancelada',
        'nula',
        'pendente',
        'titular',
    ],
    
    'minimo_termos': 3,  # Deve conter pelo menos 3 termos obrigatórios
}

# ============================================================================
# ANTECEDENTES BRASIL - Baseado em 1.170 documentos válidos (98.2% de sucesso)
# ============================================================================

TERMOS_ANTECEDENTES_BRASIL = {
    'obrigatorios_alta_prioridade': [
        # Presentes em 100% dos documentos válidos
        'certidão',            # 19.740x !!!
        'federal',             # 7.923x
        'justiça',             # 5.981x
        'tribunal',            # 5.244x
        'criminais',           # 5.148x
    ],
    
    'obrigatorios_media_prioridade': [
        # Presentes em 90-100% dos documentos válidos
        'resolução',           # 4.877x
        'região',              # 4.651x
        'processos',           # 4.629x
        'https',               # 4.402x (URL verificação)
        'regional',            # 4.094x
        'negativa',            # 3.611x !!!
        'endereço',            # 3.366x
        'interessado',         # 3.344x
        'autenticidade',       # 3.286x
        'emitida',             # 3.239x
    ],
    
    'negacao_condenacao': [
        # Termos que indicam ausência de condenação (PRIORIDADE)
        'não consta condenação',
        'nao consta condenacao',
        'não há condenação',
        'nao ha condenacao',
        'nada consta',
        'sem antecedentes criminais',
        'sem antecedentes',
        'não possui antecedentes',
        'nao possui antecedentes',
        'não constar',
        'nao constar',
        'não constam',
        'nao constam',
        'não consta ter',
        'não consta ter sido distribuído',
        'não consta em tramitação',
        'não constam distribuídas',
        'não constam inquéritos',
        'verifiquei não constar',
        'certidão negativa',
        'certidao negativa',
        'certidão judicial criminal negativa',
        'sem condenações',
        'folha sem anotações',
        'negativa a certidão',
        # DECLARAÇÃO de antecedentes (documento alternativo)
        'não respondi',
        'não responderei',
        'nem respondi',
        'nem responderei',
        'declaro sob as penas da lei',
        'sob as penas da lei',
        'limpo',
    ],
    
    'especificos': [
        # Órgãos emissores (presentes em 95.6%)
        'polícia federal',
        'policia federal',
        'justiça federal',
        'tribunal de justiça',
        'tribunal regional federal',
        'conselho da justiça federal',
        'secretaria de segurança',
        'secretaria de segurança pública',
        'seção judiciária',
        'comarca de',
        # Siglas de órgãos e sistemas
        'tjsp',
        'tjrj',
        'tjpe',
        'tjmg',
        'trf',
        'ssp',
        'pf',
        'cnj',
        'sinic',
        'epol',
        'pje',
        # Sistemas e validação
        'sistema nacional de informações criminais',
        'epol - sinic',
        'consulta',
        'verificação',
        'verificacao',
        'código de validação',
        'codigo de validacao',
        'autenticidade',
        # Certificação
        'certifico e dou fé',
        'certifico',
        'a polícia federal certifica',
        'certificamos',
        'o referido é verdade',
    ],
    
    'minimo_termos': 4,  # Deve conter pelo menos 4 termos obrigatórios
}

# ============================================================================
# COMUNICAÇÃO PORTUGUÊS - Baseado em 1.029 documentos válidos (88.2% de sucesso)
# ============================================================================

TERMOS_COMUNICACAO_PORTUGUES = {
    'obrigatorios_alta_prioridade': [
        # Presentes em 100% dos documentos válidos
        'curso',               # 5.319x !!!
        'portuguesa',          # 4.463x
        'língua',              # 4.264x
        'ensino',              # 3.847x
        'educação',            # 3.357x
        'portaria',            # 3.118x
        'certificado',         # 2.848x
    ],
    
    'obrigatorios_media_prioridade': [
        # Presentes em 70-100% dos documentos válidos
        'documento',           # 2.515x
        'extensão',            # 2.275x
        'faculdade',           # 1.920x
        'horas',               # 1.871x
        'prof',                # 1.866x
        'decreto',             # 1.849x
        'federal',             # 1.769x
        'universidade',        # 1.733x
        'nota',                # 1.715x
        'assinatura',          # 1.727x
        # Termos adicionais encontrados em documentos reais
        'ministério',          # Ministério da Educação
        'mec',                 # MEC
        'aprovado',            # Resultado: Aprovado
        'resultado',           # Resultado
        'avaliação',           # Avaliação
        'presencial',          # Avaliação presencial
        'modalidade',          # Modalidade a distância
        'distância',           # Modalidade a distância
        'declaração',          # DECLARAÇÃO
        'declaramos',          # Declaramos para os devidos fins
    ],
    
    'niveis_proficiencia': [
        # Níveis (presentes em 90.3% dos válidos)
        'básico',
        'basico',
        'intermediário',
        'intermediario',
        'avançado',
        'avancado',
        'proficiente',
        'fluente',
        'a1', 'a2', 'b1', 'b2', 'c1', 'c2',
        'celpe-bras',
        'celpe bras',
        'celpebras',
    ],
    
    'instituicoes': [
        # Instituições certificadoras (presentes em 72.4%)
        'universidade',
        'faculdade',
        'instituto',
        'escola',
        'centro de línguas',
        'centro de linguas',
        'celpe',
        'mec',
        'inep',
        'usp', 'ufrj', 'ufmg', 'unicamp', 'puc',
        'mackenzie', 'fmu', 'anhanguera',
    ],
    
    'aprovacao': [
        # Termos de aprovação/comunicação
        'aprovado',
        'apto',
        'habilitado',
        'qualificado',
        'conceito',
        'comunicação',
        'comunicacao',
        'comunicar',
        'entender',
        'falar',
        'escrever',
        'ler',
        'compreender',
        'expressar',
    ],
    
    'minimo_termos': 4,  # Deve conter pelo menos 4 termos obrigatórios
}

# ============================================================================
# ANTECEDENTES ORIGEM - Baseado em 891 documentos válidos (88.9% de sucesso)
# ============================================================================

TERMOS_ANTECEDENTES_ORIGEM = {
    'obrigatorios_alta_prioridade': [
        # Presentes em 100% dos documentos válidos
        'documento',           # 6.786x
        'ministério',          # 5.197x
        'república',           # 5.017x
        'tribunal',            # 4.395x
        'certificado',         # 3.300x
        'brasil',              # 2.928x
        'registro',            # 2.879x
        'antecedentes',        # 2.773x
    ],
    
    'obrigatorios_media_prioridade': [
        # Presentes em 80-100% dos documentos válidos
        'assinado',            # 2.496x
        'código',              # 2.181x
        'justiça',             # 1.940x
        'tradução',            # 1.990x
        'selo',                # 2.015x
        'data',                # 2.597x
    ],
    
    'traducao_legalizacao': [
        # Termos de tradução e legalização (60-70% dos válidos)
        'tradutor',            # 1.198x
        'juramentado',         # 597x
        'legalização',         # 611x
        'apostila',            # 599x
        'certidão',            # 1.375x
        'tradutor público juramentado',
        'tradutora pública juramentada',
        'traducao juramentada',
        'tradução juramentada',
        'apostila de haia',
        'apostille',
        'legalização consular',
        'legalizacao consular',
        'junta comercial',
        'intérprete',
        'intérprete comercial',
        'selo',
        'carimbo',
        'tradutora',
        'jucesp',
        'jucepar',
        'jucerja',
        'jucesc',
        'jucemg',
        'juceg',     # Goiás
        'matrícula',
        'matricula',
        # Padrões de certificação do tradutor
        'certifico',
        'certifico e dou fé',
        'dou fé',
        'achei conforme',
        'fielmente traduzi',
        'tradução fiel',
        'nada mais constava',
        'devolvo com esta tradução',
        'número da tradução',
    ],
    
    'negacao_condenacao': [
        # Termos em PORTUGUÊS (tradução juramentada obrigatória)
        'nada consta',
        'nao consta',
        'não consta',
        'nada registra',
        'não registra',
        'nao registra',
        'negativa',
        'sem antecedentes',
        'sem antecedentes criminais',
        'sem antecedentes penais',
        'não possui antecedentes',
        'nao possui antecedentes',
        'nunca foi condenado',
        'nunca foi condenada',
        'certidão negativa',
        'certidao negativa',
        'limpo',
        'limpa',
        'folha limpa',
        'ausência de antecedentes',
        'ausencia de antecedentes',
        # Haiti específico
        'não existe nenhuma condenação',
        'nao existe nenhuma condenacao',
        'certificado de antecedentes criminais',
        'atestado de antecedentes criminais',
        'em consequência',
        'vigem até',
    ],
    
    'paises_origem_comuns': [
        # Países de origem mais comuns
        'cuba',
        'venezuela',
        'haiti',
        'colômbia',
        'colombia',
        'república dominicana',
        'republica dominicana',
        'angola',
        'guiné',
        'guine',
        # Haiti específico
        'república do haiti',
        'republica do haiti',
        'porto príncipe',
        'porto principe',
        'tribunal de primeira instância',
        'tribunal de primeira instancia',
        'senegal',
        'síria',
        'siria',
        'líbano',
        'libano',
    ],
    
    'minimo_termos': 5,  # Deve conter pelo menos 5 termos obrigatórios
}

# ============================================================================
# REDUÇÃO DE PRAZO - Baseado em estimativa (85-95% de sucesso esperado)
# ============================================================================

TERMOS_REDUCAO_PRAZO = {
    'obrigatorios_alta_prioridade': [
        'redução',
        'prazo',
        'residência',
        'residencia',
        'brasil',
        'anos',
        'permanente',
    ],
    
    'obrigatorios_media_prioridade': [
        'naturalização',
        'naturalizacao',
        'decreto',
        'portaria',
        'lei',
        'tempo',
        'comprovante',
    ],
    
    'vinculos_familiares': [
        # Justificativas comuns para redução
        'cônjuge',
        'conjuge',
        'filho',
        'filha',
        'união estável',
        'uniao estavel',
        'casamento',
        'brasileiro',
        'brasileira',
        'certidão de casamento',
        'certidao de casamento',
        'certidão de nascimento',
        'certidao de nascimento',
    ],
    
    'especificos': [
        'lei de migração',
        'lei de migracao',
        'art. 65',
        'artigo 65',
        'parágrafo único',
        'paragrafo unico',
        'redução para 1 ano',
        'reducao para 1 ano',
        'redução para 2 anos',
        'reducao para 2 anos',
    ],
    
    'minimo_termos': 3,
}

# ============================================================================
# FUNÇÕES DE VALIDAÇÃO MELHORADAS
# ============================================================================

def verificar_padroes_regex(texto: str, padroes: list) -> dict:
    """
    Verifica se algum dos padrões regex está presente no texto.
    
    Returns:
        dict com 'encontrado' (bool) e 'matches' (list)
    """
    import re
    matches = []
    
    for padrao in padroes:
        encontrados = re.findall(padrao, texto, re.IGNORECASE)
        if encontrados:
            matches.extend(encontrados)
    
    return {
        'encontrado': len(matches) > 0,
        'matches': matches,
        'total': len(matches)
    }


def validar_documento_melhorado(tipo_documento: str, texto_ocr: str, minimo_confianca: int = 70) -> dict:
    """
    Valida documento usando termos otimizados baseados em análise de OCR real.
    
    Args:
        tipo_documento: Tipo do documento (CRNM, CPF, Antecedentes_Brasil, etc.)
        texto_ocr: Texto extraído via OCR
        minimo_confianca: Percentual mínimo para considerar válido (padrão: 70%)
        
    Returns:
        Dict com resultado da validação
    """
    if not texto_ocr or len(texto_ocr.strip()) < 50:
        return {
            'valido': False,
            'confianca': 0,
            'termos_encontrados': [],
            'termos_faltando': [],
            'motivo': 'Documento muito curto ou vazio'
        }
    
    texto_lower = texto_ocr.lower()
    
    # Mapear tipo para termos
    mapa_termos = {
        'CRNM': TERMOS_CRNM,
        'CPF': TERMOS_CPF,
        'Antecedentes_Brasil': TERMOS_ANTECEDENTES_BRASIL,
        'Comunicacao_Portugues': TERMOS_COMUNICACAO_PORTUGUES,
        'Antecedentes_Origem': TERMOS_ANTECEDENTES_ORIGEM,
        'Reducao_Prazo': TERMOS_REDUCAO_PRAZO,
    }
    
    if tipo_documento not in mapa_termos:
        return {
            'valido': False,
            'confianca': 0,
            'termos_encontrados': [],
            'termos_faltando': [],
            'motivo': f'Tipo de documento não suportado: {tipo_documento}'
        }
    
    termos = mapa_termos[tipo_documento]
    
    # Verificar termos de alta prioridade
    termos_alta = termos.get('obrigatorios_alta_prioridade', [])
    encontrados_alta = [t for t in termos_alta if t in texto_lower]
    
    # Verificar termos de média prioridade
    termos_media = termos.get('obrigatorios_media_prioridade', [])
    encontrados_media = [t for t in termos_media if t in texto_lower]
    
    # Verificar termos específicos
    termos_espec = termos.get('especificos', [])
    encontrados_espec = [t for t in termos_espec if t in texto_lower]
    
    # PRIORIDADE MÁXIMA: Verificar termos de negação para antecedentes
    tem_negacao = False
    if tipo_documento in ['Antecedentes_Brasil', 'Antecedentes_Origem']:
        termos_negacao = termos.get('negacao_condenacao', [])
        tem_negacao = any(termo in texto_lower for termo in termos_negacao)
    
    # Calcular pontuação
    pontos = 0
    pontos_maximos = 0
    
    # Alta prioridade: 10 pontos cada
    pontos += len(encontrados_alta) * 10
    pontos_maximos += len(termos_alta) * 10
    
    # Média prioridade: 5 pontos cada
    pontos += len(encontrados_media) * 5
    pontos_maximos += len(termos_media) * 5
    
    # Bônus por termos específicos
    bonus = min(len(encontrados_espec) * 2, 20)
    pontos += bonus
    
    # SUPER BÔNUS: Se tem negação de condenação, adicionar 30 pontos
    if tem_negacao:
        pontos += 30
    
    # Calcular confiança percentual
    confianca_base = int((pontos / pontos_maximos) * 100) if pontos_maximos > 0 else 0
    confianca = min(confianca_base, 100)
    
    # Verificar mínimo de termos obrigatórios
    minimo_termos = termos.get('minimo_termos', 3)
    total_encontrados = len(encontrados_alta) + len(encontrados_media)
    
    # REGRAS DE VALIDAÇÃO:
    # 1. Se tem negação E pelo menos 3 termos obrigatórios → SEMPRE VÁLIDO
    if tem_negacao and total_encontrados >= 3:
        valido = True
    # 2. Se atingiu o mínimo de termos obrigatórios → VÁLIDO
    elif total_encontrados >= minimo_termos:
        valido = True
    # 3. Senão, verificar confiança
    else:
        valido = confianca >= minimo_confianca and total_encontrados >= minimo_termos
    
    todos_encontrados = encontrados_alta + encontrados_media + encontrados_espec
    todos_termos = termos_alta + termos_media + termos_espec
    faltando = [t for t in todos_termos if t not in todos_encontrados]
    
    # Construir motivo
    motivo_extra = ""
    if tem_negacao:
        motivo_extra += " [SEM CONDENAÇÃO ✓]"
    
    return {
        'valido': valido,
        'confianca': confianca,
        'termos_encontrados': todos_encontrados,
        'termos_faltando': faltando[:10],
        'total_termos_encontrados': total_encontrados,
        'minimo_requerido': minimo_termos,
        'tem_negacao': tem_negacao,
        'motivo': f'Documento {"VÁLIDO" if valido else "INVÁLIDO"} - Confiança: {confianca}% ({total_encontrados}/{minimo_termos} termos obrigatórios){motivo_extra}'
    }
