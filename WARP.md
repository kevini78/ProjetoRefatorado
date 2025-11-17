# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Environment and dependencies

- Python: 3.10+
- Install dependencies (as documented in `README_REFATORACAO.md`):
  - `pip install -r requirements.txt`
- Configuration is driven mainly by environment variables:
  - `MISTRAL_API_KEY` – required for Mistral OCR in production flows
  - `LECOM_USER`, `LECOM_PASS` – credentials for the LECOM workspace (loaded from `.env`)
  - `APP_ENV=production` switches `run.py` to `ProdConfig`; otherwise `DevConfig` is used
  - `UPLOAD_FOLDER` – custom upload directory (defaults to `<repo>/uploads` via `BaseConfig`)
  - `ALLOWED_IPS` – optional comma‑separated list of IPs enforced by security middleware

## Core commands

### Run the Flask web application

- Start the server (development profile by default):
  - `python run.py`
- Notes from `README_REFATORACAO.md` / `modular_app`:
  - Entry point: `run.py` → `modular_app.create_app(DevConfig|ProdConfig)`
  - Blueprints are registered inside `modular_app/__init__.py`:
    - `web` – root pages and simple downloads
    - `api` – `/api/v1/...` (includes `/api/v1/health` and `/api/v1/ordinaria/processar`)
    - `api_uploads` – upload APIs for planilhas (ordinária/provisória + aprovação flows)
    - `automacao` – automation‑related routes
    - `aprovacoes` – approval flows (lote, parecer, recursos)
    - `pages` – HTML pages like `/aprovacao_lote`, `/aprovacao_parecer_analista`, `/analise_automatica`
    - `ocr` – OCR‑related routes

### Health checks and synchronous API for Ordinária

With the server running:

- Web health (from `web_bp`):
  - `GET /health`
- API health (from `api_bp`):
  - `GET /api/v1/health`
- Synchronous processing for a single Ordinária process (from `modular_app/routes/api.py`):
  - `POST /api/v1/ordinaria/processar` with JSON body like:
    - `{ "numero_processo": "12345678901234567890" }`

### Ordinária automation via Python API / CLI

The refactor centralizes Naturalização Ordinária in `automation.services.ordinaria_processor` (see `README_REFATORACAO.md`):

- Programmatic usage (recommended):
  - Use the façade directly:
    - ```python
      from automation.services.ordinaria_processor import OrdinariaProcessor

      with OrdinariaProcessor() as processor:
          resultado = processor.processar_processo("12345678901234567890")
      ```
  - Or use the convenience function:
    - ```python
      from automation.services.ordinaria_processor import processar_processo_ordinaria

      resultado = processar_processo_ordinaria("12345678901234567890")
      ```
- One‑off CLI for a real process (script in `scripts/run_ordinaria_once.py`):
  - `python scripts/run_ordinaria_once.py <numero_processo>`
  - The script:
    - Calls `processar_processo_ordinaria` once
    - Prints a summarized result to stdout
    - If available, inspects `planilhas/analise_ordinaria_consolidada.xlsx` and JSON globals (`resultados_ordinaria_global.json`, `resultados.ordinaria.global`) for the given process

### Batch analysis via web UI (Ordinária and Provisória)

The `ORDINARIA_WEB_IMPLEMENTATION.md` file documents the full web batch flow using `JobService` and workers in `modular_app/tasks/workers.py`.

Typical developer flow:

1. Ensure dependencies and environment variables are configured (including Selenium / browser and `.env` with LECOM credentials).
2. Run the Flask app:
   - `python run.py`
3. Navigate to the batch analysis page:
   - `http://localhost:5000/analise_automatica`
4. Fill the form:
   - **Tipo de Processo**: `Ordinária` or `Provisória`
   - **Planilha**: Excel/CSV containing a `codigo`/`código` column with process numbers
5. Submit the form:
   - A `JobService` job is enqueued (`worker_analise_ordinaria` or `worker_analise_provisoria`)
   - The worker reads codes from the uploaded file, drives Selenium, performs OCR (via Mistral / PyMuPDF), runs the eligibility rules, and writes a results spreadsheet under `uploads/` (e.g. `resultados_analise_ordinaria_YYYYMMDD_HHMMSS.xlsx` or `resultados_analise_provisoria_YYYYMMDD_HHMMSS.xlsx`).

