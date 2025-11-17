# Integração dos Testes com Interface Web

## 📌 Visão Geral

Os testes criados em `scripts/test_documentos_especificos.py` simulam **EXATAMENTE** o mesmo fluxo que ocorre quando um usuário:

1. Acessa a interface web
2. Faz upload de uma planilha Excel com números de processos
3. O sistema processa automaticamente cada processo

## 🔄 Equivalência de Fluxos

### Fluxo da Interface Web
```
Usuário → Upload Planilha → Sistema processa → Gera resultados
           (Excel)            cada processo      (Excel + JSON)
                              automaticamente
```

### Fluxo dos Testes
```
Script → Lê processos → Processa cada → Gera relatórios
         (argumentos)   processo         (JSON + MD)
                        automaticamente
```

## 🎯 Mesmas Etapas, Mesma Lógica

| Etapa | Interface Web | Testes Automatizados |
|-------|--------------|---------------------|
| **Login** | ✅ Automático | ✅ Automático |
| **Localizar Processo** | ✅ Via filtros | ✅ Via filtros |
| **Buscar Documentos** | ✅ Campos específicos + Tabela | ✅ Campos específicos + Tabela |
| **Download** | ✅ Mesmo método | ✅ Mesmo método |
| **OCR** | ✅ Mistral Vision | ✅ Mistral Vision |
| **Pré-processamento** | ✅ ImagePreprocessor | ✅ ImagePreprocessor |
| **Validação** | ✅ Termos específicos | ✅ Termos específicos |
| **Relatório** | ✅ Excel + JSON | ✅ JSON + MD |

## 🔍 Código Compartilhado

Ambos os fluxos usam as **MESMAS CLASSES**:

### 1. LecomAction
```python
# Interface Web
from automation.actions.lecom_ordinaria_action import LecomAction
lecom = LecomAction()
lecom.login()
lecom.aplicar_filtros(numero_processo)

# Testes
from automation.actions.lecom_ordinaria_action import LecomAction
lecom = LecomAction()
lecom.login()
lecom.aplicar_filtros(numero_processo)
```

### 2. DocumentAction
```python
# Interface Web
from automation.actions.document_ordinaria_action import DocumentAction
doc_action = DocumentAction(driver=lecom.driver, wait=lecom.wait)
sucesso = doc_action.baixar_e_validar_documento_individual('Documento de viagem internacional')

# Testes
from automation.actions.document_ordinaria_action import DocumentAction
doc_action = DocumentAction(driver=lecom.driver, wait=lecom.wait)
sucesso = doc_action.baixar_e_validar_documento_individual('Documento de viagem internacional')
```

### 3. OrdinariaService
```python
# Interface Web
from automation.services.ordinaria_service import OrdinariaService
service = OrdinariaService(lecom_action, document_action, repository)
resultado = service.analisar_elegibilidade(dados, data_inicial, documentos_ocr)

# Testes (implícito)
# O service é chamado internamente pelo document_action
```

## 📋 Documentos Validados

Os testes validam os **4 documentos específicos** mencionados:

### 1. Documento do representante legal
```python
# HTML do formulário
<a class="button btn waves-effect waves-light button--icon button-cancel black-text grey lighten-4 button-custom tooltipped" 
   data-position="top" data-delay="10" data-tooltip="Baixar documento" 
   aria-label="Download" role="button" tabindex="0">
    <i class="material-icons" data-position="top" data-delay="10" 
       type="cloud_download" aria-hidden="true"></i>
</a>

# Código de teste
sucesso = doc_action.baixar_e_validar_documento_individual(
    'Documento de identificação do representante legal'
)
```

### 2. Carteira de Registro Nacional Migratorio
```python
# Campo no formulário: DOC_RNM
# Busca por termos: 'crnm', 'rnm', 'rne', 'registro nacional'

sucesso = doc_action.baixar_e_validar_documento_individual(
    'Carteira de Registro Nacional Migratório'
)
```

### 3. Comprovante de tempo de residência
```python
# Campo no formulário: DOC_RESIDENCIA
# Validação: apenas caracteres mínimos (100+)

sucesso = doc_action.baixar_e_validar_documento_individual(
    'Comprovante de tempo de residência'
)
```

### 4. Documento de viagem internacional
```python
# Campo no formulário: DOC_VIAGEM
# Validação: apenas caracteres mínimos (100+)

sucesso = doc_action.baixar_e_validar_documento_individual(
    'Documento de viagem internacional'
)
```

## ✅ Garantias dos Testes

