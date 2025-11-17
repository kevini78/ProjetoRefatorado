# Guia Rápido: Resolver Problemas de Detecção de Documentos

## Resumo das Correções Feitas

### ✅ Correções Aplicadas

1. **Método OCR corrigido**: Alterado de `_extrair_texto_com_ocr` para `_processar_arquivo_ocr`
2. **Múltiplos IDs por documento**: Agora cada documento pode ter vários IDs possíveis
3. **Iframe handling melhorado**: Funciona mesmo sem iframe
4. **Detecção mais robusta**: Tenta múltiplos IDs antes de falhar

### ⚠ Problema Identificado no Log

Dos 4 documentos testados:
- ✅ **Documento representante legal** - ENCONTRADO (`input__DOC_RNMREP`)
- ✅ **RNM** - ENCONTRADO (`input__DOC_RNM`)
- ❌ **Comprovante de residência** - NÃO ENCONTRADO (IDs testados: `input__DOC_COMPRRESID`, `input__DOC_RESIDENCIA`, `input__DOC_RESID`)
- ✅ **Documento viagem** - ENCONTRADO (`input__DOC_VIAGEM`)

### 🔍 Próximos Passos

## 1. Descobrir o ID Correto do Comprovante de Residência

Execute o script de inspeção:

```bash
python scripts/inspect_document_ids.py 743961
```

**O que este script faz:**
- Faz login automaticamente
- Navega para o processo
- Lista TODOS os containers com botões de download
- Mostra os IDs e labels encontrados
- Fornece mapeamento sugerido para copiar/colar

**Saída esperada:**
```
✓ Encontrados 4 container(s) com botão de download:

  [1] ID: input__DOC_RNMREP
      Label: Documento do representante legal

  [2] ID: input__DOC_RNM
      Label: RNM

  [3] ID: input__DOC_XXXXX  ← ID CORRETO DO COMPROVANTE
      Label: Comprovante de residência

  [4] ID: input__DOC_VIAGEM
      Label: Documento de viagem
```

## 2. Atualizar o Mapeamento

Depois de descobrir o ID correto, edite o arquivo:

**Arquivo:** `automation/actions/document_provisoria_action.py`

**Localização:** Linha ~25-30

**Antes:**
```python
DOCUMENT_ID_MAP = {
    'Documento de identificacao do representante legal': ['input__DOC_RNMREP', 'input__DOC_REPRESEN'],
    'Carteira de Registro Nacional Migratorio': ['input__DOC_RNM', 'input__DOC_CRNM'],
    'Comprovante de tempo de residência': ['input__DOC_COMPRRESID', 'input__DOC_RESIDENCIA', 'input__DOC_RESID'],
    'Comprovante de tempo de residencia': ['input__DOC_COMPRRESID', 'input__DOC_RESIDENCIA', 'input__DOC_RESID'],
    'Documento de viagem internacional': ['input__DOC_VIAGEM', 'input__DOC_PASSAPORTE'],
}
```

**Depois (exemplo com ID correto):**
```python
DOCUMENT_ID_MAP = {
    'Documento de identificacao do representante legal': ['input__DOC_RNMREP', 'input__DOC_REPRESEN'],
    'Carteira de Registro Nacional Migratorio': ['input__DOC_RNM', 'input__DOC_CRNM'],
    'Comprovante de tempo de residência': ['input__DOC_XXXXX'],  # ← ID CORRETO
    'Comprovante de tempo de residencia': ['input__DOC_XXXXX'],  # ← ID CORRETO (sem acento)
    'Documento de viagem internacional': ['input__DOC_VIAGEM', 'input__DOC_PASSAPORTE'],
}
```

## 3. Testar Novamente

Execute o teste completo:

```bash
python scripts/test_provisoria_full.py 743961
```

### Verificar Resultados Esperados

✅ **Sucesso** se todos os logs mostrarem:
```
[OK] (DocumentProvisoriaAction) Documento encontrado: Comprovante de tempo de residência
[DOWNLOAD] (DocumentProvisoriaAction) Iniciando download de: Comprovante de tempo de residência
[OK] (DocumentProvisoriaAction) Arquivo baixado: ...
[MISTRAL OCR] Processando PDF: 1 página(s)
[OK] (DocumentProvisoriaAction) Documento validado ...
[SUCESSO] (DocumentProvisoriaAction) Documento validado: Comprovante de tempo de residência
```

## Alternativa: Inspeção Manual

Se o script automático não funcionar, inspecione manualmente:

1. Execute:
   ```bash
   python scripts/test_provisoria_docs.py 743961
   ```

2. Quando o navegador abrir, pressione **F12** (DevTools)

3. Na aba **Elements**, procure por:
   - Divs com IDs começando com `input__DOC_`
   - Que contenham `<i type="cloud_download">`

4. Anote o ID do container do comprovante de residência

5. Atualize o `DOCUMENT_ID_MAP` conforme passo 2

## Estrutura HTML Esperada

Os documentos devem seguir este padrão:

```html
<div id="input__DOC_XXXXX">
  <label>Nome do Documento</label>
  <div class="button-group">
    <a class="button--icon">
      <i type="visibility"></i>  <!-- Botão visualizar -->
    </a>
    <a class="button--icon">
      <i type="cloud_download"></i>  <!-- Botão download -->
    </a>
  </div>
</div>
```

## Troubleshooting Adicional

### Problema: "Documento não encontrado" mesmo com ID correto

**Causas possíveis:**
1. Documento não foi anexado ao processo
2. Botão de download não está presente (documento em validação)
3. Estrutura HTML diferente do esperado

**Soluções:**
1. Verificar no navegador se o documento realmente está anexado
2. Usar DevTools para inspecionar a estrutura HTML real
3. Verificar se o ícone é realmente `type="cloud_download"`

### Problema: "OCR falhou ou texto insuficiente"

**Causas possíveis:**
1. `MISTRAL_API_KEY` não configurada
2. PDF corrompido ou sem texto
3. Tesseract não instalado (fallback)

**Soluções:**
1. Verificar `.env` tem chave válida
2. Baixar documento manualmente e testar OCR separadamente
3. Instalar Tesseract: `choco install tesseract` (Windows)

### Problema: Download não inicia

**Causas possíveis:**
1. XPath do botão incorreto
2. JavaScript bloqueando clique
3. Popup bloqueando download

**Soluções:**
1. Verificar se o XPath `.//a[contains(@class, 'button--icon')]//i[@type='cloud_download']` está correto
2. Tentar clique via JavaScript
3. Desabilitar popups no Chrome

## Contato

Para problemas persistentes, forneça:
1. Saída completa do `inspect_document_ids.py`
2. Screenshot do DevTools mostrando o HTML do documento
3. Logs completos do teste
