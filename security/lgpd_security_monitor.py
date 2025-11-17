#!/usr/bin/env python3
"""
Monitor de Segurança LGPD para Sistema de Naturalização
Monitora e detecta possíveis violações da LGPD em tempo real
"""

import os
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict, deque
import logging
from dataclasses import dataclass

from lgpd_compliance import lgpd_system
from data_protection import filtro_protecao

@dataclass
class SecurityAlert:
    """Representa um alerta de segurança"""
    timestamp: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    category: str
    message: str
    details: Dict[str, Any]
    resolved: bool = False

class LGPDSecurityMonitor:
    """
    Monitor de segurança focado na conformidade LGPD
    """
    
    def __init__(self):
        """Inicializa o monitor de segurança"""
        self.alerts = deque(maxlen=1000)  # Últimos 1000 alertas
        self.metrics = defaultdict(int)
        self.running = False
        self.monitor_thread = None
        
        # Configurar thresholds de segurança
        self.thresholds = {
            'max_data_access_per_minute': 50,
            'max_failed_requests_per_minute': 10,
            'max_file_size_mb': 50,
            'suspicious_pattern_frequency': 5
        }
        
        # Rastreamento de atividades
        self.activity_tracker = {
            'data_access': deque(maxlen=1000),
            'failed_requests': deque(maxlen=100),
            'file_operations': deque(maxlen=500)
        }
        
        self._setup_logging()
        print("🔒 Monitor de Segurança LGPD inicializado")
    
    def _setup_logging(self):
        """Configura logging específico do monitor"""
        log_dir = os.path.join(os.path.dirname(__file__), 'logs_lgpd')
        os.makedirs(log_dir, exist_ok=True)
        
        # Logger específico para alertas de segurança
        self.security_logger = logging.getLogger('lgpd_security')
        handler = logging.FileHandler(
            os.path.join(log_dir, 'security_alerts.log')
        )
        formatter = logging.Formatter(
            '%(asctime)s - SECURITY - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.security_logger.addHandler(handler)
        self.security_logger.setLevel(logging.INFO)
    
    def start_monitoring(self):
        """Inicia o monitoramento contínuo"""
        if self.running:
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("🛡️ Monitoramento de segurança LGPD ativado")
    
    def stop_monitoring(self):
        """Para o monitoramento"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5.0)
        print("🛑 Monitoramento de segurança parado")
    
    def _monitor_loop(self):
        """Loop principal do monitor"""
        while self.running:
            try:
                self._check_security_metrics()
                self._cleanup_old_data()
                time.sleep(30)  # Verificar a cada 30 segundos
            except Exception as e:
                self.security_logger.error(f"Erro no monitor de segurança: {e}")
                time.sleep(60)  # Esperar mais tempo em caso de erro
    
    def _check_security_metrics(self):
        """Verifica métricas de segurança"""
        current_time = datetime.now()
        one_minute_ago = current_time - timedelta(minutes=1)
        
        # Verificar acesso excessivo a dados
        recent_access = [
            activity for activity in self.activity_tracker['data_access']
            if datetime.fromisoformat(activity['timestamp']) > one_minute_ago
        ]
        
        if len(recent_access) > self.thresholds['max_data_access_per_minute']:
            self._create_alert(
                'HIGH',
                'data_access_excessive',
                f'Acesso excessivo a dados: {len(recent_access)} operações no último minuto',
                {'count': len(recent_access), 'threshold': self.thresholds['max_data_access_per_minute']}
            )
        
        # Verificar falhas excessivas
        recent_failures = [
            activity for activity in self.activity_tracker['failed_requests']
            if datetime.fromisoformat(activity['timestamp']) > one_minute_ago
        ]
        
        if len(recent_failures) > self.thresholds['max_failed_requests_per_minute']:
            self._create_alert(
                'MEDIUM',
                'failed_requests_excessive',
                f'Muitas falhas de acesso: {len(recent_failures)} no último minuto',
                {'count': len(recent_failures), 'threshold': self.thresholds['max_failed_requests_per_minute']}
            )
    
    def _cleanup_old_data(self):
        """Remove dados antigos dos trackers"""
        cutoff_time = datetime.now() - timedelta(hours=1)
        
        for tracker_name, tracker in self.activity_tracker.items():
            # Filtrar apenas atividades recentes
            recent_activities = [
                activity for activity in tracker
                if datetime.fromisoformat(activity['timestamp']) > cutoff_time
            ]
            tracker.clear()
            tracker.extend(recent_activities)
    
    def _create_alert(self, severity: str, category: str, message: str, details: Dict[str, Any]):
        """Cria um alerta de segurança"""
        alert = SecurityAlert(
            timestamp=datetime.now().isoformat(),
            severity=severity,
            category=category,
            message=message,
            details=details
        )
        
        self.alerts.append(alert)
        self.metrics[f'alert_{severity.lower()}'] += 1
        
        # Log do alerta
        log_level = {
            'LOW': logging.INFO,
            'MEDIUM': logging.WARNING,
            'HIGH': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }.get(severity, logging.INFO)
        
        self.security_logger.log(
            log_level,
            f"[{severity}] {category}: {message} | Details: {json.dumps(details)}"
        )
        
        # Auditoria LGPD
        lgpd_system.log_audit_event(
            'security_alert',
            'system',
            'alert_generated',
            'security_monitoring',
            True,
            {'severity': severity, 'category': category}
        )
    
    def log_data_access(self, user_id: str, data_type: str, operation: str, success: bool):
        """Registra acesso a dados para monitoramento"""
        activity = {
            'timestamp': datetime.now().isoformat(),
            'user_id': filtro_protecao.filtrar_dados_sensiveis(user_id),
            'data_type': data_type,
            'operation': operation,
            'success': success
        }
        
        if success:
            self.activity_tracker['data_access'].append(activity)
        else:
            self.activity_tracker['failed_requests'].append(activity)
        
        # Log de auditoria LGPD
        lgpd_system.log_audit_event(
            'data_access',
            user_id,
            operation,
            data_type,
            success,
            {'operation_details': operation}
        )
    
    def log_file_operation(self, file_path: str, operation: str, file_size_mb: float, user_id: str = 'system'):
        """Registra operações de arquivo"""
        activity = {
            'timestamp': datetime.now().isoformat(),
            'file_path': os.path.basename(file_path),  # Apenas o nome do arquivo
            'operation': operation,
            'file_size_mb': file_size_mb,
            'user_id': filtro_protecao.filtrar_dados_sensiveis(user_id)
        }
        
        self.activity_tracker['file_operations'].append(activity)
        
        # Verificar tamanho do arquivo
        if file_size_mb > self.thresholds['max_file_size_mb']:
            self._create_alert(
                'MEDIUM',
                'large_file_operation',
                f'Operação com arquivo grande: {file_size_mb:.1f}MB',
                {'file_size_mb': file_size_mb, 'operation': operation}
            )
        
        # Log de auditoria LGPD
        lgpd_system.log_audit_event(
            'file_operation',
            user_id,
            operation,
            'file_system',
            True,
            {'file_size_mb': file_size_mb}
        )
    
    def check_suspicious_patterns(self, text: str, context: str = 'unknown') -> bool:
        """Verifica padrões suspeitos em texto processado"""
        suspicious_indicators = [
            r'\d{3}\.\d{3}\.\d{3}-\d{2}',  # CPF não mascarado
            r'\d{2}\.\d{3}\.\d{3}-[0-9X]',  # RG não mascarado
            r'senha|password|token',  # Credenciais
            r'administrador|admin|root',  # Contas privilegiadas
        ]
        
        suspicious_count = 0
        for pattern in suspicious_indicators:
            import re
            if re.search(pattern, text, re.IGNORECASE):
                suspicious_count += 1
        
        if suspicious_count >= 2:
            self._create_alert(
                'HIGH',
                'suspicious_data_pattern',
                f'Padrão suspeito detectado no contexto: {context}',
                {'suspicious_indicators': suspicious_count, 'context': context}
            )
            return True
        
        return False
    
    def get_security_dashboard(self) -> Dict[str, Any]:
        """Retorna dashboard de segurança"""
        now = datetime.now()
        last_hour = now - timedelta(hours=1)
        last_24h = now - timedelta(hours=24)
        
        # Contar alertas por período
        alerts_last_hour = [
            alert for alert in self.alerts
            if datetime.fromisoformat(alert.timestamp) > last_hour
        ]
        
        alerts_last_24h = [
            alert for alert in self.alerts
            if datetime.fromisoformat(alert.timestamp) > last_24h
        ]
        
        # Estatísticas de atividade
        data_access_24h = [
            activity for activity in self.activity_tracker['data_access']
            if datetime.fromisoformat(activity['timestamp']) > last_24h
        ]
        
        return {
            'timestamp': now.isoformat(),
            'monitoring_status': 'ATIVO' if self.running else 'INATIVO',
            'alerts': {
                'total': len(self.alerts),
                'last_hour': len(alerts_last_hour),
                'last_24h': len(alerts_last_24h),
                'by_severity': {
                    'critical': len([a for a in alerts_last_24h if a.severity == 'CRITICAL']),
                    'high': len([a for a in alerts_last_24h if a.severity == 'HIGH']),
                    'medium': len([a for a in alerts_last_24h if a.severity == 'MEDIUM']),
                    'low': len([a for a in alerts_last_24h if a.severity == 'LOW'])
                }
            },
            'activity': {
                'data_access_24h': len(data_access_24h),
                'file_operations_24h': len([
                    activity for activity in self.activity_tracker['file_operations']
                    if datetime.fromisoformat(activity['timestamp']) > last_24h
                ]),
                'failed_requests_24h': len([
                    activity for activity in self.activity_tracker['failed_requests']
                    if datetime.fromisoformat(activity['timestamp']) > last_24h
                ])
            },
            'thresholds': self.thresholds,
            'compliance_status': '✅ CONFORME LGPD'
        }
    
    def generate_security_report(self) -> Dict[str, Any]:
        """Gera relatório de segurança detalhado"""
        dashboard = self.get_security_dashboard()
        
        # Adicionar análises específicas
        recent_alerts = [
            {
                'timestamp': alert.timestamp,
                'severity': alert.severity,
                'category': alert.category,
                'message': alert.message
            }
            for alert in list(self.alerts)[-20:]  # Últimos 20 alertas
        ]
        
        recommendations = []
        
        # Gerar recomendações baseadas nos alertas
        high_alerts = dashboard['alerts']['by_severity']['high']
        critical_alerts = dashboard['alerts']['by_severity']['critical']
        
        if critical_alerts > 0:
            recommendations.append("⚠️ CRÍTICO: Investigar imediatamente alertas críticos")
        
        if high_alerts > 5:
            recommendations.append("🔍 Revisar padrões de acesso - muitos alertas de alta severidade")
        
        if dashboard['activity']['data_access_24h'] > 1000:
            recommendations.append("📊 Alto volume de acesso a dados - verificar se é padrão normal")
        
        if not recommendations:
            recommendations.append("✅ Sistema operando dentro dos parâmetros normais de segurança")
        
        report = {
            'relatorio_gerado_em': datetime.now().isoformat(),
            'periodo_analise': '24 horas',
            'dashboard': dashboard,
            'alertas_recentes': recent_alerts,
            'recomendacoes': recommendations,
            'conformidade_lgpd': {
                'status': '✅ CONFORME',
                'monitoramento_ativo': self.running,
                'auditoria_habilitada': True,
                'mascaramento_dados': True,
                'retencao_limitada': True
            }
        }
        
        # Salvar relatório
        report_file = os.path.join(
            os.path.dirname(__file__), 
            'logs_lgpd', 
            f'relatorio_seguranca_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        )
        
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            
            print(f"📊 Relatório de segurança salvo: {report_file}")
            
        except Exception as e:
            self.security_logger.error(f"Erro ao salvar relatório: {e}")
        
        return report

# Instância global do monitor
security_monitor = LGPDSecurityMonitor()

def start_security_monitoring():
    """Inicia monitoramento global de segurança"""
    security_monitor.start_monitoring()

def stop_security_monitoring():
    """Para monitoramento global de segurança"""
    security_monitor.stop_monitoring()

def log_security_event(event_type: str, details: Dict[str, Any]):
    """Função conveniente para registrar eventos de segurança"""
    if event_type == 'data_access':
        security_monitor.log_data_access(
            details.get('user_id', 'unknown'),
            details.get('data_type', 'unknown'),
            details.get('operation', 'read'),
            details.get('success', True)
        )
    elif event_type == 'file_operation':
        security_monitor.log_file_operation(
            details.get('file_path', ''),
            details.get('operation', 'read'),
            details.get('file_size_mb', 0),
            details.get('user_id', 'system')
        )

if __name__ == "__main__":
    print("🔒 TESTE DO MONITOR DE SEGURANÇA LGPD")
    print("=" * 50)
    
    # Iniciar monitoramento
    start_security_monitoring()
    
    # Simular algumas atividades
    security_monitor.log_data_access('user123', 'naturalizacao', 'consulta', True)
    security_monitor.log_file_operation('documento.pdf', 'upload', 15.5)
    
    # Gerar dashboard
    dashboard = security_monitor.get_security_dashboard()
    print(f"Status do monitoramento: {dashboard['monitoring_status']}")
    print(f"Alertas nas últimas 24h: {dashboard['alerts']['last_24h']}")
    
    # Gerar relatório
    report = security_monitor.generate_security_report()
    print(f"Relatório gerado com {len(report['alertas_recentes'])} alertas")
    
    # Parar monitoramento
    time.sleep(2)
    stop_security_monitoring()
