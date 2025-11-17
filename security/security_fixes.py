#!/usr/bin/env python3
"""
Correções de Segurança para OCR e Automações
Este arquivo contém correções para evitar falhas quando executar OCR e automações
"""

import os
import logging

try:
    from security_config_flexible import flexible_security_config as security_config
except ImportError:
    try:
        from security_config import security_config
    except ImportError:
        security_config = None

from datetime import datetime

def initialize_security_fixes():
    """
    Inicializa correções de segurança básicas
    """
    try:
        # Criar pastas necessárias
        for folder in ['uploads', 'logs']:
            if not os.path.exists(folder):
                os.makedirs(folder, exist_ok=True)
        return True
    except Exception as e:
        logging.error(f"Erro ao inicializar correções de segurança: {e}")
        return False

def safe_file_processing(file_path, operation="processamento"):
    """
    Processa arquivo de forma segura, tratando erros de criptografia
    """
    try:
        # Verificar se arquivo existe
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
        
        # Verificar permissões
        if not os.access(file_path, os.R_OK):
            raise PermissionError(f"Sem permissão de leitura: {file_path}")
        
        # Processar arquivo
        if operation == "encrypt" and security_config:
            return security_config.encrypt_file(file_path)
        elif operation == "decrypt" and security_config:
            return security_config.decrypt_file(file_path)
        else:
            return file_path
            
    except Exception as e:
        logging.error(f"Erro no processamento seguro do arquivo {file_path}: {e}")
        # Em caso de erro, retornar arquivo original
        return file_path

def safe_data_sanitization(data, preserve_essential=True):
    """
    Sanitiza dados de forma segura, tratando erros
    """
    try:
        from data_sanitizer import data_sanitizer
        
        if isinstance(data, str):
            return data_sanitizer.sanitize_ocr_text(data, preserve_essential)
        elif isinstance(data, dict):
            return data_sanitizer.validate_extracted_data(data)
        else:
            return data
            
    except Exception as e:
        logging.error(f"Erro na sanitização de dados: {e}")
        # Em caso de erro, retornar dados originais
        return data