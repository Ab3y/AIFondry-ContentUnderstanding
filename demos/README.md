# 🎓 Demo Scripts - Content Understanding Walkthrough

## Overview

This folder contains a progressive 3-step walkthrough for Azure AI Foundry Content Understanding:

1. **Prebuilt analyzers** for zero-configuration extraction from standard business documents
2. **Custom extraction** for domain-specific entities, summaries, and document classification
3. **A multi-document pipeline** that classifies, routes, and consolidates results across mixed inputs

Together, the demos move from simple document analysis to a production-style routing pipeline.

## Prerequisites

- Python **3.9+**
- An **Azure AI Foundry** resource with **Content Understanding** enabled
- A configured **`.env`** file in the repository root
- Network access to the sample documents hosted in the Azure samples repository

Your repo root `.env` must include:

```env
CONTENTUNDERSTANDING_ENDPOINT=https://<your-resource>.cognitiveservices.azure.com/
CONTENTUNDERSTANDING_KEY=<your-key>
```

## Setup

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r demos\requirements.txt
```

Then make sure `.env` exists in the repo root. If needed, copy the template first:

```powershell
Copy-Item .env.template .env
```

Update `.env` with:

- `CONTENTUNDERSTANDING_ENDPOINT`
- `CONTENTUNDERSTANDING_KEY`

## Script Descriptions

### `01_prebuilt_analyzer.py`

**What it does**
- Uses the built-in `prebuilt-invoice` and `prebuilt-receipt` analyzers
- Analyzes sample invoice and receipt documents from public URLs
- Prints markdown previews plus extracted structured fields

**Key concepts demonstrated**
- Using `ContentUnderstandingClient`
- Calling `begin_analyze()` with public document URLs
- Working with prebuilt analyzers
- Interpreting field confidence scores
- Rendering nested field output in tables

**How to run it**

```powershell
python demos\01_prebuilt_analyzer.py
```

**Expected output**
- Rich console panels for the invoice and receipt runs
- A markdown preview for each document
- A table of extracted fields such as totals, vendor details, dates, and line-item-related values
- Color-coded confidence values for quick triage

### `02_custom_entity_extractor.py`

**What it does**
- Creates a temporary custom analyzer on top of `prebuilt-document`
- Extracts entities such as people, organizations, dates, monetary amounts, and locations
- Generates a one-paragraph summary, key terms, and a classified document type
- Analyzes a sample invoice, then deletes the analyzer during cleanup

**Key concepts demonstrated**
- Defining a custom `ContentFieldSchema`
- Using all three generation methods: `extract`, `generate`, and `classify`
- Enabling OCR, layout, and confidence/source estimation
- Creating and deleting analyzers programmatically

**How to run it**

```powershell
python demos\02_custom_entity_extractor.py
```

**Expected output**
- A confirmation that a timestamped custom analyzer was created
- A table listing configured fields and methods
- Panels showing the detected document type, generated summary, extracted entities, and key terms
- Cleanup messages confirming the analyzer was deleted

### `03_multi_document_pipeline.py`

**What it does**
- Creates two temporary analyzers:
  - an entity/summary analyzer for general documents
  - a classifier that routes documents to the correct analyzer
- Processes multiple documents in sequence
- Produces console summaries plus a consolidated JSON report
- Deletes the analyzers during cleanup

**Key concepts demonstrated**
- Document classification and analyzer routing
- Batch processing with progress reporting
- Mixing prebuilt analyzers with custom analyzers
- Normalizing results into a single JSON structure
- Building a production-style pipeline for mixed document sets

**How to run it**

```powershell
python demos\03_multi_document_pipeline.py
```

**Expected output**
- Progress bars while documents are processed
- Per-document routing summaries showing category and analyzer used
- A classification summary table for all processed documents
- A saved `analysis_report.json` file containing the consolidated results
- Cleanup messages for both temporary analyzers

## Key Concepts

| Method | Purpose | Example in demos |
| --- | --- | --- |
| `extract` | Pull literal values directly from the document content | People, organizations, dates, monetary amounts, and locations in `02_custom_entity_extractor.py` |
| `generate` | Produce AI-generated content derived from the source document | `summary` and `key_terms` in `02_custom_entity_extractor.py`, plus `summary` in `03_multi_document_pipeline.py` |
| `classify` | Assign the document to a category for routing or labeling | `document_type` in `02_custom_entity_extractor.py`, and category-based routing in `03_multi_document_pipeline.py` |

## Confidence Scores

Use confidence scores as a lightweight decision policy:

| Confidence | Suggested action |
| --- | --- |
| `> 0.85` | Auto-approve |
| `0.5 - 0.85` | Send for human review |
| `< 0.5` | Reject or reprocess |

This matches the color-coded thresholds used in the prebuilt analyzer demo.

## Troubleshooting

- **Missing `.env`**  
  Copy the template from the repo root:
  ```powershell
  Copy-Item .env.template .env
  ```

- **Invalid endpoint**  
  Verify `CONTENTUNDERSTANDING_ENDPOINT` in the Azure Portal and ensure it matches your Azure AI Foundry resource endpoint.

- **Model not deployed**  
  Open your Content Understanding resource settings and confirm the required models and analyzer capabilities are available.

- **Rate limiting**  
  If you see throttling or transient API failures, add delays between requests or reduce batch size while testing.

## Resources

- [Content Understanding overview](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/overview)
- [Python SDK](https://pypi.org/project/azure-ai-contentunderstanding/)
- [SDK samples](https://github.com/Azure/azure-sdk-for-python/tree/main/sdk/contentunderstanding/azure-ai-contentunderstanding/samples)
- [Custom analyzer tutorial](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/tutorial/create-custom-analyzer)

## See Also

- [Main README](../README.md) - Project overview, prerequisites, and full documentation links
- [Quickstart Demo](../quickstart/README.md) - Run your first demo in 2 minutes
- [Infrastructure (Bicep / Terraform)](../infra/README.md) - Deploy the Azure resource
- [Model Explanation](../CU-Model-Explanation.md) - Why each AI model is needed
