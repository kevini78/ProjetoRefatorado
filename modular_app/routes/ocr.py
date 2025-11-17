from flask import Blueprint, render_template, request, jsonify, current_app, send_file
from werkzeug.utils import secure_filename
from ..security.decorators import require_authentication, log_sensitive_operation
from ..tasks.job_service import get_job_service
from ..tasks.workers import worker_extracao_ocr
import os
import io
import json
import zipfile

ocr_bp = Blueprint("ocr", __name__)


@ocr_bp.get("/ocr")
@require_authentication
def ocr_redirect():
    # Reutiliza a mesma página do teste de pré-processamento
    return render_template('teste_preprocessing.html')


@ocr_bp.get("/extracao_ocr")
@require_authentication
def pagina_extracao_ocr():
    return render_template('extracao_ocr.html')


@ocr_bp.post("/api/extracao_ocr/iniciar")
@require_authentication
@log_sensitive_operation('EXTRACAO_OCR_INICIAR')
def api_extracao_ocr_iniciar():
    data = request.get_json(silent=True) or {}
    processos = data.get('processos') or []
    diretorio = (data.get('diretorio_saida') or 'ocr_extraidos_doccano').strip()
    if not isinstance(processos, list) or not processos:
        return jsonify({'success': False, 'error': 'Lista de processos inválida'}), 400
    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    os.makedirs(upload_folder, exist_ok=True)

    job_service = get_job_service(current_app)

    def _target(job_id, procs, base_dir, out_dir):
        worker_extracao_ocr(job_service, job_id, procs, base_dir, out_dir)

    job_id = job_service.enqueue(_target, processos, upload_folder, diretorio, meta={'type': 'extracao_ocr', 'total': len(processos)})
    return jsonify({'success': True, 'process_id': job_id})


@ocr_bp.get("/api/extracao_ocr/status/<process_id>")
@require_authentication
def api_extracao_ocr_status(process_id: str):
    job_service = get_job_service(current_app)
    st = job_service.status(process_id) or {}
    # Mapear campos esperados pela UI
    status_map = {
        'running': 'executando',
        'completed': 'concluido',
        'error': 'erro',
        'stopped': 'interrompido',
        'starting': 'iniciando',
    }
    base = {
        'status': status_map.get(st.get('status'), 'desconhecido'),
        'total': (st.get('results') or {}).get('total') or (st.get('meta') or {}).get('total', 0),
        'processados': (st.get('results') or {}).get('processados', 0),
        'erros': (st.get('results') or {}).get('erros', 0),
        'processo_atual': (st.get('results') or {}).get('processo_atual'),
        'logs': [{'tipo': l.get('type'), 'mensagem': l.get('message'), 'ts': l.get('timestamp')} for l in (st.get('logs') or [])][-50:],
        'resultado': st.get('results') or {},
    }
    return jsonify(base)


@ocr_bp.post("/api/extracao_ocr/parar/<process_id>")
@require_authentication
@log_sensitive_operation('EXTRACAO_OCR_PARAR')
def api_extracao_ocr_parar(process_id: str):
    job_service = get_job_service(current_app)
    job_service.stop(process_id)
    return jsonify({'success': True})


