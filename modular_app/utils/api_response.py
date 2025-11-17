"""Utilitários para respostas JSON padronizadas.

Este módulo fornece funções helper para criar respostas JSON consistentes
em toda a API, seguindo as melhores práticas REST.
"""
from typing import Any, Dict, Optional, Union
from flask import jsonify
from datetime import datetime


def success_response(
    data: Any = None,
    message: str = "Operação realizada com sucesso",
    status_code: int = 200,
    meta: Optional[Dict[str, Any]] = None
) -> tuple:
    """Cria uma resposta de sucesso padronizada.
    
    Args:
        data: Dados a serem retornados
        message: Mensagem de sucesso
        status_code: Código HTTP de status
        meta: Metadados adicionais (paginação, timestamps, etc.)
        
    Returns:
        Tupla (response_json, status_code) compatível com Flask
        
    Example:
        >>> return success_response(
        ...     data={"id": 123, "name": "Processo"},
        ...     message="Processo criado com sucesso",
        ...     status_code=201
        ... )
    """
    response = {
        "success": True,
        "message": message,
        "data": data,
        "meta": meta or {},
    }
    
    # Adicionar timestamp se não estiver nos metadados
    if "timestamp" not in response["meta"]:
        response["meta"]["timestamp"] = datetime.now().isoformat()
    
    return jsonify(response), status_code


def error_response(
    message: str = "Erro ao processar requisição",
    error_code: Optional[str] = None,
    details: Optional[Union[str, Dict, list]] = None,
    status_code: int = 400,
    meta: Optional[Dict[str, Any]] = None
) -> tuple:
    """Cria uma resposta de erro padronizada.
    
    Args:
        message: Mensagem de erro amigável
        error_code: Código de erro interno (para debugging)
        details: Detalhes técnicos do erro
        status_code: Código HTTP de status
        meta: Metadados adicionais
        
    Returns:
        Tupla (response_json, status_code) compatível com Flask
        
    Example:
        >>> return error_response(
        ...     message="Código do processo inválido",
        ...     error_code="INVALID_PROCESS_CODE",
        ...     details="O código deve conter apenas números",
        ...     status_code=400
        ... )
    """
    error = {
        "message": message,
    }
    
    if error_code:
        error["code"] = error_code
    
    if details:
        error["details"] = details
    
    response = {
        "success": False,
        "error": error,
        "data": None,
        "meta": meta or {},
    }
    
    # Adicionar timestamp se não estiver nos metadados
    if "timestamp" not in response["meta"]:
        response["meta"]["timestamp"] = datetime.now().isoformat()
    
    return jsonify(response), status_code


def paginated_response(
    data: list,
    page: int,
    per_page: int,
    total: int,
    message: str = "Lista recuperada com sucesso",
    status_code: int = 200,
    extra_meta: Optional[Dict[str, Any]] = None
) -> tuple:
    """Cria uma resposta paginada padronizada.
    
    Args:
        data: Lista de itens da página atual
        page: Número da página atual
        per_page: Itens por página
        total: Total de itens
        message: Mensagem de sucesso
        status_code: Código HTTP de status
        extra_meta: Metadados adicionais
        
    Returns:
        Tupla (response_json, status_code) compatível com Flask
        
    Example:
        >>> return paginated_response(
        ...     data=processos,
        ...     page=1,
        ...     per_page=20,
        ...     total=150
        ... )
    """
    total_pages = (total + per_page - 1) // per_page  # Ceiling division
    
    meta = {
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
        "timestamp": datetime.now().isoformat(),
    }
    
    if extra_meta:
        meta.update(extra_meta)
    
    return success_response(
        data=data,
        message=message,
        status_code=status_code,
        meta=meta
    )


def async_task_response(
    task_id: str,
    message: str = "Tarefa iniciada com sucesso",
    status_code: int = 202,
    task_url: Optional[str] = None
) -> tuple:
    """Cria uma resposta para tarefas assíncronas.
    
    Args:
        task_id: ID da tarefa Celery
        message: Mensagem informativa
        status_code: Código HTTP (normalmente 202 Accepted)
        task_url: URL para consultar status da tarefa
        
    Returns:
        Tupla (response_json, status_code) compatível com Flask
        
    Example:
        >>> return async_task_response(
        ...     task_id="abc-123",
        ...     task_url="/api/v1/tasks/abc-123"
        ... )
    """
    data = {
        "task_id": task_id,
        "status": "pending",
    }
    
    if task_url:
        data["status_url"] = task_url
    
    return success_response(
        data=data,
        message=message,
        status_code=status_code,
        meta={"async": True}
    )


# Atalhos para erros HTTP comuns
def bad_request(message: str = "Requisição inválida", details: Any = None) -> tuple:
    """Atalho para erro 400 Bad Request."""
    return error_response(message=message, details=details, status_code=400)


def unauthorized(message: str = "Não autorizado") -> tuple:
    """Atalho para erro 401 Unauthorized."""
    return error_response(message=message, status_code=401)


def forbidden(message: str = "Acesso negado") -> tuple:
    """Atalho para erro 403 Forbidden."""
    return error_response(message=message, status_code=403)


def not_found(message: str = "Recurso não encontrado") -> tuple:
    """Atalho para erro 404 Not Found."""
    return error_response(message=message, status_code=404)


def conflict(message: str = "Conflito com recurso existente") -> tuple:
    """Atalho para erro 409 Conflict."""
    return error_response(message=message, status_code=409)


def internal_error(message: str = "Erro interno do servidor", details: Any = None) -> tuple:
    """Atalho para erro 500 Internal Server Error."""
    return error_response(message=message, details=details, status_code=500)
