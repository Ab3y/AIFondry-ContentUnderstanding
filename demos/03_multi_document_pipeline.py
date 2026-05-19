"""
Step 3: Multi-Document Pipeline with Classification
=====================================================
Builds a full pipeline that:
  1. Creates a classification analyzer to categorize incoming documents
  2. Creates a custom entity/summary analyzer for general documents
  3. Processes multiple documents of various types
  4. Routes each through classification → extraction
  5. Outputs a consolidated JSON report

This is the pattern you'd use in production when receiving mixed
document types from customers.
"""

import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from azure.ai.contentunderstanding import ContentUnderstandingClient
from azure.ai.contentunderstanding.models import (
    AnalysisInput,
    ContentAnalyzer,
    ContentAnalyzerConfig,
    ContentCategoryDefinition,
    ContentFieldDefinition,
    ContentFieldSchema,
    ContentFieldType,
    GenerationMethod,
)
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import AzureError
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

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


def create_entity_summary_analyzer(client: ContentUnderstandingClient) -> str:
    """Create a custom analyzer for entity extraction + summary on general documents."""
    analyzer_id = f"entity-summary-{int(time.time())}"

    field_schema = ContentFieldSchema(
        name="entity_summary_schema",
        description="Extract entities and generate summaries",
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
                description="Companies and organizations mentioned",
                items=ContentFieldDefinition(type=ContentFieldType.STRING),
            ),
            "dates": ContentFieldDefinition(
                type=ContentFieldType.ARRAY,
                method=GenerationMethod.EXTRACT,
                description="All dates mentioned",
                items=ContentFieldDefinition(type=ContentFieldType.STRING),
            ),
            "monetary_amounts": ContentFieldDefinition(
                type=ContentFieldType.ARRAY,
                method=GenerationMethod.EXTRACT,
                description="All monetary amounts",
                items=ContentFieldDefinition(type=ContentFieldType.STRING),
            ),
            "summary": ContentFieldDefinition(
                type=ContentFieldType.STRING,
                method=GenerationMethod.GENERATE,
                description="A concise summary covering purpose, key parties, and important details",
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
        description="Entity extraction and summary for general documents",
        config=config,
        field_schema=field_schema,
        models={
            "completion": "gpt-4.1",
            "embedding": "text-embedding-3-large",
        },
    )

    console.print(Panel.fit(f"Creating entity/summary analyzer [bold]{analyzer_id}[/bold]", border_style="cyan"))
    try:
        poller = client.begin_create_analyzer(analyzer_id=analyzer_id, resource=analyzer)
        poller.result()
    except AzureError as exc:
        raise RuntimeError(f"Failed to create entity/summary analyzer '{analyzer_id}': {exc}") from exc
    console.print(Panel.fit("Entity/summary analyzer created.", border_style="green"))
    return analyzer_id


def create_classifier_analyzer(client: ContentUnderstandingClient, entity_analyzer_id: str) -> str:
    """
    Create a classification analyzer that categorizes documents and routes
    recognized types to the appropriate analyzer for extraction.
    """
    classifier_id = f"doc-classifier-{int(time.time())}"

    categories = {
        "invoice": ContentCategoryDefinition(
            description="Invoices, bills, or payment requests from vendors or suppliers",
            analyzer_id="prebuilt-invoice",
        ),
        "receipt": ContentCategoryDefinition(
            description="Receipts from purchases, retail transactions, or dining",
            analyzer_id="prebuilt-receipt",
        ),
        "contract": ContentCategoryDefinition(
            description="Legal contracts, agreements, terms of service, or NDAs",
            analyzer_id=entity_analyzer_id,
        ),
        "report": ContentCategoryDefinition(
            description="Business reports, financial statements, or analysis documents",
            analyzer_id=entity_analyzer_id,
        ),
        "correspondence": ContentCategoryDefinition(
            description="Letters, memos, emails, or other business correspondence",
            analyzer_id=entity_analyzer_id,
        ),
    }

    config = ContentAnalyzerConfig(
        return_details=True,
        enable_segment=False,
        content_categories=categories,
        omit_content=False,
    )

    classifier = ContentAnalyzer(
        base_analyzer_id="prebuilt-document",
        description="Classifies documents and routes to the right analyzer",
        config=config,
        models={"completion": "gpt-4.1"},
    )

    console.print(Panel.fit(f"Creating classifier analyzer [bold]{classifier_id}[/bold]", border_style="cyan"))
    try:
        poller = client.begin_create_analyzer(analyzer_id=classifier_id, resource=classifier)
        poller.result()
    except AzureError as exc:
        raise RuntimeError(f"Failed to create classifier analyzer '{classifier_id}': {exc}") from exc
    console.print(Panel.fit("Classifier analyzer created.", border_style="green"))
    return classifier_id


