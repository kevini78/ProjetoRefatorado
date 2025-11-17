"""Tasks Celery para processamento assíncrono robusto.

Este módulo migra os workers manuais (threads) para tasks Celery,
adicionando persistência, retry automático e monitoramento.
"""
import os
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from celery import Task
from celery_app import celery


class CallbackTask(Task):
    """Task base com callbacks para atualização de estado."""
    
    def on_success(self, retval, task_id, args, kwargs):
        """Chamado quando task completa com sucesso."""
        print(f"✓ Task {task_id} completada com sucesso")
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Chamado quando task falha."""
        print(f"✗ Task {task_id} falhou: {exc}")
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Chamado quando task é reexecutada."""
        print(f"↻ Task {task_id} sendo reexecutada: {exc}")


@celery.task(base=CallbackTask, bind=True, name='modular_app.tasks.defere_indefere')
def task_defere_indefere(self, filepath: str, column_name: str) -> Dict[str, Any]:
    """Task para Defere/Indefere Recurso usando Celery.
    
    Args:
        filepath: Caminho para arquivo com códigos dos processos
        column_name: Nome da coluna com os códigos
        
    Returns:
        Dict com resumo do processamento
    """
    from automation.services.recurso_processor import RecursoProcessor
    
    processor = None
    try:
        # Atualizar estado inicial
        self.update_state(
            state='PROGRESS',
            meta={'status': 'initializing', 'progress': 15, 'message': 'Inicializando...'}
        )
        
        # Criar driver e processor
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        chrome_options = Options()
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=chrome_options)
        processor = RecursoProcessor(driver)
        
        # Login
        self.update_state(
            state='PROGRESS',
            meta={'status': 'login', 'progress': 25, 'message': 'Fazendo login...'}
        )
        
        if not processor.lecom.fazer_login():
            raise Exception('Falha no login - processo cancelado')
        
        # Ler planilha
        self.update_state(
            state='PROGRESS',
            meta={'status': 'reading', 'progress': 35, 'message': 'Lendo planilha...'}
        )
        
        codigos: List[str] = processor.ler_codigos_planilha(filepath, column_name)
        if not codigos:
            raise Exception('Nenhum código encontrado na planilha')
        
        # Processar códigos
        total = len(codigos)
        resultados: List[Dict[str, Any]] = []
        
        for i, codigo in enumerate(codigos, 1):
            progress = int((i / max(1, total)) * 100)
            self.update_state(
                state='PROGRESS',
                meta={
                    'status': 'processing',
                    'progress': progress,
                    'current': i,
                    'total': total,
                    'codigo': codigo,
                    'message': f'Processando {i}/{total}...'
                }
            )
            
            resultado = processor.processar_codigo(codigo)
            resultados.append(resultado)
            time.sleep(0.5)  # Rate limiting
        
        # Salvar resultados
        sucessos = len([r for r in resultados if r.get('status') == 'sucesso'])
        erros = len([r for r in resultados if r.get('status') == 'erro'])
        decisoes_enviadas = len([r for r in resultados if r.get('decisao_enviada', False)])
        
        summary = {
            'total_processados': len(resultados),
            'sucessos': sucessos,
            'erros': erros,
            'decisoes_enviadas': decisoes_enviadas,
            'arquivo_original': filepath,
            'resultados': resultados,
        }
        
        # Salvar planilha
        try:
            import pandas as pd
            df = pd.DataFrame(resultados)
            planilhas_dir = os.path.join(os.getcwd(), 'planilhas')
            os.makedirs(planilhas_dir, exist_ok=True)
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            out_name = f'resultados_defere_indefere_{ts}.xlsx'
            out_path = os.path.join(planilhas_dir, out_name)
            df.to_excel(out_path, index=False)
            summary['planilha_resultado'] = out_name
        except Exception as e:
            summary['erro_planilha'] = str(e)
        
        return summary
        
    except Exception as e:
        # Retry automático em caso de erro
        raise self.retry(exc=e, countdown=60, max_retries=3)
        
    finally:
        # Cleanup
        if processor:
            try:
                if hasattr(processor, 'lecom') and hasattr(processor.lecom, 'driver'):
                    processor.lecom.driver.quit()
            except Exception:
                pass
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception:
            pass


