"""API REST v2 com documentação OpenAPI/Swagger automática.

Este módulo substitui/complementa api.py com Flask-RESTX para:
- Documentação automática (Swagger UI em /api/v2/doc)
- Validação de schemas
- Modelos tipados
- Respostas padronizadas
"""
from flask import request
from flask_restx import Api, Namespace, Resource, fields
from werkzeug.datastructures import FileStorage

from modular_app.utils.api_response import (
    success_response,
    error_response,
    bad_request,
    internal_error,
    async_task_response
)

# Configurar API com documentação
api = Api(
    version='2.0',
    title='Naturalização API',
    description='API REST para automação de processos de naturalização',
    doc='/doc',
    prefix='/api/v2',
    # Configurar autorização (se necessário)
    authorizations={
        'apikey': {
            'type': 'apiKey',
            'in': 'header',
            'name': 'X-API-KEY'
        }
    }
)

# Namespaces (agrupamento de endpoints)
ns_health = api.namespace('health', description='Health checks e status do sistema')
ns_ordinaria = api.namespace('ordinaria', description='Operações de análise ordinária')
ns_provisoria = api.namespace('provisoria', description='Operações de análise provisória')
ns_definitiva = api.namespace('definitiva', description='Operações de análise definitiva')
ns_tasks = api.namespace('tasks', description='Monitoramento de tarefas assíncronas')

# ============================================================================
# MODELOS (Schemas)
# ============================================================================

# Modelo de resposta padrão
response_meta = api.model('ResponseMeta', {
    'timestamp': fields.String(description='Timestamp da resposta'),
})

success_response_model = api.model('SuccessResponse', {
    'success': fields.Boolean(required=True, description='Indica se operação foi bem-sucedida'),
    'message': fields.String(required=True, description='Mensagem descritiva'),
    'data': fields.Raw(description='Dados da resposta'),
    'meta': fields.Nested(response_meta, description='Metadados'),
})

error_response_model = api.model('ErrorResponse', {
    'success': fields.Boolean(required=True, description='Sempre False para erros'),
    'error': fields.Nested(api.model('Error', {
        'message': fields.String(required=True),
        'code': fields.String(description='Código do erro'),
        'details': fields.Raw(description='Detalhes técnicos'),
    })),
    'data': fields.Raw(description='Sempre None para erros'),
    'meta': fields.Nested(response_meta),
})

# Modelo de processo
processo_input = api.model('ProcessoInput', {
    'numero_processo': fields.String(
        required=True,
        description='Número do processo',
        example='123456789'
    ),
})

processo_result = api.model('ProcessoResult', {
    'codigo': fields.String(description='Código do processo'),
    'status': fields.String(description='Status do processamento'),
    'elegibilidade_final': fields.String(description='Resultado da elegibilidade'),
    'motivos_indeferimento': fields.List(fields.String, description='Motivos de indeferimento'),
})

# Modelo de upload
upload_parser = api.parser()
upload_parser.add_argument('file', location='files', type=FileStorage, required=True, help='Planilha Excel ou CSV')
upload_parser.add_argument('column_name', type=str, default='codigo', help='Nome da coluna com códigos')

# Modelo de task assíncrona
task_response = api.model('TaskResponse', {
    'task_id': fields.String(required=True, description='ID da tarefa Celery'),
    'status': fields.String(description='Status atual (pending, running, completed, failed)'),
    'status_url': fields.String(description='URL para consultar status'),
})

task_status = api.model('TaskStatus', {
    'task_id': fields.String(required=True),
    'status': fields.String(required=True, description='pending, running, completed, failed'),
    'progress': fields.Integer(description='Progresso (0-100)'),
    'message': fields.String(description='Mensagem de status'),
    'result': fields.Raw(description='Resultado da tarefa (se concluída)'),
})

# ============================================================================
# ENDPOINTS - HEALTH
# ============================================================================

@ns_health.route('/ping')
class HealthPing(Resource):
    """Endpoint simples para verificar se API está rodando."""
    
    @ns_health.doc('health_ping')
    @ns_health.response(200, 'Success', success_response_model)
    def get(self):
        """Retorna pong se API está ativa."""
        return success_response(
            data={'pong': True},
            message='API está ativa'
        )


@ns_health.route('/status')
class HealthStatus(Resource):
    """Status detalhado do sistema."""
    
    @ns_health.doc('health_status')
    @ns_health.response(200, 'Success', success_response_model)
    def get(self):
        """Retorna informações detalhadas do sistema."""
        import sys
        from datetime import datetime
        
        data = {
            'status': 'healthy',
            'version': '2.0.0',
            'python_version': sys.version,
            'timestamp': datetime.now().isoformat(),
        }
        
        # Verificar conexão com Redis (Celery)
        try:
            from celery_app import celery
            celery.control.inspect().stats()
            data['celery_status'] = 'connected'
        except Exception as e:
            data['celery_status'] = 'disconnected'
            data['celery_error'] = str(e)
        
        return success_response(data=data, message='Sistema operacional')


# ============================================================================
# ENDPOINTS - ORDINÁRIA
# ============================================================================

