r"""Standalone quickstart demo for Azure AI Foundry Content Understanding.

This script demonstrates how to use the Azure AI Content Understanding SDK to
analyze documents (invoices, receipts, etc.) and extract structured data using
prebuilt analyzers. It renders the results as a rich, color-coded terminal table
showing extracted fields with confidence scores.

Architecture
------------
The script follows this flow:

    1. Load configuration from the repository root ``.env`` file
    2. Create a ``ContentUnderstandingClient`` (API key or Azure Identity auth)
    3. Build an ``AnalysisInput`` from a URL or local file path
    4. Submit the document to the ``prebuilt-invoice`` analyzer (async long-running operation)
    5. Render extracted fields, confidence scores, and markdown preview via Rich

Authentication
--------------
Two authentication modes are supported:

- **API Key**: Set ``CONTENTUNDERSTANDING_KEY`` in ``.env``. The script will use
  ``AzureKeyCredential`` to authenticate.
- **Azure Identity**: If ``CONTENTUNDERSTANDING_KEY`` is empty or missing, the
  script falls back to ``DefaultAzureCredential``, which picks up credentials
  from ``az login``, managed identity, or environment variables. This is required
  when the Azure resource has ``disableLocalAuth=true`` (common in enterprise
  subscriptions with security policies).

Confidence Score Color Coding
-----------------------------
Each extracted field includes a confidence score (0.0 - 1.0) displayed with
color coding to indicate reliability:

- **Green (> 0.85)**: High confidence - safe to auto-approve
- **Yellow (0.50 - 0.85)**: Medium confidence - flag for human review
- **Red (< 0.50)**: Low confidence - reject or re-process

Field Ordering
--------------
The output table prioritizes commonly-needed invoice fields (vendor name, invoice
number, dates, totals, line items) at the top, followed by remaining fields in
their original order. This is controlled by ``PREFERRED_FIELD_LABELS``.

Prerequisites
-------------
- Python 3.9+
- An Azure AI Foundry resource (``kind: AIServices``) with Content Understanding
  enabled and model deployments configured (``gpt-4.1``, ``gpt-4.1-mini``,
  ``text-embedding-3-large``)
- A ``.env`` file in the repository root with ``CONTENTUNDERSTANDING_ENDPOINT``

Dependencies
------------
- ``azure-ai-contentunderstanding>=1.1.0`` - Content Understanding SDK
- ``azure-identity>=1.15.0`` - Azure Identity for DefaultAzureCredential
- ``python-dotenv>=1.0.0`` - Environment variable loading from ``.env``
- ``rich>=13.0.0`` - Rich terminal formatting (tables, panels, colors)

Examples
--------
Analyze Azure's sample invoice (default)::

    python quickstart\\demo.py

Analyze a document from a public URL::

    python quickstart\\demo.py https://example.com/invoice.pdf

Analyze a local file::

    python quickstart\\demo.py .\\data\\receipt.png
    python quickstart\\demo.py "C:\\Users\\me\\Documents\\invoice.pdf"

References
----------
- Content Understanding Overview:
  https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/overview
- Prebuilt Analyzers:
  https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/concepts/prebuilt-analyzers
- Python SDK (PyPI):
  https://pypi.org/project/azure-ai-contentunderstanding/
"""

# ---------------------------------------------------------------------------
# Standard library imports
# ---------------------------------------------------------------------------
from __future__ import annotations  # Allows using str | None syntax on Python 3.9

import argparse      # Parses command-line arguments (e.g., file path or URL)
import mimetypes     # Guesses file type from extension (e.g., .png -> image/png)
import os            # Access environment variables like CONTENTUNDERSTANDING_ENDPOINT
import re            # Regular expressions for text normalization
from pathlib import Path          # Cross-platform file path handling
from typing import Any            # Type hint for values of unknown type
from urllib.parse import urlparse  # Breaks a URL into components (scheme, host, path)

# ---------------------------------------------------------------------------
# Azure SDK imports
# ---------------------------------------------------------------------------
# ContentUnderstandingClient is the main entry point for the SDK.
# You create one client and reuse it for all analysis calls.
from azure.ai.contentunderstanding import ContentUnderstandingClient

# AnalysisInput wraps either a URL or raw file bytes to send to the service.
from azure.ai.contentunderstanding.models import AnalysisInput

# AzureKeyCredential authenticates using an API key string.
# Used when CONTENTUNDERSTANDING_KEY is set in .env.
from azure.core.credentials import AzureKeyCredential

# Specific exception types the SDK can raise - we catch these to show
# user-friendly error messages instead of raw stack traces.
from azure.core.exceptions import ClientAuthenticationError, HttpResponseError, ServiceRequestError

