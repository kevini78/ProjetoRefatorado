import os
import time
from datetime import datetime
from typing import List, Dict, Any


def _should_stop(job_service, job_id: str) -> bool:
    try:
        s = job_service.status(job_id) or {}
        return bool(s.get('should_stop', False))
    except Exception:
        return False


def worker_defere_indefere(job_service, job_id: str, filepath: str, column_name: str) -> None:
    """Worker para Defere/Indefere Recurso usando JobService para status/log (refatorado).
    Usa RecursoProcessor da arquitetura modular em automation/.
    """
    from automation.services.recurso_processor import RecursoProcessor

    processor = None
    try:
        job_service.update(job_id, status='running', message='Inicializando...', detail='Configurando automação (refatorado)', progress=15)
        job_service.log(job_id, 'Iniciando módulo de Defere ou Indefere Recurso (refatorado)...', 'info')

        # Criar driver e processor
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        chrome_options = Options()
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=chrome_options)
        processor = RecursoProcessor(driver)
        job_service.log(job_id, '[OK] Processor inicializado (refatorado)', 'info')

        job_service.update(job_id, status='running', message='Fazendo login...', detail='Conectando ao LECOM', progress=25)
        job_service.log(job_id, 'Realizando login no sistema LECOM...', 'info')
        if not processor.lecom.fazer_login():
            raise Exception('Falha no login - processo cancelado')
        job_service.log(job_id, '[OK] Login realizado com sucesso!', 'success')

        job_service.update(job_id, status='running', message='Lendo planilha...', detail='Carregando códigos', progress=35)
        job_service.log(job_id, f'Lendo planilha: {filepath}', 'info')
        codigos: List[str] = processor.ler_codigos_planilha(filepath, column_name)
        if not codigos:
            raise Exception('Nenhum código encontrado na planilha')
        job_service.log(job_id, f'[OK] {len(codigos)} códigos encontrados na planilha', 'success')

        total = len(codigos)
        resultados: List[Dict[str, Any]] = []
        for i, codigo in enumerate(codigos, 1):
            if _should_stop(job_service, job_id):
                job_service.log(job_id, '⏹️ Processo cancelado pelo usuário', 'warning')
                break
            progress = int((i / max(1, total)) * 100)
            job_service.update(job_id, status='running', message=f'Processando {i}/{total}...', detail=f'Código: {codigo}', progress=progress)
            job_service.log(job_id, f'[INFO] Processando código {i}/{total}: {codigo}', 'info')

            resultado = processor.processar_codigo(codigo)
            resultados.append(resultado)
            if resultado.get('status') == 'sucesso':
                job_service.log(job_id, f'[OK] {codigo}: {resultado.get("decisao")}', 'success')
            else:
                job_service.log(job_id, f'[ERRO] {codigo}: {resultado.get("erro", "Erro desconhecido")}', 'error')

        # Resumo e persistência opcional
        sucessos = len([r for r in resultados if r.get('status') == 'sucesso'])
        erros = len([r for r in resultados if r.get('status') == 'erro'])
        decisoes_enviadas = len([r for r in resultados if r.get('decisao_enviada', False)])
        summary = {
            'total_processados': len(resultados),
            'sucessos': sucessos,
            'erros': erros,
            'decisoes_enviadas': decisoes_enviadas,
            'arquivo_original': filepath,
        }
        job_service.set_result(job_id, summary)
        job_service.log(job_id, f'[DADOS] Resumo: {sucessos} sucessos, {erros} erros, {decisoes_enviadas} decisões enviadas', 'success')

        # Salvar planilha de resultados no diretório planilhas/
        try:
            import pandas as pd
            df = pd.DataFrame(resultados)
            planilhas_dir = os.path.join(os.getcwd(), 'planilhas')
            os.makedirs(planilhas_dir, exist_ok=True)
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            out_name = f'resultados_defere_indefere_{ts}.xlsx'
            out_path = os.path.join(planilhas_dir, out_name)
            df.to_excel(out_path, index=False)
            job_service.log(job_id, f'[SALVO] Resultados salvos em planilhas/: {out_name}', 'success')
        except Exception as e:
            job_service.log(job_id, f'[AVISO] Erro ao salvar planilha: {e}', 'warning')

        job_service.update(job_id, status='completed', message='Processamento concluído!', detail='Finalizado', progress=100)

    except Exception as e:
        job_service.log(job_id, f'[ERRO] {str(e)}', 'error')
        job_service.update(job_id, status='error', message='Erro', detail=str(e), progress=0)

    finally:
        if processor:
            try:
                if hasattr(processor, 'lecom') and hasattr(processor.lecom, 'driver'):
                    processor.lecom.driver.quit()
                job_service.log(job_id, '[FECHADO] Recursos liberados', 'info')
            except Exception:
                pass
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                job_service.log(job_id, '🗑️ Arquivo temporário removido', 'info')
        except Exception as e:
            job_service.log(job_id, f'[AVISO] Erro ao remover arquivo temporário: {e}', 'warning')


