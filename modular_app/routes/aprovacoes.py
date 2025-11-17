from flask import Blueprint, request, jsonify, current_app
import os
import uuid
from datetime import datetime

from ..security.decorators import api_login_required, log_sensitive_operation
from ..tasks.job_service import get_job_service
from ..tasks.workers import worker_aprovacao_lote, worker_aprovacao_parecer

aprovacoes_bp = Blueprint("aprovacoes", __name__)


# ------------------------
# Aprovação em lote (API)
# ------------------------

@aprovacoes_bp.post("/api/aprovacao_lote/iniciar")
@api_login_required
@log_sensitive_operation("APROVACAO_LOTE_INICIAR")
def api_aprovacao_lote_iniciar():
    try:
        data = request.get_json(silent=True) or {}
        max_iteracoes = int(data.get('max_iteracoes', 10))
        modo_execucao = data.get('modo_execucao', 'continuo')
        tempo_espera_minutos = int(data.get('tempo_espera_minutos', 10))

        job_service = get_job_service(current_app)

        def _target(job_id, max_iter, mode, wait_min):
            worker_aprovacao_lote(job_service, job_id, max_iter, mode, wait_min)

        job_id = job_service.enqueue(_target, max_iteracoes, modo_execucao, tempo_espera_minutos,
                                     meta={'type': 'aprovacao_lote', 'max_iteracoes': max_iteracoes,
                                           'modo_execucao': modo_execucao, 'tempo_espera_minutos': tempo_espera_minutos})
        return jsonify({'success': True, 'process_id': job_id, 'message': 'Processo iniciado com sucesso'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@aprovacoes_bp.get("/api/aprovacao_lote/status/<process_id>")
@api_login_required
def api_aprovacao_lote_status(process_id: str):
    try:
        job_service = get_job_service(current_app)
        data = job_service.status(process_id) or {}
        if not data:
            return jsonify({'error': 'Processo não encontrado'}), 404
        data['process_id'] = process_id
        if 'logs' in data and isinstance(data['logs'], list):
            data['logs'] = data['logs'][-50:]
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@aprovacoes_bp.post("/api/aprovacao_lote/parar/<process_id>")
@api_login_required
@log_sensitive_operation("APROVACAO_LOTE_PARAR")
def api_aprovacao_lote_parar(process_id: str):
    try:
        job_service = get_job_service(current_app)
        job_service.stop(process_id)
        job_service.update(process_id, status='stopping', message='Parando...', detail='Interrompendo execução')
        return jsonify({'success': True, 'message': 'Comando de parada enviado'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# -----------------------------------------
# Aprovação de Parecer do Analista (API)
# -----------------------------------------

@aprovacoes_bp.post("/api/aprovacao_parecer_analista/iniciar")
@api_login_required
@log_sensitive_operation("APROVACAO_PARECER_INICIAR")
def api_aprovacao_parecer_iniciar():
    try:
        process_id = str(uuid.uuid4())
        # aceitar alias do modo e também JSON
        data_json = request.get_json(silent=True) or {}
        modo_selecao = (
            request.form.get('modo_selecao')
            or request.form.get('modo')
            or request.form.get('execution_mode')
            or data_json.get('modo_selecao')
            or data_json.get('modo')
            or data_json.get('execution_mode')
        )
        arquivo_upload = request.files.get('planilha') or request.files.get('file')
        caminho_planilha = None

        # Se veio arquivo, força modo planilha; senão, default versao
        if not modo_selecao and arquivo_upload:
            modo_selecao = 'planilha'
        if not modo_selecao:
            modo_selecao = 'versao'

        if modo_selecao == 'planilha':
            if arquivo_upload and arquivo_upload.filename:
                # upload novo
                if not arquivo_upload.filename.lower().endswith(('.xlsx', '.xls', '.csv')):
                    return jsonify({'success': False, 'error': 'Arquivo deve ser .xlsx, .xls ou .csv'}), 400
                upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'temp')
                os.makedirs(upload_dir, exist_ok=True)
                filename = f"{process_id}_{arquivo_upload.filename}"
                caminho_planilha = os.path.join(upload_dir, filename)
                arquivo_upload.save(caminho_planilha)
            else:
                # Sem upload no request: usar arquivo existente em uploads
                upload_root = current_app.config['UPLOAD_FOLDER']
                os.makedirs(upload_root, exist_ok=True)
                nome_arquivo = (
                    request.form.get('nome_arquivo')
                    or request.form.get('filename')
                    or data_json.get('nome_arquivo')
                    or data_json.get('filename')
                )
                allowed_ext = ('.xlsx', '.xls', '.csv')
                if nome_arquivo:
                    candidato = os.path.join(upload_root, nome_arquivo)
                    if not os.path.exists(candidato):
                        return jsonify({'success': False, 'error': f'Arquivo não encontrado: {nome_arquivo}'}), 400
                    if not candidato.lower().endswith(allowed_ext):
                        return jsonify({'success': False, 'error': 'Arquivo deve ser .xlsx, .xls ou .csv'}), 400
                    caminho_planilha = candidato
                else:
                    # Pega o mais recente por mtime
                    arquivos = [
                        os.path.join(upload_root, f) for f in os.listdir(upload_root)
                        if f.lower().endswith(allowed_ext)
                    ]
                    if not arquivos:
                        return jsonify({'success': False, 'error': 'Nenhuma planilha encontrada em uploads/'}), 400
                    caminho_planilha = max(arquivos, key=os.path.getmtime)

        job_service = get_job_service(current_app)

        def _target(job_id, modo, caminho):
            worker_aprovacao_parecer(job_service, job_id, modo, caminho)

        job_id = job_service.enqueue(
            _target,
            modo_selecao,
            caminho_planilha,
            meta={
                'type': 'aprovacao_parecer',
                'modo': modo_selecao,
                'arquivo': os.path.basename(caminho_planilha) if caminho_planilha else None
            }
        )
        return jsonify({'success': True, 'process_id': job_id, 'message': f'Processo iniciado com sucesso no modo {modo_selecao}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@aprovacoes_bp.get("/api/aprovacao_parecer_analista/status/<process_id>")
@api_login_required
def api_aprovacao_parecer_status(process_id: str):
    try:
        job_service = get_job_service(current_app)
        data = job_service.status(process_id) or {}
        if not data:
            return jsonify({'error': 'Processo não encontrado'}), 404
        data['process_id'] = process_id
        if 'logs' in data and isinstance(data['logs'], list):
            data['logs'] = data['logs'][-50:]
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@aprovacoes_bp.post("/api/aprovacao_parecer_analista/parar/<process_id>")
@api_login_required
@log_sensitive_operation("APROVACAO_PARECER_PARAR")
def api_aprovacao_parecer_parar(process_id: str):
    try:
        job_service = get_job_service(current_app)
        job_service.stop(process_id)
        job_service.update(process_id, status='stopping', message='Parando...', detail='Gerando planilha...')
        return jsonify({'success': True, 'message': 'Parando execução e gerando planilha...'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
