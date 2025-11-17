from flask import Blueprint, request, jsonify, current_app
import os
from werkzeug.utils import secure_filename
from datetime import datetime

from ..security.decorators import api_login_required, log_sensitive_operation
from ..tasks.job_service import get_job_service
from ..tasks.workers import worker_aprovacao_recurso, worker_defere_indefere

api_uploads_bp = Blueprint("api_uploads", __name__)


@api_uploads_bp.post("/upload_aprovacao_recurso")
@api_login_required
@log_sensitive_operation("UPLOAD_APROVACAO_RECURSO")
def upload_aprovacao_recurso():
    try:
        file = request.files.get('file')
        column_name = request.form.get('columnName', 'codigo')
        if not file or not file.filename:
            return jsonify({'success': False, 'message': 'Nenhum arquivo enviado'}), 400

        allowed = {'xlsx', 'csv', 'xls'}
        ext = (file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else '')
        if ext not in allowed:
            return jsonify({'success': False, 'message': 'Formato de arquivo não permitido'}), 400

        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secure_filename(file.filename)}"
        upload_folder = current_app.config.get('UPLOAD_FOLDER')
        os.makedirs(upload_folder, exist_ok=True)
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)

        # Enfileirar com JobService chamando o novo worker
        job_service = get_job_service(current_app)

        def _target(job_id, path, col):
            worker_aprovacao_recurso(job_service, job_id, path, col)

        job_id = job_service.enqueue(_target, filepath, column_name, meta={'type': 'aprovacao_recurso', 'file': filename})
        return jsonify({'success': True, 'message': 'Processamento iniciado', 'process_id': job_id})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro no servidor: {str(e)}'}), 500


@api_uploads_bp.get("/api/aprovacao_recurso/status/<process_id>")
@api_login_required
def api_aprovacao_recurso_status(process_id: str):
    try:
        job_service = get_job_service(current_app)
        data = job_service.status(process_id) or {}
        data['process_id'] = process_id
        # Truncar logs para evitar payload grande
        if 'logs' in data and isinstance(data['logs'], list):
            data['logs'] = data['logs'][-50:]
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_uploads_bp.post("/upload_defere_indefere_recurso")
@api_login_required
@log_sensitive_operation("UPLOAD_DEFERE_INDEFERE_RECURSO")
def upload_defere_indefere_recurso():
    try:
        file = request.files.get('file')
        column_name = request.form.get('columnName', 'codigo')
        if not file or not file.filename:
            return jsonify({'success': False, 'message': 'Nenhum arquivo enviado'}), 400

        allowed = {'xlsx', 'csv', 'xls'}
        ext = (file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else '')
        if ext not in allowed:
            return jsonify({'success': False, 'message': 'Formato de arquivo não permitido'}), 400

        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secure_filename(file.filename)}"
        upload_folder = current_app.config.get('UPLOAD_FOLDER')
        os.makedirs(upload_folder, exist_ok=True)
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)

        job_service = get_job_service(current_app)

        def _target(job_id, path, col):
            worker_defere_indefere(job_service, job_id, path, col)

        job_id = job_service.enqueue(_target, filepath, column_name, meta={'type': 'defere_indefere_recurso', 'file': filename})
        return jsonify({'success': True, 'message': 'Processamento iniciado', 'process_id': job_id})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro ao processar arquivo: {str(e)}'})


@api_uploads_bp.get("/api/defere_indefere_recurso/status/<process_id>")
@api_login_required
def api_defere_indefere_recurso_status(process_id: str):
    try:
        job_service = get_job_service(current_app)
        data = job_service.status(process_id) or {}
        data['process_id'] = process_id
        if 'logs' in data and isinstance(data['logs'], list):
            data['logs'] = data['logs'][-50:]
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
