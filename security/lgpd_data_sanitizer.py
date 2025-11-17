#!/usr/bin/env python3
"""
Sanitizador de Dados LGPD
Remove dados sensíveis do código fonte mantendo a funcionalidade
"""

import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

class LGPDDataSanitizer:
    """
    Sanitizador que remove dados sensíveis do código fonte
    """
    
    def __init__(self):
        """Inicializa o sanitizador"""
        self.project_root = Path(__file__).parent
        self.backup_dir = self.project_root / 'backup_sanitizacao'
        
        # Padrões para substituição segura
        self.safe_replacements = {
            # CPFs de exemplo para substituição
            r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b': 'XXX.XXX.XXX-XX',
            r'\b\d{11}\b(?=.*cpf|CPF)': 'XXXXXXXXXXX',
            
            # RGs de exemplo
            r'\b\d{2}\.\d{3}\.\d{3}-[0-9X]\b': 'XX.XXX.XXX-X',
            
            # Telefones
            r'\(\d{2}\)\s*\d{4,5}-\d{4}': '(XX) XXXXX-XXXX',
            
            # Emails (manter apenas domínio)
            r'\b[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Z|a-z]{2,})\b': r'usuario@\1',
            
            # CEPs
            r'\b\d{5}-\d{3}\b': 'XXXXX-XXX',
            
            # Senhas hardcodadas simples
            r'(password|senha)\s*=\s*["\']([^"\']{3,})["\']': r'\1="[REMOVIDO_LGPD]"',
        }
        
        # Arquivos a serem ignorados (já são seguros ou de teste)
        self.ignored_files = {
            'lgpd_compliance.py',
            'lgpd_compliance_checker.py', 
            'data_protection.py',
            'config_lgpd.py',
            'lgpd_security_monitor.py',
            'lgpd_data_sanitizer.py'  # Este próprio arquivo
        }
        
        print("🧹 Sanitizador de Dados LGPD inicializado")
    
    def create_backup(self) -> bool:
        """Cria backup dos arquivos antes da sanitização"""
        try:
            if self.backup_dir.exists():
                shutil.rmtree(self.backup_dir)
            
            self.backup_dir.mkdir()
            
            # Copiar todos os arquivos Python
            for py_file in self.project_root.glob('*.py'):
                if py_file.name not in self.ignored_files:
                    shutil.copy2(py_file, self.backup_dir / py_file.name)
            
            print(f"✅ Backup criado em: {self.backup_dir}")
            return True
            
        except Exception as e:
            print(f"❌ Erro ao criar backup: {e}")
            return False
    
    def sanitize_file(self, file_path: Path) -> Tuple[bool, List[str]]:
        """
        Sanitiza um arquivo específico
        
        Returns:
            Tuple[bool, List[str]]: (sucesso, lista de substituições feitas)
        """
        changes_made = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # Aplicar substituições
            for pattern, replacement in self.safe_replacements.items():
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
                    changes_made.append(f"Substituído padrão '{pattern}': {len(matches)} ocorrências")
            
            # Salvar apenas se houve mudanças
            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"   ✅ {file_path.name}: {len(changes_made)} substituições")
            
            return True, changes_made
            
        except Exception as e:
            print(f"   ❌ Erro ao sanitizar {file_path.name}: {e}")
            return False, []
    
    def sanitize_project(self) -> Dict[str, any]:
        """
        Sanitiza todo o projeto
        
        Returns:
            Relatório da sanitização
        """
        print("🧹 INICIANDO SANITIZAÇÃO DO PROJETO")
        print("=" * 50)
        
        # Criar backup
        if not self.create_backup():
            return {'erro': 'Não foi possível criar backup'}
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'arquivos_processados': 0,
            'arquivos_modificados': 0,
            'total_substituicoes': 0,
            'detalhes': {},
            'arquivos_ignorados': list(self.ignored_files)
        }
        
        # Processar arquivos Python
        for py_file in self.project_root.glob('*.py'):
            if py_file.name in self.ignored_files:
                print(f"   ⏭️ Ignorado: {py_file.name} (arquivo LGPD)")
                continue
            
            results['arquivos_processados'] += 1
            success, changes = self.sanitize_file(py_file)
            
            if changes:
                results['arquivos_modificados'] += 1
                results['total_substituicoes'] += len(changes)
                results['detalhes'][py_file.name] = changes
        
        print(f"\n{'='*50}")
        print(f"✅ SANITIZAÇÃO CONCLUÍDA")
        print(f"📁 Arquivos processados: {results['arquivos_processados']}")
        print(f"🔧 Arquivos modificados: {results['arquivos_modificados']}")
        print(f"🔄 Total de substituições: {results['total_substituicoes']}")
        print(f"💾 Backup salvo em: {self.backup_dir}")
        print(f"{'='*50}")
        
        return results
    
    def restore_backup(self) -> bool:
        """Restaura arquivos do backup"""
        try:
            if not self.backup_dir.exists():
                print("❌ Backup não encontrado")
                return False
            
            for backup_file in self.backup_dir.glob('*.py'):
                target_file = self.project_root / backup_file.name
                shutil.copy2(backup_file, target_file)
            
            print("✅ Backup restaurado com sucesso")
            return True
            
        except Exception as e:
            print(f"❌ Erro ao restaurar backup: {e}")
            return False
    
    def validate_sanitization(self) -> Dict[str, any]:
        """Valida se a sanitização foi efetiva"""
        print("🔍 Validando sanitização...")
        
        validation_results = {
            'arquivos_verificados': 0,
            'problemas_encontrados': 0,
            'detalhes_problemas': []
        }
        
        # Padrões que não deveriam mais existir (dados reais)
        forbidden_patterns = [
            (r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b(?!.*XXX)', 'CPF real encontrado'),
            (r'\b\d{11}\b(?=.*[^X])', 'CPF numérico real encontrado'),
            (r'\(\d{2}\)\s*\d{4,5}-\d{4}(?!.*X)', 'Telefone real encontrado'),
        ]
        
        for py_file in self.project_root.glob('*.py'):
            if py_file.name in self.ignored_files:
                continue
            
            validation_results['arquivos_verificados'] += 1
            
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                for pattern, description in forbidden_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        validation_results['problemas_encontrados'] += len(matches)
                        validation_results['detalhes_problemas'].append({
                            'arquivo': py_file.name,
                            'problema': description,
                            'ocorrencias': len(matches)
                        })
            
            except Exception as e:
                print(f"⚠️ Erro ao validar {py_file.name}: {e}")
        
        if validation_results['problemas_encontrados'] == 0:
            print("✅ Validação bem-sucedida: nenhum dado sensível encontrado")
        else:
            print(f"⚠️ Encontrados {validation_results['problemas_encontrados']} possíveis problemas")
        
        return validation_results

def main():
    """Função principal"""
    sanitizer = LGPDDataSanitizer()
    
    print("🔒 SANITIZADOR DE DADOS LGPD")
    print("=" * 30)
    print("Este script irá:")
    print("1. Criar backup dos arquivos")
    print("2. Remover dados sensíveis do código")
    print("3. Validar a sanitização")
    print()
    
    resposta = input("Deseja continuar? (s/N): ").lower().strip()
    if resposta != 's':
        print("❌ Operação cancelada")
        return
    
    # Executar sanitização
    results = sanitizer.sanitize_project()
    
    if 'erro' in results:
        print(f"❌ Erro: {results['erro']}")
        return
    
    # Validar sanitização
    validation = sanitizer.validate_sanitization()
    
    # Salvar relatório
    import json
    report_file = sanitizer.project_root / 'logs_lgpd' / f'relatorio_sanitizacao_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    
    try:
        os.makedirs(sanitizer.project_root / 'logs_lgpd', exist_ok=True)
        
        full_report = {
            'sanitizacao': results,
            'validacao': validation,
            'recomendacoes': [
                'Revisar manualmente os arquivos modificados',
                'Testar funcionalidades após sanitização',
                'Manter backup para recuperação se necessário'
            ]
        }
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(full_report, f, ensure_ascii=False, indent=2)
        
        print(f"📄 Relatório salvo em: {report_file}")
        
    except Exception as e:
        print(f"⚠️ Erro ao salvar relatório: {e}")

if __name__ == "__main__":
    main()