### 1. Download Correto
```python
# Testa que o sistema:
# ✅ Encontra o documento no formulário
# ✅ Clica no botão de download correto
# ✅ Detecta o arquivo baixado
# ✅ Move para pasta correta
```

### 2. OCR Funcional
```python
# Testa que o sistema:
# ✅ Aplica pré-processamento (ImagePreprocessor)
# ✅ Chama API Mistral corretamente
# ✅ Extrai texto com sucesso
# ✅ Retorna texto legível
```

### 3. Validação Consistente
```python
# Testa que o sistema:
# ✅ Usa termos corretos por tipo de documento
# ✅ Aplica lógica de validação apropriada
# ✅ Retorna resultado correto (válido/inválido)
# ✅ Fornece motivos de falha quando aplicável
```

## 🔄 Sincronização com Interface Web

### Quando executar os testes?

1. **Antes de fazer deploy:**
   ```bash
   scripts\run_testes.bat 743961
   ```
   → Garante que tudo funciona antes de publicar

2. **Após mudanças no código:**
   ```bash
   scripts\run_testes.bat 743961 784408
   ```
   → Detecta regressões imediatamente

3. **Periodicamente (CI/CD):**
   ```bash
   python scripts/run_testes_documentos.py 743961
   ```
   → Mantém qualidade contínua

## 🎯 Processos de Teste

### Por que usar processos de deferimento?

Processos de **deferimento** têm todos os documentos anexados corretamente, permitindo testar:

- ✅ Download de todos os 4 documentos
- ✅ OCR em documentos variados
- ✅ Validação positiva (documentos corretos)

### Processos recomendados:

```python
# Processo 743961 - Completo
processos_teste = ['743961']

# Múltiplos processos
processos_teste = ['743961', '784408', '...']
```

## 📊 Interpretação dos Resultados

### Sucesso (100%)
```
✅ Todos os 4 documentos foram:
   - Baixados corretamente
   - Processados via OCR
   - Validados com sucesso

→ Sistema está funcionando perfeitamente
→ Seguro fazer deploy
```

### Falha Parcial (< 100%)
```
⚠️ Alguns documentos falharam:
   - Processo 743961: Documento de viagem internacional
     → Documento não anexado

→ Verificar se processo de teste está correto
→ OU identificar problema no código
```

### Falha Total (0%)
```
❌ Todos os documentos falharam:
   - Possível problema de login
   - Possível mudança na estrutura do site
   - Possível problema de rede/API

→ Investigar logs detalhados
→ Verificar credenciais
→ Verificar conectividade
```

## 🚀 Fluxo Completo de Desenvolvimento

### 1. Desenvolvimento Local
```bash
# Fazer alterações no código
# ...

# Executar testes
scripts\run_testes.bat

# Verificar resultados
# Corrigir se necessário
```

### 2. Teste Manual (Interface Web)
```
1. Acessar interface web
2. Upload planilha de teste
3. Verificar processamento
4. Comparar com resultados dos testes
```

### 3. Deploy
```
Se ambos (testes + interface) funcionam:
→ Deploy seguro ✅

Se algum falha:
→ Investigar e corrigir ❌
```

## 📝 Exemplo de Integração CI/CD

```yaml
# .github/workflows/tests.yml
name: Testes de Documentos

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Run tests
        env:
          LECOM_USER: ${{ secrets.LECOM_USER }}
          LECOM_PASSWORD: ${{ secrets.LECOM_PASSWORD }}
          MISTRAL_API_KEY: ${{ secrets.MISTRAL_API_KEY }}
        run: python scripts/run_testes_documentos.py 743961
      
      - name: Upload reports
        uses: actions/upload-artifact@v2
        with:
          name: test-reports
          path: relatorio_testes_documentos_*.json
```

## 🎓 Boas Práticas

### ✅ DO:
- Execute testes antes de cada deploy
- Use processos de deferimento reais
- Revise relatórios detalhadamente
- Mantenha processos de teste atualizados
- Documente falhas e correções

### ❌ DON'T:
- Não execute em produção
- Não use processos sem documentos
- Não ignore falhas de validação
- Não pule testes por pressa
- Não compartilhe credenciais

## 📞 Suporte

Para dúvidas sobre integração:
1. Consulte esta documentação
2. Revise `scripts/README_TESTES_DOCUMENTOS.md`
3. Analise os logs de execução
4. Compare com código da interface web

---

**Documentação criada em:** 16/11/2025  
**Versão:** 1.0.0  
**Compatibilidade:** Interface Web v1.x
