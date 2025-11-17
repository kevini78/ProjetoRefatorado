# Guia Rápido - Testes de Documentos Específicos

## 🎯 O que este teste faz?

Valida automaticamente 4 documentos específicos em processos de naturalização:
1. ✅ Documento do representante legal
2. ✅ Carteira de Registro Nacional Migratorio
3. ✅ Comprovante de tempo de residência  
4. ✅ Documento de viagem internacional

**Para cada documento, o teste:**
- 📥 Baixa o arquivo do processo
- 🔍 Extrai texto via OCR (Mistral Vision)
- ✔️ Valida o conteúdo

## ⚡ Execução Rápida (Windows)

### Opção 1: Clique duplo
1. Navegue até: `ProjetoRefatorado\scripts\`
2. Clique duas vezes em: `run_testes.bat`
3. Aguarde a execução

### Opção 2: Linha de comando
```cmd
cd ProjetoRefatorado
scripts\run_testes.bat
```

### Testar múltiplos processos
```cmd
scripts\run_testes.bat 743961 784408
```

## 📊 Onde encontrar os resultados?

Após a execução, procure na pasta `ProjetoRefatorado`:

- 📄 `relatorio_testes_documentos_YYYYMMDD_HHMMSS.json`
- 📄 `relatorio_testes_documentos_YYYYMMDD_HHMMSS.md`

## ✅ Interpretando os Resultados

### Sucesso Total
```
🎉 TODOS OS TESTES PASSARAM COM SUCESSO! 🎉
Sucessos: 4 (100.0%)
```

### Falhas Parciais
```
⚠️ ALGUNS TESTES FALHARAM ⚠️
Sucessos: 3 (75.0%)
Falhas: 1 (25.0%)

FALHAS IDENTIFICADAS:
  ❌ Processo 743961: Comprovante de tempo de residência
     → Documento não anexado
```

## 🔧 Requisitos

### Antes de executar:
1. ✅ Python 3.8+ instalado
2. ✅ Arquivo `.env` configurado com credenciais:
   ```
   LECOM_USER=seu_usuario
   LECOM_PASSWORD=sua_senha
   MISTRAL_API_KEY=sua_chave_api
   ```
3. ✅ Dependências instaladas:
   ```cmd
   pip install -r requirements.txt
   ```

## 🎓 Como funciona?

### Fluxo Completo
```
┌─────────────────┐
│ 1. Inicialização│  ← Abre navegador e faz login
└────────┬────────┘
         ↓
┌─────────────────┐
│ 2. Localização  │  ← Busca processo no sistema
└────────┬────────┘
         ↓
┌─────────────────┐
│ 3. Download     │  ← Baixa cada documento
└────────┬────────┘
         ↓
┌─────────────────┐
│ 4. OCR          │  ← Extrai texto (Mistral Vision)
└────────┬────────┘
         ↓
┌─────────────────┐
│ 5. Validação    │  ← Verifica conteúdo
└────────┬────────┘
         ↓
┌─────────────────┐
│ 6. Relatório    │  ← Gera resultados
└─────────────────┘
```

## 🎯 Processos de Teste Recomendados

Use processos de **DEFERIMENTO** (com todos os documentos anexados):

- ✅ **743961** - Processo completo (padrão)
- ✅ **784408** - Processo alternativo
- ➕ Adicione seus próprios processos de teste

## ❓ Resolução de Problemas

### "Login falhou"
→ Verifique `.env` e credenciais

### "Documento não encontrado"
→ Confirme que o processo tem todos os documentos anexados

### "OCR falhou"
→ Verifique `MISTRAL_API_KEY` e conexão com internet

### "Validação falhou"
→ Documento pode ser do tipo errado ou corrompido

## 📝 Arquivos Importantes

```
ProjetoRefatorado/
├── scripts/
│   ├── test_documentos_especificos.py   ← Código principal
│   ├── run_testes_documentos.py         ← Gerador de relatórios
│   ├── run_testes.bat                   ← Executor Windows
│   └── README_TESTES_DOCUMENTOS.md      ← Documentação completa
├── .env                                  ← Credenciais (necessário)
└── relatorio_testes_documentos_*.json   ← Resultados (gerado)
```

## 🚀 Próximos Passos

### Após executar os testes:
1. ✅ Revise os relatórios gerados
2. ✅ Corrija falhas identificadas
3. ✅ Execute novamente para confirmar correções
4. ✅ Integre com pipeline de CI/CD (se aplicável)

### Para mais informações:
- 📖 Consulte: `scripts/README_TESTES_DOCUMENTOS.md`
- 🔍 Veja os logs detalhados durante a execução
- 💻 Revise o código para entender o fluxo

## 📞 Contato

Se tiver dúvidas ou problemas:
1. Verifique os logs de execução
2. Consulte a documentação completa
3. Revise o código dos testes

---

**Última atualização:** 16/11/2025
**Versão:** 1.0.0