@celery.task(base=CallbackTask, bind=True, name='modular_app.tasks.analise_ordinaria')
def task_analise_ordinaria(self, filepath: str, column_name: str = 'codigo') -> Dict[str, Any]:
    """Task para Análise Automática do tipo Ordinária.
    
    Args:
        filepath: Caminho para arquivo com códigos dos processos
        column_name: Nome da coluna com os códigos
        
    Returns:
        Dict com resumo do processamento
    """
    import pandas as pd
    from automation.services.ordinaria_processor import OrdinariaProcessor
    
    proc = None
    try:
        # Atualizar estado
        self.update_state(
            state='PROGRESS',
            meta={'status': 'initializing', 'progress': 10, 'message': 'Inicializando...'}
        )
        
        # Ler códigos
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
            serie = serie.str.replace('.', '', regex=False).str.replace(',', '', regex=False)
            return serie.tolist()
        
        codigos = _ler_codigos(filepath, column_name)
        if not codigos:
            raise Exception('Nenhum código encontrado na planilha')
        
        # Inicializar Processor
        self.update_state(
            state='PROGRESS',
            meta={'status': 'setup', 'progress': 15, 'message': 'Abrindo navegador...'}
        )
        
        proc = OrdinariaProcessor(driver=None)
        
        # Login
        self.update_state(
            state='PROGRESS',
            meta={'status': 'login', 'progress': 20, 'message': 'Fazendo login...'}
        )
        
        if not proc.lecom_action.login():
            raise Exception('Falha no login no LECOM (Ordinária)')
        
        proc.lecom_action.ja_logado = True
        
        # Processar
        resultados = []
        total = len(codigos)
        
        for i, codigo in enumerate(codigos, 1):
            progress = int(20 + (i / max(1, total)) * 70)
            self.update_state(
                state='PROGRESS',
                meta={
                    'status': 'processing',
                    'progress': progress,
                    'current': i,
                    'total': total,
                    'codigo': codigo,
                    'message': f'Processando {i}/{total}...'
                }
            )
            
            try:
                resultado = proc.processar_processo(codigo)
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
        
        # Salvar usando serviço unificado
        try:
            from modular_app.services.unified_results_service import UnifiedResultsService
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            unified_service = UnifiedResultsService()
            out_path = unified_service.salvar_lote_ordinaria(resultados, timestamp=ts)
            out_name = os.path.basename(out_path)
        except Exception as e:
            out_name = f'erro_salvar: {str(e)}'
        
        summary = {
            'total_processados': len(resultados),
            'sucessos': len([r for r in resultados if str(r.get('status', '')).lower() in ('sucesso', 'processado com sucesso')]),
            'erros': len([r for r in resultados if str(r.get('status', '')).lower() not in ('sucesso', 'processado com sucesso')]),
            'arquivo_original': filepath,
            'planilha_resultado': out_name,
        }
        
        return summary
        
    except Exception as e:
        raise self.retry(exc=e, countdown=60, max_retries=3)
        
    finally:
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception:
            pass
        try:
            if proc and hasattr(proc, 'fechar'):
                proc.fechar()
        except Exception:
            pass


@celery.task(base=CallbackTask, bind=True, name='modular_app.tasks.aprovacao_lote')
def task_aprovacao_lote(self, max_iteracoes: int, modo_execucao: str, tempo_espera_minutos: int = 10) -> Dict[str, Any]:
    """Task para Aprovação em Lote.
    
    Args:
        max_iteracoes: Número máximo de iterações
        modo_execucao: 'continuo' ou 'unico'
        tempo_espera_minutos: Tempo de espera entre ciclos
        
    Returns:
        Dict com resumo do processamento
    """
    from automation.services.lote_processor import LoteProcessor
    
    processor = None
    try:
        self.update_state(
            state='PROGRESS',
            meta={'status': 'initializing', 'progress': 15, 'message': 'Inicializando...'}
        )
        
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        chrome_options = Options()
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=chrome_options)
        driver.maximize_window()
        processor = LoteProcessor(driver)
        
        if modo_execucao == 'continuo':
            ciclos_executados = 0
            for i in range(max_iteracoes):
                progress = int(35 + (i / max(1, max_iteracoes)) * 50)
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'status': 'processing',
                        'progress': progress,
                        'ciclo': i + 1,
                        'total_ciclos': max_iteracoes,
                        'message': f'Ciclo {i+1}/{max_iteracoes}'
                    }
                )
                
                resultado_ciclo = processor.executar()
                if resultado_ciclo:
                    ciclos_executados += 1
                
                if i < max_iteracoes - 1:
                    # Espera entre ciclos
                    total_seg = max(1, tempo_espera_minutos) * 60
                    time.sleep(total_seg)
            
            return {
                'modo': 'continuo',
                'ciclos_executados': ciclos_executados,
                'total_ciclos': max_iteracoes,
            }
        else:
            self.update_state(
                state='PROGRESS',
                meta={'status': 'processing', 'progress': 50, 'message': 'Execução única...'}
            )
            
            if processor.executar():
                return {'modo': 'unico', 'status': 'sucesso'}
            else:
                raise Exception('Falha na execução única')
        
    except Exception as e:
        raise self.retry(exc=e, countdown=60, max_retries=2)
        
    finally:
        if processor:
            try:
                if hasattr(processor, 'lecom') and hasattr(processor.lecom, 'driver'):
                    processor.lecom.driver.quit()
            except Exception:
                pass


# ============================================================================
# TASKS PERIÓDICAS (para usar com Celery Beat)
# ============================================================================

