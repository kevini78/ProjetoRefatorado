from flask import Blueprint, render_template, request, current_app
from werkzeug.utils import secure_filename
from ..security.decorators import require_authentication
import os

pages_bp = Blueprint("pages", __name__)


@pages_bp.get("/aprovacao_lote")
@require_authentication
def pagina_aprovacao_lote():
    return render_template('aprovacao_lote.html')


@pages_bp.get("/aprovacao_parecer_analista")
@require_authentication
def pagina_aprovacao_parecer():
    return render_template('aprovacao_parecer_analista.html')


@pages_bp.get("/aprovacao_conteudo_recurso")
@require_authentication
def pagina_aprovacao_conteudo_recurso():
    return render_template('aprovacao_conteudo_recurso.html')


@pages_bp.get("/defere_indefere_recurso")
@require_authentication
def pagina_defere_indefere_recurso():
    return render_template('defere_indefere_recurso.html')


@pages_bp.route("/configurar", methods=["GET", "POST"])
@require_authentication
def pagina_configurar():
    """Página simples para upload de planilha de histórico.
    O arquivo é salvo em UPLOAD_FOLDER e uma mensagem é exibida.
    """
    message = None
    if request.method == 'POST':
        f = request.files.get('arquivo')
        if f and f.filename:
            try:
                os.makedirs(current_app.config.get('UPLOAD_FOLDER'), exist_ok=True)
                dest = os.path.join(current_app.config.get('UPLOAD_FOLDER'), secure_filename(f.filename))
                f.save(dest)
                message = f"Sucesso: arquivo salvo em {os.path.basename(dest)}"
            except Exception as e:
                current_app.logger.exception("Erro ao salvar arquivo de configuração")
                message = "Erro ao salvar arquivo. Verifique os logs do servidor para mais detalhes."
        else:
            message = "Nenhum arquivo selecionado"
    return render_template('configurar.html', message=message)


@pages_bp.get("/analisar")
@require_authentication
def pagina_analisar():
    return render_template('analisar.html')


@pages_bp.get("/busca_automatica")
@require_authentication
def pagina_busca_automatica():
    return render_template('busca_automatica.html')


@pages_bp.get("/complementacao")
@require_authentication
def pagina_complementacao():
    return render_template('complementacao.html')


@pages_bp.route("/analise_automatica", methods=["GET", "POST"])
@require_authentication
def pagina_analise_automatica():
    if request.method == 'POST':
        try:
            from ..tasks.job_service import get_job_service
            from ..tasks.workers import (
                worker_analise_provisoria,
                worker_analise_ordinaria,
                worker_analise_definitiva,
            )
            tipo = request.form.get('tipo_processo', '').strip().lower()
            f = request.files.get('planilha') or request.files.get('file')
            if not f or not f.filename:
                return render_template('analise_automatica.html', resultado='[ERRO] Nenhum arquivo selecionado'), 400
            if tipo not in ('provisoria', 'ordinaria', 'definitiva'):
                return render_template('analise_automatica.html', resultado='[ERRO] Tipo de processo ainda não suportado nesta página'), 400
            # Salvar arquivo em uploads/
            from werkzeug.utils import secure_filename
            import os
            from datetime import datetime
            upload_folder = current_app.config.get('UPLOAD_FOLDER')
            os.makedirs(upload_folder, exist_ok=True)
            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secure_filename(f.filename)}"
            filepath = os.path.join(upload_folder, filename)
            f.save(filepath)
            # Enfileirar worker correto baseado no tipo
            job_service = get_job_service(current_app)
            if tipo == 'provisoria':
                def _target(job_id, path, col):
                    worker_analise_provisoria(job_service, job_id, path, col)
                meta_type = 'analise_provisoria'
            elif tipo == 'ordinaria':
                def _target(job_id, path, col):
                    worker_analise_ordinaria(job_service, job_id, path, col)
                meta_type = 'analise_ordinaria'
            else:  # definitiva
                def _target(job_id, path, col):
                    worker_analise_definitiva(job_service, job_id, path, col)
                meta_type = 'analise_definitiva'
            job_id = job_service.enqueue(_target, filepath, 'codigo', meta={'type': meta_type, 'file': filename})
            msg = f"[OK] Upload recebido e processamento {tipo.upper()} iniciado. ID: {job_id}. O arquivo foi salvo como {filename}."
            return render_template('analise_automatica.html', resultado=msg)
        except Exception as e:
            current_app.logger.exception("Falha ao iniciar processamento automático")
            return render_template('analise_automatica.html', resultado="[ERRO] Falha ao iniciar processamento. Verifique os logs do servidor."), 500
    return render_template('analise_automatica.html')
