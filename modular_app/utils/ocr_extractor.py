import os
import re
import json
import time
import base64
import requests
from typing import Dict, Any, Optional


def normalizar_nome_nome_sobrenome(nome: str) -> str:
    partes = (nome or "").strip().split()
    if len(partes) == 2:
        return f"{partes[1].upper()} {partes[0].upper()}"
    return (nome or "").upper()


def separar_filiacao(filiacao: str):
    if not filiacao or filiacao.strip() == "Não encontrado":
        return ['', '']
    filiacao = filiacao.strip()
    if '/' in filiacao:
        nomes = [n.strip() for n in filiacao.split('/') if n.strip()]
        if len(nomes) == 1:
            return [nomes[0], '']
        elif len(nomes) >= 2:
            return [nomes[0], nomes[1]]
        else:
            return ['', '']
    if '\n' in filiacao:
        linhas = [linha.strip() for linha in filiacao.split('\n') if linha.strip()]
        if len(linhas) >= 2:
            return [linhas[0], linhas[1]]
        elif len(linhas) == 1:
            return [linhas[0], '']
        else:
            return ['', '']
    palavras = [p for p in filiacao.split() if p and len(p) > 1]
    if len(palavras) == 0:
        return ['', '']
    elif len(palavras) == 1:
        return [filiacao, '']
    elif len(palavras) == 2:
        return [filiacao, '']
    elif len(palavras) == 3:
        return [' '.join(palavras[:2]), palavras[2]]
    elif len(palavras) == 4:
        return [' '.join(palavras[:2]), ' '.join(palavras[2:])]
    elif len(palavras) == 5:
        return [' '.join(palavras[:3]), ' '.join(palavras[3:])]
    elif len(palavras) == 6:
        return [' '.join(palavras[:3]), ' '.join(palavras[3:])]
    else:
        meio = len(palavras) // 2
        return [' '.join(palavras[:meio]), ' '.join(palavras[meio:])]