def render_document_summary(doc_result: dict) -> None:
    content_count = len(doc_result["contents"])
    console.print(Panel.fit(f"Processed [bold]{doc_result['filename']}[/bold] with {content_count} routed result(s)", border_style="blue"))

    for content_entry in doc_result["contents"]:
        category = content_entry["category"] or "unknown"
        analyzer_used = content_entry["analyzer_used"] or "unknown"
        summary = content_entry["fields"].get("summary", {}).get("value") if content_entry["fields"] else None

        detail_table = Table(show_header=False, box=None, pad_edge=False)
        detail_table.add_column(style="bold cyan", no_wrap=True)
        detail_table.add_column()
        detail_table.add_row("Category", category)
        detail_table.add_row("Analyzer", analyzer_used)
        if summary:
            detail_table.add_row("Summary", str(summary)[:180] + ("..." if len(str(summary)) > 180 else ""))

        entity_fields = ["people", "organizations", "dates", "monetary_amounts"]
        for field_name in entity_fields:
            values = content_entry["fields"].get(field_name, {}).get("values")
            if values:
                detail_table.add_row(field_name.replace("_", " ").title(), ", ".join(str(v) for v in values[:5]))

        console.print(Panel(detail_table, title=f"Result: {category}", border_style="magenta"))


def process_documents(client: ContentUnderstandingClient, classifier_id: str, document_urls: list[str]) -> list[dict]:
    """Process a batch of documents through the classification pipeline."""
    results = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task("Processing documents", total=len(document_urls))

        for url in document_urls:
            filename = url.split("/")[-1]
            progress.update(task_id, description=f"Processing {filename}")

            doc_result = {
                "filename": filename,
                "source_url": url,
                "contents": [],
            }

            try:
                poller = client.begin_analyze(
                    analyzer_id=classifier_id,
                    inputs=[AnalysisInput(url=url)],
                )
                result = poller.result()
            except AzureError as exc:
                doc_result["error"] = str(exc)
                results.append(doc_result)
                console.print(Panel.fit(f"Unable to process {filename}.\n[red]{exc}[/red]", title="API Error", border_style="red"))
                progress.advance(task_id)
                continue
            except Exception as exc:
                doc_result["error"] = str(exc)
                results.append(doc_result)
                console.print(Panel.fit(f"Unexpected error while processing {filename}.\n[red]{exc}[/red]", title="Error", border_style="red"))
                progress.advance(task_id)
                continue

            if not result.contents:
                console.print(Panel.fit(f"No content returned for {filename}.", title="Empty Result", border_style="yellow"))
                results.append(doc_result)
                progress.advance(task_id)
                continue

            for content in result.contents:
                content_entry = {
                    "category": getattr(content, "category", None),
                    "analyzer_used": getattr(content, "analyzer_id", None),
                    "markdown_preview": content.markdown[:200] if content.markdown else None,
                    "fields": {},
                }

                if content.fields:
                    for name, field in content.fields.items():
                        if field is None:
                            continue

                        value = field.value
                        confidence = field.confidence

                        if isinstance(value, list):
                            items = [item.value for item in value if item and item.value]
                            content_entry["fields"][name] = {
                                "values": items,
                                "count": len(items),
                            }
                        elif isinstance(value, dict):
                            content_entry["fields"][name] = {"value": str(value)}
                        else:
                            content_entry["fields"][name] = {
                                "value": value,
                                "confidence": confidence,
                            }

                doc_result["contents"].append(content_entry)

            results.append(doc_result)
            render_document_summary(doc_result)
            progress.advance(task_id)

    return results


