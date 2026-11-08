# Google AI Model Pricing Source Documentation

## Source Information
- **Source URL**: [https://ai.google.dev/pricing](https://ai.google.dev/pricing)
- **Retrieval Date**: 2026-11-07
- **Model Selected**: `gemini-3-flash-preview` (Gemini 3 Flash Preview)

## Published Rates (Standard Paid Tier)
- **Input Tokens**: $0.50 per 1,000,000 tokens ($0.0000005 per token)
- **Output Tokens (including thinking tokens)**: $3.00 per 1,000,000 tokens ($0.000003 per token)

### Official Pricing Table Quote
Under the `gemini-3-flash-preview` Standard Paid Tier table at [https://ai.google.dev/pricing](https://ai.google.dev/pricing) (fetched 2026-11-07):
> *"Output price (including thinking tokens) | Free Tier: Free of charge | Paid Tier, per 1M tokens in USD: $3.00"*

## Cost Computation Formula (Method B - Including Thinking Tokens)
$$\text{Cost} = (\text{Prompt Tokens} \times \$0.0000005) + ((\text{Candidate Tokens} + \text{Thought Tokens}) \times \$0.000003)$$

Using measured live-run totals across the 14 successful HTTP 200 calls (14,445 prompt tokens; 751 candidate tokens; 7,715 thought tokens):
$$\text{Cost} = (14{,}445 \times \$0.0000005) + ((751 + 7{,}715) \times \$0.000003) = \$0.0072225 + \$0.025398 = \mathbf{\$0.0326205}\text{ (approx. }\mathbf{\$0.033}\text{)}$$

*Note: In the free tier, requests are free of charge within project rate limits; the formula above reflects standard paid commercial rates.*