# ---------------------------------------------------------------------------
# Third-party imports
# ---------------------------------------------------------------------------
# python-dotenv reads key=value pairs from a .env file into environment variables.
from dotenv import load_dotenv

# Rich is a Python library for beautiful terminal output. We use it for:
#   Console  - the main output object (replaces print())
#   Markdown - renders markdown text in the terminal
#   Panel    - draws a bordered box around content
#   Table    - draws formatted tables with columns and rows
#   Text     - styled text with colors (used for confidence scores)
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.traceback import install as install_rich_traceback

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default document to analyze when no argument is provided.
# This is a publicly-hosted sample invoice from Microsoft's GitHub.
SAMPLE_INVOICE_URL = (
    "https://raw.githubusercontent.com/"
    "Azure-Samples/azure-ai-content-understanding-assets/"
    "main/document/invoice.pdf"
)

# Environment variable names we look for in the .env file.
ENV_VARS = ("CONTENTUNDERSTANDING_ENDPOINT", "CONTENTUNDERSTANDING_KEY")

# Maps user-friendly labels to the various field names the SDK might return.
# The prebuilt-invoice analyzer returns fields like "VendorName", "InvoiceId",
# etc. Different analyzers may use slightly different names (e.g., "SellerName"
# vs "VendorName"), so we normalize and match against multiple variants.
# Fields listed here appear first in the output table, in this order.
PREFERRED_FIELD_LABELS = [
    ("Vendor Name", {"vendorname", "sellername", "merchantname"}),
    ("Invoice Number", {"invoiceid", "invoicenumber"}),
    ("Invoice Date", {"invoicedate", "billdate"}),
    ("Due Date", {"duedate", "paymentduedate"}),
    ("Subtotal", {"subtotal"}),
    ("Tax", {"totaltax", "tax"}),
    ("Invoice Total", {"invoicetotal", "totalamount", "total"}),
    ("Amount Due", {"amountdue", "balance", "balancedue"}),
    ("Line Items", {"items", "lineitems"}),
]

# Rich Console is the central object for all terminal output in this script.
# Instead of print(), we use console.print() which supports colors, tables, etc.
console = Console()


# ---------------------------------------------------------------------------
# Custom Exception
# ---------------------------------------------------------------------------

class DemoConfigurationError(RuntimeError):
    """Raised when the quickstart configuration is missing or invalid.

    This is a custom exception so we can catch configuration problems
    separately from SDK or network errors and show targeted help messages.
    """


# ---------------------------------------------------------------------------
# Configuration & Authentication
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    """Parse the optional URL or file path argument from the command line.

    If no argument is given, the script defaults to analyzing Azure's public
    sample invoice. The user can pass either:
      - A public URL (e.g., https://example.com/invoice.pdf)
      - A local file path (e.g., .\\data\\receipt.png)

    Returns:
        argparse.Namespace with a ``source`` attribute containing the URL or path.
    """
    parser = argparse.ArgumentParser(
        description="Analyze an invoice with Azure AI Foundry Content Understanding.",
    )
    parser.add_argument(
        "source",
        nargs="?",          # Makes the argument optional
        default=SAMPLE_INVOICE_URL,
        help="Optional public URL or local file path. Defaults to Azure's sample invoice.",
    )
    return parser.parse_args()


def load_environment() -> Path:
    """Load environment variables from the repository root ``.env`` file.

    The ``.env`` file lives one directory above this script (the repo root).
    It contains two key settings:

    - ``CONTENTUNDERSTANDING_ENDPOINT``: The URL of your Azure AI Services
      resource (e.g., https://my-resource.cognitiveservices.azure.com).
      This is REQUIRED.
    - ``CONTENTUNDERSTANDING_KEY``: Your API key. This is OPTIONAL - if not
      set, the script uses DefaultAzureCredential (your ``az login`` session).

    The function validates that the endpoint is a proper URL before proceeding.

    Returns:
        Path to the ``.env`` file that was loaded.

    Raises:
        DemoConfigurationError: If ``.env`` is missing or the endpoint is invalid.
    """
    # Look for .env in the parent directory (repo root), not in quickstart/
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        raise DemoConfigurationError(
            "Missing .env file. Copy .env.template to .env in the repository root, then "
            "set CONTENTUNDERSTANDING_ENDPOINT and CONTENTUNDERSTANDING_KEY."
        )

    # Load the .env file. override=False means existing env vars won't be overwritten.
    load_dotenv(env_path, override=False)

    # Validate that the endpoint is set
    if not os.environ.get("CONTENTUNDERSTANDING_ENDPOINT", "").strip():
        raise DemoConfigurationError("Missing required environment variable: CONTENTUNDERSTANDING_ENDPOINT.")

    # Validate that the endpoint looks like a real URL
    endpoint = os.environ["CONTENTUNDERSTANDING_ENDPOINT"].strip()
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise DemoConfigurationError(
            "CONTENTUNDERSTANDING_ENDPOINT must be a full URL like "
            "https://<your-resource-name>.cognitiveservices.azure.com"
        )

    # Clean up the values (remove trailing slashes, whitespace)
    os.environ["CONTENTUNDERSTANDING_ENDPOINT"] = endpoint.rstrip("/")
    key = os.environ.get("CONTENTUNDERSTANDING_KEY", "").strip()
    if key:
        os.environ["CONTENTUNDERSTANDING_KEY"] = key
    return env_path


