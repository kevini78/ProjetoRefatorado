from flask import Blueprint, render_template, request, jsonify, current_app, redirect, url_for
from datetime import datetime

from ..security.decorators import log_sensitive_operation

automacao_bp = Blueprint("automacao", __name__)


@automacao_bp.route("/automacao_processos", methods=["GET", "POST"])
@log_sensitive_operation("AUTOMACAO_ANALISE_PROCESSOS")
def automacao_processos():
    if request.method == 'GET':
        try:
            return render_template('automacao_processos.html')
        except Exception:
            # If template not present, return simple page
            return "<h3>Automação de Processos</h3>", 200

    try:
        texto_despachos = (request.form.get('texto_despachos') or '').strip()
        mascarar_dados = request.form.get('mascarar_dados') == 'on'
        if not texto_despachos:
            return jsonify({'status': 'erro', 'erro': 'Texto dos despachos não fornecido'})

        from automacao_analise_processos import AutomacaoAnaliseProcessos
        if not hasattr(current_app, 'automacao_ativa'):
            current_app.automacao_ativa = AutomacaoAnaliseProcessos()
        automacao = current_app.automacao_ativa

        resultados = automacao.processar_lista_despachos(texto_despachos)
        if mascarar_dados:
            resultados = [automacao.mascarar_dados_sensiveis(r) for r in resultados]

        current_app.logger.info(f'Automação de processos executada: {len(resultados)} processos processados')
        return jsonify({
            'status': 'sucesso',
            'resultados': resultados,
            'total_processos': len(resultados),
            'timestamp': datetime.now().isoformat(),
        })
    except Exception as e:
        return jsonify({'status': 'erro', 'erro': str(e)})


@automacao_bp.get("/automacao_processos/status")
@log_sensitive_operation("STATUS_AUTOMACAO")
def status_automacao():
    return jsonify({'novos_resultados': [], 'processamento_concluido': False, 'timestamp': datetime.now().isoformat()})


@automacao_bp.post("/automacao_processos/parar")
@log_sensitive_operation("PARAR_AUTOMACAO")
def parar_automacao():
    try:
        if hasattr(current_app, 'automacao_ativa'):
            try:
                current_app.automacao_ativa.fechar_driver()
            except Exception:
                pass
            delattr(current_app, 'automacao_ativa')
        return jsonify({'status': 'sucesso', 'mensagem': 'Automação parada com sucesso'})
    except Exception as e:
        return jsonify({'status': 'erro', 'erro': str(e)})
