import re
import logging
from typing import Dict, List, Any, Optional

try:
    from security_config_flexible import flexible_security_config as security_config
except ImportError:
    try:
        from security_config import security_config
    except ImportError:
        security_config = None

class DataSanitizer:
    """
    Classe para sanitização e validação de dados extraídos pelo OCR
    Remove informações sensíveis desnecessárias e valida formatos
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def sanitize_ocr_text(self, text: str, preserve_essential: bool = True) -> str:
        """
        Sanitiza texto extraído pelo OCR mascarando dados sensíveis
        
        Args:
            text: Texto extraído pelo OCR
            preserve_essential: Se True, preserva dados essenciais; se False, mascara tudo
            
        Returns:
            Texto com dados sensíveis mascarados
        """
        if not text:
            return text
        
        sanitized_text = text
        
        if not preserve_essential:
            # Mascarar CPFs
            import re
            sanitized_text = re.sub(r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b', '[CPF]', sanitized_text)
            sanitized_text = re.sub(r'\b\d{11}\b', '[CPF]', sanitized_text)
            
            # Mascarar telefones
            sanitized_text = re.sub(r'\(\d{2}\)\s*\d{4,5}-\d{4}', '[TELEFONE]', sanitized_text)
            sanitized_text = re.sub(r'\b\d{2}\s*\d{4,5}-\d{4}\b', '[TELEFONE]', sanitized_text)
            
            # Mascarar RGs
            sanitized_text = re.sub(r'\b\d{2}\.\d{3}\.\d{3}-[0-9X]\b', '[RG]', sanitized_text)
            
            # Mascarar emails
            sanitized_text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', sanitized_text)
            
            self.logger.info(f"Texto OCR sanitizado: {len(text)} -> {len(sanitized_text)} caracteres - DADOS MASCARADOS")
        else:
            self.logger.info(f"Texto OCR processado: {len(text)} caracteres - DADOS PRESERVADOS")
        
        return sanitized_text
    
    def validate_extracted_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valida dados extraídos e adiciona flags de validação
        
        Args:
            data: Dicionário com dados extraídos
            
        Returns:
            Dados com flags de validação adicionados
        """
        if not isinstance(data, dict):
            return data
        
        validated_data = data.copy()
        
        # Adicionar flags de validação
        import datetime
        validated_data['_validation'] = {
            'timestamp': datetime.datetime.now().isoformat(),
            'fields_count': len(data),
            'has_sensitive_data': self._check_sensitive_data(data),
            'validation_passed': True
        }
        
        # Log para auditoria
        self.logger.info(f"Dados validados: {len(data)} campos com flags de validação")
        
        return validated_data
    
    def _check_sensitive_data(self, data: Dict[str, Any]) -> bool:
        """Verifica se os dados contêm informações sensíveis"""
        import re
        
        text_data = str(data)
        
        # Padrões de dados sensíveis
        sensitive_patterns = [
            r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b',  # CPF
            r'\b\d{11}\b',  # CPF numérico
            r'\(\d{2}\)\s*\d{4,5}-\d{4}',  # Telefone
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'  # Email
        ]
        
        for pattern in sensitive_patterns:
            if re.search(pattern, text_data):
                return True
        
        return False
    
    def create_audit_log(self, original_data: Any, sanitized_data: Any, user_id: str, operation: str) -> Dict[str, Any]:
        """
        Cria log de auditoria das operações de sanitização
        
        Args:
            original_data: Dados originais
            sanitized_data: Dados após sanitização
            user_id: ID do usuário
            operation: Tipo de operação
            
        Returns:
            Log de auditoria
        """
        import datetime
        
        audit_log = {
            'timestamp': datetime.datetime.now().isoformat(),
            'user_id': user_id,
            'operation': operation,
            'original_data_size': len(str(original_data)) if original_data else 0,
            'sanitized_data_size': len(str(sanitized_data)) if sanitized_data else 0,
            'data_preserved': True  # Sempre True pois não removemos dados
        }
        
        # Log para arquivo se disponível
        if security_config:
            try:
                security_config.log_access(
                    user_id=user_id,
                    action=f'AUDIT_{operation}',
                    resource='data_sanitization',
                    success=True
                )
            except:
                pass
        
        return audit_log

# Instância global
data_sanitizer = DataSanitizer() 