#!/usr/bin/env python3
"""
CAMADA 7: SANITIZAÇÃO DE ENTRADA PARA PREVENIR XSS E PATH TRAVERSAL
Implementado em security_config.py e security_middleware.py
"""

import re
import os
import html
import bleach
from typing import Any, Union, List
from urllib.parse import unquote

class InputSanitizer:
    """
    Classe para sanitização de entrada do usuário
    CAMADA 7: Sanitização de entrada para prevenir XSS e path traversal
    """
    
    def __init__(self):
        # Caracteres perigosos para path traversal
        self.dangerous_chars = [':', '*', '?', '"', '<', '>', '|', '\0', '..', '//']
        
        # Tags HTML permitidas (lista restrita)
        self.allowed_tags = ['b', 'i', 'em', 'strong', 'p', 'br']
        
        # Atributos HTML permitidos
        self.allowed_attributes = {}
        
        # Padrões de path traversal
        self.path_traversal_patterns = [
            r'\.\.+',  # .. e ...
            r'[/\\]\.\.',  # /.. e \..
            r'\.\.[/\\]',  # ../ e ..\
            r'%2e%2e',  # URL encoded ..
            r'%252e%252e',  # Double URL encoded ..
        ]
    
    def sanitize_filename(self, filename: str) -> str:
        """
        Sanitiza nome de arquivo para evitar path traversal
        
        Args:
            filename: Nome do arquivo original
            
        Returns:
            Nome do arquivo sanitizado
        """
        if not filename:
            return 'unnamed_file'
        
        # Decodificar URL encoding
        filename = unquote(filename)
        
        # Remover path traversal
        for pattern in self.path_traversal_patterns:
            filename = re.sub(pattern, '', filename, flags=re.IGNORECASE)
        
        # Remover caracteres perigosos
        for char in self.dangerous_chars:
            filename = filename.replace(char, '_')
        
        # Remover espaços no início/fim
        filename = filename.strip()
        
        # Prevenir nomes reservados no Windows
        reserved_names = [
            'CON', 'PRN', 'AUX', 'NUL',
            'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
            'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
        ]
        
        name_without_ext = os.path.splitext(filename)[0].upper()
        if name_without_ext in reserved_names:
            filename = f"file_{filename}"
        
        # Garantir que não está vazio
        if not filename or filename == '.':
            filename = 'unnamed_file'
        
        # Limitar tamanho
        if len(filename) > 255:
            name, ext = os.path.splitext(filename)
            filename = name[:255-len(ext)] + ext
        
        return filename
    
    def sanitize_text(self, text: str, preserve_html: bool = False) -> str:
        """
        Sanitiza texto para prevenir XSS
        
        Args:
            text: Texto a ser sanitizado
            preserve_html: Se deve preservar HTML válido
            
        Returns:
            Texto sanitizado
        """
        if not text:
            return ""
        
        # Converter para string se necessário
        text = str(text)
        
        if preserve_html:
            # Usar bleach para sanitizar HTML
            clean_text = bleach.clean(
                text, 
                tags=self.allowed_tags, 
                attributes=self.allowed_attributes,
                strip=True
            )
        else:
            # Remover todas as tags HTML
            clean_text = bleach.clean(text, tags=[], attributes={}, strip=True)
        
        # Escapar caracteres especiais
        clean_text = html.escape(clean_text)
        
        # Remover caracteres de controle
        clean_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', clean_text)
        
        return clean_text
    
    def sanitize_input(self, input_data: Any) -> Any:
        """
        Sanitiza entrada do usuário baseada no tipo
        
        Args:
            input_data: Dados de entrada
            
        Returns:
            Dados sanitizados
        """
        if isinstance(input_data, str):
            return self.sanitize_text(input_data)
        elif isinstance(input_data, dict):
            return {key: self.sanitize_input(value) for key, value in input_data.items()}
        elif isinstance(input_data, list):
            return [self.sanitize_input(item) for item in input_data]
        else:
            return input_data
    
    def validate_file_path(self, file_path: str, base_directory: str = None) -> bool:
        """
        Valida se um caminho de arquivo é seguro
        
        Args:
            file_path: Caminho do arquivo
            base_directory: Diretório base permitido
            
        Returns:
            True se o caminho é seguro
        """
        if not file_path:
            return False
        
        # Normalizar caminho
        normalized_path = os.path.normpath(file_path)
        
        # Verificar path traversal
        for pattern in self.path_traversal_patterns:
            if re.search(pattern, normalized_path, re.IGNORECASE):
                return False
        
        # Se base_directory especificado, verificar se está dentro
        if base_directory:
            base_path = os.path.normpath(base_directory)
            try:
                # Resolver caminho absoluto
                abs_file_path = os.path.abspath(normalized_path)
                abs_base_path = os.path.abspath(base_path)
                
                # Verificar se arquivo está dentro do diretório base
                if not abs_file_path.startswith(abs_base_path):
                    return False
            except (OSError, ValueError):
                return False
        
        return True
    
    def sanitize_sql_input(self, input_data: str) -> str:
        """
        Sanitiza entrada para prevenir SQL injection
        
        Args:
            input_data: Dados de entrada
            
        Returns:
            Dados sanitizados
        """
        if not input_data:
            return ""
        
        # Escapar caracteres especiais do SQL
        dangerous_chars = ["'", '"', ';', '--', '/*', '*/', 'xp_', 'sp_']
        
        sanitized = str(input_data)
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '')
        
        # Remover espaços extras
        sanitized = ' '.join(sanitized.split())
        
        return sanitized
    
    def sanitize_json_input(self, json_data: dict) -> dict:
        """
        Sanitiza dados JSON de entrada
        
        Args:
            json_data: Dados JSON
            
        Returns:
            Dados JSON sanitizados
        """
        if not isinstance(json_data, dict):
            return json_data
        
        sanitized = {}
        for key, value in json_data.items():
            # Sanitizar chave
            clean_key = self.sanitize_text(str(key))
            
            # Sanitizar valor baseado no tipo
            if isinstance(value, str):
                clean_value = self.sanitize_text(value)
            elif isinstance(value, dict):
                clean_value = self.sanitize_json_input(value)
            elif isinstance(value, list):
                clean_value = [self.sanitize_input(item) for item in value]
            else:
                clean_value = value
            
            sanitized[clean_key] = clean_value
        
        return sanitized
    
    def validate_email(self, email: str) -> bool:
        """
        Valida formato de email
        
        Args:
            email: Email a ser validado
            
        Returns:
            True se email é válido
        """
        if not email:
            return False
        
        # Padrão básico de email
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        return bool(re.match(email_pattern, email))
    
    def sanitize_email(self, email: str) -> str:
        """
        Sanitiza email removendo caracteres perigosos
        
        Args:
            email: Email a ser sanitizado
            
        Returns:
            Email sanitizado
        """
        if not email:
            return ""
        
        # Converter para minúsculas
        email = email.lower().strip()
        
        # Remover caracteres perigosos
        dangerous_chars = ['<', '>', '"', "'", '&', ';', '(', ')', '[', ']']
        for char in dangerous_chars:
            email = email.replace(char, '')
        
        # Validar formato
        if not self.validate_email(email):
            return ""
        
        return email
    
    def sanitize_url(self, url: str) -> str:
        """
        Sanitiza URL removendo caracteres perigosos
        
        Args:
            url: URL a ser sanitizada
            
        Returns:
            URL sanitizada
        """
        if not url:
            return ""
        
        # Decodificar URL encoding
        url = unquote(url)
        
        # Remover caracteres perigosos
        dangerous_chars = ['<', '>', '"', "'", '&', ';', '(', ')', '[', ']', 'javascript:', 'data:', 'vbscript:']
        for char in dangerous_chars:
            url = url.replace(char, '')
        
        # Verificar se é uma URL válida
        url_pattern = r'^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/.*)?$'
        if not re.match(url_pattern, url):
            return ""
        
        return url
    
    def sanitize_phone(self, phone: str) -> str:
        """
        Sanitiza número de telefone
        
        Args:
            phone: Número de telefone
            
        Returns:
            Número sanitizado
        """
        if not phone:
            return ""
        
        # Remover todos os caracteres não numéricos exceto + no início
        if phone.startswith('+'):
            sanitized = '+' + re.sub(r'[^\d]', '', phone[1:])
        else:
            sanitized = re.sub(r'[^\d]', '', phone)
        
        # Validar formato básico
        if len(sanitized) < 10 or len(sanitized) > 15:
            return ""
        
        return sanitized