def create_client() -> ContentUnderstandingClient:
    """Create and return a Content Understanding client.

    The client is the main object you use to interact with the Content
    Understanding service. It handles authentication, HTTP requests, and
    response parsing.

    Authentication strategy:
        1. If ``CONTENTUNDERSTANDING_KEY`` is set in ``.env``, use API key auth.
           This is the simplest method - just a string passed in every request.
        2. If the key is empty/missing, fall back to ``DefaultAzureCredential``.
           This automatically picks up credentials from (in order):
           - Environment variables (AZURE_CLIENT_ID, etc.)
           - Managed Identity (when running on Azure)
           - Azure CLI (``az login``)
           - Visual Studio Code
           - Interactive browser login

    Returns:
        A configured ``ContentUnderstandingClient`` ready to make API calls.
    """
    endpoint = os.environ["CONTENTUNDERSTANDING_ENDPOINT"]
    key = os.environ.get("CONTENTUNDERSTANDING_KEY", "").strip()

    if key:
        # API key auth: simple, works when disableLocalAuth=false on the resource
        credential = AzureKeyCredential(key)
    else:
        # Azure Identity auth: required when the resource has disableLocalAuth=true
        # (common in enterprise subscriptions with security policies)
        from azure.identity import DefaultAzureCredential
        credential = DefaultAzureCredential()

    return ContentUnderstandingClient(endpoint=endpoint, credential=credential)


# ---------------------------------------------------------------------------
# Input Handling
# ---------------------------------------------------------------------------

def build_analysis_input(source: str) -> tuple[AnalysisInput, str]:
    """Build an AnalysisInput from a public URL or local file path.

    The Content Understanding SDK accepts two kinds of input:
      - **URL**: A publicly accessible URL pointing to a document. The service
        downloads the file directly. This is the simplest option.
      - **Binary data**: Raw file bytes uploaded from your machine. Use this
        for local files or files behind authentication.

    This function detects which type the user provided and builds the
    appropriate ``AnalysisInput`` object.

    Args:
        source: Either a URL (starting with http:// or https://) or a local
                file path (absolute or relative).

    Returns:
        A tuple of (AnalysisInput, display_label) where display_label is a
        human-readable string shown in the output.

    Raises:
        FileNotFoundError: If a local file path was given but the file doesn't exist.
    """
    # Check if the source looks like a URL
    parsed = urlparse(source)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        # It's a URL - the service will download the file directly
        return AnalysisInput(url=source), source

    # It's a local file path - we need to read the bytes and upload them
    file_path = Path(source).expanduser()
    if not file_path.is_absolute():
        file_path = Path.cwd() / file_path  # Make relative paths absolute
    file_path = file_path.resolve()          # Resolve any .. or symlinks

    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(f"Local file not found: {file_path}")

    # Guess the MIME type from the file extension (e.g., .png -> image/png)
    # The service needs this to know how to process the file.
    mime_type, _ = mimetypes.guess_type(file_path.name)
    return (
        AnalysisInput(
            data=file_path.read_bytes(),           # Read the entire file into memory
            name=file_path.name,                   # Just the filename, not the full path
            mime_type=mime_type or "application/octet-stream",  # Fallback MIME type
        ),
        str(file_path),
    )


# ---------------------------------------------------------------------------
# Document Analysis
# ---------------------------------------------------------------------------

