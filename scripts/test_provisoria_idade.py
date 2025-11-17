import os
import sys
import time

# Garantir que a raiz do projeto esteja no sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from automation.services.provisoria_processor import ProvisoriaProcessor


def main(codes):
    print('[TEST] Iniciando ProvisoriaProcessor para teste de idade...')
    proc = ProvisoriaProcessor(driver=None)

    print('[TEST] Fazendo login...')
    if not proc.lecom.login():
        print('[FAIL] Login falhou')
        return 1
    print('[OK] Login realizado')

    rc = 0
    for code in codes:
        print('\n' + '='*80)
        print(f'=== TESTE PROCESSO: {code} ===')
        print('='*80)
        try:
            # PASSO 1: Navegar para o processo (aplica filtros e extrai data inicial)
            print('\n[PASSO 1] Navegando para o processo e extraindo data inicial...')
            ok = proc.lecom.aplicar_filtros(code)
            if not ok:
                print('[FAIL] aplicar_filtros falhou para', code)
                rc = 2
                continue
            
            # Verificar se a data inicial foi extraída corretamente NO PASSO 1
            data_ref = getattr(proc.lecom, 'data_inicial_processo', None)
            print(f'\n[VERIFICAÇÃO] Data inicial após aplicar_filtros: {data_ref}')
            if data_ref:
                print('[OK] Data inicial EXTRAÍDA com sucesso no momento correto (antes do iframe)!')
            else:
                print('[ERRO] Data inicial NÃO foi extraída - verificação falhou!')
            
            time.sleep(2)

            # PASSO 2: Extrair dados pessoais (inclui data de nascimento) dentro do iframe
            print('\n[PASSO 2] Extraindo dados pessoais do formulário (dentro do iframe)...')
            try:
                dados = proc.lecom.extrair_dados_pessoais_formulario() or {}
            except Exception as e:
                print(f'[ERRO] Falha ao extrair dados pessoais: {e}')
                dados = {}

            print(f'\n[DADOS PESSOAIS] Nome: {dados.get("nome_completo", "N/A")}')
            print(f'[DADOS PESSOAIS] Pai: {dados.get("nome_pai", "N/A")}')
            print(f'[DADOS PESSOAIS] Mãe: {dados.get("nome_mae", "N/A")}')
            print(f'[DADOS PESSOAIS] Data Nascimento: {dados.get("data_nascimento", "N/A")}')
            print(f'[INFO] Data inicial já extraída no PASSO 1: {data_ref}')

            # PASSO 3: Rodar análise de elegibilidade provisória
            print('\n[PASSO 3] Executando análise de elegibilidade...')
            try:
                res_eval = proc.service.avaliar(proc.lecom, dados, data_ref) or {}
            except Exception as e:
                print(f'[ERRO] Falha na avaliação de elegibilidade: {e}')
                rc = max(rc, 3)
                continue

            # RESULTADO FINAL
            print('\n' + '='*80)
            print('=== RESULTADO DA ANÁLISE ===')
            print('='*80)
            idade = res_eval.get('idade_naturalizando') or res_eval.get('idade')
            print(f'\n[RESULTADO] Data Inicial Processo: {data_ref}')
            print(f'[RESULTADO] Data Nascimento: {dados.get("data_nascimento", "N/A")}')
            print(f'[RESULTADO] Idade Calculada: {idade if idade is not None else "INDETERMINADA"}')
            print(f'[RESULTADO] Elegibilidade: {res_eval.get("elegibilidade_final", "N/A")}')
            print(f'[RESULTADO] Motivo: {res_eval.get("motivo_final", "N/A")}')
            print('='*80)

            if idade is None:
                print('\n[WARN] ❌ Idade continua INDETERMINADA para este processo')
                rc = max(rc, 4)
            else:
                print(f'\n[OK] ✅ Idade calculada com sucesso: {idade} anos')

        except Exception as e:
            print('[ERRO] Exceção inesperada para código', code, ':', e)
            rc = max(rc, 5)

    try:
        if hasattr(proc, 'lecom') and hasattr(proc.lecom, 'fechar'):
            proc.lecom.fechar()
    except Exception:
        pass

    return rc


if __name__ == '__main__':
    # Se nenhum código for passado, usa o mesmo padrão do test_provisoria_flow
    codes = sys.argv[1:] or ["743961"]
    sys.exit(main(codes))
