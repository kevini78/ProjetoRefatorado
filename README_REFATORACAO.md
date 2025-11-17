# Refatoração da Automação de Naturalização Ordinária

## 🎯 Objetivo

Refatorar o código da automação de naturalização ordinária seguindo boas práticas de arquitetura em camadas:
- **Service**: Regras de negócio
- **Repository**: Acesso a dados  
- **Action**: Interações externas

## 📁 Nova Estrutura

```
app/
├── actions/                    # Camada de interações externas
│   ├── lecom_action.py        # Navegação web, login, Selenium
│   └── document_action.py     # Downloads, OCR, processamento docs
├── repositories/              # Camada de acesso a dados
│   └── ordinaria_repository.py # Extrair/salvar dados, planilhas
├── services/                  # Camada de regras de negócio
│   ├── ordinaria_service.py   # Análise elegibilidade, decisões
│   └── ordinaria_processor.py # Façade que orquestra tudo
└── adapters/                  # Compatibilidade com código existente
    └── navegacao_ordinaria_adapter.py
```

## ✅ Funcionalidades Preservadas

### 🔍 Padrões de Alerta da PF
- Detecção de excesso de ausência do país
- Identificação de problemas com comunicação em português
- Análise do parecer da Polícia Federal

### ⏱️ Padrões de Prazo de Residência
- Verificação de 4 anos para naturalização ordinária
- Redução para 1 ano com comprovante (filho brasileiro, cônjuge, etc.)
- Validação automática dos prazos

### 📄 Fallback para Download de Documentos
- Busca primária em campos específicos do formulário
- Fallback para busca na tabela de anexos
- Busca por termos amplos quando necessário
- Estratégias específicas por tipo de documento

### 🔤 Validação com Termos Melhorados
- Integração com `termos_validacao_melhorados.py`
- Validação baseada em análise de 5.323 documentos reais
- Fallback para validação básica quando termos melhorados não disponíveis
- Confiança mínima configurável por tipo de documento

### 🤖 OCR com Mistral + Pré-processamento
- OCR usando Mistral Pixtral-12b para máxima precisão
- Pré-processamento de imagens com CLAHE, sharpening, remoção de ruído
- Fallback para Tesseract quando Mistral não disponível
- Processamento otimizado por tipo de documento

## 🔄 Como Usar

### Opção 1: Usar o Processor (Recomendado)
```python
from automation.services.ordinaria_processor import OrdinariaProcessor

with OrdinariaProcessor() as processor:
    resultado = processor.processar_processo("12345678901234567890")
    print(f"Status: {resultado['status']}")
```

### Opção 2: Função de Conveniência
```python
from automation.services.ordinaria_processor import processar_processo_ordinaria

resultado = processar_processo_ordinaria("12345678901234567890")
```

### Opção 3: Adaptador (Compatibilidade Total)
```python
from automation.adapters.navegacao_ordinaria_adapter import NavegacaoOrdinaria

# Interface idêntica ao código original
nav = NavegacaoOrdinaria()
nav.login()
resultado = nav.processar_processo("12345678901234567890")
```

### Opção 4: Camadas Separadas (Uso Avançado)
```python
from automation.actions.lecom_action import LecomAction
from automation.actions.document_action import DocumentAction
from automation.repositories.ordinaria_repository import OrdinariaRepository
from automation.services.ordinaria_service import OrdinariaService

# Inicializar camadas
lecom_action = LecomAction()
document_action = DocumentAction(lecom_action.driver, lecom_action.wait)
repository = OrdinariaRepository(lecom_action, document_action)
service = OrdinariaService(lecom_action, document_action, repository)

# Usar cada camada conforme necessário
```

## 🔧 Compatibilidade

### Módulos Atualizados
- `AprovarParecerAnalista/aprovacao_parecer_analista.py`
- `AprovarLote/aprovacao_lote.py`

Agora usam o adaptador que mantém a interface original mas usa a nova arquitetura internamente.

### Código Existente
Todo código que usava `NavegacaoOrdinaria` continua funcionando sem alterações através do adaptador.

