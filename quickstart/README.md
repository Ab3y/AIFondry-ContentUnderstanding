# ⚡ Quickstart - Content Understanding in 2 Minutes

This quickstart gives you a fast, standalone demo for Azure AI Foundry Content Understanding using the `prebuilt-invoice` analyzer.

## Prerequisites

- Python 3.9+
- An Azure AI Foundry resource with **Content Understanding** enabled

## Run in 2 minutes

### 1) Install dependencies

From the repository root:

```powershell
python -m pip install -r quickstart\requirements.txt
```

### 2) Set up your `.env`

Create a `.env` file in the repository root:

```powershell
copy .env.template .env
```

Then update `.env` with your Azure AI Foundry endpoint and key:

```env
CONTENTUNDERSTANDING_ENDPOINT=https://<your-resource-name>.cognitiveservices.azure.com
CONTENTUNDERSTANDING_KEY=<your-api-key>
```

### 3) Run the demo

Use the public sample invoice:

```powershell
python quickstart\demo.py
```

Or pass your own public URL or local file path:

```powershell
python quickstart\demo.py https://example.com/invoice.pdf
python quickstart\demo.py .\data\my-invoice.pdf
```

## Expected output

The demo shows:

- A rich terminal header for the Content Understanding demo
- A color-coded table of extracted invoice fields and confidence scores
- A markdown preview of the analyzed document
- A summary section when the service returns one

## Need more details?

See the main [README](../README.md) for the full walkthrough, additional demos, and background information.

## See Also

- [Demo Walkthrough Scripts](../demos/README.md) - Progressive 3-step deep dive
- [Infrastructure (Bicep / Terraform)](../infra/README.md) - Deploy the Azure resource
- [Model Explanation](../CU-Model-Explanation.md) - Why each AI model is needed