The `/analise_automatica` route and the respective workers are the canonical path for testing the end‑to‑end web batch flows.

### Ad‑hoc regression / diagnostic scripts

These scripts live under `scripts/` and are used as targeted checks around specific flows and bug fixes. They are not wired into a formal test runner but are the closest thing to “tests” in this repo.

- Ordinária planilha generation (repository behavior):
  - `python scripts/test_planilha_ordinaria.py`
  - Uses `automation.repositories.ordinaria_repository.OrdinariaRepository` with fake actions to generate one row in the Ordinária result spreadsheet and prints the last row for inspection.

- Provisória end‑to‑end flow inspection (pre‑refactor behavior + Selenium):
  - `python scripts/test_provisoria_flow.py 743961`
  - Uses `ProvisoriaAction` directly to:
    - Run `aplicar_filtros(code)` for each given code
    - Verify `data_inicial_processo` was captured
    - Inspect the PF opinion field `CHPF_PARECER`

- Provisória age / date‑order fix validation (documented in `PROVISORIA_DATE_FIX.md`):
  - Single code or multiple codes (space‑separated):
    - `python scripts/test_provisoria_idade.py 743961`
    - `python scripts/test_provisoria_idade.py 743961 668121`
  - This script checks that:
    - `aplicar_filtros` extracts the initial process date *after* the activity table is loaded
    - Age is computed correctly from the extracted initial date and the date of birth
    - The eligibility result matches the Provisória rules

- Validation terms for foreign criminal record (Pakistan example):
  - `python scripts/test_termos_pakistan.py`
  - This calls `automation.data.termos_validacao_melhorados.validar_documento_melhorado('Antecedentes_Origem', texto, minimo_confianca=70)` and prints whether the text is considered valid and the computed confidence.

## High‑level architecture

### 1. Modular Flask app (`modular_app` + `run.py`)

The web layer is a modular Flask application built around an app factory:

- `run.py` chooses `DevConfig` or `ProdConfig` from `modular_app.config` based on `APP_ENV`, then calls `modular_app.create_app` and binds the app to `0.0.0.0` on `PORT` (default 5000).
- `modular_app/__init__.py`:
  - Creates the Flask instance with explicit `templates/` and `static/` folders
  - Loads configuration from the passed config class
  - Injects minimal Jinja globals (`csrf_token`, `current_time`, `app_version`) for templates
  - Registers security middleware (`modular_app.security.middleware.register_security`) to apply HTTP headers / IP restrictions
  - Instantiates a global in‑memory `JobService` attached to `app.extensions['job_service']`
  - Registers multiple blueprints that split responsibilities:
    - `web_bp` – basic pages, index, health, and file download helpers
    - `api_bp` – versioned JSON API (`/api/v1/...`) including the synchronous Ordinária processing endpoint
    - `api_uploads_bp` – upload and job‑creation endpoints backing the planilha flows
    - `automacao_bp` – automation‑specific routes
    - `aprovacoes_bp` – endpoints for lote / parecer / recurso approval actions
    - `pages_bp` – HTML pages such as `/analise_automatica` that drive JobService workers
    - `ocr_bp` – endpoints related to OCR utilities

Config classes (`BaseConfig`, `DevConfig`, `ProdConfig`, `TestConfig`) centralize upload folders, max upload size, and security headers (CSP, allowed origins, etc.), and are the main place to look when changing directories or hardening security.

### 2. In‑memory job queue (`modular_app.tasks.job_service` + `modular_app.tasks.workers`)

Long‑running automations (batch planilha processing, approvals, OCR extraction) are modeled as jobs executed in background threads:

- `JobService` is a minimal, thread‑safe in‑memory registry that:
  - Creates jobs with metadata (`create`)
  - Runs work in a daemon thread via `enqueue(target, *args, **kwargs)`
  - Tracks `status`, `message`, `progress`, `logs`, `should_stop`, and `results`
  - Provides `status(job_id)` and `stop(job_id)` primitives used by HTTP controllers
