"""
Step 1: Using Prebuilt Analyzers
================================
Demonstrates how to use Content Understanding's built-in analyzers
to extract structured data from standard business documents (invoices,
receipts) with zero configuration.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from azure.ai.contentunderstanding import ContentUnderstandingClient
from azure.ai.contentunderstanding.models import AnalysisInput
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import AzureError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

console = Console()


def create_client() -> ContentUnderstandingClient:
    """Create and return a Content Understanding client.

    Uses API key if CONTENTUNDERSTANDING_KEY is set, otherwise falls back
    to DefaultAzureCredential (works with ``az login``).
    """
    endpoint = os.getenv("CONTENTUNDERSTANDING_ENDPOINT")
    key = os.getenv("CONTENTUNDERSTANDING_KEY", "").strip()

    if not endpoint:
        raise RuntimeError(
            "Missing required environment variable: CONTENTUNDERSTANDING_ENDPOINT. "
            f"Update {Path(__file__).resolve().parent.parent / '.env'} and try again."
        )

    if key:
        credential = AzureKeyCredential(key)
    else:
        from azure.identity import DefaultAzureCredential
        credential = DefaultAzureCredential()

    return ContentUnderstandingClient(endpoint=endpoint, credential=credential)


def confidence_text(confidence) -> Text:
    if confidence is None:
        return Text("n/a", style="dim")
    if confidence > 0.85:
        style = "bold green"
    elif confidence >= 0.5:
        style = "bold yellow"
    else:
        style = "bold red"
    return Text(f"{confidence:.2f}", style=style)


def format_scalar_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def print_fields(fields: dict, indent: int = 0, table: Table | None = None, parent: str = "") -> Table:
    """Recursively render extracted fields with confidence scores."""
    if table is None:
        table = Table(show_header=True, header_style="bold cyan", expand=True)
        table.add_column("Field", style="bold")
        table.add_column("Value")
        table.add_column("Confidence", justify="right")

    for name, field in fields.items():
        if field is None:
            continue

        path = f"{parent}.{name}" if parent else name
        value = getattr(field, "value", None)
        confidence = getattr(field, "confidence", None)

        if isinstance(value, dict):
            table.add_row(f"{'  ' * indent}{path}", "[object]", confidence_text(confidence))
            print_fields(value, indent + 1, table, path)
        elif isinstance(value, list):
            preview_values = []
            nested_items = []
            for index, item in enumerate(value):
                item_value = getattr(item, "value", item)
                if isinstance(item_value, dict):
                    nested_items.append((index, item_value))
                elif item_value not in (None, ""):
                    preview_values.append(str(item_value))

            preview = ", ".join(preview_values[:5])
            if len(preview_values) > 5:
                preview += ", ..."
            if not preview:
                preview = f"[{len(value)} items]"
            else:
                preview = f"[{len(value)} items] {preview}"

            table.add_row(f"{'  ' * indent}{path}", preview, confidence_text(confidence))
            for index, nested_value in nested_items[:3]:
                print_fields(nested_value, indent + 1, table, f"{path}[{index}]")
        else:
            table.add_row(f"{'  ' * indent}{path}", format_scalar_value(value), confidence_text(confidence))

    return table


def analyze_with_prebuilt(client: ContentUnderstandingClient, analyzer_id: str, document_url: str):
    """
    Analyze a document using a prebuilt analyzer.

    Args:
        client: The Content Understanding client.
        analyzer_id: The prebuilt analyzer to use (e.g., "prebuilt-invoice").
        document_url: Public URL of the document to analyze.
    """
    filename = document_url.split("/")[-1]
    console.print(
        Panel.fit(
            f"[bold]{analyzer_id}[/bold]\n[dim]{filename}[/dim]",
            title="Analysis Run",
            border_style="blue",
        )
    )

    try:
        poller = client.begin_analyze(
            analyzer_id=analyzer_id,
            inputs=[AnalysisInput(url=document_url)],
        )
        result = poller.result()
    except AzureError as exc:
        console.print(
            Panel.fit(
                f"Unable to analyze {filename}.\n[red]{exc}[/red]",
                title="API Error",
                border_style="red",
            )
        )
        return
    except Exception as exc:
        console.print(
            Panel.fit(
                f"Unexpected error while analyzing {filename}.\n[red]{exc}[/red]",
                title="Error",
                border_style="red",
            )
        )
        return

    if not result.contents:
        console.print(Panel.fit("No content returned.", title="Empty Result", border_style="yellow"))
        return

    for content in result.contents:
        console.print(Panel.fit("Markdown Preview", border_style="magenta"))
        markdown_preview = content.markdown[:500] if content.markdown else "No markdown returned."
        console.print(Panel(markdown_preview, border_style="magenta"))

        if content.fields:
            console.print(Panel.fit("Extracted Fields", border_style="cyan"))
            console.print(print_fields(content.fields))
        else:
            console.print(Panel.fit("No extracted fields returned.", border_style="yellow"))


def main():
    try:
        client = create_client()
    except RuntimeError as exc:
        console.print(Panel.fit(str(exc), title="Configuration Error", border_style="red"))
        return
    except Exception as exc:
        console.print(Panel.fit(str(exc), title="Startup Error", border_style="red"))
        return

    sample_invoice = (
        "https://raw.githubusercontent.com/"
        "Azure-Samples/azure-ai-content-understanding-assets/"
        "main/document/invoice.pdf"
    )

    sample_receipt = (
        "https://raw.githubusercontent.com/"
        "Azure-Samples/azure-ai-content-understanding-assets/"
        "main/document/receipt.png"
    )

    console.print(Panel.fit("EXAMPLE 1: Prebuilt Invoice Analyzer", border_style="green"))
    analyze_with_prebuilt(client, "prebuilt-invoice", sample_invoice)

    console.print(Panel.fit("EXAMPLE 2: Prebuilt Receipt Analyzer", border_style="green"))
    analyze_with_prebuilt(client, "prebuilt-receipt", sample_receipt)

    console.print(Panel.fit("Prebuilt analyzer walkthrough complete!", border_style="green"))


if __name__ == "__main__":
    main()