def worker_aprovacao_recurso(job_service, job_id: str, filepath: str, column_name: str) -> None:
    """Worker para Aprovação do Conteúdo de Recurso usando JobService (refatorado).
    Usa RecursoProcessor da arquitetura modular.
    """
    from automation.services.recurso_processor import RecursoProcessor

    processor = None
    try:
        job_service.update(job_id, status='running', message='Inicializando...', detail='Configurando automação (refatorado)', progress=15)
        job_service.log(job_id, 'Iniciando módulo de aprovação do conteúdo de recurso (refatorado)...', 'info')

        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        chrome_options = Options()
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=chrome_options)
        processor = RecursoProcessor(driver)
        job_service.log(job_id, '[OK] Processor inicializado (refatorado)', 'info')

        job_service.update(job_id, status='running', message='Fazendo login...', detail='Conectando ao LECOM', progress=25)
        job_service.log(job_id, 'Realizando login no sistema LECOM...', 'info')
        if not processor.lecom.fazer_login():
            raise Exception('Falha no login no LECOM')
        job_service.log(job_id, '[OK] Login realizado com sucesso!', 'success')

        job_service.update(job_id, status='running', message='Processando planilha...', detail='Lendo códigos dos processos', progress=50)
        job_service.log(job_id, f'Processando planilha: {os.path.basename(filepath)}', 'info')
        job_service.log(job_id, f'[BUSCA] Lendo códigos da planilha com coluna: {column_name}', 'info')

        codigos: List[str] = processor.ler_codigos_planilha(filepath, column_name)
        if not codigos:
            raise Exception('Nenhum código encontrado na planilha')
        job_service.log(job_id, f'[DADOS] Encontrados {len(codigos)} códigos para processar', 'info')

        resultados: List[Dict[str, Any]] = []
        total = len(codigos)
        for i, codigo in enumerate(codigos, 1):
            if _should_stop(job_service, job_id):
                job_service.log(job_id, '⏹️ Processo interrompido pelo usuário', 'warning')
                break
            progress = 50 + (i / max(1, total)) * 40
            job_service.update(job_id, status='running', message=f'Processando {i}/{total}...', detail=f'Processo: {codigo}', progress=progress)
            job_service.log(job_id, f'[RELOAD] Processando código {i}/{total}: {codigo}', 'info')

            try:
                _ = processor.lecom.driver.current_url  # validar driver
            except Exception:
                job_service.log(job_id, f'[ERRO] Driver perdido no processo {i}, finalizando...', 'error')
                break

            resultado = processor.processar_codigo(codigo)
            resultados.append(resultado)
            if resultado.get('status') == 'sucesso':
                job_service.log(job_id, f'[OK] {codigo}: {resultado.get("decisao")}', 'success')
            else:
                job_service.log(job_id, f'[ERRO] {codigo}: {resultado.get("erro", "Erro desconhecido")}', 'error')

            time.sleep(1)

        # Salvar resultados usando serviço unificado
        job_service.log(job_id, f'[SALVO] Salvando resultados de {len(resultados)} processos...', 'info')
        job_service.update(job_id, status='running', message='Salvando resultados...', detail='Gerando planilha', progress=90)
        try:
            from modular_app.services.unified_results_service import UnifiedResultsService
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            unified_service = UnifiedResultsService()
            out_path = unified_service.salvar_resultado_parecer_analista(resultados, timestamp=ts)
            out_name = os.path.basename(out_path)
            
            job_service.log(job_id, f'[SALVO] Resultados salvos em planilhas/: {out_name}', 'success')
            job_service.log(job_id, f'[CONSOLIDADO] Resultados também adicionados ao arquivo consolidado', 'success')
        except Exception as e:
            job_service.log(job_id, f'[AVISO] Erro ao salvar planilha: {e}', 'warning')

        job_service.set_result(job_id, {
            'total_processados': len(resultados),
            'sucessos': len([r for r in resultados if r.get('status') == 'sucesso'] ),
            'erros': len([r for r in resultados if r.get('status') == 'erro'] ),
            'resultados': resultados,
        })
        job_service.update(job_id, status='completed', message='Concluído!', detail='Processamento finalizado', progress=100)

    except Exception as e:
        import traceback
        job_service.log(job_id, f'[ERRO] Erro durante processamento: {str(e)}', 'error')
        job_service.log(job_id, f'[BUSCA] Traceback: {traceback.format_exc()}', 'error')
        job_service.update(job_id, status='error', message='Erro', detail=str(e), progress=0)

    finally:
        try:
            if processor and hasattr(processor, 'lecom') and hasattr(processor.lecom, 'driver'):
                processor.lecom.driver.quit()
        except Exception:
            pass
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                job_service.log(job_id, '🗑️ Arquivo temporário removido', 'info')
        except Exception as e:
            job_service.log(job_id, f'[AVISO] Erro ao remover arquivo temporário: {e}', 'warning')