- `modular_app/tasks/workers.py` contains the concrete workers that encapsulate domain flows:
  - `worker_analise_ordinaria` – batch Ordinária analysis using `OrdinariaProcessor`, reading Excel/CSV, logging progress, and exporting `resultados_analise_ordinaria_*.xlsx`
  - `worker_analise_provisoria` – batch Provisória analysis using `ProvisoriaProcessor`, including the corrected date‑extraction order and age rules
  - `worker_defere_indefere`, `worker_aprovacao_recurso`, `worker_aprovacao_lote`, `worker_aprovacao_parecer` – wrappers around the legacy modules `DefereIndefereRecurso`, `AprovarConteudoRecurso`, `AprovarLote`, and `AprovarParecerAnalista` that:
    - Perform Selenium login, drive the old flows, and log structured results
    - Persist Excel summaries next to the uploaded planilha
    - Respect `JobService.should_stop` and handle cleanup of temp files and browser resources
  - `worker_extracao_ocr` – mass OCR extraction targeting Doccano, scanning `uploads/` for files matching provided process numbers, running OCR (via `modular_app.utils.ocr_extractor`), applying masking, and writing type‑segmented JSONL files plus a `resumo_extracao.json` summary.

The HTTP layer (especially `pages_bp` and `api_uploads_bp`) is thin: it validates inputs, hands off to `JobService.enqueue` with the proper worker and arguments, and exposes status/stop endpoints. When modifying job behavior or adding new long‑running flows, prefer extending the workers and using `JobService` consistently rather than starting new threads from controllers.

### 3. Ordinária automation architecture (`automation` package)

`README_REFATORACAO.md` outlines the layered architecture for the refactored Naturalização Ordinária flow; the concrete implementation lives in `automation/`:

- Actions – external interactions (LECOM, Selenium, OCR):
  - `automation.actions.lecom_ordinaria_action.LecomAction`:
    - Owns the Selenium `webdriver.Chrome` instance and its `WebDriverWait`
    - Handles login to LECOM using credentials from `.env`
    - Navigates to the process workspace URL and the `form-web` URL for the selected cycle
    - Extracts `data_inicial_processo` from UI subtitles (with a fallback selector for legacy markup)
    - Manages iframe transitions (`navegar_para_iframe_form_app`, `voltar_do_iframe`) and returns to the workspace between processes
  - `automation.actions.document_ordinaria_action.DocumentAction`:
    - Locates documents either in dedicated fields or in the attachments table
    - Applies special strategies for specific document categories (e.g. antecedents from country of origin, reduction‑of‑residency proof)
    - Downloads documents, runs image/PDF preprocessing (`Ordinaria.preprocessing_ocr.ImagePreprocessor`), and performs OCR via either Mistral (primary) or Tesseract (fallback)
    - Extracts structured information (names, parents, birth date, RNM, CPF, classifications, residence periods) using helpers from `Ordinaria.ocr_utils`

- Repository – data access / persistence:
  - `automation.repositories.ordinaria_repository.OrdinariaRepository`:
    - Encapsulates reading/writing of spreadsheets and other storage artifacts
    - Generates consolidated Ordinária result spreadsheets; `scripts/test_planilha_ordinaria.py` is a good reference for expected columns and behavior

- Service – business rules:
  - `automation.services.ordinaria_service.OrdinariaService` (not shown above but referenced widely):
    - Evaluates the legal requirements for Ordinária (capacity, residence duration, communication in Portuguese, criminal records, document completeness)
    - Integrates improved validation terms from `automation.data.termos_validacao_melhorados`
    - Produces `resultado_elegibilidade`, automatic decision payloads, and a human‑oriented summary (`resumo_executivo`)

- Processor – façade / orchestration:
  - `automation.services.ordinaria_processor.OrdinariaProcessor`:
    - Wires together `LecomAction`, `DocumentAction`, `OrdinariaRepository`, and `OrdinariaService`
    - Defines the canonical step sequence for a single process:
      1. Login (if needed)
      2. Navigate to the process and capture `data_inicial_processo`
      3. Extract personal data from the form (including date of birth)
      4. Run eligibility analysis, including document downloads/OCR
      5. Generate the decision, summary, and spreadsheet rows
      6. Return to the workspace
    - Returns a rich result dict consumed by HTTP APIs, CLI scripts, and batch workers
    - Implements `fechar()` and context‑manager support for safe Selenium teardown

