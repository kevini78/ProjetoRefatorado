# Testes de Documentos Específicos

## Visão Geral

Este conjunto de testes valida o download, extração OCR e validação dos seguintes documentos específicos:

1. **Documento do representante legal**
2. **Carteira de Registro Nacional Migratorio (CRNM)**
3. **Comprovante de tempo de residência**
4. **Documento de viagem internacional**

Os testes simulam o mesmo fluxo que ocorre quando uma planilha é enviada pela interface web, garantindo que todos os documentos sejam processados corretamente.

## Estrutura dos Arquivos

```
scripts/
├── test_documentos_especificos.py  # Classe principal de testes
├── run_testes_documentos.py        # Script de execução com relatórios
├── run_testes.bat                  # Script batch para Windows
└── README_TESTES_DOCUMENTOS.md     # Esta documentação
```

## Como Executar os Testes

### Opção 1: Usando Python Diretamente

#### Teste com processo padrão (743961):
```bash
python scripts/test_documentos_especificos.py
```

#### Teste com múltiplos processos:
```bash
python scripts/test_documentos_especificos.py 743961 784408
```

#### Executar com geração de relatórios:
```bash
python scripts/run_testes_documentos.py
```

#### Executar múltiplos processos com relatórios:
```bash
python scripts/run_testes_documentos.py 743961 784408
```

### Opção 2: Usando Script Batch (Windows)

#### Teste simples:
```cmd
scripts\run_testes.bat
```

#### Teste com múltiplos processos:
```cmd
scripts\run_testes.bat 743961 784408
```

## Fluxo de Teste

Para cada documento, o teste executa as seguintes etapas:

1. **Inicialização:**
   - Abre navegador Chrome em modo headless
   - Faz login no sistema
   - Navega para o workspace

2. **Localização do Processo:**
   - Aplica filtros para localizar o processo específico
   - Extrai data inicial do processo

3. **Download do Documento:**
   - Busca o documento em campos específicos do formulário
   - Se não encontrar, busca na tabela de anexos
   - Executa o download do documento

4. **Extração OCR:**
   - Aplica pré-processamento na imagem/PDF
   - Executa OCR usando Mistral Vision (Pixtral-12b)
   - Extrai texto completo do documento

5. **Validação:**
   - Valida o conteúdo extraído usando termos específicos
   - Para alguns documentos, valida apenas caracteres mínimos
   - Registra sucesso ou falha com motivos detalhados

## Relatórios Gerados

Quando executado com `run_testes_documentos.py`, o sistema gera:

### Relatório JSON
```json
{
  "data_execucao": "2025-11-16 16:30:00",
  "total_processos": 1,
  "processos": [
    {
      "numero_processo": "743961",
      "total_documentos": 4,
      "documentos_sucesso": 4,
      "documentos_falha": 0,
      "documentos_erro": 0,
      "percentual_sucesso": 100.0,
      "tempo_total_segundos": 45.2,
      "documentos": [...]
    }
  ],
  "estatisticas_globais": {
    "total_documentos_testados": 4,
    "total_sucessos": 4,
    "total_falhas": 0,
    "total_erros": 0,
    "percentual_sucesso_geral": 100.0
  }
}
```

### Relatório Markdown

Formato legível com tabelas detalhadas:

```markdown
# Relatório de Testes de Documentos Específicos

## Estatísticas Gerais
- Processos Testados: 1
- Total de Documentos: 4
- Sucessos: 4 (100.0%)

## Detalhes por Processo

### Processo 743961
| Documento | Download | OCR | Validação | Tamanho Texto | Tempo |
|-----------|----------|-----|-----------|---------------|-------|
| Documento do representante legal | ✅ | ✅ | ✅ | 1234 chars | 12.5s |
| ... | ... | ... | ... | ... | ... |
```

## Interpretando os Resultados

### Status dos Testes

- **✅ Sucesso:** Documento foi baixado, OCR executado e validação passou
- **❌ Falha:** Documento não foi encontrado ou validação falhou
- **⚠️ Erro:** Ocorreu um erro durante o processamento

### Verificações Realizadas

#### Download
- ✅ Documento encontrado em campo específico ou tabela
- ✅ Arquivo baixado com sucesso
- ❌ Documento não anexado

#### OCR
- ✅ Texto extraído com sucesso
- ✅ Pré-processamento aplicado
- ⚠️ Caracteres mínimos não atingidos

#### Validação
- ✅ Termos obrigatórios encontrados
- ✅ Formato correto
- ❌ Documento inválido ou incorreto

## Processos de Teste Disponíveis

Processos de deferimento (todos os documentos anexados):
- **743961** - Processo completo com todos os documentos
- Adicione outros processos conforme necessário

## Troubleshooting

### Erro: "Login falhou"
- Verifique credenciais no arquivo `.env`
- Confirme que LECOM_USER e LECOM_PASSWORD estão corretos

### Erro: "Documento não encontrado"
- Verifique se o processo tem o documento anexado
- Confirme que está usando um processo de deferimento

### Erro: "OCR falhou"
- Verifique se MISTRAL_API_KEY está configurada
- Confirme conexão com internet
- Verifique créditos da API Mistral

### Erro: "Validação falhou"
- Documento pode estar corrompido
- OCR pode ter extraído texto incorreto
- Documento pode ser do tipo errado

## Validação por Tipo de Documento

### Documento do representante legal
- **Validação:** Termos como "identidade", "RG", "CNH"
- **Mínimo:** 2 termos obrigatórios

### Carteira de Registro Nacional Migratorio
- **Validação:** "RNM", "CRNM", "registro nacional"
- **Mínimo:** 2 termos obrigatórios

### Comprovante de tempo de residência
- **Validação:** Apenas caracteres mínimos (100+)
- **Nota:** Não valida termos específicos, apenas comprimento do texto

### Documento de viagem internacional
- **Validação:** Apenas caracteres mínimos (100+)
- **Nota:** Aceita passaportes de qualquer formato

## Integração com Interface Web

Os testes simulam **exatamente** o mesmo fluxo que ocorre quando:

1. Usuário acessa a interface web
2. Faz upload de uma planilha com processos
3. Sistema processa cada processo automaticamente

Isso garante que:
- ✅ Documentos são baixados corretamente
- ✅ OCR funciona como esperado
- ✅ Validação está consistente
- ✅ Não há regressões no código

## Adicionando Novos Processos de Teste

Para adicionar novos processos:

1. Identifique processos de **deferimento** (com todos os documentos)
2. Anote o número do processo
3. Execute o teste:
   ```bash
   python scripts/test_documentos_especificos.py <NOVO_PROCESSO>
   ```

## Manutenção

### Atualizar lista de documentos testados

Edite `test_documentos_especificos.py`:
```python
DOCUMENTOS_OBRIGATORIOS = [
    'Documento de identificação do representante legal',
    'Carteira de Registro Nacional Migratório',
    'Comprovante de tempo de residência',
    'Documento de viagem internacional',
    # Adicione novos documentos aqui
]
```

### Ajustar validação

Edite `automation/actions/document_ordinaria_action.py`:
- Método `_validar_conteudo_documento_especifico`
- Arquivo `automation/data/termos_validacao_melhorados.py`

## Contato e Suporte

Para problemas ou dúvidas:
1. Verifique os logs de execução
2. Consulte a documentação do projeto principal
3. Revise o código dos testes para entender o fluxo