def render_classification_summary(results: list[dict]) -> None:
    table = Table(title="Classification Summary", header_style="bold cyan", expand=True)
    table.add_column("Document", style="bold")
    table.add_column("Category")
    table.add_column("Analyzer")
    table.add_column("Status")

    for doc in results:
        if doc.get("error"):
            table.add_row(doc["filename"], "-", "-", f"Error: {doc['error']}")
            continue
        if not doc["contents"]:
            table.add_row(doc["filename"], "-", "-", "No content")
            continue

        first_content = doc["contents"][0]
        table.add_row(
            doc["filename"],
            str(first_content.get("category") or "unknown"),
            str(first_content.get("analyzer_used") or "unknown"),
            "Processed",
        )

    console.print(table)


def render_consolidated_report(results: list[dict], output_path: str) -> None:
    report_table = Table(title="Consolidated Report", header_style="bold green", expand=True)
    report_table.add_column("Document", style="bold")
    report_table.add_column("Highlights")

    for doc in results:
        if doc.get("error"):
            report_table.add_row(doc["filename"], f"[red]Error:[/red] {doc['error']}")
            continue

        highlights = []
        for content in doc["contents"]:
            category = content.get("category") or "unknown"
            summary = content["fields"].get("summary", {}).get("value") if content.get("fields") else None
            if summary:
                highlights.append(f"[bold]{category}[/bold]: {str(summary)[:120]}{'...' if len(str(summary)) > 120 else ''}")
            else:
                highlights.append(f"[bold]{category}[/bold]: No generated summary")

        report_table.add_row(doc["filename"], "\n".join(highlights) if highlights else "No routed content")

    console.print(report_table)
    console.print(Panel.fit(f"Consolidated report saved to [bold]{output_path}[/bold]", border_style="green"))


def main():
    client = None
    entity_analyzer_id = None
    classifier_id = None

    try:
        client = create_client()

        entity_analyzer_id = create_entity_summary_analyzer(client)
        classifier_id = create_classifier_analyzer(client, entity_analyzer_id)

        document_urls = [
            "https://raw.githubusercontent.com/Azure-Samples/azure-ai-content-understanding-assets/main/document/invoice.pdf",
            "https://raw.githubusercontent.com/Azure-Samples/azure-ai-content-understanding-assets/main/document/receipt.png",
        ]

        console.print(Panel.fit(f"Processing {len(document_urls)} documents", border_style="blue"))
        results = process_documents(client, classifier_id, document_urls)
        render_classification_summary(results)

        output_path = "analysis_report.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=str)
        render_consolidated_report(results, output_path)
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
        if client and classifier_id:
            try:
                console.print(Panel.fit(f"Deleting analyzer '{classifier_id}'", border_style="yellow"))
                client.delete_analyzer(analyzer_id=classifier_id)
            except Exception as exc:
                console.print(Panel.fit(f"Failed to delete '{classifier_id}': {exc}", title="Cleanup Warning", border_style="yellow"))
        if client and entity_analyzer_id:
            try:
                console.print(Panel.fit(f"Deleting analyzer '{entity_analyzer_id}'", border_style="yellow"))
                client.delete_analyzer(analyzer_id=entity_analyzer_id)
            except Exception as exc:
                console.print(Panel.fit(f"Failed to delete '{entity_analyzer_id}': {exc}", title="Cleanup Warning", border_style="yellow"))

    console.print(Panel.fit("Multi-document pipeline walkthrough complete!", border_style="green"))


if __name__ == "__main__":
    main()