Existing legacy entrypoints (`AprovarParecerAnalista`, `AprovarLote`, etc.) are preserved but internally leverage the new architecture where possible via adapters, as described in `README_REFATORACAO.md`.

### 4. Provisória automation architecture

Provisória flows are partially refactored but still closely follow the original structure:

- `automation.actions.provisoria_action.ProvisoriaAction` (see `PROVISORIA_DATE_FIX.md` and the test scripts):
  - Logs into LECOM and navigates to Provisória processes
  - `aplicar_filtros` is responsible for loading the activity table **before** extracting the initial process date from the subtitle and then locating the correct activity / iframe
  - The ordering of “wait for table → extract date → enter iframe” is critical; regressions should be validated using `scripts/test_provisoria_idade.py`.

- `automation.services.provisoria_service.ProvisoriaService` and `ProvisoriaProcessor`:
  - `ProvisoriaProcessor` composes `ProvisoriaAction` and the service, exposes `processar_codigo`, and is used by `worker_analise_provisoria`
  - The service encapsulates the eligibility rules:
    - Age calculation based on the extracted initial process date and date of birth
    - Residence and document validation
    - Consolidation of PF opinion and OCR‑derived document checks

Any change to the Provisória flow that touches `aplicar_filtros`, date extraction, or eligibility rules should be accompanied by re‑running:

- `python scripts/test_provisoria_flow.py <codigo>`
- `python scripts/test_provisoria_idade.py <codigo ...>`

### 5. OCR and validation engine

OCR is a cross‑cutting concern used in both Ordinária and Provisória flows:

- Core OCR logic for web flows is centralized in `modular_app/utils/ocr_extractor.py` (see `README_REFATORACAO.md` and `ORDINARIA_WEB_IMPLEMENTATION.md`):
  - Uses PyMuPDF (`fitz`) to render PDFs instead of `pdf2image`/Poppler
  - Delegates to Mistral Pixtral‑12b via the `mistralai` client for high‑accuracy text extraction
  - Falls back to Tesseract (`pytesseract`) when Mistral is unavailable

- Domain‑specific extraction helpers live under `Ordinaria/` and are reused by the new `automation.actions` layer to parse key fields from free‑form text.

- `automation.data.termos_validacao_melhorados` encodes improved regex/semantic patterns derived from thousands of real documents; it is used to:
  - Detect negations and missing clauses (e.g. in foreign criminal record certificates)
  - Compute confidence scores and validity flags per document type
  - Provide fallback behaviors when improved terms are unavailable

The `worker_extracao_ocr` worker is designed for building labeled datasets: it reads files from `uploads/`, masks sensitive data, and writes Doccano‑compatible JSONL grouped by inferred document type.

### 6. Security and LGPD tooling

Security concerns are centralized in two areas:

- `modular_app/security`:
  - `decorators.py` defines decorators applied to new APIs and OCR routes (for example, checking authentication or IP allow‑lists)
  - `middleware.py` registers security headers (CSP, etc.) and any global request/response hooks

- `security/` (top‑level package):
  - Layered security scripts (`CAMADA_1_CRIPTOGRAFIA_AES128.py`, `CAMADA_...`) and utilities (`data_sanitizer`, `lgpd_compliance`, `security_config_*`, `security_middleware*`) implement privacy and logging policies and are used by the main app where relevant
  - These modules are referenced by OCR workers and other flows to ensure masking and LGPD compliance, and should be kept in sync with any changes to how OCR text is stored or exported.

## When extending this codebase

- For new long‑running flows, prefer implementing a new worker function in `modular_app/tasks/workers.py` and exposing it via a small HTTP endpoint that uses `JobService.enqueue`.
- For new automation around LECOM or similar systems, follow the existing layered pattern:
  - Action (Selenium/OCR), Repository (planilhas/DB), Service (rules), Processor (façade).
- When touching Provisória or Ordinária flows that involve dates or planilha outputs, use the existing scripts in `scripts/` as regression checks instead of introducing a separate ad‑hoc harness.
