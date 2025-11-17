# Implementação de Validação de Documentos Provisória

## Resumo das Alterações

Foi implementada a lógica específica de detecção, download e validação de documentos para o fluxo de **Naturalização Provisória**, independente do fluxo Ordinária.

## Arquivos Criados

### 1. `automation/actions/document_provisoria_action.py`
**Propósito**: Classe dedicada à detecção e validação de documentos específicos da Provisória.

**Funcionalidades**:
- Detecta documentos pelo ID do container HTML (ex: `input__DOC_RNM`, `input__DOC_RNMREP`)
- Localiza botões de download através da estrutura HTML específica da Provisória
- Faz download de documentos PDF
- Valida documentos usando OCR (reutiliza lógica da Ordinária)
- Suporta os 4 documentos obrigatórios da Provisória

**Documentos suportados**:
1. `Documento de identificacao do representante legal` (ID: `input__DOC_RNMREP`)
2. `Carteira de Registro Nacional Migratorio` (ID: `input__DOC_RNM`)
3. `Comprovante de tempo de residência` (ID: `input__DOC_COMPRRESID`)
4. `Documento de viagem internacional` (ID: `input__DOC_VIAGEM`)

**Métodos principais**:
- `baixar_e_validar_documento_individual(nome_documento)`: Baixa e valida um documento
- `baixar_e_validar_todos_documentos(lista_documentos)`: Processa múltiplos documentos
- `_documento_existe(nome_documento)`: Verifica se o documento está presente no formulário

### 2. `scripts/test_provisoria_docs.py`
**Propósito**: Script de teste para verificar a detecção de documentos.

**Uso**:
```bash
python scripts/test_provisoria_docs.py NUMERO_PROCESSO
```

**Exemplo**:
```bash
python scripts/test_provisoria_docs.py 743961
```

**O que o teste faz**:
1. Faz login na plataforma
2. Navega para o processo especificado
3. Tenta detectar cada um dos 4 documentos
4. Exibe relatório de quais documentos foram encontrados
5. Mantém a janela do navegador aberta para inspeção manual

## Arquivos Modificados

### 1. `automation/services/provisoria_service.py`
**Alterações**:
- Removida dependência de `DocumentAction` da Ordinária
- Implementado uso de `DocumentProvisoriaAction` específica
- Simplificada lógica de validação de gatilhos (idade < 10 anos)
- Removida dependência de `OrdinariaRepository` e parecer PF

**Antes**:
```python
from automation.actions.document_ordinaria_action import DocumentAction
from automation.repositories.ordinaria_repository import OrdinariaRepository
repo = OrdinariaRepository(lecom, DocumentAction(lecom.driver, lecom.wait))
```

**Depois**:
```python
from automation.actions.document_provisoria_action import DocumentProvisoriaAction
doc_action = DocumentProvisoriaAction(lecom.driver, lecom.wait)
```

## Estrutura HTML dos Documentos Provisória

Os documentos na Provisória têm uma estrutura HTML diferente da Ordinária:

```html
<div id="input__DOC_RNM">
  <div class="button-group">
    <!-- Botão de visualização -->
    <a class="button--icon">
      <i type="visibility"></i>
    </a>
    
    <!-- Botão de download -->
    <a class="button--icon">
      <i type="cloud_download"></i>
    </a>
  </div>
</div>
```

**Diferenças da Ordinária**:
- IDs de container específicos (`input__DOC_*` vs. outros padrões)
- Ícones com atributo `type` ao invés de classes CSS
- Estrutura de botões agrupados

## Mapeamento de Documentos

| Nome do Documento | ID do Container | Descrição |
|------------------|-----------------|-----------|
| Documento de identificacao do representante legal | `input__DOC_RNMREP` | Documento de identidade do responsável legal |
| Carteira de Registro Nacional Migratorio | `input__DOC_RNM` | RNM do naturalizando |
| Comprovante de tempo de residência | `input__DOC_COMPRRESID` | Comprovante de residência no Brasil |
| Documento de viagem internacional | `input__DOC_VIAGEM` | Passaporte ou doc. de viagem |

## Fluxo de Validação

### 0. Parecer da Polícia Federal (Gatilho Prioritário)

Antes de validar os documentos, o sistema verifica o **parecer da PF** para determinar se o naturalizando ingressou no Brasil antes dos 10 anos:

```python
parecer_pf = lecom.extrair_parecer_pf()
```

**Estratégias (em ordem de prioridade):**

1. **Parecer PF** (prioritário)
   - Busca padrões como "antes dos 10 anos", "depois dos 10 anos"
   - Se PF indicar "depois dos 10" → **Indeferimento automático**
   - Se PF indicar "antes dos 10" → **Gatilho aprovado**