def extrair_campos_ocr_mistral(filepath: str, modo_texto_bruto: bool = False, max_retries: int = 3, max_paginas: Optional[int] = None) -> Dict[str, Any]:
    """Extrai campos com Mistral Vision, com pré-processamento e retry."""
    from mistralai import Mistral  # noqa: F401 (import side-effects tolerated)
    from dotenv import load_dotenv
    import mimetypes
    import tempfile
    try:
        import fitz  # PyMuPDF - não requer Poppler
    except ImportError:
        print("[ERRO] PyMuPDF (fitz) não instalado. Instale com: pip install PyMuPDF")
        return {"erro": "PyMuPDF não instalado"}
    from PIL import Image
    import cv2
    import numpy as np
    import io

    # Recarregar preprocessor se necessário
    import sys
    if 'preprocessing_ocr' in sys.modules:
        del sys.modules['preprocessing_ocr']
    from preprocessing_ocr import ImagePreprocessor

    arquivo_nome = os.path.basename(filepath) if filepath else "arquivo_indefinido"
    print(f"[OCR-DEBUG] Iniciando OCR para arquivo: {arquivo_nome}")
    print(f"[OCR-DEBUG] Caminho completo: {filepath}")
    print(f"[OCR-DEBUG] Modo texto bruto: {modo_texto_bruto}")

    import random
    cache_buster = random.randint(1000, 9999)
    print(f"[OCR-DEBUG] Cache buster: {cache_buster}")

    load_dotenv()
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        print(f"[OCR-DEBUG] ERRO: API key não encontrada para {arquivo_nome}")
        return {"erro": "Chave da API Mistral não configurada"}

    def image_to_base64_with_preprocessing(image: Image.Image) -> str:
        import io
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                temp_path = tmp.name
                image.save(temp_path)
            preprocessor = ImagePreprocessor()
            # Carregar imagem para preprocessamento
            img = cv2.imread(temp_path)
            img_processada, metadata = preprocessor.preprocess(img, apply_all=True)
            print(f"[PRÉ-PROC] Etapas: {', '.join(metadata.get('etapas_aplicadas', []))}")
            print(f"[PRÉ-PROC] Qualidade: {metadata.get('quality_score', 0):.1f}/100")
            img_pil = Image.fromarray(cv2.cvtColor(img_processada, cv2.COLOR_GRAY2RGB))
            try:
                os.remove(temp_path)
            except Exception:
                pass
            buf = io.BytesIO()
            img_pil.save(buf, format="JPEG")
            return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
        except Exception as e:
            print(f"[ERRO] Falha no pré-processamento: {e}, usando imagem original")
            buf = io.BytesIO()
            image.save(buf, format="JPEG")
            return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()

    try:
        if filepath.lower().endswith('.pdf'):
            # Usar PyMuPDF (fitz) em vez de pdf2image - não requer Poppler!
            print(f"[PDF] Abrindo PDF com PyMuPDF (sem Poppler)...")
            doc = fitz.open(filepath)
            total_paginas = len(doc)
            
            # Determinar quantas páginas processar
            if max_paginas is not None:
                paginas_processar = min(max_paginas, total_paginas)
            elif modo_texto_bruto and total_paginas > 4:
                paginas_processar = 4
            else:
                paginas_processar = min(8, total_paginas)
            
            print(f"[PDF] Total de páginas: {total_paginas}, processando: {paginas_processar}")
            
            imagens = []
            for num_pagina in range(paginas_processar):
                pagina = doc[num_pagina]
                # Renderizar página como imagem (3x resolução para melhor OCR)
                pix = pagina.get_pixmap(matrix=fitz.Matrix(3.0, 3.0))
                img_bytes = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_bytes))
                imagens.append(img)
            
            doc.close()
            
            image_urls = [image_to_base64_with_preprocessing(img) for img in imagens]
            print(f"[MISTRAL OCR] {len(image_urls)} páginas pré-processadas de {total_paginas} total (PyMuPDF)")
        else:
            img = Image.open(filepath)
            image_urls = [image_to_base64_with_preprocessing(img)]
            print(f"[MISTRAL OCR] 1 imagem pré-processada")
    except Exception as e:
        print(f"[ERRO] Erro no processamento: {e}")
        import traceback
        traceback.print_exc()
        return {}

    if modo_texto_bruto:
        prompt = (
            "Analise este documento e extraia TODO o texto visível de forma legível.\n\n"
            "IMPORTANTE:\n"
            "- Extraia APENAS o texto bruto do documento\n"
            "- Não tente identificar campos específicos\n"
            "- Não retorne JSON estruturado\n"
            "- Retorne apenas o texto extraído, linha por linha\n"
            "- Mantenha a formatação original quando possível\n"
            "- Corrija caracteres óbvios (ex: 0 por O, 1 por l, 5 por S)\n"
            "- Para jornais oficiais, foque nas seções relevantes (portarias, despachos)\n"
            "- Para documentos com muitas páginas, priorize o conteúdo principal\n\n"
            "Retorne apenas o texto extraído, sem formatação especial."
        )
    else:
        prompt = (
            f"Analise este documento de identidade brasileiro pré-processado e extraia os seguintes campos com máxima precisão:\n\n"
            "nome completo, CPF, filiação, data de nascimento, nacionalidade, validade, RNM, classificação, prazo de residência\n\n"
            "IMPORTANTE:\n"
            "- Use apenas os dados claramente legíveis DESTE DOCUMENTO ESPECÍFICO\n"
            "- Para CPF, use formato XXX.XXX.XXX-XX\n"
            "- Para datas, use formato DD/MM/AAAA\n"
            "- Para filiação, separe os nomes de mãe e pai com quebra de linha ou barra\n"
            "- Se algum campo não for encontrado ou não estiver legível, escreva \"Não encontrado\"\n"
            "- Corrija caracteres óbvios (ex: 0 por O, 1 por l, 5 por S)\n"
            f"- ANÁLISE ID: {cache_buster} para {arquivo_nome}\n\n"
            "Retorne como um objeto JSON com os campos extraídos."
        )

    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.environ.get('MISTRAL_API_KEY','')}",
        "Cache-Control": "no-cache",
        "X-Request-ID": f"{arquivo_nome}-{cache_buster}",
    }

    messages = [
        {"role": "system", "content": [{"type": "text", "text": "Extraia os campos do documento conforme solicitado pelo usuário e retorne um JSON. Use máxima precisão e corrija caracteres óbvios."}]},
        {"role": "user", "content": ([{"type": "text", "text": prompt}] + [{"type": "image_url", "image_url": u} for u in image_urls])},
    ]

    data = {"model": "pixtral-12b-2409", "messages": messages}
    if not modo_texto_bruto:
        data["response_format"] = {"type": "json_object"}

    for tentativa in range(1, max_retries + 1):
        try:
            print(f"DEBUG: Tentativa {tentativa}/{max_retries} para API Mistral")
            resp = requests.post(url, headers=headers, json=data, timeout=120)
            print(f"DEBUG: Status da resposta: {resp.status_code}")
            if resp.status_code == 200:
                conteudo = resp.json()['choices'][0]['message']['content']
                if modo_texto_bruto:
                    print(f"DEBUG FINAL: Texto extraído com sucesso - {len(conteudo)} caracteres")
                    return {"texto_bruto": conteudo}
                campos = json.loads(conteudo)
                if 'filiação' in campos:
                    campos['filiação'] = separar_filiacao(campos['filiação'])
                    if len(campos['filiação']) >= 2:
                        campos['pai'] = campos['filiação'][1].strip()
                        campos['mae'] = campos['filiação'][0].strip()
                elif 'filiacao' in campos:
                    campos['filiação'] = separar_filiacao(campos['filiacao'])
                    if len(campos['filiação']) >= 2:
                        campos['pai'] = campos['filiação'][1].strip()
                        campos['mae'] = campos['filiação'][0].strip()
                campos['nome'] = campos.get('nome_completo', campos.get('nome', ''))
                campos['data_nasc'] = campos.get('data_de_nascimento', campos.get('data_nasc', ''))
                if campos.get('nome'):
                    campos['nome'] = normalizar_nome_nome_sobrenome(campos['nome'])
                campos['_arquivo_origem'] = arquivo_nome
                campos['_timestamp_ocr'] = time.time()
                print(f"[OCR-DEBUG] FINAL: {len(campos)} campos extraídos com pré-processamento para {arquivo_nome}")
                return campos
            elif resp.status_code in [429, 500, 502, 503, 504]:
                if tentativa < max_retries:
                    wait_time = min(2 ** tentativa, 30)
                    print(f"DEBUG: Erro temporário {resp.status_code}. Aguardando {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    return {}
            else:
                print(f"DEBUG: Erro não recuperável {resp.status_code}")
                return {}
        except requests.exceptions.Timeout:
            if tentativa < max_retries:
                wait_time = min(2 ** tentativa, 30)
                print(f"DEBUG: Timeout. Aguardando {wait_time}s e repetindo...")
                time.sleep(wait_time)
                continue
            else:
                return {}
        except json.JSONDecodeError:
            if tentativa < max_retries:
                time.sleep(2 ** tentativa)
                continue
            else:
                return {}
        except Exception as e:
            print(f"DEBUG: Erro na extração OCR: {e}")
            if tentativa < max_retries:
                time.sleep(2 ** tentativa)
                continue
            else:
                return {}

    print(f"DEBUG: Todas as {max_retries} tentativas falharam")
    return {}
