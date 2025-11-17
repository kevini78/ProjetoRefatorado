import os
import sys
import json
import time
import pandas as pd

from automation.services.ordinaria_processor import processar_processo_ordinaria


def main():
    if len(sys.argv) < 2:
        print("Uso: python scripts/run_ordinaria_once.py <numero_processo>")
        sys.exit(1)

    numero = sys.argv[1]
    print(f"[RUN] Iniciando processamento real do processo {numero}...")
    inicio = time.time()

    resultado = processar_processo_ordinaria(numero)

    duracao = time.time() - inicio
    print(f"[RUN] Concluído em {duracao:.1f}s")

    # Resumo do resultado
    print("\n[RESUMO]")
    print("sucesso:", resultado.get('sucesso'))
    print("status:", resultado.get('status'))
    print("elegibilidade_final:", resultado.get('elegibilidade_final'))
    print("motivos_indeferimento:", resultado.get('motivos_indeferimento'))

    # Verificar/mostrar planilha
    caminho_planilha = os.path.join(os.getcwd(), 'planilhas', 'analise_ordinaria_consolidada.xlsx')
    if os.path.exists(caminho_planilha):
        print("\n[PLANILHA] Caminho:", caminho_planilha)
        try:
            df = pd.read_excel(caminho_planilha)
            df_proc = df[df['Número do Processo'].astype(str) == str(numero)]
            if not df_proc.empty:
                print("[PLANILHA] Última linha do processo:")
                print(df_proc.tail(1).to_string(index=False))
            else:
                print("[PLANILHA] Processo não encontrado na planilha")
        except Exception as e:
            print("[PLANILHA] Erro ao ler planilha:", e)
    else:
        print("[PLANILHA] Planilha não encontrada")

    # Verificar JSON global
    arquivos_globais = [
        os.path.join(os.getcwd(), 'resultados_ordinaria_global.json'),
        os.path.join(os.getcwd(), 'resultados.ordinaria.global'),
    ]
    for arq in arquivos_globais:
        if os.path.exists(arq):
            try:
                with open(arq, 'r', encoding='utf-8') as f:
                    dados = json.load(f)
                print(f"[GLOBAL] {arq} contém {len(dados)} registros. Último numero_processo:", dados[-1].get('numero_processo'))
            except Exception as e:
                print(f"[GLOBAL] Erro lendo {arq}:", e)
        else:
            print(f"[GLOBAL] Arquivo não encontrado: {arq}")


if __name__ == '__main__':
    main()
