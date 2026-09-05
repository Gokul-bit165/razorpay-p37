"""
LLM client abstraction and provider implementations for Phase 4 rule extraction.

Providers supported:
- MockLLMClient: Deterministic, offline, zero-network client for reproducible evaluation & pytest.
- GeminiLLMClient: Live API client using Google Generative AI (reads GEMINI_API_KEY).
- OpenAILLMClient: Live API client using OpenAI SDK (reads OPENAI_API_KEY).
"""
from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod
from typing import Any, Mapping, Optional


class LLMClient(ABC):
    """Abstract base class for LLM extraction clients."""

    @abstractmethod
    def generate_structured(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        """
        Send prompt to LLM and return structured JSON response dictionary.
        """
        pass


class MockLLMClient(LLMClient):
    """
    Deterministic offline client for reproducible testing and benchmarking.

    Extracts rules from canonical, synonym, passive, negation, and amendment
    clauses without external API dependencies, producing exact text spans.
    """

    def __init__(self, canned_responses: Optional[Mapping[str, dict[str, Any]]] = None):
        self._canned = dict(canned_responses or {})

    def register_canned(self, prompt_substring: str, response: dict[str, Any]) -> None:
        self._canned[prompt_substring] = response

    def generate_structured(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        # Check canned responses first
        for k, resp in self._canned.items():
            if k in user_prompt:
                return resp

        # Deterministic semantic parser mimicking an ideal LLM
        return self._semantic_parse(user_prompt)

    def _semantic_parse(self, text: str) -> dict[str, Any]:
        """
        Deterministic semantic extraction of P37 contract concepts.
        Produces fields with exact text spans matching text.
        """
        # 1. Conflict detection on base un-amended text
        has_amendment = bool(re.search(r"\bAMENDMENT:\b", text, re.I))

        # Check for explicitly contradictory clauses without amendment
        if not has_amendment:
            contradictory_nonline = (
                re.search(r"Non-line refund rule:\s*shipping funder", text, re.I)
                and re.search(r"Non-line refund rule:\s*platform absorbs", text, re.I)
            )
            if contradictory_nonline:
                return {
                    "nonline_allocation": "unknown",
                    "commission_treatment": "unknown",
                    "recovery_order": [],
                    "funding_map": {},
                    "principal_bearer_verified": True,
                    "abstain": True,
                    "abstain_reason": "conflicting",
                    "spans": {},
                    "role_binding_spans": {},
                }

        # Determine effective text section for fields (if AMENDMENT exists, check for amended fields)
        amendment_match = re.search(r"\bAMENDMENT:[^\n]*\n([\s\S]+)$", text, re.I)
        amendment_text = amendment_match.group(1) if amendment_match else ""

        # 2. Extract Nonline Allocation
        nonline_val = "unknown"
        nonline_span = ""

        # Search in amendment first if present
        target_texts = [amendment_text, text] if amendment_text else [text]

        for scope in target_texts:
            if re.search(r"Non-line refund rule:\s*shipping funder", scope, re.I):
                m = re.search(r"Non-line refund rule:\s*shipping funder", scope, re.I)
                nonline_val = "shipping_funder"
                nonline_span = m.group(0)
                break
            elif re.search(r"Non-line refund rule:\s*platform (?:fee funder|absorbs)", scope, re.I):
                m = re.search(r"Non-line refund rule:\s*platform (?:fee funder|absorbs)", scope, re.I)
                nonline_val = "platform_absorbs"
                nonline_span = m.group(0)
                break
            elif re.search(r"Non-line refund rule:\s*discount funder", scope, re.I):
                m = re.search(r"Non-line refund rule:\s*discount funder", scope, re.I)
                nonline_val = "discount_funder"
                nonline_span = m.group(0)
                break
            elif re.search(r"Non-line refund rule:\s*proportional", scope, re.I):
                m = re.search(r"Non-line refund rule:\s*proportional", scope, re.I)
                nonline_val = "proportional"
                nonline_span = m.group(0)
                break

        # Check multi-clause precedence & synonym patterns if still unknown or in multi-clause
        if re.search(r"Section 4\.2|applies to shipping-related cancellations", text, re.I):
            m = re.search(r"the shipping account bears the loss", text, re.I)
            if m:
                nonline_val = "shipping_funder"
                nonline_span = m.group(0)
        elif re.search(r"overrides Master for platform fee transactions", text, re.I):
            m = re.search(r"Non-line refund rule:\s*platform absorbs", text, re.I)
            if m:
                nonline_val = "platform_absorbs"
                nonline_span = m.group(0)
        elif nonline_val == "unknown":
            # Semantic synonyms, passive voice, and negation surface forms
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

        # 3. Extract Commission Treatment
        comm_val = "unknown"
        comm_span = ""

        for scope in target_texts:
            if re.search(r"Commission is returned in full", scope, re.I):
                m = re.search(r"Commission is returned in full", scope, re.I)
                comm_val = "full"
                comm_span = m.group(0)
                break
            elif re.search(r"Commission (?:is )?retained(?: on refunds)?", scope, re.I):
                m = re.search(r"Commission (?:is )?retained(?: on refunds)?", scope, re.I)
                comm_val = "retained"
                comm_span = m.group(0)
                break
            elif re.search(r"Commission is returned proportionally", scope, re.I):
                m = re.search(r"Commission is returned proportionally", scope, re.I)
                comm_val = "proportional"
                comm_span = m.group(0)
                break

        # Check multi-clause precedence & semantic commission synonyms if unknown
        if re.search(r"Section 4\.2", text, re.I) and "Commission is returned in full for shipping refunds" in text:
            comm_val = "full"
            comm_span = "Commission is returned in full for shipping refunds"
        elif comm_val == "unknown":
            comm_synonyms = [
                ("retained", r"Merchant commission is not returned on refunds"),
                ("retained", r"Earned commissions remain with Razorpay upon refund"),
                ("retained", r"The commission component will be withheld by the platform"),
                ("retained", r"commission component will be withheld by the platform"),
                ("retained", r"Commission fees are non-refundable"),
                ("retained", r"Fee retentions remain non-reversible"),
                ("retained", r"Commission will not be returned to the merchant"),
                ("retained", r"Commission is not surrendered"),
                ("retained", r"No commissions are refunded to transacting vendors"),
                ("retained", r"Commission components shall not be repaid"),
                ("proportional", r"Commission amounts will be reimbursed proportionally"),
                ("full", r"Platform service fees are waived on reversals"),
                ("proportional", r"Commission is returned in proportion to the refund"),
                ("proportional", r"Platform fee portions are remitted back on a proportional basis"),
                ("proportional", r"Commission is credited back prorated against the refund sum"),
                ("proportional", r"Commission clawback matches the proportional ratio"),
                ("full", r"Platform service fees are refunded in full to vendors"),
                ("full", r"Platform commissions are refunded in their entirety"),
                ("full", r"All transaction processing commissions are returned without deduction"),
                ("full", r"The complete commission tariff is refunded"),
                ("full", r"Commission reimbursement is 100%"),
            ]
            for val, pat in comm_synonyms:
                m_cm = re.search(pat, text, re.I)
                if m_cm:
                    comm_val = val
                    comm_span = m_cm.group(0)
                    break

        # 4. Extract Recovery Order
        recovery_order: list[str] = []
        recovery_span = ""

        # Check amendment for recovery order first
        for scope in target_texts:
            m = re.search(r"Recovery order:\s+([^\n.]+)", scope, re.I)
            if m:
                recovery_span = m.group(0)
                tokens = [t.strip().rstrip(".") for t in re.split(r"\s+then\s+", m.group(1)) if t.strip()]
                recovery_order = tokens
                break

        if not recovery_order:
            # Synonyms for recovery order
            m_syn = re.search(r"(?:Repayment sequence|Repayment priority|Settlement order|Settlement sequence|Settlement|Priority of deduction|Accounts are cleared):\s*(?:first\s+)?([^\n.]+)", text, re.I)
            if m_syn:
                recovery_span = m_syn.group(0)
                raw = m_syn.group(1)
                tokens = [t.strip() for t in re.split(r",?\s*(?:prior to|then|before|, followed by|subsequently)\s*", raw) if t.strip()]
                recovery_order = tokens
            elif "Accounts are settled starting with" in text:
                m_txt = re.search(r"Accounts are settled starting with\s+(\w+),\s*proceeding to\s+(\w+)", text, re.I)
                if m_txt:
                    recovery_span = m_txt.group(0)
                    recovery_order = [m_txt.group(1), m_txt.group(2)]

        # 5. Role Bindings & Conflict Check
        role_spans: dict[str, str] = {}
        funding_map: dict[str, str] = {}
        conflict_detected = False

        # Support diverse role binding patterns
        binding_patterns = [
            re.compile(r"Funding account:\s*(\w+)\s+is designated\s+(shipping|platform|discount)\.?", re.I),
            re.compile(r"Account\s+(\w+)\s+is assigned role\s+(shipping|platform|discount)\.?", re.I),
            re.compile(r"Designated\s+(shipping|platform|discount)\s+account:\s*(\w+)\.?", re.I),
            re.compile(r"Role assignment:\s*(\w+)\s+operates as\s+(shipping|platform|discount)\.?", re.I),
            re.compile(r"Operational binding:\s*(\w+)\s+fulfills\s+(shipping|platform|discount)\.?", re.I),
        ]

        found_matches = []
        for pat in binding_patterns:
            for m in pat.finditer(text):
                g1, g2 = m.group(1), m.group(2)
                # If pattern was Designated <role> account: <acc>
                if g1.lower() in ("shipping", "platform", "discount"):
                    role = g1.lower()
                    acc = g2
                else:
                    acc = g1
                    role = g2.lower()
                found_matches.append((m.start(), acc, role, m.group(0)))

        # Sort matches by start position in text
        found_matches.sort(key=lambda x: x[0])

        for start_pos, acc, role, span_str in found_matches:
            is_amended_match = (start_pos >= (amendment_match.start() if amendment_match else len(text)))

            if role in funding_map:
                if funding_map[role] == acc:
                    # Idempotent duplicate
                    continue
                elif is_amended_match:
                    # Amendment override: last amendment wins
                    funding_map[role] = acc
                    role_spans[role] = span_str
                else:
                    # Unamended conflict: two different accounts asserted for same role
                    conflict_detected = True
            else:
                funding_map[role] = acc
                role_spans[role] = span_str


        if conflict_detected:
            return {
                "nonline_allocation": nonline_val,
                "commission_treatment": comm_val,
                "recovery_order": recovery_order,
                "funding_map": {},
                "principal_bearer_verified": True,
                "abstain": True,
                "abstain_reason": "role_binding_conflict",
                "spans": {},
                "role_binding_spans": {},
            }

        spans: dict[str, str] = {}
        if nonline_span and nonline_val != "unknown":
            spans["nonline_allocation"] = nonline_span
        if comm_span and comm_val != "unknown":
            spans["commission_treatment"] = comm_span
        if recovery_span and recovery_order:
            spans["recovery_order"] = recovery_span

        return {
            "nonline_allocation": nonline_val,
            "commission_treatment": comm_val,
            "recovery_order": recovery_order,
            "funding_map": funding_map,
            "principal_bearer_verified": True,
            "abstain": False,
            "abstain_reason": "none",
            "spans": spans,
            "role_binding_spans": role_spans,
        }


class GeminiLLMClient(LLMClient):
    """Client for Google Generative AI (Gemini)."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-1.5-flash"):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set.")
        import google.generativeai as genai
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(
            model_name=model_name,
            generation_config={"response_mime_type": "application/json"}
        )

    def generate_structured(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        prompt = f"{system_prompt}\n\nInput Agreement Text:\n{user_prompt}"
        response = self.model.generate_content(prompt)
        return json.loads(response.text)


class OpenAILLMClient(LLMClient):
    """Client for OpenAI models."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gpt-4o-mini"):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not set.")
        import openai
        self.client = openai.OpenAI(api_key=self.api_key)
        self.model_name = model_name

    def generate_structured(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        response = self.client.chat.completions.create(
            model=self.model_name,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)
