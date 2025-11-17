from flask import Blueprint, render_template_string, current_app, send_file, send_from_directory, redirect, url_for, flash, jsonify
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
        caminho_arquivo = os.path.join(current_app.config["UPLOAD_FOLDER"], nome_arquivo)
        if not os.path.exists(caminho_arquivo):
            # Mantém comportamento legacy de feedback com flash + redirect quando usado via UI
            try:
                flash("Arquivo não encontrado", "error")
            except Exception:
                pass
            return redirect(url_for("web.index"))
        return send_file(caminho_arquivo, as_attachment=True, download_name=nome_arquivo)
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
        requested_path = os.path.abspath(os.path.join(base_dir, filename))
        if not (requested_path.startswith(base_dir + os.sep) or requested_path == base_dir):
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
        download_folder = os.path.join(os.getcwd(), "downloads_automacao")
        caminho_arquivo = os.path.join(download_folder, filename)
        if not os.path.exists(caminho_arquivo):
            try:
                flash("Arquivo não encontrado", "error")
            except Exception:
                pass
            return redirect(url_for("web.index"))
        if not filename.lower().endswith(".pdf"):
            try:
                flash("Tipo de arquivo não permitido", "error")
            except Exception:
                pass
            return redirect(url_for("web.index"))
        return send_from_directory(download_folder, filename, as_attachment=True)
    except Exception as e:
        try:
            flash(f"Erro ao baixar arquivo: {str(e)}", "error")
        except Exception:
            pass
        return redirect(url_for("web.index"))
