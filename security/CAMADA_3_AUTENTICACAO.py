#!/usr/bin/env python3
"""
CAMADA 3: SISTEMA DE AUTENTICAÇÃO ROBUSTO COM CONTROLE DE ACESSO
Arquivo: auth_manager.py
"""

import os
import jwt
import time
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from functools import wraps
from flask import request, session, g, current_app, jsonify
from flask_login import UserMixin, current_user
import sqlite3
import json

class User(UserMixin):
    """Modelo de usuário com controle de acesso baseado em papéis"""
    
    def __init__(self, user_id: str, username: str, email: str, 
                 role: str, password_hash: str = None, active: bool = True):
        self.id = user_id
        self.username = username
        self.email = email
        self.role = role
        self.password_hash = password_hash
        self.active = active
        self.created_at = datetime.now()
        self.last_login = None
        self.failed_login_attempts = 0
        self.account_locked_until = None
        
    def get_id(self):
        return self.id
        
    def is_active(self):
        return self.active and (
            self.account_locked_until is None or 
            self.account_locked_until < datetime.now()
        )
        
    def has_permission(self, permission: str) -> bool:
        """Verifica se usuário tem permissão específica"""
        # Implementar lógica de permissões baseada em papéis
        role_permissions = {
            'admin': ['read', 'write', 'delete', 'manage_users'],
            'analyst': ['read', 'write'],
            'viewer': ['read']
        }
        return permission in role_permissions.get(self.role, [])
        
    def to_dict(self) -> Dict[str, Any]:
        """Converte usuário para dicionário (sem dados sensíveis)"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'active': self.active,
            'created_at': self.created_at.isoformat(),
            'last_login': self.last_login.isoformat() if self.last_login else None
        }

class AuthManager:
    """Gerenciador de autenticação e autorização"""
    
    def __init__(self):
        self.db_path = 'users.db'
        self.jwt_secret = os.environ.get('JWT_SECRET_KEY') or secrets.token_urlsafe(64)
        self.max_login_attempts = 5
        self.lockout_duration = timedelta(minutes=30)
        self.session_timeout = timedelta(hours=1)
        self.password_min_length = 12
        self.password_complexity_rules = {
            'uppercase': True,
            'lowercase': True,
            'digits': True,
            'special_chars': True
        }
        
        self._init_database()
        self._create_default_admin()
        
    def _init_database(self):
        """Inicializa banco de dados de usuários"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'viewer',
                    active BOOLEAN NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    failed_login_attempts INTEGER DEFAULT 0,
                    account_locked_until TIMESTAMP,
                    password_changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    must_change_password BOOLEAN DEFAULT 0
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    ip_address TEXT,
                    user_agent TEXT,
                    active BOOLEAN DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Erro ao inicializar base de dados: {e}")
            raise
            
    def _create_default_admin(self):
        """Cria usuário administrador padrão se não existir"""
        try:
            if not self.get_user_by_username('admin'):
                # Senha padrão complexa - deve ser alterada no primeiro login
                default_password = os.environ.get('ADMIN_DEFAULT_PASSWORD', 'Admin@123456789!')
                
                self.create_user(
                    username='admin',
                    email='admin@sistema.gov.br',
                    password=default_password,
                    role='admin',
                    must_change_password=True
                )
                
                print("⚠️  ATENÇÃO: Usuário admin criado com senha padrão - ALTERE IMEDIATAMENTE!")
                
        except Exception as e:
            print(f"Erro ao criar usuário admin padrão: {e}")
            
    def validate_password_complexity(self, password: str) -> Tuple[bool, List[str]]:
        """Valida complexidade da senha"""
        errors = []
        
        if len(password) < self.password_min_length:
            errors.append(f"Senha deve ter pelo menos {self.password_min_length} caracteres")
            
        if self.password_complexity_rules['uppercase'] and not any(c.isupper() for c in password):
            errors.append("Senha deve conter pelo menos uma letra maiúscula")
            
        if self.password_complexity_rules['lowercase'] and not any(c.islower() for c in password):
            errors.append("Senha deve conter pelo menos uma letra minúscula")
            
        if self.password_complexity_rules['digits'] and not any(c.isdigit() for c in password):
            errors.append("Senha deve conter pelo menos um número")
            
        if self.password_complexity_rules['special_chars'] and not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            errors.append("Senha deve conter pelo menos um caractere especial")
            
        return len(errors) == 0, errors
        
    def create_user(self, username: str, email: str, password: str, 
                   role: str = 'viewer', must_change_password: bool = False) -> bool:
        """Cria novo usuário"""
        try:
            # Validar complexidade da senha
            valid, errors = self.validate_password_complexity(password)
            if not valid:
                raise ValueError(f"Senha não atende aos requisitos: {'; '.join(errors)}")
                
            # Gerar hash da senha
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            user_id = secrets.token_urlsafe(16)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO users (id, username, email, password_hash, role, must_change_password)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, username, email, password_hash, role, must_change_password))
            
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            print(f"Erro ao criar usuário: {e}")
            raise
            
    def authenticate_user(self, username: str, password: str, 
                         ip_address: str = None) -> Tuple[Optional[User], str]:
        """Autentica usuário"""
        try:
            user = self.get_user_by_username(username)
            
            if not user:
                return None, "Credenciais inválidas"
                
            # Verificar se conta está bloqueada
            if user.account_locked_until and user.account_locked_until > datetime.now():
                return None, "Conta temporariamente bloqueada"
                
            # Verificar senha
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            if password_hash != user.password_hash:
                self._handle_failed_login(user.id, ip_address)
                return None, "Credenciais inválidas"
                
            # Verificar se usuário está ativo
            if not user.is_active():
                return None, "Conta inativa"
                
            # Login bem-sucedido
            self._handle_successful_login(user.id, ip_address)
            
            return user, "Login realizado com sucesso"
            
        except Exception as e:
            print(f"Erro na autenticação: {e}")
            return None, "Erro interno do sistema"
            
    def _handle_failed_login(self, user_id: str, ip_address: str = None):
        """Manipula tentativa de login falhada"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Incrementar contador de tentativas
            cursor.execute('''
                UPDATE users 
                SET failed_login_attempts = failed_login_attempts + 1
                WHERE id = ?
            ''', (user_id,))
            
            # Verificar se deve bloquear conta
            cursor.execute('SELECT failed_login_attempts FROM users WHERE id = ?', (user_id,))
            attempts = cursor.fetchone()[0]
            
            if attempts >= self.max_login_attempts:
                lockout_until = datetime.now() + self.lockout_duration
                cursor.execute('''
                    UPDATE users 
                    SET account_locked_until = ?
                    WHERE id = ?
                ''', (lockout_until, user_id))
                
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Erro ao manipular login falhado: {e}")
            
    def _handle_successful_login(self, user_id: str, ip_address: str = None):
        """Manipula login bem-sucedido"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Resetar contador de tentativas e remover bloqueio
            cursor.execute('''
                UPDATE users 
                SET failed_login_attempts = 0,
                    account_locked_until = NULL,
                    last_login = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (user_id,))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Erro ao manipular login bem-sucedido: {e}")
            
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Busca usuário por nome"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, username, email, role, password_hash, active,
                       failed_login_attempts, account_locked_until, last_login
                FROM users WHERE username = ?
            ''', (username,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                user = User(
                    user_id=row[0],
                    username=row[1],
                    email=row[2],
                    role=row[3],
                    password_hash=row[4],
                    active=bool(row[5])
                )
                user.failed_login_attempts = row[6]
                user.account_locked_until = datetime.fromisoformat(row[7]) if row[7] else None
                user.last_login = datetime.fromisoformat(row[8]) if row[8] else None
                
                return user
                
            return None
            
        except Exception as e:
            print(f"Erro ao buscar usuário: {e}")
            return None

# Instância global
auth_manager = AuthManager()

# Decoradores de autenticação e autorização
def require_auth(f):
    """Decorador que exige autenticação"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Verificar se usuário está autenticado
        if not current_user.is_authenticated:
            return jsonify({'error': 'Autenticação necessária'}), 401
            
        return f(*args, **kwargs)
    return decorated_function

def require_permission(permission: str):
    """Decorador que exige permissão específica"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({'error': 'Autenticação necessária'}), 401
                
            if not current_user.has_permission(permission):
                return jsonify({'error': 'Permissão insuficiente'}), 403
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_role(required_role: str):
    """Decorador que exige papel específico"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({'error': 'Autenticação necessária'}), 401
                
            if current_user.role != required_role and current_user.role != 'admin':
                return jsonify({'error': f'Papel {required_role} necessário'}), 403
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator
