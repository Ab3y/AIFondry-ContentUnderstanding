"""
Step 2: Custom Entity Extractor with Summary Generation
========================================================
Creates a custom analyzer that extracts key entities (people, organizations,
dates, monetary amounts) and generates a one-paragraph summary from any
document type.

This demonstrates the three extraction methods:
  - extract: Pull literal values from the document
  - generate: AI-generated fields (summaries, insights)
  - classify: Categorize the document type
"""

import os
import time
from pathlib import Path

from dotenv import load_dotenv
from azure.ai.contentunderstanding import ContentUnderstandingClient
from azure.ai.contentunderstanding.models import (
    AnalysisInput,
    ContentAnalyzer,
    ContentAnalyzerConfig,
    ContentFieldDefinition,
    ContentFieldSchema,
    ContentFieldType,
    GenerationMethod,
)
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import AzureError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

console = Console()
ENTITY_STYLES = {
    "people": ("People", "cyan"),
    "organizations": ("Organizations", "magenta"),
    "dates": ("Dates", "green"),
    "monetary_amounts": ("Amounts", "yellow"),
    "locations": ("Locations", "blue"),
}


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


def create_entity_extractor(client: ContentUnderstandingClient) -> str:
    """
    Create a custom analyzer that extracts key entities and generates summaries.

    Returns the analyzer ID.
    """
    analyzer_id = f"entity-extractor-{int(time.time())}"

    field_schema = ContentFieldSchema(
        name="entity_extraction_schema",
        description="Schema for extracting key entities and generating document summaries",
        fields={
            "people": ContentFieldDefinition(
                type=ContentFieldType.ARRAY,
                method=GenerationMethod.EXTRACT,
                description="Names of people mentioned in the document",
                items=ContentFieldDefinition(type=ContentFieldType.STRING),
            ),
            "organizations": ContentFieldDefinition(
                type=ContentFieldType.ARRAY,
                method=GenerationMethod.EXTRACT,
                description="Names of companies and organizations mentioned",
                items=ContentFieldDefinition(type=ContentFieldType.STRING),
            ),
            "dates": ContentFieldDefinition(
                type=ContentFieldType.ARRAY,
                method=GenerationMethod.EXTRACT,
                description="All dates mentioned in the document",
                items=ContentFieldDefinition(type=ContentFieldType.STRING),
            ),
            "monetary_amounts": ContentFieldDefinition(
                type=ContentFieldType.ARRAY,
                method=GenerationMethod.EXTRACT,
                description="All monetary amounts and currencies mentioned",
                items=ContentFieldDefinition(type=ContentFieldType.STRING),
            ),
            "locations": ContentFieldDefinition(
                type=ContentFieldType.ARRAY,
                method=GenerationMethod.EXTRACT,
                description="Physical addresses, cities, states, or countries mentioned",
                items=ContentFieldDefinition(type=ContentFieldType.STRING),
            ),
            "summary": ContentFieldDefinition(
                type=ContentFieldType.STRING,
                method=GenerationMethod.GENERATE,
                description=(
                    "A concise one-paragraph summary of the document, covering "
                    "the main purpose, key parties involved, and any important "
                    "dates or amounts."
                ),
            ),
            "key_terms": ContentFieldDefinition(
                type=ContentFieldType.ARRAY,
                method=GenerationMethod.GENERATE,
                description="The 5 most important terms or concepts in the document",
                items=ContentFieldDefinition(type=ContentFieldType.STRING),
            ),
            "document_type": ContentFieldDefinition(
                type=ContentFieldType.STRING,
                method=GenerationMethod.CLASSIFY,
                description="The type of document being analyzed",
                enum=[
                    "invoice",
                    "receipt",
                    "contract",
                    "report",
                    "letter",
                    "memo",
                    "form",
                    "other",
                ],
            ),
        },
    )

    config = ContentAnalyzerConfig(
        return_details=True,
        enable_ocr=True,
        enable_layout=True,
        estimate_field_source_and_confidence=True,
    )

    analyzer = ContentAnalyzer(
        base_analyzer_id="prebuilt-document",
        description="Custom analyzer for entity extraction and document summarization",
        config=config,
        field_schema=field_schema,
        models={
            "completion": "gpt-4.1",
            "embedding": "text-embedding-3-large",
        },
    )

    console.print(Panel.fit(f"Creating custom analyzer [bold]{analyzer_id}[/bold]", border_style="cyan"))
    try:
        poller = client.begin_create_analyzer(
            analyzer_id=analyzer_id,
            resource=analyzer,
        )
        poller.result()
        result = client.get_analyzer(analyzer_id=analyzer_id)
    except AzureError as exc:
        raise RuntimeError(f"Failed to create analyzer '{analyzer_id}': {exc}") from exc

    console.print(Panel.fit(f"Analyzer '{analyzer_id}' created successfully!", border_style="green"))
    if result.field_schema and result.field_schema.fields:
        table = Table(title="Configured Fields", header_style="bold cyan")
        table.add_column("Field", style="bold")
        table.add_column("Type")
        table.add_column("Method")
        for name, field_def in result.field_schema.fields.items():
            method = field_def.method if field_def.method else "auto"
            table.add_row(name, str(field_def.type), str(method))
        console.print(table)

    return analyzer_id