@celery.task(name='modular_app.tasks.celery_tasks.task_limpar_temp')
def task_limpar_temp() -> Dict[str, Any]:
    """Task periódica: Limpa arquivos temporários antigos.
    
    Agenda sugerida: A cada 10 minutos
    """
    import os
    import time
    from datetime import datetime, timedelta
    
    temp_dir = os.path.join(os.getcwd(), 'temp')
    if not os.path.exists(temp_dir):
        return {'status': 'skipped', 'reason': 'Diretório temp não existe'}
    
    removidos = 0
    erros = 0
    
    # Remover arquivos com mais de 1 hora
    limite = time.time() - 3600  # 1 hora
    
    try:
        for filename in os.listdir(temp_dir):
            filepath = os.path.join(temp_dir, filename)
            if os.path.isfile(filepath):
                if os.path.getmtime(filepath) < limite:
                    try:
                        os.remove(filepath)
                        removidos += 1
                    except Exception:
                        erros += 1
    except Exception as e:
        return {'status': 'error', 'message': str(e)}
    
    return {
        'status': 'completed',
        'arquivos_removidos': removidos,
        'erros': erros,
        'executado_em': datetime.now().isoformat(),
    }


@celery.task(name='modular_app.tasks.celery_tasks.task_health_check')
def task_health_check() -> Dict[str, Any]:
    """Task periódica: Verifica saúde do sistema.
    
    Agenda sugerida: A cada hora
    """
    import psutil
    from datetime import datetime
    
    try:
        health = {
            'timestamp': datetime.now().isoformat(),
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent if os.name != 'nt' else psutil.disk_usage('C:\\').percent,
        }
        
        # Alertas
        alerts = []
        if health['cpu_percent'] > 80:
            alerts.append('CPU acima de 80%')
        if health['memory_percent'] > 85:
            alerts.append('Memória acima de 85%')
        if health['disk_percent'] > 90:
            alerts.append('Disco acima de 90%')
        
        health['alerts'] = alerts
        health['status'] = 'warning' if alerts else 'healthy'
        
        return health
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


@celery.task(name='modular_app.tasks.celery_tasks.task_backup_diario')
def task_backup_diario() -> Dict[str, Any]:
    """Task periódica: Backup diário de dados importantes.
    
    Agenda sugerida: Todos os dias às 2h da manhã
    """
    import shutil
    from datetime import datetime
    
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = os.path.join(os.getcwd(), 'backups', timestamp)
        os.makedirs(backup_dir, exist_ok=True)
        
        # Backup da base de dados
        db_path = os.path.join(os.getcwd(), 'naturalizacao.db')
        if os.path.exists(db_path):
            shutil.copy2(db_path, os.path.join(backup_dir, 'naturalizacao.db'))
        
        # Backup de planilhas (últimos 7 dias)
        planilhas_dir = os.path.join(os.getcwd(), 'planilhas')
        if os.path.exists(planilhas_dir):
            backup_planilhas = os.path.join(backup_dir, 'planilhas')
            os.makedirs(backup_planilhas, exist_ok=True)
            
            limite = time.time() - (7 * 24 * 3600)  # 7 dias
            for filename in os.listdir(planilhas_dir):
                filepath = os.path.join(planilhas_dir, filename)
                if os.path.isfile(filepath) and os.path.getmtime(filepath) > limite:
                    shutil.copy2(filepath, backup_planilhas)
        
        return {
            'status': 'completed',
            'backup_dir': backup_dir,
            'timestamp': timestamp,
        }
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


@celery.task(name='modular_app.tasks.celery_tasks.task_relatorio_semanal')
def task_relatorio_semanal() -> Dict[str, Any]:
    """Task periódica: Gera relatório semanal de atividades.
    
    Agenda sugerida: Segunda a sexta às 9h
    """
    from datetime import datetime, timedelta
    
    try:
        # Exemplo: contar arquivos processados na última semana
        planilhas_dir = os.path.join(os.getcwd(), 'planilhas')
        if not os.path.exists(planilhas_dir):
            return {'status': 'skipped', 'reason': 'Sem dados para relatório'}
        
        limite = time.time() - (7 * 24 * 3600)  # 7 dias
        arquivos_semana = 0
        
        for filename in os.listdir(planilhas_dir):
            filepath = os.path.join(planilhas_dir, filename)
            if os.path.isfile(filepath) and os.path.getmtime(filepath) > limite:
                arquivos_semana += 1
        
        return {
            'status': 'completed',
            'periodo': 'últimos 7 dias',
            'arquivos_processados': arquivos_semana,
            'gerado_em': datetime.now().isoformat(),
        }
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


@celery.task(name='modular_app.tasks.celery_tasks.task_relatorio_mensal')
def task_relatorio_mensal() -> Dict[str, Any]:
    """Task periódica: Gera relatório mensal consolidado.
    
    Agenda sugerida: Primeiro dia do mês às 8h
    """
    from datetime import datetime
    import pandas as pd
    
    try:
        # Exemplo: consolidar dados do mês anterior
        agora = datetime.now()
        mes_anterior = agora.replace(day=1) - timedelta(days=1)
        
        return {
            'status': 'completed',
            'mes_referencia': mes_anterior.strftime('%Y-%m'),
            'gerado_em': agora.isoformat(),
        }
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


# Adicionar mais tasks conforme necessário...
# task_analise_provisoria, task_analise_definitiva, task_aprovacao_parecer, etc.
