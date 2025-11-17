# Sistema de Planilhas Unificadas

## Visão Geral

Este documento descreve o sistema unificado de geração de planilhas de resultados implementado no projeto de automação de naturalização.

## Motivação

Anteriormente, o sistema gerava planilhas de resultados em locais diferentes:
- **Parecer do Analista**: Salvava `resultados_aprovacao_recurso_<timestamp>.xlsx` no diretório base do arquivo de entrada
- **Ordinária**: Salvava `resultados_analise_ordinaria_<timestamp>.xlsx` no diretório base e também mantinha `planilhas/analise_ordinaria_consolidada.xlsx`

Esta fragmentação dificultava o gerenciamento e consulta dos resultados.

## Solução Unificada

### Diretório Único: `planilhas/`

Todos os resultados de análises agora são salvos no diretório `planilhas/` na raiz do projeto:

```
ProjetoRefatorado/
├── planilhas/
│   ├── resultados_consolidados.xlsx           # Arquivo consolidado único com TODOS os resultados
│   ├── resultados_parecer_analista_<timestamp>.xlsx
│   ├── resultados_ordinaria_<timestamp>.xlsx
│   ├── resultados_provisoria_<timestamp>.xlsx
│   ├── resultados_definitiva_<timestamp>.xlsx
│   └── resultados_defere_indefere_<timestamp>.xlsx
```

### Serviço Unificado

O módulo `modular_app/services/unified_results_service.py` centraliza toda a lógica de geração de planilhas:

```python
from modular_app.services.unified_results_service import UnifiedResultsService

# Criar serviço
service = UnifiedResultsService()

# Salvar resultados do Parecer do Analista
service.salvar_resultado_parecer_analista(resultados, timestamp='20231117_143000')

# Salvar resultados da Ordinária
service.salvar_lote_ordinaria(resultados, timestamp='20231117_143000')
```

## Arquivo Consolidado

O arquivo `planilhas/resultados_consolidados.xlsx` é **automaticamente atualizado** cada vez que um processo é executado. Ele contém:

### Estrutura de Colunas

As colunas variam dependendo do tipo de análise, mas incluem:

#### Campos Comuns
- **Número do Processo**: Identificador único do processo
- **Código do Processo**: Código normalizado
- **Tipo de Análise**: "Parecer do Analista", "Naturalização Ordinária", etc.
- **Status**: Sucesso, Erro, etc.
- **Data da Análise**: Data de execução
- **Hora da Análise**: Hora de execução
- **Erro**: Mensagem de erro (se houver)

#### Campos Específicos do Parecer do Analista
- **Decisão**: Deferimento, Indeferimento, etc.
- **Decisão Enviada**: Sim/Não

#### Campos Específicos da Ordinária
- **Nome**: Nome do requerente
- **Elegibilidade Final**: Resultado da análise
- **Percentual Final**: Percentual de documentos validados
- **Motivo Final**: Motivo do resultado
- **Motivos Indeferimento**: Lista de motivos (separados por `;`)
- **Documentos Faltantes**: Lista de documentos (separados por `;`)

### Deduplicação Automática

O sistema remove automaticamente duplicatas baseadas no **Código do Processo**, mantendo sempre o registro mais recente.

## Workers Atualizados

Todos os workers foram atualizados para usar o sistema unificado:

1. **worker_aprovacao_recurso**: Parecer do Analista
2. **worker_analise_ordinaria**: Naturalização Ordinária
3. **worker_analise_provisoria**: Naturalização Provisória
4. **worker_analise_definitiva**: Naturalização Definitiva
5. **worker_defere_indefere**: Defere/Indefere Recurso

## Controle de Versão (Git)

O `.gitignore` foi atualizado para:
- **Ignorar** todos os arquivos `.xlsx` e `.csv` em `planilhas/`
- **Manter** o diretório `planilhas/` via `.gitkeep`
- Proteger dados sensíveis dos resultados

## Benefícios

1. ✅ **Centralização**: Todos os resultados em um único local
2. ✅ **Rastreabilidade**: Arquivo consolidado com histórico completo
3. ✅ **Consistência**: Formato padronizado entre diferentes tipos de análise
4. ✅ **Deduplicação**: Evita registros duplicados automaticamente
5. ✅ **Organização**: Estrutura clara e previsível
6. ✅ **Arquivos Individuais**: Mantém arquivos com timestamp para auditoria

## Migração de Dados Antigos

Se você tem planilhas antigas em outros diretórios:

1. Identifique as planilhas antigas (normalmente em `uploads/` ou raiz do projeto)
2. Mova manualmente para `planilhas/`
3. Execute uma análise para atualizar o consolidado automaticamente

## Exemplos de Uso

### Consultar Resultados de um Processo Específico

1. Abra `planilhas/resultados_consolidados.xlsx`
2. Use filtro na coluna "Código do Processo"
3. Visualize o resultado mais recente

### Gerar Relatório por Tipo de Análise

1. Abra `planilhas/resultados_consolidados.xlsx`
2. Use filtro na coluna "Tipo de Análise"
3. Filtre por "Parecer do Analista" ou "Naturalização Ordinária"

### Verificar Processos com Erro

1. Abra `planilhas/resultados_consolidados.xlsx`
2. Use filtro na coluna "Status"
3. Filtre por "erro"
4. Veja detalhes na coluna "Erro"

## Observações Importantes

- ⚠️ O arquivo consolidado cresce com o tempo - considere arquivamento periódico
- ⚠️ Arquivos individuais com timestamp são mantidos para auditoria detalhada
- ⚠️ Sempre verifique o arquivo consolidado para ter a visão mais completa
- ⚠️ Dados sensíveis (CPF, RNM) podem estar presentes - proteja adequadamente

## Suporte

Para questões ou problemas relacionados ao sistema de planilhas unificadas, consulte:
- Código fonte: `modular_app/services/unified_results_service.py`
- Workers: `modular_app/tasks/workers.py`
- Repositório Ordinária: `automation/repositories/ordinaria_repository.py`