def render_entity_section(title: str, style: str, items: list[str]) -> None:
    body = "\n".join(f"• {item}" for item in items) if items else "No values detected."
    console.print(Panel(body, title=title, border_style=style))


def render_key_terms(terms: list[str]) -> None:
    term_text = Text()
    for term in terms:
        term_text.append(f" {term} ", style="bold white on dark_green")
        term_text.append(" ")
    console.print(Panel(term_text if term_text.plain.strip() else "No key terms generated.", title="Key Terms", border_style="green"))


def analyze_document(client: ContentUnderstandingClient, analyzer_id: str, document_url: str):
    """Analyze a document and print extracted entities and summary."""
    filename = document_url.split("/")[-1]
    console.print(Panel.fit(f"Analyzing [bold]{filename}[/bold]", border_style="blue"))

    try:
        poller = client.begin_analyze(
            analyzer_id=analyzer_id,
            inputs=[AnalysisInput(url=document_url)],
        )
        result = poller.result()
    except AzureError as exc:
        console.print(Panel.fit(f"Unable to analyze {filename}.\n[red]{exc}[/red]", title="API Error", border_style="red"))
        return
    except Exception as exc:
        console.print(Panel.fit(f"Unexpected error while analyzing {filename}.\n[red]{exc}[/red]", title="Error", border_style="red"))
        return

    if not result.contents:
        console.print(Panel.fit("No content returned.", title="Empty Result", border_style="yellow"))
        return

    content = result.contents[0]

    if content.markdown:
        console.print(Panel(content.markdown[:300] + ("..." if len(content.markdown) > 300 else ""), title="Markdown Preview", border_style="magenta"))

    if not content.fields:
        console.print(Panel.fit("No fields extracted.", border_style="yellow"))
        return

    doc_type = content.fields.get("document_type")
    doc_type_value = getattr(doc_type, "value", "unknown")
    console.print(Panel.fit(f"[bold white on blue] {doc_type_value} [/bold white on blue]", title="Document Type", border_style="blue"))

    summary = content.fields.get("summary")
    if summary and summary.value:
        console.print(Panel(summary.value, title="Summary", border_style="bright_magenta"))

    for field_name, (label, style) in ENTITY_STYLES.items():
        field = content.fields.get(field_name)
        items = [item.value for item in getattr(field, "value", []) if getattr(item, "value", None)]
        render_entity_section(label, style, items)

    key_terms = content.fields.get("key_terms")
    terms = [item.value for item in getattr(key_terms, "value", []) if getattr(item, "value", None)]
    render_key_terms(terms)


def main():
    analyzer_id = None
    try:
        client = create_client()
        analyzer_id = create_entity_extractor(client)

        sample_docs = [
            (
                "https://raw.githubusercontent.com/"
                "Azure-Samples/azure-ai-content-understanding-assets/"
                "main/document/invoice.pdf"
            ),
        ]

        for doc_url in sample_docs:
            analyze_document(client, analyzer_id, doc_url)
    except RuntimeError as exc:
        console.print(Panel.fit(str(exc), title="Setup Error", border_style="red"))
        return
    except AzureError as exc:
        console.print(Panel.fit(str(exc), title="API Error", border_style="red"))
        return
    except Exception as exc:
        console.print(Panel.fit(str(exc), title="Error", border_style="red"))
        return
    finally:
        if analyzer_id:
            try:
                console.print(Panel.fit(f"Cleaning up analyzer '{analyzer_id}'", border_style="yellow"))
                client.delete_analyzer(analyzer_id=analyzer_id)
                console.print(Panel.fit(f"Analyzer '{analyzer_id}' deleted.", border_style="green"))
            except Exception as exc:
                console.print(Panel.fit(f"Cleanup failed for '{analyzer_id}': {exc}", title="Cleanup Warning", border_style="yellow"))

    console.print(Panel.fit("Custom entity extraction walkthrough complete!", border_style="green"))


if __name__ == "__main__":
    main()
