# Content Understanding - Model Explanation

Content Understanding requires three AI model deployments to power its document processing pipeline. Each model serves a distinct role.

## gpt-4.1 (Completion Model)

This is the **brain** of Content Understanding. When you define fields with `generate` or `classify` methods, the service sends the extracted document content to this LLM to:

- **Generate** summaries, insights, and inferred values
- **Classify** documents into categories (invoice, receipt, contract, etc.)
- **Interpret** complex field extraction where literal text matching isn't enough

It's the most capable model in the pipeline and handles nuanced reasoning about document content.

> **Note**: Microsoft now recommends `gpt-5.2` as the completion model. The GPT-4.1 family retires October 2026, but `gpt-4.1` works fine for demos today.

## gpt-4.1-mini (Lightweight Completion)

Used for **faster, cheaper processing** on simpler tasks within the pipeline:

- Field confidence estimation
- Source grounding (mapping extracted values back to their location in the document)
- Simpler extraction tasks that don't need the full `gpt-4.1`

Think of it as the "fast path." Content Understanding routes simpler subtasks here to reduce latency and cost.

## text-embedding-3-large (Embedding Model)

This converts text into **vector representations** (embeddings). Used for:

- **Semantic matching** - finding where in the document a field value came from
- **Field-to-content alignment** - matching your field schema descriptions to relevant sections of the document
- **Contextualization** - the service tokenizes each page into approximately 1,000 tokens and uses embeddings to identify which parts are relevant to each field

## How They Work Together

```
Document --> OCR/Layout --> Markdown
                              |
                    text-embedding-3-large (find relevant sections)
                              |
                    gpt-4.1-mini (simple extractions, confidence scores)
                              |
                    gpt-4.1 (generate summaries, classify, complex fields)
                              |
                    Structured Output + Confidence Scores
```

## Cost Implications

- You pay for the **Content Understanding service** (per-page extraction) plus the **Azure OpenAI model usage** for field extraction
- Using `gpt-4.1-mini` for simpler tasks keeps costs down compared to routing everything through `gpt-4.1`
- Contextualization is billed at approximately 1,000 tokens per page/image, 100,000 per hour of audio, and 1,000,000 per hour of video
- There is no monthly subscription. Pricing is pure pay-as-you-go

## Resources

- [Content Understanding Overview](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/overview)
- [Analyzer Reference (Field Methods)](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/concepts/analyzer-reference)
- [Service Limits](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/service-limits)
- [Pricing](https://azure.microsoft.com/en-us/pricing/details/content-understanding/)
