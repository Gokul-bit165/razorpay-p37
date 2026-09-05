# Findings: Audit of MockLLMClient and Extraction Evaluation Provenance

## T1.1 Audit of `MockLLMClient` Implementation

### How `MockLLMClient` Produces Rules on Unseen Rendered Text
When evaluated on unseen contract text produced by `contract_renderer.py` (Regime C), `MockLLMClient` does **not** perform zero-shot language model inference, nor is it merely returning pre-canned responses keyed on clause identifiers.

Instead, `MockLLMClient` executes `_semantic_parse(user_prompt)`, which is a **bespoke, second regex-and-keyword rule extraction engine** containing hand-coded regular expressions tailored to the phrasing templates and synonym pools of the contract dataset.

### Code Evidence from `src/p37/extraction/llm_client.py`

In `src/p37/extraction/llm_client.py`, `MockLLMClient.generate_structured` falls back to `_semantic_parse`:

```python
# Lines 50-51
# Deterministic semantic parser mimicking an ideal LLM
return self._semantic_parse(user_prompt)
```

Within `_semantic_parse(text: str)`, extraction of nonline allocations, commission treatments, recovery orders, and role bindings is performed using extensive lists of hardcoded regular expression tuples and phrase matchers:

```python
# Lines 125-156
synonym_patterns = [
    ("shipping_funder", r"carrier settlement pool bears the loss"),
    ("shipping_funder", r"freight and logistics provider shoulders unallocated reversal balances"),
    ("shipping_funder", r"transportation facilitator bears final liability"),
    ("shipping_funder", r"delivery and handling partners are assigned sole responsibility"),
    ("shipping_funder", r"dispatch logistics associates absorb remaining unmapped"),
    ("shipping_funder", r"party providing the shipping service"),
    ("shipping_funder", r"shipping partner bears the cost(?: of all non-line refunds)?"),
    ("shipping_funder", r"shipping account bears the loss"),
    ("platform_absorbs", r"(?:non-line )?losses are absorbed by the marketplace operator"),
    ("platform_absorbs", r"unassigned refund deductions are absorbed entirely by the marketplace operator"),
    ("platform_absorbs", r"non-itemized balances shall be defrayed directly by the central platform"),
    ("platform_absorbs", r"overhead and miscellaneous return costs fall squarely upon the platform host"),
    ("platform_absorbs", r"system-wide return adjustments are written off by the platform administrator"),
    ("platform_absorbs", r"(?:absorbed by|assumed by|covered by|discharged by) the (?:central )?(?:marketplace )?platform(?: partner)?"),
    ("platform_absorbs", r"central platform assumes full absorption"),
    ("discount_funder", r"promotional concession losses fall on the promotional fund account"),
    ("discount_funder", r"rebate adjustments are charged against the promotional reserve pool"),
    ("discount_funder", r"promotional subsidization deficits revert to the coupon-sponsoring account"),
    ("discount_funder", r"markdown allowances and promo deficits are deducted from the marketing allowance"),
    ("discount_funder", r"campaign voucher funding balances carry full clawback obligations"),
    ("discount_funder", r"(?:assumed by|covered by|discharged by) the entity funding discount allowances"),
    ("discount_funder", r"discount-funding party bears the cost"),
    ("proportional", r"any non-order-line refund is shared across all linked accounts in proportion"),
    ("proportional", r"unattributed return balances are split ratably"),
    ("proportional", r"overhead clawback liabilities are apportioned among parties on a pro-rata basis"),
    ("proportional", r"participate evenly in non-itemized return distributions"),
    ("proportional", r"clawbacks without specific item bindings are shared ratably"),
    ("proportional", r"(?:borne by|assumed by|covered by) all recipient accounts on a proportional basis"),
    ("proportional", r"share non-line refunds proportionally"),
]
for val, pat in synonym_patterns:
    m_syn = re.search(pat, text, re.I)
    if m_syn:
        nonline_val = val
        nonline_span = m_syn.group(0)
        break
```

Similar hardcoded regex tables exist for commission treatments (lines 190–219) and recovery sequences (lines 234–246).

### Conclusion

The logic inside `MockLLMClient` is a second handwritten parser created by this repository's authors, not a language model, meaning that any evaluation comparing `MockLLMClient` against `extractor.py` is merely comparing two handwritten parsers rather than demonstrating an LLM advantage.