def analyze_document(client: ContentUnderstandingClient, analysis_input: AnalysisInput):
    """Submit a document for analysis and wait for the result.

    Content Understanding uses a **long-running operation** (LRO) pattern:
      1. ``begin_analyze()`` sends the document to the service and returns a
         "poller" object immediately. The service starts processing in the
         background.
      2. ``poller.result()`` blocks until the service finishes processing and
         returns the full result. For a single-page document this typically
         takes 5-30 seconds.

    The ``prebuilt-invoice`` analyzer is a zero-configuration analyzer that
    knows how to extract common invoice fields (vendor, dates, amounts, line
    items) without any custom training. Other prebuilt analyzers include
    ``prebuilt-receipt``, ``prebuilt-layout``, etc.

    Args:
        client: An authenticated ContentUnderstandingClient.
        analysis_input: The document to analyze (URL or binary data).

    Returns:
        The analysis result containing extracted fields, markdown, and metadata.
    """
    # console.status() shows an animated spinner while we wait
    with console.status("[bold cyan]Analyzing document...[/bold cyan]"):
        poller = client.begin_analyze(
            analyzer_id="prebuilt-invoice",  # Use the prebuilt invoice analyzer
            inputs=[analysis_input],         # List of inputs (we send one document)
        )
        return poller.result()  # Block until analysis is complete


# ---------------------------------------------------------------------------
# Field Name Utilities
# ---------------------------------------------------------------------------

def normalize_name(name: str) -> str:
    """Normalize a field name for fuzzy matching.

    The SDK returns field names in various formats (camelCase, PascalCase,
    snake_case). To match them against our PREFERRED_FIELD_LABELS, we strip
    everything except lowercase letters and digits.

    Examples:
        "VendorName"      -> "vendorname"
        "Invoice_Total"   -> "invoicetotal"
        "total-tax"       -> "totaltax"
    """
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def humanize_field_name(name: str) -> str:
    """Convert SDK-style field names into user-friendly labels.

    Inserts spaces before capital letters and replaces underscores with spaces
    to make field names readable in the output table.

    Examples:
        "VendorName"        -> "Vendor Name"
        "monetary_amounts"  -> "Monetary Amounts"
        "CustomerTaxId"     -> "Customer Tax Id"
    """
    return re.sub(r"(?<!^)(?=[A-Z])", " ", name).replace("_", " ").strip().title()


# ---------------------------------------------------------------------------
# Value Formatting Utilities
# ---------------------------------------------------------------------------

def confidence_text(confidence: float | None) -> Text:
    """Return a color-coded confidence score for display in Rich tables.

    Content Understanding assigns a confidence score (0.0 - 1.0) to each
    extracted field, indicating how certain the AI is about the value.

    Color coding:
        - Green (> 0.85): High confidence. Safe to use without human review.
        - Yellow (0.50 - 0.85): Medium confidence. Should be reviewed by a human.
        - Red (< 0.50): Low confidence. Likely incorrect - reject or re-process.
        - "n/a" (None): The service didn't provide a confidence score for this
          field (common for computed/aggregate fields like totals).

    Args:
        confidence: A float between 0.0 and 1.0, or None.

    Returns:
        A Rich Text object with the appropriate color style applied.
    """
    if confidence is None:
        return Text("n/a", style="dim")
    if confidence > 0.85:
        style = "bold green"
    elif confidence >= 0.5:
        style = "bold yellow"
    else:
        style = "bold red"
    return Text(f"{confidence:.2f}", style=style)


def format_simple_value(value: Any) -> str:
    """Format a plain Python value for display."""
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def format_field_value(field: Any, depth: int = 0) -> str:
    """Format a content field or nested value into readable text."""
    if field is None:
        return "—"

    if hasattr(field, "value"):
        value = field.value
        if hasattr(field, "value_object") and getattr(field, "value_object", None):
            entries = []
            for key, nested in field.value_object.items():
                entries.append(f"{humanize_field_name(key)}: {format_field_value(nested, depth + 1)}")
            return "; ".join(entries) if depth else "\n".join(entries)
        if hasattr(field, "value_array") and getattr(field, "value_array", None) is not None:
            items = field.value_array or []
            preview = [format_field_value(item, depth + 1) for item in items[:5]]
            body = "\n".join(f"{index + 1}. {item}" for index, item in enumerate(preview))
            if len(items) > 5:
                body = f"{body}\n… {len(items) - 5} more item(s)"
            return body or "—"
    else:
        value = field

    if isinstance(value, dict):
        entries = []
        for key, nested in value.items():
            rendered = format_field_value(nested, depth + 1)
            entries.append(f"{humanize_field_name(str(key))}: {rendered}")
        return "; ".join(entries) if depth else "\n".join(entries)

    if isinstance(value, list):
        preview = [format_field_value(item, depth + 1) for item in value[:5]]
        body = "\n".join(f"{index + 1}. {item}" for index, item in enumerate(preview))
        if len(value) > 5:
            body = f"{body}\n… {len(value) - 5} more item(s)"
        return body or "—"

    return format_simple_value(value)


