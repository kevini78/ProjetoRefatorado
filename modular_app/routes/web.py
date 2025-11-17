from flask import Blueprint, render_template_string, current_app, send_file, send_from_directory, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
import os

web_bp = Blueprint("web", __name__)


@web_bp.get("/")
def index():
    # Renderiza a home real a partir de templates/index.html para facilitar os testes
    from flask import render_template
    return render_template('index.html')


@web_bp.get("/favicon.ico")
def favicon():
    """Evita 404 para favicon. Retorna 204 (sem conteúdo)."""
    from flask import Response
    return Response(status=204, headers={"Content-Type": "image/x-icon"})


@web_bp.get("/health")
def health():
    return {"status": "ok", "component": "web"}, 200


@web_bp.get("/download_planilha_modificada/<nome_arquivo>")
def bp_download_planilha_modificada(nome_arquivo: str):
    """Download de planilha gerada/modificada. Usa UPLOAD_FOLDER da config."""
    try:
        base_dir = os.path.abspath(current_app.config["UPLOAD_FOLDER"])
        # Sanitiza o nome do arquivo para evitar path traversal e caracteres perigosos
        safe_name = secure_filename(nome_arquivo)
        if not safe_name:
            try:
                flash("Nome de arquivo inválido", "error")
            except Exception:
                pass
            return redirect(url_for("web.index"))
        caminho_arquivo = os.path.abspath(os.path.join(base_dir, safe_name))
        # Garante que o caminho permaneça dentro de UPLOAD_FOLDER (defesa extra)
        if os.path.commonpath([base_dir, caminho_arquivo]) != base_dir:
            try:
                flash("Caminho de arquivo inválido", "error")
            except Exception:
                pass
            return redirect(url_for("web.index"))
        if not os.path.exists(caminho_arquivo):
            # Mantém comportamento legacy de feedback com flash + redirect quando usado via UI
            try:
                flash("Arquivo não encontrado", "error")
            except Exception:
                pass
            return redirect(url_for("web.index"))
        return send_file(caminho_arquivo, as_attachment=True, download_name=os.path.basename(caminho_arquivo))
    except Exception as e:
        try:
            flash(f"Erro ao fazer download: {str(e)}", "error")
        except Exception:
            pass
        return redirect(url_for("web.index"))


@web_bp.get("/download/<filename>")
def bp_download_upload(filename: str):
    """Download de arquivos na pasta de uploads (compatível com rota legacy)."""
    try:
        base_dir = os.path.abspath(current_app.config.get("UPLOAD_FOLDER", os.path.join(os.getcwd(), "uploads")))
        # Sanitiza o nome do arquivo para evitar path traversal e caracteres perigosos
        safe_name = secure_filename(filename)
        if not safe_name:
            return jsonify({"success": False, "message": "Nome de arquivo inválido"}), 400
        requested_path = os.path.abspath(os.path.join(base_dir, safe_name))
        # Garante que o caminho permaneça dentro de UPLOAD_FOLDER (evita path traversal)
        if os.path.commonpath([base_dir, requested_path]) != base_dir:
            return jsonify({"success": False, "message": "Caminho inválido"}), 400
        if os.path.exists(requested_path):
            return send_file(requested_path, as_attachment=True)
        return jsonify({"success": False, "message": f"Arquivo não encontrado para download: {requested_path}"}), 404
    except Exception as e:
        return jsonify({"success": False, "message": f"Erro ao baixar arquivo: {str(e)}"}), 500


@web_bp.get("/automacao/download/<filename>")
def bp_download_automacao(filename: str):
    """Download de documentos produzidos pela automação (se existirem em downloads_automacao)."""
    try:
        download_folder = os.path.abspath(os.path.join(os.getcwd(), "downloads_automacao"))
        caminho_arquivo = os.path.abspath(os.path.join(download_folder, filename))
        # Garante que o caminho permaneça dentro de downloads_automacao (evita path traversal)
        if os.path.commonpath([download_folder, caminho_arquivo]) != download_folder:
            try:
                flash("Caminho de arquivo inválido", "error")
            except Exception:
                pass
            return redirect(url_for("web.index"))
        if not os.path.exists(caminho_arquivo):
            try:
                flash("Arquivo não encontrado", "error")
            except Exception:
                pass
            return redirect(url_for("web.index"))
        safe_name = os.path.basename(caminho_arquivo)
        if not safe_name.lower().endswith(".pdf"):
            try:
                flash("Tipo de arquivo não permitido", "error")
            except Exception:
                pass
            return redirect(url_for("web.index"))
        return send_from_directory(download_folder, safe_name, as_attachment=True)
    except Exception as e:
        try:
            flash(f"Erro ao baixar arquivo: {str(e)}", "error")
        except Exception:
            pass
        return redirect(url_for("web.index"))