## 📊 Benefícios da Refatoração

### 🏗️ Arquitetura Limpa
- Separação clara de responsabilidades
- Baixo acoplamento entre camadas
- Alta coesão dentro de cada camada

### 🧪 Testabilidade
- Cada camada pode ser testada independentemente
- Injeção de dependências facilita mocks
- Lógica de negócio isolada

### 🔧 Manutenibilidade
- Código mais organizado e legível
- Mudanças isoladas em camadas específicas
- Reutilização de componentes

### 🚀 Extensibilidade
- Fácil adição de novos tipos de naturalização
- Novos métodos de OCR ou validação
- Integração com outros sistemas

## 🛠️ Dependências

### Preservadas
- `selenium`: Automação web
- `mistralai`: OCR avançado
- `pytesseract`: OCR fallback
- `opencv-python`: Processamento de imagens
- `pandas`: Manipulação de dados
- `openpyxl`: Geração de planilhas

### Estrutura de Arquivos Original
- `Ordinaria/`: Mantida para compatibilidade
- `termos_validacao_melhorados.py`: Preservado
- `ocr_utils.py`: Preservado
- `preprocessing_ocr.py`: Preservado

## 🔍 Validação

Execute o arquivo `exemplo_uso_nova_arquitetura.py` para testar todas as formas de uso:

```bash
python exemplo_uso_nova_arquitetura.py
```

## 📝 Notas Importantes

### App modular (Flask)
- Entry point: `run.py` (usa `modular_app.create_app`)
- Blueprints registrados:
  - `web` (saúde, downloads)
  - `api` (saúde, `/api/v1/ordinaria/processar`)
  - `api_uploads` (uploads: aprovação de recurso e defere/indefere recurso)
  - `automacao` (rotas `/automacao_processos`)
  - `aprovacoes` (APIs de aprovação em lote e parecer)
  - `pages` (páginas HTML: `/aprovacao_lote`, `/aprovacao_parecer_analista`, `/aprovacao_conteudo_recurso`, `/defere_indefere_recurso`)

### JobService (fila em memória)
- Enfileira jobs com `enqueue` e expõe `status`, `stop`, `log` e `set_result`.
- Usado pelos uploads e pelas aprovações (lote/parecer) para padronizar status.
- Endpoints de status/parada:
  - Lote: `GET /api/aprovacao_lote/status/<id>`, `POST /api/aprovacao_lote/parar/<id>`
  - Parecer: `GET /api/aprovacao_parecer_analista/status/<id>`, `POST /api/aprovacao_parecer_analista/parar/<id>`

### Segurança
- Decoradores centralizados em `modular_app/security/decorators.py`.
- Aplicados nas APIs novas e padronizados nas rotas de OCR legadas.

1. **Todos os padrões existentes foram preservados**
2. **Validação com termos melhorados continua funcionando**
3. **Fallbacks de busca de documentos mantidos**
4. **OCR com Mistral + pré-processamento preservado**
5. **Compatibilidade total com código existente**
6. **Performance mantida ou melhorada**

A refatoração foi feita de forma **não-destrutiva**, garantindo que toda funcionalidade existente continue operando normalmente.

## Como rodar a aplicação (Flask)
- Requisitos: Python 3.10+, dependências do projeto (pip install -r requirements.txt)
- Variáveis de ambiente relevantes:
  - MISTRAL_API_KEY: chave para OCR Mistral (obrigatória para OCR)
  - APP_ENV=production para executar com ProdConfig (opcional)
  - UPLOAD_FOLDER para customizar diretório de uploads (opcional)

Iniciar o servidor:
```bash
python run.py
```

A aplicação usa blueprints registrados em modular_app/__init__.py.

## Observações sobre OCR
- A função de OCR extrair_campos_ocr_mistral foi movida para modular_app/utils/ocr_extractor.py.
- Os módulos que antes importavam de app.py agora importam de modular_app.utils.ocr_extractor.
- Os caminhos de upload foram centralizados: quando possível, usamos BaseConfig.UPLOAD_FOLDER.