def choose_field_rows(fields: dict[str, Any]) -> list[tuple[str, Any]]:
    """Order fields to prioritize invoice details users care about most."""
    normalized_map = {normalize_name(name): (name, field) for name, field in fields.items()}
    rows: list[tuple[str, Any]] = []
    used: set[str] = set()

    for label, candidates in PREFERRED_FIELD_LABELS:
        for candidate in candidates:
            match = normalized_map.get(candidate)
            if match and match[0] not in used:
                rows.append((label, match[1]))
                used.add(match[0])
                break

    for name, field in fields.items():
        if name not in used:
            rows.append((humanize_field_name(name), field))

    return rows


def extract_summary(content: Any) -> str | None:
    """Try to find a summary-like field when one is returned by the service."""
    direct_summary = getattr(content, "summary", None)
    if isinstance(direct_summary, str) and direct_summary.strip():
        return direct_summary.strip()

    for name, field in (content.fields or {}).items():
        normalized = normalize_name(name)
        if "summary" in normalized:
            summary_text = format_field_value(field).strip()
            if summary_text and summary_text != "—":
                return summary_text
    return None


def render_results(result: Any, source_label: str) -> None:
    """Render analysis results with Rich panels and tables."""
    if not result.contents:
        raise RuntimeError("The service returned no content for the supplied document.")

    content = result.contents[0]
    console.print(Panel.fit("[bold bright_cyan]Content Understanding Demo[/bold bright_cyan]", border_style="cyan"))
    console.print(f"[bold]Analyzer:[/bold] prebuilt-invoice")
    console.print(f"[bold]Source:[/bold] {source_label}\n")

    table = Table(title="Extracted Fields", show_lines=True, header_style="bold magenta")
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value", style="white", overflow="fold")
    table.add_column("Confidence", justify="right")

    for label, field in choose_field_rows(content.fields or {}):
        table.add_row(label, format_field_value(field), confidence_text(getattr(field, "confidence", None)))

    if table.row_count == 0:
        console.print(Panel("No extracted fields were returned.", title="Extracted Fields", border_style="yellow"))
    else:
        console.print(table)

    markdown_text = (content.markdown or "No markdown returned.").strip()
    markdown_preview = markdown_text[:500]
    if len(markdown_text) > 500:
        markdown_preview += "..."
    console.print(
        Panel(
            Markdown(markdown_preview or "No markdown returned."),
            title="Markdown Preview",
            border_style="blue",
        )
    )

    summary = extract_summary(content)
    if summary:
        console.print(Panel(summary, title="Summary", border_style="green"))

    if getattr(result, "warnings", None):
        warning_lines = "\n".join(str(warning) for warning in result.warnings)
        console.print(Panel(warning_lines, title="Warnings", border_style="yellow"))


def handle_error(error: Exception) -> int:
    """Render a friendly error message and return a process exit code."""
    if isinstance(error, DemoConfigurationError):
        console.print(Panel(str(error), title="Configuration Error", border_style="red"))
        return 2

    if isinstance(error, FileNotFoundError):
        console.print(Panel(str(error), title="File Error", border_style="red"))
        return 3

    if isinstance(error, ClientAuthenticationError):
        console.print(
            Panel(
                "Authentication failed. Double-check CONTENTUNDERSTANDING_KEY and make sure it belongs "
                "to the resource in CONTENTUNDERSTANDING_ENDPOINT.",
                title="Authentication Error",
                border_style="red",
            )
        )
        return 4

    if isinstance(error, ServiceRequestError):
        console.print(
            Panel(
                "Could not reach the Content Understanding endpoint. Verify the endpoint URL, network access, "
                "and that your Azure resource is available.",
                title="Network Error",
                border_style="red",
            )
        )
        return 5

    if isinstance(error, HttpResponseError):
        console.print(
            Panel(
                f"The service rejected the request: {error.message or str(error)}",
                title="Service Error",
                border_style="red",
            )
        )
        return 6

    console.print(Panel(str(error), title="Unexpected Error", border_style="red"))
    return 1


def main() -> int:
    """Run the quickstart demo."""
    install_rich_traceback(show_locals=False)
    args = parse_args()

    try:
        load_environment()
        client = create_client()
        analysis_input, source_label = build_analysis_input(args.source)
        result = analyze_document(client, analysis_input)
        render_results(result, source_label)
        return 0
    except Exception as error:
        return handle_error(error)


if __name__ == "__main__":
    raise SystemExit(main())