2. **Data do formulário** (fallback)
   - Extrai data de ingresso/residência do formulário
   - Calcula idade na data de ingresso
   - Se < 10 anos → **Gatilho aprovado**

3. **Idade atual** (fallback final)
   - Se idade atual < 10 anos → **Gatilho aprovado**

**Logs esperados:**
```
[PARECER PF] Extraído: Deferimento, Antes 10 anos: True
[OK] (ProvisóriaAction) PF: Ingresso ANTES dos 10 anos identificado
[GATILHO] Aprovado via parecer PF (antes dos 10)
```

### 1. Detecção
```python
doc_action._documento_existe(nome_documento)
```
- Busca o container pelo ID
- Verifica presença do botão de download
- Retorna `True` se encontrado

### 2. Download
```python
doc_action._baixar_documento(nome_documento)
```
- Localiza o link de download (ícone `cloud_download`)
- Clica no botão
- Aguarda o arquivo ser baixado
- Retorna o caminho do arquivo

### 3. Validação OCR
```python
doc_action._validar_documento_com_ocr(caminho_arquivo, nome_documento)
```
- Extrai texto do PDF usando OCR (Mistral API + fallback Tesseract)
- Verifica palavras-chave relevantes
- Valida tamanho mínimo do texto
- Retorna `True` se validado

## Teste do Fluxo Completo

Para testar o fluxo completo de análise de processos Provisória:

```bash
python scripts/test_provisoria_full.py CODIGO1 CODIGO2 ...
```

**Exemplo**:
```bash
python scripts/test_provisoria_full.py 743961 750123 755888
```

**Critérios de sucesso**:
- `elegibilidade_final` = `"deferimento"`
- `percentual_final` >= 100.0 (todos os 4 documentos válidos)
- `status` = `"Processado com sucesso"`

## Troubleshooting

### Documento não encontrado
**Sintoma**: `[AVISO] Container ou botão não encontrado`

**Possíveis causas**:
1. ID do container incorreto - verificar HTML real
2. Documento não foi anexado ao processo
3. Página não carregou completamente

**Solução**:
- Usar `test_provisoria_docs.py` para inspecionar
- Verificar console do navegador
- Confirmar que o processo tem todos os documentos

### OCR falha
**Sintoma**: `[ERRO] Erro ao validar documento`

**Possíveis causas**:
1. `MISTRAL_API_KEY` não configurada no `.env`
2. PDF corrompido ou ilegível
3. Tesseract não instalado (fallback)

**Solução**:
- Verificar `.env` tem `MISTRAL_API_KEY`
- Testar download manual do documento
- Instalar Tesseract OCR

### Download timeout
**Sintoma**: `[ERRO] Timeout ao aguardar download`

**Possíveis causas**:
1. Arquivo muito grande
2. Conexão lenta
3. Popup bloqueando download

**Solução**:
- Aumentar timeout em `_aguardar_download(timeout=60)`
- Verificar pasta Downloads não está cheia
- Desabilitar popups no navegador

## Próximos Passos

1. **Executar teste de detecção**:
   ```bash
   python scripts/test_provisoria_docs.py 743961
   ```

2. **Se houver falhas de detecção**:
   - Inspecionar HTML real no navegador (DevTools)
   - Ajustar IDs em `DOCUMENT_ID_MAP` se necessário
   - Verificar XPath dos botões de download

3. **Executar teste completo**:
   ```bash
   python scripts/test_provisoria_full.py 743961
   ```

4. **Validar resultados**:
   - Verificar arquivo `uploads/resultados_analise_provisoria_*.xlsx`
   - Confirmar todos os processos têm `deferimento` + 100%

## Notas Técnicas

### Separação Ordinária vs. Provisória
- **Ordinária**: Usa `document_ordinaria_action.py` + `ordinaria_repository.py`
- **Provisória**: Usa `document_provisoria_action.py` (independente)
- **OCR**: Compartilhado via importação temporária de `DocumentAction`

### Reutilização de OCR
A validação OCR reutiliza a lógica da Ordinária:
```python
from automation.actions.document_ordinaria_action import DocumentAction
doc_action_temp = DocumentAction(self.driver, self.wait)
texto = doc_action_temp._extrair_texto_com_ocr(caminho, nome)
```

Isso evita duplicação de código complexo de OCR (Mistral + preprocessamento + fallbacks).

### Normalização de Nomes
Documentos são normalizados (lowercase + sem acentos) para matching flexível:
- "Carteira de Registro Nacional Migratório" → "carteira de registro nacional migratorio"
- Permite variações de escrita

## Contato e Suporte

Para dúvidas ou problemas:
1. Verificar logs detalhados no console
2. Inspecionar janela do navegador (mantida aberta nos testes)
3. Revisar este documento para troubleshooting
