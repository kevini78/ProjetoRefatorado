from flask import Blueprint, request, jsonify

api_bp = Blueprint("api", __name__)


@api_bp.get("/health")
def api_health():
    return {"status": "ok", "component": "api"}, 200


@api_bp.post("/ordinaria/processar")
def processar_ordinaria():
    """Processa um número de processo usando a automação ordinária (síncrono)."""
    data = request.get_json(silent=True) or {}
    numero = data.get("numero_processo") or request.args.get("numero_processo")
    if not numero:
        return jsonify({"erro": "numero_processo ausente"}), 400

    try:
        from automation.services.ordinaria_processor import processar_processo_ordinaria
        resultado = processar_processo_ordinaria(numero)
        return jsonify({
            "sucesso": bool(resultado.get("sucesso")),
            "status": resultado.get("status"),
            "elegibilidade_final": resultado.get("elegibilidade_final"),
            "motivos_indeferimento": resultado.get("motivos_indeferimento", []),
        }), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
