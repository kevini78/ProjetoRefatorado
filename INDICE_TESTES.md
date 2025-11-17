# 📚 Índice - Testes de Documentos Específicos

## 🎯 Início Rápido

**Quer executar os testes agora?**
1. 📖 Leia: [`GUIA_RAPIDO_TESTES.md`](GUIA_RAPIDO_TESTES.md)
2. ✅ Execute: `scripts\verificar_prereq.py` (verificar pré-requisitos)
3. ▶️ Execute: `scripts\run_testes.bat`

## 📁 Estrutura da Documentação

### 📘 Documentos Principais

| Documento | Descrição | Para quem? |
|-----------|-----------|------------|
| [`GUIA_RAPIDO_TESTES.md`](GUIA_RAPIDO_TESTES.md) | Guia rápido de execução | **COMECE AQUI** - Todos os usuários |
| [`ENTREGA_TESTES_DOCUMENTOS.md`](ENTREGA_TESTES_DOCUMENTOS.md) | Resumo executivo da entrega | Gestores e revisores |
| [`scripts/README_TESTES_DOCUMENTOS.md`](scripts/README_TESTES_DOCUMENTOS.md) | Referência completa | Desenvolvedores |
| [`INTEGRACAO_WEB_TESTES.md`](INTEGRACAO_WEB_TESTES.md) | Como integrar com web | DevOps e Integradores |
| [`INDICE_TESTES.md`](INDICE_TESTES.md) | Este índice | Navegação |

### 💻 Scripts e Código

| Arquivo | Descrição | Tipo |
|---------|-----------|------|
| [`scripts/test_documentos_especificos.py`](scripts/test_documentos_especificos.py) | Classe principal de testes | Python (444 linhas) |
| [`scripts/run_testes_documentos.py`](scripts/run_testes_documentos.py) | Executor com relatórios | Python (223 linhas) |
| [`scripts/verificar_prereq.py`](scripts/verificar_prereq.py) | Verificação de pré-requisitos | Python (240 linhas) |
| [`scripts/run_testes.bat`](scripts/run_testes.bat) | Script de execução Windows | Batch (80 linhas) |

## 🗺️ Navegação por Objetivo

### 🎯 "Quero executar os testes"
```
1. GUIA_RAPIDO_TESTES.md
   ↓
2. scripts/verificar_prereq.py (verificar ambiente)
   ↓
3. scripts/run_testes.bat (executar)
```

### 📖 "Quero entender como funciona"
```
1. ENTREGA_TESTES_DOCUMENTOS.md (visão geral)
   ↓
2. scripts/README_TESTES_DOCUMENTOS.md (detalhes técnicos)
   ↓
3. scripts/test_documentos_especificos.py (código fonte)
```

### 🔄 "Quero integrar com a web"
```
1. INTEGRACAO_WEB_TESTES.md (teoria)
   ↓
2. scripts/test_documentos_especificos.py (implementação)
   ↓
3. Comparar com código da interface web
```

### 🐛 "Tenho um problema"
```
1. scripts/README_TESTES_DOCUMENTOS.md → Seção "Troubleshooting"
   ↓
2. scripts/verificar_prereq.py (verificar configuração)
   ↓
3. Logs da execução (console output)
```

### 🔧 "Quero modificar os testes"
```
1. scripts/README_TESTES_DOCUMENTOS.md → Seção "Manutenção"
   ↓
2. scripts/test_documentos_especificos.py (editar)
   ↓
3. Testar mudanças com scripts/run_testes.bat
```

## 📊 Documentos por Nível

### 🟢 Nível Básico (Uso Geral)
- **GUIA_RAPIDO_TESTES.md** - Como executar (5 minutos)
- **scripts/run_testes.bat** - Executar no Windows (clique duplo)

### 🟡 Nível Intermediário (Desenvolvimento)
- **ENTREGA_TESTES_DOCUMENTOS.md** - O que foi entregue
- **scripts/README_TESTES_DOCUMENTOS.md** - Como usar e manter
- **scripts/verificar_prereq.py** - Verificar ambiente

### 🔴 Nível Avançado (Arquitetura)
- **INTEGRACAO_WEB_TESTES.md** - Integração e CI/CD
- **scripts/test_documentos_especificos.py** - Código fonte
- **scripts/run_testes_documentos.py** - Geração de relatórios

## 🎓 Tutoriais Passo a Passo

### Tutorial 1: Primeira Execução
```
1. Abrir: GUIA_RAPIDO_TESTES.md
2. Ler: Seção "Requisitos"
3. Executar: python scripts/verificar_prereq.py
4. Corrigir problemas (se houver)
5. Executar: scripts\run_testes.bat
6. Revisar relatórios gerados
```

### Tutorial 2: Adicionar Novo Processo
```
1. Identificar número do processo de deferimento
2. Executar: scripts\run_testes.bat <NUMERO_PROCESSO>
3. Verificar resultados
4. Se passou, adicionar à lista de processos padrão
```

