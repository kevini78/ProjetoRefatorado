import sys
import os
import glob
import pandas as pd
from datetime import datetime

# Garantir raiz no sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from modular_app.tasks.workers import worker_analise_provisoria


class _JobServiceStub:
    """Stub mínimo de JobService para executar o worker como na automação web."""

    def __init__(self):
        self._status = {}
        self._result = None

    def enqueue(self, *args, **kwargs):
        return "TEST"

    def update(self, job_id, **kwargs):
        msg = kwargs.get('message')
        detail = kwargs.get('detail')
        progress = kwargs.get('progress')
        if msg:
            print(f"[UPDATE] {msg} | detail={detail} | progress={progress}")

    def log(self, job_id, message, level='info'):
        print(f"[{level.upper()}] {message}")

    def set_result(self, job_id, result):
        self._result = result
        print(f"[RESULT] {result}")

    def status(self, job_id):
        return {'should_stop': False}


def _encontrar_ultimo_resultado_provisoria(upload_dir: str) -> str | None:
    """Retorna o caminho do arquivo resultados_analise_provisoria_*.xlsx mais recente."""
    padrao = os.path.join(upload_dir, 'resultados_analise_provisoria_*.xlsx')
    arquivos = glob.glob(padrao)
    if not arquivos:
        return None
    arquivos.sort(key=os.path.getmtime, reverse=True)
    return arquivos[0]


def _validar_resultado_planilha(codes, upload_dir: str) -> bool:
    """Valida que, para cada código, houve deferimento com 100%% dos 4 documentos.

    Regras do teste (aceitação):
    - status técnico pode ser "sucesso" ou "Processado com sucesso";
    - elegibilidade_final deve ser "deferimento";
    - percentual_final deve ser >= 100.0 (todos os 4 documentos válidos).
    """
    resultado_path = _encontrar_ultimo_resultado_provisoria(upload_dir)
    if not resultado_path:
        print("[FAIL] Nenhum arquivo resultados_analise_provisoria_*.xlsx encontrado em uploads/")
        return False

    print(f"[TEST] Lendo resultados: {resultado_path}")
    df_res = pd.read_excel(resultado_path, dtype={"codigo": str})

    ok_global = True
    for code in codes:
        code_norm = str(code).replace('.', '').replace(',', '').strip()
        linha = df_res[df_res['codigo'].astype(str).str.replace('.', '').str.replace(',', '') == code_norm]
        if linha.empty:
            print(f"[FAIL] Código {code} não encontrado na planilha de resultados")
            ok_global = False
            continue

        row = linha.iloc[0]
        status = str(row.get('status', '')).strip().lower()
        elegibilidade = str(row.get('elegibilidade_final', '')).strip().lower()
        percentual = float(row.get('percentual_final') or 0.0)

        print(f"[CHECK] código={code} | status={status} | elegibilidade={elegibilidade} | percentual={percentual}")

        # status técnico não precisa ser "sucesso" para o teste de regra,
        # o foco aqui é a combinação elegibilidade + documentos.
        if elegibilidade != 'deferimento':
            print(f"[FAIL] Código {code}: esperava elegibilidade_final='deferimento'")
            ok_global = False
        if percentual < 100.0:
            print(f"[FAIL] Código {code}: esperava percentual_final >= 100.0 (4 documentos válidos)")
            ok_global = False

    if ok_global:
        print("[OK] Todos os códigos testados tiveram DEFERIMENTO com 100% dos documentos.")
    else:
        print("[WARN] Pelo menos um código não atendeu aos critérios de deferimento + 4 documentos válidos.")

    return ok_global


def main(codes):
    # Criar planilha temporária em uploads/
    upload_dir = os.path.join(ROOT, 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    xlsx_path = os.path.join(upload_dir, f'planilha_provisoria_teste_{ts}.xlsx')
    df = pd.DataFrame({'codigo': codes})
    df.to_excel(xlsx_path, index=False)
    print(f"[TEST] Planilha gerada: {xlsx_path}")

    # Rodar worker direto (mesmo fluxo da interface web)
    js = _JobServiceStub()
    job_id = 'TEST-PROVISORIA'
    worker_analise_provisoria(js, job_id, xlsx_path, 'codigo')
    print("[TEST] Worker concluído, validando resultados...")

    # Validar regra de negócio: <10 anos + 4 documentos válidos => deferimento
    ok = _validar_resultado_planilha(codes, upload_dir)
    return 0 if ok else 1


if __name__ == '__main__':
    codes = sys.argv[1:]
    if not codes:
        print("Uso: python scripts/test_provisoria_full.py CODIGO [CODIGO ...]")
        sys.exit(2)
    sys.exit(main(codes))