def worker_aprovacao_lote(job_service, job_id: str, max_iteracoes: int, modo_execucao: str, tempo_espera_minutos: int = 10) -> None:
    """Worker para Aprovação em Lote usando JobService (refatorado).
    Usa LoteProcessor da arquitetura modular.
    """
    from automation.services.lote_processor import LoteProcessor

    processor = None
    try:
        job_service.update(job_id, status='running', message='Inicializando...', detail='Configurando automação (refatorado)', progress=15)
        job_service.log(job_id, 'Iniciando módulo de aprovação em lote (refatorado)...', 'info')

        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        chrome_options = Options()
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=chrome_options)
        driver.maximize_window()
        processor = LoteProcessor(driver)
        job_service.update(job_id, status='running', message='Inicializando Driver...', detail='Abrindo navegador VISUAL', progress=25)
        job_service.log(job_id, 'Processor de lote inicializado em MODO VISUAL (refatorado)', 'success')

        if modo_execucao == 'continuo':
            job_service.update(job_id, status='running', message='Executando Ciclos Contínuos...', detail=f'Máximo {max_iteracoes} ciclos', progress=35)
            job_service.log(job_id, f'Iniciando {max_iteracoes} ciclos completos de aprovação...', 'info')
            job_service.log(job_id, f'⏰ Tempo de espera entre ciclos: {tempo_espera_minutos} minutos', 'info')

            ciclos_executados = 0
            for i in range(max_iteracoes):
                if _should_stop(job_service, job_id):
                    job_service.log(job_id, 'Execução interrompida pelo usuário', 'warning')
                    break
                progress = 35 + (i / max(1, max_iteracoes)) * 50
                job_service.update(job_id, status='running', message=f'Ciclo {i+1}/{max_iteracoes}', detail='Executando aprovações em lote...', progress=progress)
                job_service.log(job_id, f'[RELOAD] Iniciando ciclo completo {i+1}/{max_iteracoes}...', 'info')

                resultado_ciclo = processor.executar()
                if resultado_ciclo:
                    ciclos_executados += 1
                    job_service.log(job_id, f'[OK] Ciclo {i+1} concluído com sucesso', 'success')
                else:
                    job_service.log(job_id, f'[AVISO] Ciclo {i+1} não encontrou processos para aprovar', 'warning')

                if i < max_iteracoes - 1:
                    job_service.log(job_id, f'[AGUARDE] Aguardando {tempo_espera_minutos} minutos antes do próximo ciclo...', 'info')
                    # Espera com logs simples a cada 30s
                    total_seg = max(1, tempo_espera_minutos) * 60
                    intervalos = max(1, total_seg // 30)
                    for _ in range(int(intervalos)):
                        if _should_stop(job_service, job_id):
                            break
                        time.sleep(total_seg / intervalos)
                    job_service.log(job_id, f'[OK] Espera concluída - iniciando próximo ciclo', 'success')

            job_service.log(job_id, f'🏁 Execução finalizada.', 'success')
        else:
            job_service.update(job_id, status='running', message='Execução Única...', detail='Processando aprovações...', progress=50)
            job_service.log(job_id, 'Iniciando execução única...', 'info')
            if processor.executar():
                job_service.log(job_id, '[OK] Execução única concluída com sucesso', 'success')
            else:
                raise Exception('Falha na execução única')

        job_service.update(job_id, status='completed', message='Concluído!', detail='Processo finalizado com sucesso', progress=100)

    except Exception as e:
        job_service.update(job_id, status='error', message='Erro', detail=str(e), progress=0)
        job_service.log(job_id, f'[ERRO] Erro: {str(e)}', 'error')
    finally:
        if processor:
            try:
                if hasattr(processor, 'lecom') and hasattr(processor.lecom, 'driver'):
                    processor.lecom.driver.quit()
                job_service.log(job_id, 'Recursos liberados', 'info')
            except Exception:
                pass


from typing import Optional


def worker_analise_ordinaria(job_service, job_id: str, filepath: str, column_name: str = 'codigo') -> None:
    """Worker para Análise Automática do tipo Ordinária (refatorado).
    Usa OrdinariaProcessor com login automático (.env) e fluxo completo.
    """
    import os
    import pandas as pd
    from datetime import datetime
    import time
    try:
        job_service.update(job_id, status='running', message='Inicializando...', detail='Configurando automação Ordinária', progress=10)
        job_service.log(job_id, 'Iniciando análise Ordinária (refatorado)...', 'info')

        # Ler códigos (case-insensitive)
        def _ler_codigos(caminho: str, col: str) -> list[str]:
            _, ext = os.path.splitext(caminho.lower())
            if ext in ('.xlsx', '.xls'):
                df = pd.read_excel(caminho, dtype=str)
            elif ext == '.csv':
                df = pd.read_csv(caminho, dtype=str)
            else:
                df = pd.read_excel(caminho, dtype=str)
            mapa = {str(c).strip().lower(): c for c in df.columns}
            alvo = (col or 'codigo').strip().lower()
            real = mapa.get(alvo) or mapa.get('codigo') or mapa.get('código')
            if not real:
                real = list(df.columns)[0]
            serie = df[real].dropna().astype(str).map(lambda x: x.strip()).replace({'': None}).dropna()
            # normalizar removendo separadores
            serie = serie.str.replace('.', '', regex=False).str.replace(',', '', regex=False)
            return serie.tolist()

        codigos = _ler_codigos(filepath, column_name)
        if not codigos:
            raise Exception('Nenhum código encontrado na planilha')
        job_service.log(job_id, f'[OK] {len(codigos)} códigos lidos', 'success')

        # Inicializar Processor (Selenium abre aqui)
        from automation.services.ordinaria_processor import OrdinariaProcessor
        job_service.update(job_id, status='running', message='Abrindo navegador...', detail='Inicializando Selenium', progress=15)
        job_service.log(job_id, '[WEB] Inicializando Selenium (Chrome headful)...', 'info')
        proc = OrdinariaProcessor(driver=None)

        # Login automático
        job_service.update(job_id, status='running', message='Fazendo login automático...', detail='Autenticando no LECOM', progress=20)
        if not proc.lecom_action.login():
            raise Exception('Falha no login no LECOM (Ordinária)')
        proc.lecom_action.ja_logado = True
        # Garantir workspace
        try:
            cur = proc.lecom_action.driver.current_url
            if 'workspace' not in (cur or '').lower():
                proc.lecom_action.driver.get('https://justica.servicos.gov.br/workspace')
                time.sleep(2)
        except Exception:
            pass
        job_service.log(job_id, '[OK] Login realizado e workspace acessado', 'success')

        # Processar
        resultados = []
        total = len(codigos)
        for i, codigo in enumerate(codigos, 1):
            if _should_stop(job_service, job_id):
                job_service.log(job_id, '⏹️ Processo cancelado pelo usuário', 'warning')
                break
            progress = int(20 + (i / max(1, total)) * 70)
            job_service.update(job_id, status='running', message=f'Processando {i}/{total}...', detail=f'Código: {codigo}', progress=progress)
            job_service.log(job_id, f'[INFO] Ordinária: {codigo}', 'info')
            try:
                # Processar processo usando OrdinariaProcessor
                resultado = proc.processar_processo(codigo)
                
                # Formatar saída
                out = {
                    'codigo': codigo,
                    'status': 'sucesso' if resultado.get('sucesso') else 'erro',
                    'elegibilidade_final': resultado.get('elegibilidade_final'),
                    'percentual_final': resultado.get('resultado_elegibilidade', {}).get('percentual_final'),
                    'motivo_final': resultado.get('resultado_elegibilidade', {}).get('motivo_final'),
                    'motivos_indeferimento': resultado.get('motivos_indeferimento', []),
                    'documentos_faltantes': resultado.get('documentos_faltantes', []),
                    'erro': resultado.get('erro')
                }
            except Exception as e:
                out = {'codigo': codigo, 'status': 'erro', 'erro': str(e)}
            resultados.append(out)
            status_ok = str(out.get('status','')).lower()
            if status_ok in ('sucesso', 'processado com sucesso'):
                job_service.log(job_id, f"[OK] {codigo}: {out.get('elegibilidade_final', 'N/A')}", 'success')
            else:
                job_service.log(job_id, f"[ERRO] {codigo}: {out.get('erro','Erro desconhecido')}", 'error')

        # Salvar planilha usando serviço unificado
        try:
            from modular_app.services.unified_results_service import UnifiedResultsService
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            unified_service = UnifiedResultsService()
            out_path = unified_service.salvar_lote_ordinaria(resultados, timestamp=ts)
            out_name = os.path.basename(out_path)
            
            job_service.log(job_id, f'[SALVO] Resultados salvos em planilhas/: {out_name}', 'success')
            job_service.log(job_id, f'[CONSOLIDADO] Resultados também adicionados ao arquivo consolidado', 'success')
        except Exception as e:
            job_service.log(job_id, f'[AVISO] Erro ao salvar planilha: {e}', 'warning')

        # Summary
        job_service.set_result(job_id, {
            'total_processados': len(resultados),
            'sucessos': len([r for r in resultados if str(r.get('status','')).lower() in ('sucesso','processado com sucesso') ]),
            'erros': len([r for r in resultados if str(r.get('status','')).lower() not in ('sucesso','processado com sucesso') ]),
            'arquivo_original': filepath,
        })
        job_service.update(job_id, status='completed', message='Concluído!', detail='Análise Ordinária finalizada', progress=100)
    except Exception as e:
        job_service.log(job_id, f'[ERRO] {str(e)}', 'error')
        job_service.update(job_id, status='error', message='Erro', detail=str(e), progress=0)
    finally:
        # Cleanup
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                job_service.log(job_id, '🗑️ Arquivo temporário removido', 'info')
        except Exception:
            pass
        try:
            # fechar driver
            try:
                if proc and hasattr(proc, 'fechar'):
                    proc.fechar()
            except Exception:
                pass
        except Exception:
            pass


def worker_analise_provisoria(job_service, job_id: str, filepath: str, column_name: str = 'codigo') -> None:
    """Worker para Análise Automática do tipo Provisória (refatorado).
    Usa ProvisoriaAction/Processor com login automático (.env) e fluxo compatível com o original.
    """
    import os
    import pandas as pd
    from datetime import datetime
    import time
    try:
        job_service.update(job_id, status='running', message='Inicializando...', detail='Configurando automação Provisória', progress=10)
        job_service.log(job_id, 'Iniciando análise Provisória (refatorado)...', 'info')

        # Ler códigos (case-insensitive)
        def _ler_codigos(caminho: str, col: str) -> list[str]:
            _, ext = os.path.splitext(caminho.lower())
            if ext in ('.xlsx', '.xls'):
                df = pd.read_excel(caminho, dtype=str)
            elif ext == '.csv':
                df = pd.read_csv(caminho, dtype=str)
            else:
                df = pd.read_excel(caminho, dtype=str)
            mapa = {str(c).strip().lower(): c for c in df.columns}
            alvo = (col or 'codigo').strip().lower()
            real = mapa.get(alvo) or mapa.get('codigo') or mapa.get('código')
            if not real:
                real = list(df.columns)[0]
            serie = df[real].dropna().astype(str).map(lambda x: x.strip()).replace({'': None}).dropna()
            # normalizar removendo separadores
            serie = serie.str.replace('.', '', regex=False).str.replace(',', '', regex=False)
            return serie.tolist()

        codigos = _ler_codigos(filepath, column_name)
        if not codigos:
            raise Exception('Nenhum código encontrado na planilha')
        job_service.log(job_id, f'[OK] {len(codigos)} códigos lidos', 'success')

        # Inicializar Processor/Action (Selenium abre aqui)
        from automation.services.provisoria_processor import ProvisoriaProcessor
        job_service.update(job_id, status='running', message='Abrindo navegador...', detail='Inicializando Selenium', progress=15)
        job_service.log(job_id, '[WEB] Inicializando Selenium (Chrome headful)...', 'info')
        proc = ProvisoriaProcessor(driver=None)

        # Login automático
        job_service.update(job_id, status='running', message='Fazendo login automático...', detail='Autenticando no LECOM', progress=20)
        if not hasattr(proc, 'lecom') or not proc.lecom.login():
            raise Exception('Falha no login no LECOM (Provisória)')
        # Garantir workspace
        try:
            cur = proc.lecom.driver.current_url
            if 'workspace' not in (cur or '').lower():
                proc.lecom.driver.get('https://justica.servicos.gov.br/workspace')
                time.sleep(2)
        except Exception:
            pass
        job_service.log(job_id, '[OK] Login realizado e workspace acessado', 'success')

        # Processar
        resultados = []
        total = len(codigos)
        for i, codigo in enumerate(codigos, 1):
            if _should_stop(job_service, job_id):
                job_service.log(job_id, '⏹️ Processo cancelado pelo usuário', 'warning')
                break
            progress = int(20 + (i / max(1, total)) * 70)
            job_service.update(job_id, status='running', message=f'Processando {i}/{total}...', detail=f'Código: {codigo}', progress=progress)
            job_service.log(job_id, f'[INFO] Provisória: {codigo}', 'info')
            try:
                # Garantir navegação visível p/ logs da Web (antes do Processor)
                try:
                    job_service.log(job_id, f"[NAV] Provisória: buscando processo {codigo}...", 'info')
                    _ok_nav = proc.lecom.aplicar_filtros(codigo)
                    if _ok_nav:
                        job_service.log(job_id, f"[OK] Provisória: processo {codigo} carregado (workspace/form-web)", 'success')
                    else:
                        job_service.log(job_id, f"[AVISO] Provisória: não foi possível carregar {codigo} via aplicar_filtros (seguindo com Processor)", 'warning')
                except Exception as _e_nav:
                    job_service.log(job_id, f"[AVISO] Provisória: exceção ao navegar para {codigo}: {_e_nav}", 'warning')
                # Usar Processor para executar o fluxo completo (login, navegação, avaliação)
                resultado = proc.processar_codigo(codigo)
                out = {
                    'codigo': codigo,
                    'status': resultado.get('status', 'erro'),
                    'analise_elegibilidade': resultado.get('analise_elegibilidade', {}),
                    'erro': resultado.get('erro')
                }
            except Exception as e:
                out = {'codigo': codigo, 'status': 'erro', 'erro': str(e)}
            resultados.append(out)
            status_ok = str(out.get('status','')).lower()
            if status_ok in ('sucesso', 'processado com sucesso'):
                job_service.log(job_id, f"[OK] {codigo}: {out.get('status')}", 'success')
            else:
                job_service.log(job_id, f"[ERRO] {codigo}: {out.get('erro','Erro desconhecido')}", 'error')

        # Salvar planilha no diretório planilhas/
        try:
            planilhas_dir = os.path.join(os.getcwd(), 'planilhas')
            os.makedirs(planilhas_dir, exist_ok=True)
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            out_name = f'resultados_analise_provisoria_{ts}.xlsx'
            out_path = os.path.join(planilhas_dir, out_name)

            rows = []
            for r in resultados:
                ae = r.get('analise_elegibilidade') or {}
                rows.append({
                    'codigo': r.get('codigo'),
                    'status': r.get('status'),
                    'elegibilidade_final': ae.get('elegibilidade_final'),
                    'percentual_final': ae.get('percentual_final'),
                    'motivo_final': ae.get('motivo_final'),
                    'erro': r.get('erro')
                })
            pd.DataFrame(rows).to_excel(out_path, index=False)
            job_service.log(job_id, f'[SALVO] Resultados salvos em planilhas/: {out_name}', 'success')
        except Exception as e:
            job_service.log(job_id, f'[AVISO] Erro ao salvar planilha: {e}', 'warning')

        # Summary
        job_service.set_result(job_id, {
            'total_processados': len(resultados),
            'sucessos': len([r for r in resultados if str(r.get('status','')).lower() in ('sucesso','processado com sucesso') ]),
            'erros': len([r for r in resultados if str(r.get('status','')).lower() not in ('sucesso','processado com sucesso') ]),
            'arquivo_original': filepath,
        })
        job_service.update(job_id, status='completed', message='Concluído!', detail='Análise Provisória finalizada', progress=100)
    except Exception as e:
        job_service.log(job_id, f'[ERRO] {str(e)}', 'error')
        job_service.update(job_id, status='error', message='Erro', detail=str(e), progress=0)
    finally:
        # Cleanup
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                job_service.log(job_id, '5d1e0f Arquivo tempore1rio removido', 'info')
        except Exception:
            pass
        try:
            # fechar driver
            try:
                if proc and hasattr(proc, 'lecom') and hasattr(proc.lecom, 'fechar'):
                    proc.lecom.fechar()
            except Exception:
                pass
        except Exception:
            pass


def worker_analise_definitiva(job_service, job_id: str, filepath: str, column_name: str = 'codigo') -> None:
    """Worker para Ane1lise Autome1tica do tipo Definitiva.
    Usa DefinitivaProcessor com login autome1tico (.env) e o pipeline
    existente em `Definitiva/analise_processos.py`.
    """
    import os
    import pandas as pd
    from datetime import datetime
    import time

    try:
        job_service.update(
            job_id,
            status='running',
            message='Inicializando...',
            detail='Configurando automae7e3o Definitiva',
            progress=10,
        )
        job_service.log(job_id, 'Iniciando ane1lise Definitiva (refatorado)...', 'info')

        def _ler_codigos(caminho: str, col: str) -> list[str]:
            _, ext = os.path.splitext(caminho.lower())
            if ext in ('.xlsx', '.xls'):
                df = pd.read_excel(caminho, dtype=str)
            elif ext == '.csv':
                df = pd.read_csv(caminho, dtype=str)
            else:
                df = pd.read_excel(caminho, dtype=str)
            mapa = {str(c).strip().lower(): c for c in df.columns}
            alvo = (col or 'codigo').strip().lower()
            real = mapa.get(alvo) or mapa.get('codigo') or mapa.get('cf3digo')
            if not real:
                real = list(df.columns)[0]
            serie = df[real].dropna().astype(str).map(lambda x: x.strip()).replace({'': None}).dropna()
            serie = serie.str.replace('.', '', regex=False).str.replace(',', '', regex=False)
            return serie.tolist()

        codigos = _ler_codigos(filepath, column_name)
        if not codigos:
            raise Exception('Nenhum cf3digo encontrado na planilha')
        job_service.log(job_id, f'[OK] {len(codigos)} cf3digos lidos', 'success')

        from automation.services.definitiva_processor import DefinitivaProcessor

        job_service.update(
            job_id,
            status='running',
            message='Abrindo navegador...',
            detail='Inicializando Selenium',
            progress=15,
        )
        job_service.log(job_id, '[WEB] Inicializando Selenium (Chrome headful)...', 'info')
        proc = DefinitivaProcessor(driver=None)

        # Login autome1tico
        job_service.update(
            job_id,
            status='running',
            message='Fazendo login autome1tico...',
            detail='Autenticando no LECOM',
            progress=20,
        )
        if not proc.lecom_action.login():
            raise Exception('Falha no login no LECOM (Definitiva)')

        try:
            cur = proc.lecom_action.driver.current_url
            if 'workspace' not in (cur or '').lower():
                proc.lecom_action.driver.get('https://justica.servicos.gov.br/workspace')
                time.sleep(2)
        except Exception:
            pass
        job_service.log(job_id, '[OK] Login realizado e workspace acessado', 'success')

        resultados = []
        total = len(codigos)
        for i, codigo in enumerate(codigos, 1):
            if _should_stop(job_service, job_id):
                job_service.log(job_id, '3f9e0f Processo cancelado pelo usue1rio', 'warning')
                break

            progress = int(20 + (i / max(1, total)) * 70)
            job_service.update(
                job_id,
                status='running',
                message=f'Processando {i}/{total}...',
                detail=f'Cf3digo: {codigo}',
                progress=progress,
            )
            job_service.log(job_id, f'[INFO] Definitiva: {codigo}', 'info')

            try:
                resultado = proc.processar_processo(codigo)
                analise = resultado.get('analise_elegibilidade') or {}
                status_label = str(resultado.get('status', '')).lower()
                status_simplificado = 'sucesso' if status_label not in ('erro', 'timeout') else 'erro'

                data_proc = resultado.get('data_processamento')
                total_docs = int(resultado.get('total_documentos', 0) or 0)
                docs_proc = resultado.get('documentos_processados') or []
                indeferimento_auto = bool(resultado.get('indeferimento_automatico'))
                motivo_indef = resultado.get('motivo_indef') or resultado.get('motivo') or ''

                # Observações / cláusulas
                observacoes_parts = []
                if status_label == 'indeferimento automático' or indeferimento_auto:
                    base_motivo = motivo_indef or 'Indeferimento automático sem motivo detalhado'
                    observacoes_parts.append(
                        f"Processo {codigo} INDEFERIDO automaticamente: {base_motivo}"
                    )
                    # Cláusula de análise manual para casos de naturalização não encontrada
                    if 'naturalização provisória não encontrada no banco' in base_motivo.lower():
                        observacoes_parts.append(
                            "Cláusula: ANÁLISE MANUAL RECOMENDADA caso exista portaria ou outro "
                            "documento de naturalização anexado no processo."
                        )
                elif status_label in ('erro', 'timeout'):
                    obs_erro = resultado.get('erro') or 'Erro não detalhado'
                    observacoes_parts.append(
                        f"Processo {codigo} com erro no processamento: {obs_erro}"
                    )
                else:
                    if analise:
                        try:
                            conf_pct = float(analise.get('confianca') or 0) * 100.0
                        except Exception:
                            conf_pct = 0.0
                        observacoes_parts.append(
                            f"Processo {codigo}: elegibilidade={analise.get('elegibilidade')} "
                            f"(confiança={conf_pct:.1f}%)."
                        )

                observacoes = " ".join(observacoes_parts).strip()

                # Documento baixado?
                if indeferimento_auto and total_docs == 0:
                    doc_baixado = 'Não (indeferimento automático)'
                else:
                    doc_baixado = 'Sim' if total_docs > 0 else 'Não'

                out = {
                    'codigo': codigo,
                    'status': status_simplificado,
                    'status_detalhado': resultado.get('status'),
                    'elegibilidade': analise.get('elegibilidade'),
                    'confianca': analise.get('confianca'),
                    'score_total': analise.get('score_total'),
                    'erro': resultado.get('erro'),
                    'data_processamento': data_proc,
                    'observacoes': observacoes,
                    'documento_baixado': doc_baixado,
                    'documentos_processados': len(docs_proc),
                    'total_documentos': total_docs,
                }
            except Exception as e:  # pragma: no cover - defensivo
                out = {
                    'codigo': codigo,
                    'status': 'erro',
                    'status_detalhado': 'Erro',
                    'elegibilidade': None,
                    'confianca': None,
                    'score_total': None,
                    'erro': str(e),
                }

            resultados.append(out)
            if out['status'] == 'sucesso':
                job_service.log(job_id, f"[OK] {codigo}: {out.get('elegibilidade', 'N/A')}", 'success')
            else:
                job_service.log(job_id, f"[ERRO] {codigo}: {out.get('erro','Erro desconhecido')}", 'error')

        # Salvar planilha de resultados no diretório planilhas/
        try:
            planilhas_dir = os.path.join(os.getcwd(), 'planilhas')
            os.makedirs(planilhas_dir, exist_ok=True)
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            out_name = f'resultados_analise_definitiva_{ts}.xlsx'
            out_path = os.path.join(planilhas_dir, out_name)

            rows = []
            for r in resultados:
                # Campos compatíveis com a planilha antiga
                codigo = r.get('codigo')
                status_detalhado = r.get('status_detalhado') or ''
                data_proc = r.get('data_processamento') or ''
                observacoes = r.get('observacoes') or ''
                doc_baixado = r.get('documento_baixado') or ''
                docs_proc = int(r.get('documentos_processados') or 0)
                total_docs = int(r.get('total_documentos') or 0)

                rows.append({
                    'Código': codigo,
                    'Status': status_detalhado,
                    'Resultado Processamento': status_detalhado,
                    'Verificação da análise do robô': '',  # Campo para preenchimento manual (Correta/Incorreta)
                    'Data Processamento': data_proc,
                    'Observações': observacoes,
                    'Documento Baixado': doc_baixado,
                    'Caminho Documento': '',  # Não há caminho consolidado neste fluxo modular
                    'Documentos Processados': docs_proc,
                    'Total Documentos': total_docs,
                })

            pd.DataFrame(rows).to_excel(out_path, index=False)
            job_service.log(job_id, f'[SALVO] Resultados salvos em planilhas/: {out_name}', 'success')
        except Exception as e:
            job_service.log(job_id, f'[AVISO] Erro ao salvar planilha: {e}', 'warning')

        # Summary
        job_service.set_result(job_id, {
            'total_processados': len(resultados),
            'sucessos': len([r for r in resultados if str(r.get('status','')).lower() == 'sucesso']),
            'erros': len([r for r in resultados if str(r.get('status','')).lower() != 'sucesso']),
            'arquivo_original': filepath,
        })
        job_service.update(job_id, status='completed', message='Conclueddo!', detail='Ane1lise Definitiva finalizada', progress=100)
    except Exception as e:
        job_service.log(job_id, f'[ERRO] {str(e)}', 'error')
        job_service.update(job_id, status='error', message='Erro', detail=str(e), progress=0)
    finally:
        # Cleanup
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                job_service.log(job_id, '5d1e0f Arquivo tempore1rio removido', 'info')
        except Exception:
            pass
        try:
            try:
                if proc and hasattr(proc, 'fechar'):
                    proc.fechar()
            except Exception:
                pass
        except Exception:
            pass


def worker_extracao_ocr(job_service, job_id: str, processos: list[str], base_output_dir: str, diretorio_saida: str) -> None:
    """Worker para extração massiva de OCR visando geração de arquivos para Doccano.

    Estratégia: para cada número de processo, procurar arquivos na pasta de uploads cujo
    nome contenha o número (apenas dígitos) e aplicar OCR (texto bruto + mascaramento básico).
    Gera arquivos JSONL por tipo de documento em base_output_dir/diretorio_saida.
    """
    import os
    import re
    import json
    import time
    import traceback
    from datetime import datetime
    from modular_app.utils.ocr_extractor import extrair_campos_ocr_mistral

    def _digits(s: str) -> str:
        return re.sub(r"\D", "", s or "")

    def _tipo_arquivo(nome: str) -> str:
        n = (nome or "").lower()
        if any(k in n for k in ["crnm", "rnm", "rnM", "carteira", "registro nacional"]):
            return "CRNM"
        if "cpf" in n:
            return "CPF"
        if "antecedente" in n and ("brasil" in n or "nacional" in n):
            return "Antecedentes_BR"
        if "antecedente" in n and ("origem" in n or "pais" in n or "country" in n):
            return "Antecedentes_Origem"
        if any(k in n for k in ["portugues", "português", "comunicacao", "comunicação", "lingua", "língua"]):
            return "Portugues"
        if any(k in n for k in ["residencia", "residência"]):
            return "RESIDENCIA"
        if any(k in n for k in ["viagem", "passaporte"]):
            return "VIAGEM"
        return "OUTROS"

    def _mascarar_basico(texto: str) -> str:
        if not texto:
            return texto
        import re
        t = texto
        t = re.sub(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b", "[CPF MASCARADO]", t)
        t = re.sub(r"\b\d{11}\b", "[CPF MASCARADO]", t)
        t = re.sub(r"CPF:\s*\d{3}\.\d{3}\.\d{3}-\d{2}", "CPF: [MASCARADO]", t)
        t = re.sub(r"\b\d{2}\.\d{3}\.\d{3}-[0-9X]\b", "[RG MASCARADO]", t)
        t = re.sub(r"RG:\s*\d{2}\.\d{3}\.\d{3}-[0-9X]", "RG: [MASCARADO]", t)
        t = re.sub(r"\b\d{5}-\d{3}\b", "[CEP MASCARADO]", t)
        t = re.sub(r"\(\d{2}\)\s*\d{4,5}-\d{4}", "[TELEFONE MASCARADO]", t)
        return t

    try:
        # Preparação
        job_service.update(job_id, status='running', message='Preparando ambiente...', progress=5)
        job_service.log(job_id, 'Iniciando extração massiva de OCR...', 'info')

        output_root = os.path.abspath(os.path.join(base_output_dir, diretorio_saida))
        os.makedirs(output_root, exist_ok=True)
        job_service.log(job_id, f"Diretório de saída: {output_root}", 'info')

        upload_dir = os.path.abspath(base_output_dir)
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir, exist_ok=True)
        job_service.log(job_id, f"Diretório de uploads base: {upload_dir}", 'info')

        total = len(processos or [])
        processados = 0
        erros = 0

        # Abrir arquivos JSONL por tipo (append)
        arquivos_por_tipo = {
            'CRNM': os.path.join(output_root, 'crnm.jsonl'),
            'CPF': os.path.join(output_root, 'cpf.jsonl'),
            'Antecedentes_BR': os.path.join(output_root, 'antecedentes_br.jsonl'),
            'Antecedentes_Origem': os.path.join(output_root, 'antecedentes_origem.jsonl'),
            'Portugues': os.path.join(output_root, 'portugues.jsonl'),
            'OUTROS': os.path.join(output_root, 'outros.jsonl'),
        }
        resumo = {k: {'total': 0, 'validados': 0, 'nao_validados': 0, 'arquivo_doccano': os.path.basename(v)} for k, v in arquivos_por_tipo.items()}

        # Loop principal
        for i, proc in enumerate(processos or [], 1):
            if _should_stop(job_service, job_id):
                job_service.update(job_id, status='stopped', message='Parado pelo usuário', progress=90)
                job_service.log(job_id, '🛑 Execução interrompida pelo usuário', 'warning')
                break

            proc_digits = _digits(proc)
            job_service.update(job_id, status='running', message=f'Processando {i}/{total}...', progress=int(5 + (i/ max(1,total))*90), results={'total': total, 'processados': processados, 'erros': erros, 'processo_atual': proc})
            job_service.log(job_id, f'[BUSCA] Processo {proc} (digits={proc_digits})', 'info')

            # Buscar candidatos na pasta de uploads
            candidatos = []
            try:
                for root, _, files in os.walk(upload_dir):
                    for fn in files:
                        if proc_digits and proc_digits in re.sub(r"\D", "", fn):
                            if fn.lower().endswith(('.pdf', '.jpg', '.jpeg', '.png')):
                                candidatos.append(os.path.join(root, fn))
                if not candidatos:
                    job_service.log(job_id, f'[AVISO] Nenhum arquivo encontrado para {proc}', 'warning')
            except Exception as e:
                job_service.log(job_id, f'[ERRO] Falha ao buscar arquivos para {proc}: {e}', 'error')
                erros += 1
                continue

            # Processar candidatos
            for caminho in candidatos:
                if _should_stop(job_service, job_id):
                    break
                nome = os.path.basename(caminho)
                tipo = _tipo_arquivo(nome)
                if tipo in ('RESIDENCIA', 'VIAGEM'):
                    job_service.log(job_id, f'[SKIP] {nome} ignorado por política (residência/viagem)', 'info')
                    continue

                job_service.log(job_id, f'[OCR] {nome} (tipo={tipo})', 'info')
                try:
                    res = extrair_campos_ocr_mistral(caminho, modo_texto_bruto=True, max_retries=1, max_paginas=1)
                except Exception as e:
                    job_service.log(job_id, f'[ERRO] Falha no OCR de {nome}: {e}', 'error')
                    erros += 1
                    continue

                texto = (res or {}).get('texto_bruto')
                if texto:
                    try:
                        from data_protection import limpar_texto_ocr as _limpar
                        texto = _limpar(texto)
                        job_service.log(job_id, f'[LGPD] Mascaramento aplicado (externo) em {nome}', 'info')
                    except Exception:
                        texto = _mascarar_basico(texto)
                        job_service.log(job_id, f'[LGPD] Mascaramento básico aplicado em {nome}', 'info')

                # Registrar no JSONL
                try:
                    payload = {"text": texto or "", "meta": {"processo": proc, "arquivo": nome, "tipo": tipo}}
                    with open(arquivos_por_tipo.get(tipo, arquivos_por_tipo['OUTROS']), 'a', encoding='utf-8') as f:
                        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
                    resumo_key = tipo if tipo in resumo else 'OUTROS'
                    resumo[resumo_key]['total'] += 1
                    if texto and texto.strip():
                        resumo[resumo_key]['validados'] += 1
                    else:
                        resumo[resumo_key]['nao_validados'] += 1
                except Exception as e:
                    job_service.log(job_id, f'[ERRO] Falha ao salvar JSONL para {nome}: {e}', 'error')
                    erros += 1

            processados += 1

        # Salvar resumo
        try:
            resumo_path = os.path.join(output_root, 'resumo_extracao.json')
            with open(resumo_path, 'w', encoding='utf-8') as f:
                json.dump({'resumo_por_tipo': resumo, 'gerado_em': datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
            job_service.log(job_id, f'[SALVO] Resumo: {os.path.basename(resumo_path)}', 'success')
        except Exception as e:
            job_service.log(job_id, f'[AVISO] Não foi possível salvar resumo: {e}', 'warning')

        resultado_final = {
            'total': total,
            'processados': processados,
            'erros': erros,
            'diretorio_saida': output_root,
            'resumo_por_tipo': resumo,
            'arquivos_doccano': {k: os.path.basename(v) for k, v in arquivos_por_tipo.items()},
        }
        job_service.set_result(job_id, resultado_final)
        job_service.update(job_id, status='completed', message='Concluído', progress=100)
        job_service.log(job_id, '🏁 Extração massiva concluída', 'success')

    except Exception as e:
        job_service.log(job_id, f'[ERRO] Erro geral: {str(e)}', 'error')
        job_service.log(job_id, traceback.format_exc(), 'error')
        job_service.update(job_id, status='error', message=str(e), progress=0)

def worker_aprovacao_parecer(job_service, job_id: str, modo_selecao: str, caminho_planilha: Optional[str]) -> None:
    """Worker para Aprovação de Parecer do Analista usando JobService (refatorado).
    Usa AnalistaProcessor da arquitetura modular.
    """
    from automation.services.analista_processor import AnalistaProcessor
    import os

    processor = None
    try:
        job_service.update(job_id, status='running', message='Inicializando...', detail='Configurando automação (refatorado)', progress=15)
        job_service.log(job_id, f'Iniciando módulo de aprovação de parecer do analista no modo {modo_selecao} (refatorado)...', 'info')
        if modo_selecao == 'planilha' and caminho_planilha:
            job_service.log(job_id, f'Planilha carregada: {os.path.basename(caminho_planilha)}', 'info')

        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        chrome_options = Options()
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=chrome_options)
        driver.maximize_window()
        processor = AnalistaProcessor(driver)
        job_service.update(job_id, status='running', message='Inicializando Driver...', detail='Abrindo navegador VISUAL', progress=25)
        job_service.log(job_id, 'Processor de analista inicializado em MODO VISUAL (refatorado)', 'success')

        job_service.update(job_id, status='running', message='Executando Processo...', detail='Processando aprovações de parecer', progress=35)
        job_service.log(job_id, 'Iniciando processo de aprovação de parecer do analista (refatorado)...', 'info')

        if _should_stop(job_service, job_id):
            job_service.update(job_id, status='stopped', message='Execução Interrompida', detail='Parado pelo usuário', progress=50)
            job_service.log(job_id, '🛑 Execução interrompida pelo usuário', 'warning')
            return

        resultados = processor.executar(modo=modo_selecao, caminho_planilha=caminho_planilha)
        if resultados:
            job_service.update(job_id, status='completed', message='Processo Concluído', detail='Todas as aprovações processadas', progress=100)
            total = len(resultados)
            cpmig = len([p for p in resultados if p.get('status') == 'ENVIAR PARA CPMIG'])
            manual = len([p for p in resultados if p.get('status') == 'ANÁLISE MANUAL'])
            job_service.log(job_id, f'[DADOS] Resumo: {total} processos | CPMIG: {cpmig} | Manual: {manual}', 'info')
        else:
            job_service.update(job_id, status='error', message='Processo Finalizado com Problemas', detail='Nenhum processo foi processado', progress=90)

    except Exception as e:
        job_service.update(job_id, status='error', message='Erro na Execução', detail=str(e), progress=0)
        job_service.log(job_id, f'[ERRO] Erro durante execução: {str(e)}', 'error')
    finally:
        if processor:
            try:
                if hasattr(processor, 'lecom') and hasattr(processor.lecom, 'driver'):
                    processor.lecom.driver.quit()
                job_service.log(job_id, '[OK] Recursos limpos e driver fechado', 'info')
            except Exception:
                pass
        try:
            if caminho_planilha and os.path.exists(caminho_planilha):
                # Remover apenas arquivos salvos em temp (upload do request)
                norm = os.path.normpath(caminho_planilha)
                parts = set(norm.split(os.sep))
                if 'temp' in parts:
                    os.remove(caminho_planilha)
                    job_service.log(job_id, '🗑️ Arquivo temporário removido', 'info')
                else:
                    job_service.log(job_id, f'[SKIP] Arquivo preservado: {os.path.basename(caminho_planilha)}', 'info')
        except Exception as e:
            job_service.log(job_id, f'[AVISO] Erro ao tratar arquivo: {e}', 'warning')