@ocr_bp.get("/api/extracao_ocr/download")
@require_authentication
def api_extracao_ocr_download():
    diretorio = (request.args.get('diretorio') or '').strip()
    if not diretorio:
        return jsonify({'success': False, 'error': 'diretorio não informado'}), 400
    # Não permitir separadores de caminho ou tentativa de subir diretórios
    if any(sep in diretorio for sep in ('/', '\\')) or '..' in diretorio:
        return jsonify({'success': False, 'error': 'diretório inválido'}), 400
    # Sanitiza o nome do diretório para evitar caracteres perigosos
    diretorio_safe = secure_filename(diretorio)
    if not diretorio_safe:
        return jsonify({'success': False, 'error': 'diretório inválido'}), 400
    base_dir = os.path.abspath(current_app.config.get('UPLOAD_FOLDER'))
    target_dir = os.path.abspath(os.path.join(base_dir, diretorio_safe))
    # Garante que o diretório alvo permanece dentro de UPLOAD_FOLDER (evita path traversal)
    if os.path.commonpath([base_dir, target_dir]) != base_dir:
        return jsonify({'success': False, 'error': 'diretório inválido'}), 400
    if not os.path.exists(target_dir):
        return jsonify({'success': False, 'error': 'diretório não encontrado'}), 404

    # Compactar em memória
    mem_io = io.BytesIO()
    with zipfile.ZipFile(mem_io, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(target_dir):
            for fn in files:
                full = os.path.join(root, fn)
                arc = os.path.relpath(full, start=target_dir)
                zf.write(full, arcname=arc)
    mem_io.seek(0)
    return send_file(mem_io, as_attachment=True, download_name=f'{os.path.basename(target_dir)}.zip')


@ocr_bp.get("/api/extracao_ocr/estatisticas")
@require_authentication
def api_extracao_ocr_estatisticas():
    diretorio = (request.args.get('diretorio') or '').strip()
    if not diretorio:
        return jsonify({'success': False, 'error': 'diretório não informado'}), 400
    # Não permitir separadores de caminho ou tentativa de subir diretórios
    if any(sep in diretorio for sep in ('/', '\\')) or '..' in diretorio:
        return jsonify({'success': False, 'error': 'diretório inválido'}), 400
    # Sanitiza o nome do diretório para evitar caracteres perigosos
    diretorio_safe = secure_filename(diretorio)
    if not diretorio_safe:
        return jsonify({'success': False, 'error': 'diretório inválido'}), 400
    base_dir = os.path.abspath(current_app.config.get('UPLOAD_FOLDER'))
    target_dir = os.path.abspath(os.path.join(base_dir, diretorio_safe))
    # Garante que o diretório alvo permanece dentro de UPLOAD_FOLDER (evita path traversal)
    if os.path.commonpath([base_dir, target_dir]) != base_dir:
        return jsonify({'success': False, 'error': 'diretório inválido'}), 400
    resumo_path = os.path.join(target_dir, 'resumo_extracao.json')
    if not os.path.exists(resumo_path):
        return jsonify({'success': False, 'error': 'Resumo não encontrado'}), 404
    try:
        with open(resumo_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify({'success': True, **data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@ocr_bp.get("/teste-preprocessing")
@require_authentication
def teste_preprocessing():
    """Página para teste de pré-processamento de OCR"""
    return render_template('teste_preprocessing.html')


@ocr_bp.post("/api/teste-preprocessing")
@require_authentication
@log_sensitive_operation('TESTE_PREPROCESSING_OCR')
def api_teste_preprocessing():
    """API para processar documento com pré-processamento e mascaramento"""
    import os
    import json
    import time
    import shutil
    import base64
    import tempfile
    import numpy as np
    import cv2

    try:
        # FORÇAR reload completo do módulo (remover do cache e reimportar)
        import sys
        if 'preprocessing_ocr' in sys.modules:
            del sys.modules['preprocessing_ocr']
            print("[DEBUG] Módulo preprocessing_ocr removido do cache")

        from preprocessing_ocr import ImagePreprocessor
        print("[DEBUG] Módulo preprocessing_ocr reimportado")

        # Testar se a função foi atualizada
        if hasattr(ImagePreprocessor, '_correct_orientation'):
            print("[DEBUG] ✓ Função _correct_orientation NOVA detectada")
        else:
            print("[DEBUG] ⚠ Usando versão antiga do módulo")
        from data_masking import DataMasker
        from PIL import Image

        # Verificar se arquivo foi enviado
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'Nenhum arquivo enviado'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'Nome de arquivo vazio'}), 400

        # Salvar arquivo temporário
        temp_dir = tempfile.mkdtemp()
        filepath = os.path.join(temp_dir, secure_filename(file.filename))
        file.save(filepath)

        start_time = time.time()

        try:
            # Converter PDF para imagem se necessário
            if filepath.lower().endswith('.pdf'):
                print(f"[INFO] Processando PDF com múltiplas páginas...")
                from pdf2image import convert_from_path
                imagens = convert_from_path(filepath, poppler_path=r'C:\\Users\\kevin.iqbal\\Desktop\\poppler\\Release-24.08.0-0\\poppler-24.08.0\\Library\\bin')
                print(f"[INFO] {len(imagens)} página(s) detectada(s)")

                # Para visualização, usar apenas a primeira página
                pil_img_preview = imagens[0]
                img_path_preview = os.path.join(temp_dir, 'temp_image_page1.jpg')
                pil_img_preview.save(img_path_preview, 'JPEG')

                # Processar TODAS as páginas
                processed_pages = []
                all_pages_paths = []

                for idx, pil_img in enumerate(imagens, 1):
                    print(f"[INFO] Processando página {idx}/{len(imagens)}...")

                    # Salvar página temporária
                    page_path = os.path.join(temp_dir, f'page_{idx}.jpg')
                    pil_img.save(page_path, 'JPEG')
                    all_pages_paths.append(page_path)

                    # Converter para OpenCV
                    img_array = np.array(pil_img)
                    if len(img_array.shape) == 3:
                        img_cv = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                    else:
                        img_cv = img_array

                    # Aplicar pré-processamento
                    preprocessor = ImagePreprocessor()
                    preset_mode = request.form.get('preset_mode', 'mistral')

                    if preset_mode == 'none':
                        if len(img_cv.shape) == 3:
                            processed_img = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
                        else:
                            processed_img = img_cv
                        metadata = {
                            "etapas_aplicadas": ["none - sem preprocessamento"],
                            "pagina": idx
                        }
                    elif preset_mode == 'mistral':
                        # Carregar imagem para preprocessamento
                        img_page = cv2.imread(page_path)
                        processed_img, metadata = preprocessor.preprocess(img_page, apply_all=True)
                        metadata["pagina"] = idx
                    else:
                        options = {
                            'apply_all': False,
                            'apply_clahe': request.form.get('apply_clahe') == 'true',
                            'apply_denoise': request.form.get('apply_denoise') == 'true',
                            'apply_deskew': request.form.get('apply_deskew') == 'true',
                            'apply_autocrop': request.form.get('apply_autocrop') == 'true',
                            'apply_binarization': request.form.get('apply_binarization') == 'true',
                            'apply_sharpen': request.form.get('apply_sharpen') == 'true',
                        }

                        # Correção explícita de orientação ANTES do pipeline
                        orientation_angle_applied = None
                        if options.get('apply_deskew'):
                            try:
                                from preprocessing_ocr import ImagePreprocessor as _IP
                                _tmp = _IP()
                                # Converter para grayscale se necessário
                                img_gray = img_cv if len(img_cv.shape) == 2 else cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
                                angle_detect = _tmp._detect_orientation(img_gray)

                                if angle_detect and angle_detect % 360 != 0:
                                    print(f"[ORIENT] Rotacionando imagem em {angle_detect}°")
                                    if angle_detect == 90:
                                        img_cv = cv2.rotate(img_cv, cv2.ROTATE_90_CLOCKWISE)
                                    elif angle_detect == 180:
                                        img_cv = cv2.rotate(img_cv, cv2.ROTATE_180)
                                    elif angle_detect == 270:
                                        img_cv = cv2.rotate(img_cv, cv2.ROTATE_90_COUNTERCLOCKWISE)
                                    orientation_angle_applied = angle_detect
                                    print(f"[ORIENT] ✓ Correção de orientação aplicada: {angle_detect}°")
                                else:
                                    print(f"[ORIENT] Documento já na orientação correta (0°)")
                            except Exception as _e:
                                print(f"[ORIENT] Falha ao corrigir orientação: {_e}")
                                import traceback
                                traceback.print_exc()

                            # Desativar deskew no pipeline (evitar rotação fina)
                            options['apply_deskew'] = False

                        processed_img, metadata = preprocessor.preprocess(img_cv, **options)
                        if orientation_angle_applied is not None:
                            metadata = metadata or {"etapas_aplicadas": []}
                            etapas = metadata.get("etapas_aplicadas", [])
                            etapas.insert(0, f"orientation_fix({orientation_angle_applied}°)")
                            metadata["etapas_aplicadas"] = etapas
                        metadata["pagina"] = idx

                    # Salvar página processada
                    processed_page_path = os.path.join(temp_dir, f'processed_page_{idx}.jpg')
                    cv2.imwrite(processed_page_path, processed_img)
                    processed_pages.append(processed_page_path)

                # Para visualização, usar primeira página
                filepath = img_path_preview
                processed_path = processed_pages[0]

                # Combinar metadados
                metadata = {
                    "etapas_aplicadas": metadata.get("etapas_aplicadas", []),
                    "total_paginas": len(imagens),
                    "original_shape": None,
                    "final_shape": None
                }

            else:
                # Imagem única
                pil_img = Image.open(filepath)

                # Converter PIL Image para numpy array (OpenCV)
                img_array = np.array(pil_img)
                if len(img_array.shape) == 3:
                    img_cv = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                else:
                    img_cv = img_array

                # Aplicar pré-processamento
                preprocessor = ImagePreprocessor()
                preset_mode = request.form.get('preset_mode', 'mistral')

                if preset_mode == 'none':
                    if len(img_cv.shape) == 3:
                        processed_img = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
                    else:
                        processed_img = img_cv
                    metadata = {
                        "etapas_aplicadas": ["none - sem preprocessamento"],
                        "original_shape": img_cv.shape,
                        "final_shape": processed_img.shape,
                        "total_paginas": 1
                    }
                elif preset_mode == 'mistral':
                    # Carregar imagem para preprocessamento
                    img_file = cv2.imread(filepath)
                    processed_img, metadata = preprocessor.preprocess(img_file, apply_all=True)
                    metadata["total_paginas"] = 1
                else:
                    options = {
                        'apply_all': False,
                        'apply_clahe': request.form.get('apply_clahe') == 'true',
                        'apply_denoise': request.form.get('apply_denoise') == 'true',
                        'apply_deskew': request.form.get('apply_deskew') == 'true',
                        'apply_autocrop': request.form.get('apply_autocrop') == 'true',
                        'apply_binarization': request.form.get('apply_binarization') == 'true',
                        'apply_sharpen': request.form.get('apply_sharpen') == 'true',
                    }

                    # Correção explícita de orientação ANTES do pipeline
                    orientation_angle_applied = None
                    if options.get('apply_deskew'):
                        try:
                            from preprocessing_ocr import ImagePreprocessor as _IP
                            _tmp = _IP()
                            # Converter para grayscale se necessário
                            img_gray = img_cv if len(img_cv.shape) == 2 else cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
                            angle_detect = _tmp._detect_orientation(img_gray)

                            if angle_detect and angle_detect % 360 != 0:
                                print(f"[ORIENT] Rotacionando imagem em {angle_detect}°")
                                if angle_detect == 90:
                                    img_cv = cv2.rotate(img_cv, cv2.ROTATE_90_CLOCKWISE)
                                elif angle_detect == 180:
                                    img_cv = cv2.rotate(img_cv, cv2.ROTATE_180)
                                elif angle_detect == 270:
                                    img_cv = cv2.rotate(img_cv, cv2.ROTATE_90_COUNTERCLOCKWISE)
                                orientation_angle_applied = angle_detect
                                print(f"[ORIENT] ✓ Correção de orientação aplicada: {angle_detect}°")
                            else:
                                print(f"[ORIENT] Documento já na orientação correta (0°)")
                        except Exception as _e:
                            print(f"[ORIENT] Falha ao corrigir orientação: {_e}")
                            import traceback
                            traceback.print_exc()

                        # Desativar deskew no pipeline (evitar rotação fina)
                        options['apply_deskew'] = False

                    processed_img, metadata = preprocessor.preprocess(img_cv, **options)
                    if orientation_angle_applied is not None:
                        metadata = metadata or {"etapas_aplicadas": []}
                        etapas = metadata.get("etapas_aplicadas", [])
                        etapas.insert(0, f"orientation_fix({orientation_angle_applied}°)")
                        metadata["etapas_aplicadas"] = etapas
                    metadata["total_paginas"] = 1

                # Salvar imagem processada
                processed_path = os.path.join(temp_dir, 'processed.jpg')
                cv2.imwrite(processed_path, processed_img)
                processed_pages = [processed_path]
                all_pages_paths = [filepath]

            # Converter para base64 (imagem original - primeira página para visualização)
            with open(filepath, 'rb') as f:
                original_b64 = base64.b64encode(f.read()).decode()
                original_data_uri = f"data:image/jpeg;base64,{original_b64}"

            # Converter imagem processada para base64 (primeira página para visualização)
            with open(processed_path, 'rb') as f:
                processed_b64 = base64.b64encode(f.read()).decode()
                processed_data_uri = f"data:image/jpeg;base64,{processed_b64}"

            # Executar OCR com Mistral em TODAS as páginas processadas
            print(f"[INFO] Executando OCR Mistral em {len(processed_pages)} página(s)...")

            from modular_app.utils.ocr_extractor import extrair_campos_ocr_mistral

            if len(processed_pages) > 1:
                # Múltiplas páginas - processar todas
                textos_por_pagina = []
                for idx, page_path in enumerate(processed_pages, 1):
                    print(f"[OCR] Processando página {idx}/{len(processed_pages)}...")
                    ocr_result = extrair_campos_ocr_mistral(page_path, modo_texto_bruto=True)
                    texto_pagina = ocr_result.get('texto_bruto', '') if ocr_result else ''
                    textos_por_pagina.append(f"\n\n{'='*60}\n📄 PÁGINA {idx}\n{'='*60}\n\n{texto_pagina}")

                # Combinar todos os textos
                texto_bruto = "\n".join(textos_por_pagina)
            else:
                # Página única
                ocr_result = extrair_campos_ocr_mistral(processed_path, modo_texto_bruto=True)
                texto_bruto = ocr_result.get('texto_bruto', '') if ocr_result else ''

            print(f"[INFO] OCR concluído. Total de caracteres extraídos: {len(texto_bruto)}")

            # Aplicar mascaramento de dados sensíveis
            masker = DataMasker()

            # Obter tipos de mascaramento selecionados
            try:
                mask_types_str = request.form.get('mask_types', '[]')
                mask_types = json.loads(mask_types_str)
            except:
                mask_types = ['cpf', 'rg', 'rnm', 'telefone', 'email']

            texto_mascarado, masked_data = masker.mask_text(texto_bruto, mask_types)

            # Adicionar destaque HTML aos dados mascarados
            texto_com_destaque = masker.highlight_masked_data(texto_mascarado, mask_types)

            # Calcular tempo de processamento
            processing_time = round(time.time() - start_time, 2)

            # Preparar resposta
            response = {
                'success': True,
                'original_image': original_data_uri,
                'processed_image': processed_data_uri,
                'texto_original': texto_bruto,
                'texto_mascarado': texto_com_destaque,
                'metadata': metadata,
                'masked_stats': {
                    'total_masked': sum(len(v) for v in masked_data.values()),
                    'by_type': {k: len(v) for k, v in masked_data.items()}
                },
                'processing_time': processing_time
            }

            return jsonify(response)

        except Exception as e:
            print(f"[ERRO] Erro no processamento: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

        finally:
            # Limpar arquivos temporários
            try:
                shutil.rmtree(temp_dir)
            except:
                pass

    except Exception as e:
        print(f"[ERRO] Erro geral na API: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