# Instância global
input_sanitizer = InputSanitizer()

# Decorators para sanitização automática
def sanitize_input_decorator(f):
    """
    Decorator para sanitizar entrada automaticamente
    
    Args:
        f: Função a ser decorada
        
    Returns:
        Função decorada com sanitização
    """
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import request
        
        # Sanitizar dados do formulário
        if request.form:
            for key, value in request.form.items():
                request.form[key] = input_sanitizer.sanitize_text(value)
        
        # Sanitizar dados JSON
        if request.is_json:
            json_data = request.get_json()
            sanitized_json = input_sanitizer.sanitize_json_input(json_data)
            request._cached_json = sanitized_json
        
        # Sanitizar parâmetros de query
        if request.args:
            for key, value in request.args.items():
                request.args[key] = input_sanitizer.sanitize_text(value)
        
        return f(*args, **kwargs)
    
    return decorated_function

def validate_file_upload_decorator(f):
    """
    Decorator para validar uploads de arquivo
    
    Args:
        f: Função a ser decorada
        
    Returns:
        Função decorada com validação
    """
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import request, jsonify
        
        if 'file' not in request.files:
            return jsonify({'error': 'Nenhum arquivo enviado'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
        
        # Sanitizar nome do arquivo
        sanitized_filename = input_sanitizer.sanitize_filename(file.filename)
        
        # Verificar se nome foi alterado (possível ataque)
        if sanitized_filename != file.filename:
            return jsonify({'error': 'Nome de arquivo inválido'}), 400
        
        return f(*args, **kwargs)
    
    return decorated_function
