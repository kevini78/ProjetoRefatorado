#!/usr/bin/env python3
"""
CAMADA 4: LOGS DE AUDITORIA COMPLETOS PARA TODAS AS OPERAÇÕES
Arquivo: logging_config.py
"""

import os
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional

class SecurityAuditLogger:
    """
    Sistema de logging de auditoria para todas as operações
    CAMADA 4: Logs de auditoria completos
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._setup_audit_logging()
        
    def _setup_audit_logging(self):
        """Configura sistema de logging de auditoria"""
        # Criar diretório de logs se não existir
        if not os.path.exists('logs'):
            os.makedirs('logs')
            
        # Configurar logger de auditoria
        audit_logger = logging.getLogger('audit')
        audit_logger.setLevel(logging.INFO)
        
        # Handler para arquivo de auditoria
        audit_handler = logging.FileHandler('logs/audit.log')
        audit_handler.setLevel(logging.INFO)
        
        # Formato do log de auditoria
        audit_formatter = logging.Formatter(
            '%(asctime)s - AUDIT - %(levelname)s - %(message)s'
        )
        audit_handler.setFormatter(audit_formatter)
        audit_logger.addHandler(audit_handler)
        
        # Handler para arquivo de segurança
        security_handler = logging.FileHandler('logs/security.log')
        security_handler.setLevel(logging.INFO)
        
        security_formatter = logging.Formatter(
            '%(asctime)s - SECURITY - %(levelname)s - %(message)s'
        )
        security_handler.setFormatter(security_formatter)
        audit_logger.addHandler(security_handler)
        
        self.audit_logger = audit_logger
        
    def log_user_action(self, user_id: str, action: str, resource: str, 
                       success: bool = True, details: Optional[Dict] = None):
        """
        Registra ação do usuário
        
        Args:
            user_id: ID do usuário
            action: Ação realizada
            resource: Recurso acessado
            success: Se a ação foi bem-sucedida
            details: Detalhes adicionais
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': 'USER_ACTION',
            'user_id': user_id,
            'action': action,
            'resource': resource,
            'success': success,
            'details': details or {}
        }
        
        self.audit_logger.info(f"USER_ACTION: {json.dumps(log_entry, ensure_ascii=False)}")
        
    def log_data_access(self, user_id: str, data_type: str, operation: str, 
                       success: bool = True, record_count: int = 0):
        """
        Registra acesso a dados
        
        Args:
            user_id: ID do usuário
            data_type: Tipo de dados acessados
            operation: Operação realizada (read, write, delete)
            success: Se a operação foi bem-sucedida
            record_count: Número de registros processados
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': 'DATA_ACCESS',
            'user_id': user_id,
            'data_type': data_type,
            'operation': operation,
            'success': success,
            'record_count': record_count
        }
        
        self.audit_logger.info(f"DATA_ACCESS: {json.dumps(log_entry, ensure_ascii=False)}")
        
    def log_security_event(self, event_type: str, user_id: str, details: Dict, 
                          ip_address: Optional[str] = None):
        """
        Registra evento de segurança
        
        Args:
            event_type: Tipo do evento de segurança
            user_id: ID do usuário
            details: Detalhes do evento
            ip_address: Endereço IP (opcional)
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': 'SECURITY_EVENT',
            'security_event_type': event_type,
            'user_id': user_id,
            'ip_address': ip_address or 'N/A',
            'details': details
        }
        
        self.audit_logger.warning(f"SECURITY_EVENT: {json.dumps(log_entry, ensure_ascii=False)}")
        
    def log_system_event(self, event_type: str, component: str, message: str, 
                        level: str = 'INFO'):
        """
        Registra evento do sistema
        
        Args:
            event_type: Tipo do evento
            component: Componente do sistema
            message: Mensagem do evento
            level: Nível do log (INFO, WARNING, ERROR)
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': 'SYSTEM_EVENT',
            'system_event_type': event_type,
            'component': component,
            'message': message,
            'level': level
        }
        
        if level == 'ERROR':
            self.audit_logger.error(f"SYSTEM_EVENT: {json.dumps(log_entry, ensure_ascii=False)}")
        elif level == 'WARNING':
            self.audit_logger.warning(f"SYSTEM_EVENT: {json.dumps(log_entry, ensure_ascii=False)}")
        else:
            self.audit_logger.info(f"SYSTEM_EVENT: {json.dumps(log_entry, ensure_ascii=False)}")
            
    def log_ocr_processing(self, user_id: str, file_name: str, file_size: int, 
                          processing_time: float, success: bool = True, 
                          extracted_fields: int = 0):
        """
        Registra processamento OCR
        
        Args:
            user_id: ID do usuário
            file_name: Nome do arquivo processado
            file_size: Tamanho do arquivo em bytes
            processing_time: Tempo de processamento em segundos
            success: Se o processamento foi bem-sucedido
            extracted_fields: Número de campos extraídos
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': 'OCR_PROCESSING',
            'user_id': user_id,
            'file_name': file_name,
            'file_size': file_size,
            'processing_time': processing_time,
            'success': success,
            'extracted_fields': extracted_fields
        }
        
        self.audit_logger.info(f"OCR_PROCESSING: {json.dumps(log_entry, ensure_ascii=False)}")
        
    def log_data_sanitization(self, user_id: str, data_type: str, 
                             original_size: int, sanitized_size: int, 
                             masked_fields: int):
        """
        Registra sanitização de dados
        
        Args:
            user_id: ID do usuário
            data_type: Tipo de dados sanitizados
            original_size: Tamanho original dos dados
            sanitized_size: Tamanho após sanitização
            masked_fields: Número de campos mascarados
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': 'DATA_SANITIZATION',
            'user_id': user_id,
            'data_type': data_type,
            'original_size': original_size,
            'sanitized_size': sanitized_size,
            'masked_fields': masked_fields
        }
        
        self.audit_logger.info(f"DATA_SANITIZATION: {json.dumps(log_entry, ensure_ascii=False)}")
        
    def log_file_operations(self, user_id: str, operation: str, file_path: str, 
                           file_size: int, success: bool = True):
        """
        Registra operações de arquivo
        
        Args:
            user_id: ID do usuário
            operation: Operação realizada (upload, download, delete, encrypt, decrypt)
            file_path: Caminho do arquivo
            file_size: Tamanho do arquivo em bytes
            success: Se a operação foi bem-sucedida
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': 'FILE_OPERATION',
            'user_id': user_id,
            'operation': operation,
            'file_path': file_path,
            'file_size': file_size,
            'success': success
        }
        
        self.audit_logger.info(f"FILE_OPERATION: {json.dumps(log_entry, ensure_ascii=False)}")
        
    def generate_audit_report(self, start_date: Optional[datetime] = None, 
                            end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Gera relatório de auditoria
        
        Args:
            start_date: Data de início (opcional)
            end_date: Data de fim (opcional)
            
        Returns:
            Relatório de auditoria
        """
        # Implementar geração de relatório baseado nos logs
        report = {
            'generated_at': datetime.now().isoformat(),
            'period': {
                'start': start_date.isoformat() if start_date else None,
                'end': end_date.isoformat() if end_date else None
            },
            'summary': {
                'total_events': 0,
                'user_actions': 0,
                'data_access': 0,
                'security_events': 0,
                'system_events': 0,
                'ocr_processing': 0,
                'file_operations': 0
            }
        }
        
        return report

# Instância global
audit_logger = SecurityAuditLogger()