### Tutorial 3: Adicionar Novo Documento
```
1. Abrir: scripts/test_documentos_especificos.py
2. Editar: DOCUMENTOS_OBRIGATORIOS (adicionar documento)
3. Salvar e executar: scripts\run_testes.bat
4. Verificar se novo documento é testado
5. Ajustar validação se necessário
```

### Tutorial 4: Integração CI/CD
```
1. Ler: INTEGRACAO_WEB_TESTES.md
2. Copiar: Exemplo de configuração CI/CD
3. Adaptar: Para seu ambiente (GitHub/GitLab/etc)
4. Testar: Pipeline localmente
5. Fazer commit: Configuração do pipeline
```

## 🔍 Busca Rápida

### Por Palavra-chave

#### "Download"
- scripts/README_TESTES_DOCUMENTOS.md → Seção "Fluxo de Teste"
- INTEGRACAO_WEB_TESTES.md → Seção "Garantias dos Testes"
- scripts/test_documentos_especificos.py → Método `testar_documento_individual()`

#### "OCR"
- ENTREGA_TESTES_DOCUMENTOS.md → Seção "Validações Realizadas"
- scripts/README_TESTES_DOCUMENTOS.md → Seção "Fluxo de Teste"
- automation/actions/document_ordinaria_action.py → Métodos OCR

#### "Validação"
- scripts/README_TESTES_DOCUMENTOS.md → Seção "Validação por Tipo"
- INTEGRACAO_WEB_TESTES.md → Seção "Garantias"
- automation/actions/document_ordinaria_action.py → `_validar_conteudo_documento_especifico()`

#### "Relatório"
- GUIA_RAPIDO_TESTES.md → Seção "Onde encontrar os resultados"
- scripts/run_testes_documentos.py → Funções de geração

#### "Erro" / "Problema"
- scripts/README_TESTES_DOCUMENTOS.md → Seção "Troubleshooting"
- GUIA_RAPIDO_TESTES.md → Seção "Resolução de Problemas"

## 📱 Contatos e Links

### Documentação Relacionada
- Documentação do projeto principal: `README.md`
- Documentação de naturalização ordinária: `ORDINARIA_WEB_IMPLEMENTATION.md`
- Outros testes: `scripts/test_*.py`

### Arquivos de Configuração
- Credenciais: `.env` (não versionado)
- Dependências: `requirements.txt`
- Dados de teste: `dados_exportacao_ordinaria/*.json`

### Saídas e Logs
- Relatórios JSON: `relatorio_testes_documentos_*.json`
- Relatórios Markdown: `relatorio_testes_documentos_*.md`
- Arquivos baixados: `uploads/`
- Resultados: `resultados_ordinaria_global.json`

## 🎯 Checklist de Leitura

### Para Começar ✅
- [ ] Li GUIA_RAPIDO_TESTES.md
- [ ] Executei verificar_prereq.py
- [ ] Corrigi todos os pré-requisitos
- [ ] Executei run_testes.bat com sucesso
- [ ] Revisei relatórios gerados

### Para Desenvolver ✅
- [ ] Li ENTREGA_TESTES_DOCUMENTOS.md
- [ ] Li scripts/README_TESTES_DOCUMENTOS.md
- [ ] Entendi estrutura do código
- [ ] Sei como adicionar novos testes
- [ ] Sei como ajustar validações

### Para Integrar ✅
- [ ] Li INTEGRACAO_WEB_TESTES.md
- [ ] Entendi equivalência de fluxos
- [ ] Sei quando executar testes
- [ ] Posso configurar CI/CD
- [ ] Sei interpretar resultados

## 📌 Notas Importantes

### ⚠️ Avisos
1. **Não execute em produção** - Use apenas em ambiente de testes
2. **Use processos de deferimento** - Garantem que todos os documentos existem
3. **Verifique credenciais** - Arquivo `.env` deve estar configurado
4. **Monitore API Mistral** - Custos podem variar com uso

### ✅ Melhores Práticas
1. **Execute antes de deploy** - Detecta problemas cedo
2. **Revise relatórios** - Entenda por que testes falharam
3. **Mantenha processos atualizados** - Use processos recentes
4. **Documente mudanças** - Facilita manutenção futura

## 🔄 Histórico de Versões

### Versão 1.0.0 (16/11/2025)
- ✅ Criação inicial da suite de testes
- ✅ 4 documentos específicos implementados
- ✅ Documentação completa
- ✅ Integração com interface web
- ✅ Geração de relatórios JSON e Markdown
- ✅ Script de verificação de pré-requisitos

## 🎉 Conclusão

Esta documentação cobre **todos os aspectos** dos testes de documentos específicos:

- ✅ Como executar
- ✅ Como funciona
- ✅ Como integrar
- ✅ Como manter
- ✅ Como resolver problemas

**Comece com:** [`GUIA_RAPIDO_TESTES.md`](GUIA_RAPIDO_TESTES.md)

---

**Última atualização:** 16/11/2025  
**Versão:** 1.0.0  
**Documentos:** 8 arquivos | ~2.000 linhas
