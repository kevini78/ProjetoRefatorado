#!/usr/bin/env python3
"""
CAMADA 8: LIMPEZA AUTOMÁTICA DE DADOS ANTIGOS
Implementado em security_config.py e lgpd_compliance.py
"""

import os
import shutil
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import json

class DataCleanupManager:
    """
    Gerenciador de limpeza automática de dados antigos
    CAMADA 8: Limpeza automática de dados antigos
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Políticas de retenção (em horas)
        self.retention_policies = {
            'temp_files': 24,        # 1 dia
            'upload_files': 72,      # 3 dias
            'log_files': 168,        # 7 dias
            'audit_logs': 8760,      # 1 ano
            'backup_files': 720,     # 30 dias
            'cache_files': 12,       # 12 horas
            'session_files': 1,      # 1 hora
            'ocr_results': 48        # 2 dias
        }
        
        # Diretórios para limpeza
        self.cleanup_directories = {
            'temp_files': ['temp', 'tmp', 'cache'],
            'upload_files': ['uploads', 'downloads_automacao'],
            'log_files': ['logs'],
            'audit_logs': ['logs_lgpd'],
            'backup_files': ['backup', 'backups'],
            'cache_files': ['cache', 'temp'],
            'session_files': ['sessions'],
            'ocr_results': ['results', 'ocr_output']
        }
    
    def cleanup_old_files(self, directory: str, max_age_hours: int = 24) -> Dict[str, Any]:
        """
        Remove arquivos antigos de um diretório
        
        Args:
            directory: Diretório para limpeza
            max_age_hours: Idade máxima em horas
            
        Returns:
            Estatísticas da limpeza
        """
        cleanup_stats = {
            'directory': directory,
            'max_age_hours': max_age_hours,
            'files_removed': 0,
            'bytes_freed': 0,
            'errors': [],
            'start_time': datetime.now().isoformat()
        }
        
        try:
            if not os.path.exists(directory):
                self.logger.warning(f"Diretório não existe: {directory}")
                return cleanup_stats
            
            current_time = datetime.now()
            max_age = timedelta(hours=max_age_hours)
            
            for filename in os.listdir(directory):
                file_path = os.path.join(directory, filename)
                
                if os.path.isfile(file_path):
                    try:
                        file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                        file_size = os.path.getsize(file_path)
                        
                        if current_time - file_time > max_age:
                            os.remove(file_path)
                            cleanup_stats['files_removed'] += 1
                            cleanup_stats['bytes_freed'] += file_size
                            
                            self.logger.info(f"Arquivo antigo removido: {file_path}")
                    
                    except Exception as e:
                        error_msg = f"Erro ao remover {file_path}: {e}"
                        cleanup_stats['errors'].append(error_msg)
                        self.logger.error(error_msg)
                
                elif os.path.isdir(file_path):
                    # Limpar subdiretórios recursivamente
                    subdir_stats = self.cleanup_old_files(file_path, max_age_hours)
                    cleanup_stats['files_removed'] += subdir_stats['files_removed']
                    cleanup_stats['bytes_freed'] += subdir_stats['bytes_freed']
                    cleanup_stats['errors'].extend(subdir_stats['errors'])
            
            cleanup_stats['end_time'] = datetime.now().isoformat()
            cleanup_stats['duration_seconds'] = (
                datetime.fromisoformat(cleanup_stats['end_time']) - 
                datetime.fromisoformat(cleanup_stats['start_time'])
            ).total_seconds()
            
            self.logger.info(f"Limpeza concluída: {cleanup_stats['files_removed']} arquivos removidos, "
                           f"{cleanup_stats['bytes_freed']} bytes liberados")
            
        except Exception as e:
            error_msg = f"Erro geral na limpeza de {directory}: {e}"
            cleanup_stats['errors'].append(error_msg)
            self.logger.error(error_msg)
        
        return cleanup_stats
    
    def cleanup_by_policy(self, policy_name: str) -> Dict[str, Any]:
        """
        Limpa arquivos baseado em uma política específica
        
        Args:
            policy_name: Nome da política de retenção
            
        Returns:
            Estatísticas da limpeza
        """
        if policy_name not in self.retention_policies:
            return {'error': f'Política não encontrada: {policy_name}'}
        
        max_age_hours = self.retention_policies[policy_name]
        directories = self.cleanup_directories.get(policy_name, [])
        
        total_stats = {
            'policy_name': policy_name,
            'max_age_hours': max_age_hours,
            'total_files_removed': 0,
            'total_bytes_freed': 0,
            'directories_processed': 0,
            'errors': [],
            'start_time': datetime.now().isoformat()
        }
        
        for directory in directories:
            if os.path.exists(directory):
                stats = self.cleanup_old_files(directory, max_age_hours)
                total_stats['total_files_removed'] += stats['files_removed']
                total_stats['total_bytes_freed'] += stats['bytes_freed']
                total_stats['errors'].extend(stats['errors'])
                total_stats['directories_processed'] += 1
        
        total_stats['end_time'] = datetime.now().isoformat()
        
        return total_stats
    
    def cleanup_all_policies(self) -> Dict[str, Any]:
        """
        Executa limpeza baseada em todas as políticas
        
        Returns:
            Estatísticas gerais da limpeza
        """
        all_stats = {
            'start_time': datetime.now().isoformat(),
            'policies_executed': 0,
            'total_files_removed': 0,
            'total_bytes_freed': 0,
            'policies_results': {},
            'errors': []
        }
        
        for policy_name in self.retention_policies.keys():
            try:
                policy_stats = self.cleanup_by_policy(policy_name)
                all_stats['policies_results'][policy_name] = policy_stats
                all_stats['total_files_removed'] += policy_stats.get('total_files_removed', 0)
                all_stats['total_bytes_freed'] += policy_stats.get('total_bytes_freed', 0)
                all_stats['policies_executed'] += 1
                
                if 'error' in policy_stats:
                    all_stats['errors'].append(f"{policy_name}: {policy_stats['error']}")
                
            except Exception as e:
                error_msg = f"Erro na política {policy_name}: {e}"
                all_stats['errors'].append(error_msg)
                self.logger.error(error_msg)
        
        all_stats['end_time'] = datetime.now().isoformat()
        
        return all_stats
    
    def cleanup_sensitive_data(self, directory: str, patterns: List[str] = None) -> Dict[str, Any]:
        """
        Limpa dados sensíveis específicos
        
        Args:
            directory: Diretório para limpeza
            patterns: Padrões de arquivos sensíveis
            
        Returns:
            Estatísticas da limpeza
        """
        if patterns is None:
            patterns = [
                '*.tmp', '*.temp', '*.cache',
                '*_backup*', '*_old*', '*_bak*',
                '*.log.old', '*.log.bak'
            ]
        
        cleanup_stats = {
            'directory': directory,
            'patterns': patterns,
            'files_removed': 0,
            'bytes_freed': 0,
            'errors': [],
            'start_time': datetime.now().isoformat()
        }
        
        try:
            if not os.path.exists(directory):
                return cleanup_stats
            
            for root, dirs, files in os.walk(directory):
                for file in files:
                    file_path = os.path.join(root, file)
                    
                    # Verificar se arquivo corresponde aos padrões
                    should_remove = False
                    for pattern in patterns:
                        if self._matches_pattern(file, pattern):
                            should_remove = True
                            break
                    
                    if should_remove:
                        try:
                            file_size = os.path.getsize(file_path)
                            os.remove(file_path)
                            cleanup_stats['files_removed'] += 1
                            cleanup_stats['bytes_freed'] += file_size
                            
                            self.logger.info(f"Dado sensível removido: {file_path}")
                        
                        except Exception as e:
                            error_msg = f"Erro ao remover {file_path}: {e}"
                            cleanup_stats['errors'].append(error_msg)
                            self.logger.error(error_msg)
            
            cleanup_stats['end_time'] = datetime.now().isoformat()
            
        except Exception as e:
            error_msg = f"Erro na limpeza de dados sensíveis: {e}"
            cleanup_stats['errors'].append(error_msg)
            self.logger.error(error_msg)
        
        return cleanup_stats
    
    def _matches_pattern(self, filename: str, pattern: str) -> bool:
        """
        Verifica se um arquivo corresponde a um padrão
        
        Args:
            filename: Nome do arquivo
            pattern: Padrão a ser verificado
            
        Returns:
            True se corresponde ao padrão
        """
        import fnmatch
        return fnmatch.fnmatch(filename.lower(), pattern.lower())
    
    def cleanup_empty_directories(self, directory: str) -> Dict[str, Any]:
        """
        Remove diretórios vazios
        
        Args:
            directory: Diretório base para limpeza
            
        Returns:
            Estatísticas da limpeza
        """
        cleanup_stats = {
            'directory': directory,
            'directories_removed': 0,
            'errors': [],
            'start_time': datetime.now().isoformat()
        }
        
        try:
            if not os.path.exists(directory):
                return cleanup_stats
            
            # Percorrer diretórios de baixo para cima
            for root, dirs, files in os.walk(directory, topdown=False):
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    
                    try:
                        # Verificar se diretório está vazio
                        if not os.listdir(dir_path):
                            os.rmdir(dir_path)
                            cleanup_stats['directories_removed'] += 1
                            self.logger.info(f"Diretório vazio removido: {dir_path}")
                    
                    except Exception as e:
                        error_msg = f"Erro ao remover diretório {dir_path}: {e}"
                        cleanup_stats['errors'].append(error_msg)
                        self.logger.error(error_msg)
            
            cleanup_stats['end_time'] = datetime.now().isoformat()
            
        except Exception as e:
            error_msg = f"Erro na limpeza de diretórios vazios: {e}"
            cleanup_stats['errors'].append(error_msg)
            self.logger.error(error_msg)
        
        return cleanup_stats
    
    def get_cleanup_report(self) -> Dict[str, Any]:
        """
        Gera relatório de limpeza
        
        Returns:
            Relatório de limpeza
        """
        report = {
            'generated_at': datetime.now().isoformat(),
            'retention_policies': self.retention_policies,
            'cleanup_directories': self.cleanup_directories,
            'recommendations': [
                'Execute limpeza diária para arquivos temporários',
                'Execute limpeza semanal para logs antigos',
                'Execute limpeza mensal para backups antigos',
                'Monitore espaço em disco regularmente',
                'Configure alertas para espaço em disco baixo'
            ]
        }
        
        return report
    
    def schedule_cleanup(self, policy_name: str, interval_hours: int = 24):
        """
        Agenda limpeza automática
        
        Args:
            policy_name: Nome da política
            interval_hours: Intervalo em horas
        """
        # Implementar agendamento usando threading ou celery
        self.logger.info(f"Limpeza agendada para política {policy_name} a cada {interval_hours} horas")

# Instância global
cleanup_manager = DataCleanupManager()

# Função de conveniência para limpeza automática
def run_automatic_cleanup():
    """
    Executa limpeza automática de todos os dados antigos
    """
    try:
        stats = cleanup_manager.cleanup_all_policies()
        
        # Log do resultado
        logger = logging.getLogger(__name__)
        logger.info(f"Limpeza automática concluída: {stats['total_files_removed']} arquivos removidos, "
                   f"{stats['total_bytes_freed']} bytes liberados")
        
        return stats
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Erro na limpeza automática: {e}")
        return {'error': str(e)}
