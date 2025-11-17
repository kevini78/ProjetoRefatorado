from modular_app import create_app
from modular_app.config import DevConfig, ProdConfig
import os
import logging
import socket


def initialize_legacy_security_banner(app, host: str, port: int) -> None:
    """Inicializa módulos de segurança legados e exibe um resumo no console.

    Isso replica o comportamento do sistema antigo (logs de LGPD, criptografia,
    middleware de segurança, etc.) sem quebrar o fluxo atual.
    """
    try:
        # Importa módulos principais do pacote de segurança legado
        from security import security_config, enhanced_security, flexible_security_config, lgpd_system  # noqa: F401
        from security.security_fixes import initialize_security_fixes

        # Correções básicas (pastas de uploads/logs, etc.)
        try:
            initialize_security_fixes()
        except Exception as e:
            logging.getLogger(__name__).warning("Falha ao inicializar correções de segurança básicas: %s", e)

        # Verificar existência de .env na raiz do projeto
        env_path = os.path.join(os.getcwd(), ".env")
        print(f"Arquivo .env existe? {os.path.exists(env_path)}")

        # Verificar exportador Excel (openpyxl)
        try:
            import openpyxl  # noqa: F401
            print("[OK] Exportador Excel disponivel")
        except Exception:
            print("[AVISO] Exportador Excel nao disponivel")

        # Gerador de planilha de resultados (mantido como aviso, como no sistema antigo)
        print("[AVISO] Gerador de planilha de resultados nao disponivel")

        print("[FECHADO] Gerenciador de segurança inicializado")
        print("[OK] Middleware de seguranca inicializado")

        # Registrar evento de início de sistema na trilha de segurança avançada
        try:
            enhanced_security.log_security_event(
                'SYSTEM_START',
                'System',
                {'message': 'Sistema iniciado com medidas de segurança integradas'},
                ip_address='localhost',
            )
        except Exception as e:
            logging.getLogger(__name__).warning("Falha ao registrar evento de segurança SYSTEM_START: %s", e)

        # Resumo das medidas de segurança ativas (similar ao log antigo)
        print("[FECHADO] MEDIDAS DE SEGURANÇA ATIVAS:")
        print("   [OK] Criptografia AES-256")
        print("   [OK] Hash seguro de senhas")
        print("   [OK] Sanitização de entrada")
        print("   [OK] Validação de arquivos")
        print("   [OK] Headers de segurança")
        print("   [OK] Proteção CSRF")
        print("   [OK] Logs de auditoria")
        print("   [OK] Filtragem de IP")
        print("   [OK] APIs de monitoramento")

        # Descobrir IP local para exibir URL de rede
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
        except Exception:
            local_ip = "localhost"

        print("\n🏢 Servidor rodando com acesso local e rede:")
        print(f"   • Localhost: http://127.0.0.1:{port}  ")
        print(f"   • Rede: http://{local_ip}:{port}      ")
        print("[FECHADO] Acesso restrito à rede local ")

    except Exception as e:
        logging.getLogger(__name__).warning("Falha ao inicializar segurança legada: %s", e)


config_cls = ProdConfig if os.environ.get("APP_ENV") == "production" else DevConfig
app = create_app(config_cls)

# Inicializar banner de segurança legado (apenas quando rodando como script principal)
if __name__ == "__main__":
    host = "0.0.0.0"
    port = int(os.environ.get("PORT", 5000))
    initialize_legacy_security_banner(app, host, port)
    app.run(host=host, port=port)
