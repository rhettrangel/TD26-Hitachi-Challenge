# Google AI Model Pricing Source Documentation

## Model & Tier Information
- **Model**: `gemini-3-flash-preview`
- **Tier**: Standard (paid). Batch, Flex, and Priority tiers were not used and are not cited.
- **Source URL**: [https://ai.google.dev/pricing](https://ai.google.dev/pricing) (Gemini 3 Flash Preview, Standard tab)
- **Retrieval Date**: 2026-11-07

## Rates (per 1M tokens, USD, Paid Tier, Standard)
- **Input (text/image/video)**: $0.50 (audio $1.00, not used)
- **Output (including thinking tokens)**: $3.00
- **Free Tier**: Listed as "Free of charge" for these rows on the same page. The run's actual charge depends on the key's billing tier, which is to be confirmed on the AI Studio billing page.

## Quote
Under the `gemini-3-flash-preview` Standard Paid Tier table at [https://ai.google.dev/pricing](https://ai.google.dev/pricing) (fetched 2026-11-07):
> *"Output price (including thinking tokens)"*
appears in the Standard table, which is the basis for billing thought tokens at the output rate.

## Caveat
This is a preview model. Rates may change before release. Costs are based on the rates as of the retrieval date.

## Cost Computation Formula
$$\text{Cost} = (\text{prompt tokens} \times \$0.0000005) + ((\text{candidate tokens} + \text{thought tokens}) \times \$0.000003)$$

Using totals of 14,445 prompt, 751 candidate, and 7,715 thought tokens across 14 successful calls:
$$\text{Cost} = (14{,}445 \times \$0.0000005) + ((751 + 7{,}715) \times \$0.000003) = \$0.0072225 + \$0.025398 = \mathbf{\$0.0326205}\text{ (about }\mathbf{\$0.033}\text{)}$$

- 22,911 billed tokens come from 14 successful live calls. E-15 was rate-limited (HTTP 429) and used no tokens.
- Thinking tokens (7,715) were derived as total minus prompt minus candidates, because the raw usage files don't label them.
- $0.033 is at paid Standard rates. Billing tier used: free. Actual charge: $0.