@ns_ordinaria.route('/processar')
class OrdinariaProcessar(Resource):
    """Processamento de análise ordinária (síncrono)."""
    
    @ns_ordinaria.doc('ordinaria_processar_sync')
    @ns_ordinaria.expect(processo_input)
    @ns_ordinaria.response(200, 'Success', success_response_model)
    @ns_ordinaria.response(400, 'Bad Request', error_response_model)
    @ns_ordinaria.response(500, 'Internal Error', error_response_model)
    def post(self):
        """Processa um processo ordinário de forma síncrona.
        
        Este endpoint executa o processamento imediatamente e aguarda
        a conclusão antes de retornar. Use apenas para testes ou processos
        individuais. Para lotes, use o endpoint assíncrono.
        """
        data = request.get_json()
        numero = data.get('numero_processo')
        
        if not numero:
            return bad_request(
                message='Campo numero_processo é obrigatório',
                details={'field': 'numero_processo'}
            )
        
        try:
            from automation.services.ordinaria_processor import processar_processo_ordinaria
            resultado = processar_processo_ordinaria(numero)
            
            return success_response(
                data={
                    'sucesso': bool(resultado.get('sucesso')),
                    'status': resultado.get('status'),
                    'elegibilidade_final': resultado.get('elegibilidade_final'),
                    'motivos_indeferimento': resultado.get('motivos_indeferimento', []),
                },
                message='Processo analisado com sucesso'
            )
        except Exception as e:
            return internal_error(
                message='Erro ao processar processo',
                details=str(e)
            )


@ns_ordinaria.route('/processar-lote')
class OrdinariaProcessarLote(Resource):
    """Processamento de lote ordinário (assíncrono com Celery)."""
    
    @ns_ordinaria.doc('ordinaria_processar_lote')
    @ns_ordinaria.expect(upload_parser)
    @ns_ordinaria.response(202, 'Accepted', api.model('AsyncTaskResponse', {
        'success': fields.Boolean(),
        'message': fields.String(),
        'data': fields.Nested(task_response),
        'meta': fields.Nested(response_meta),
    }))
    @ns_ordinaria.response(400, 'Bad Request', error_response_model)
    def post(self):
        """Inicia processamento em lote de processos ordinários.
        
        Este endpoint aceita uma planilha (Excel/CSV) e inicia uma tarefa
        assíncrona para processar todos os códigos. Retorna imediatamente
        com um task_id para acompanhamento.
        """
        if 'file' not in request.files:
            return bad_request(
                message='Arquivo não fornecido',
                details='Envie um arquivo Excel ou CSV no campo "file"'
            )
        
        file = request.files['file']
        column_name = request.form.get('column_name', 'codigo')
        
        if file.filename == '':
            return bad_request(message='Nome de arquivo vazio')
        
        # Salvar arquivo temporário
        import os
        from werkzeug.utils import secure_filename
        filename = secure_filename(file.filename)
        temp_dir = os.path.join(os.getcwd(), 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        filepath = os.path.join(temp_dir, filename)
        file.save(filepath)
        
        # Enfileirar task Celery
        try:
            from modular_app.tasks.celery_tasks import task_analise_ordinaria
            task = task_analise_ordinaria.delay(filepath, column_name)
            
            return async_task_response(
                task_id=task.id,
                message='Processamento em lote iniciado',
                task_url=f'/api/v2/tasks/{task.id}'
            )
        except Exception as e:
            return internal_error(
                message='Erro ao iniciar processamento',
                details=str(e)
            )


# ============================================================================
# ENDPOINTS - TASKS
# ============================================================================

@ns_tasks.route('/<string:task_id>')
@ns_tasks.param('task_id', 'ID da tarefa Celery')
class TaskStatus(Resource):
    """Consulta status de tarefa assíncrona."""
    
    @ns_tasks.doc('task_status')
    @ns_tasks.response(200, 'Success', api.model('TaskStatusResponse', {
        'success': fields.Boolean(),
        'message': fields.String(),
        'data': fields.Nested(task_status),
        'meta': fields.Nested(response_meta),
    }))
    @ns_tasks.response(404, 'Not Found', error_response_model)
    def get(self, task_id):
        """Retorna o status atual de uma tarefa.
        
        Estados possíveis:
        - PENDING: Aguardando execução
        - STARTED: Em execução
        - PROGRESS: Em andamento (com informações de progresso)
        - SUCCESS: Concluída com sucesso
        - FAILURE: Falhou
        - RETRY: Sendo reexecutada
        """
        try:
            from celery.result import AsyncResult
            task = AsyncResult(task_id)
            
            response_data = {
                'task_id': task_id,
                'status': task.state,
            }
            
            if task.state == 'PENDING':
                response_data['message'] = 'Tarefa aguardando execução'
            elif task.state == 'STARTED':
                response_data['message'] = 'Tarefa iniciada'
            elif task.state == 'PROGRESS':
                response_data['message'] = 'Em andamento'
                response_data.update(task.info or {})
            elif task.state == 'SUCCESS':
                response_data['message'] = 'Concluída com sucesso'
                response_data['result'] = task.result
            elif task.state == 'FAILURE':
                response_data['message'] = 'Falhou'
                response_data['error'] = str(task.info)
            
            return success_response(
                data=response_data,
                message=f'Status da tarefa: {task.state}'
            )
        except Exception as e:
            return internal_error(
                message='Erro ao consultar tarefa',
                details=str(e)
            )


# ============================================================================
# ADICIONAR MAIS NAMESPACES CONFORME NECESSÁRIO
# ============================================================================
# - ns_provisoria.route('/processar')
# - ns_definitiva.route('/processar')
# - ns_aprovacoes (aprovação de parecer, recursos, etc.)
