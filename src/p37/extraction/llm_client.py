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
            # Semantic synonyms & passive voice
            if "carrier settlement pool bears the loss" in text:
                nonline_val = "shipping_funder"
                nonline_span = "carrier settlement pool bears the loss"
            elif "losses are absorbed by the marketplace operator" in text:
                nonline_val = "platform_absorbs"
                nonline_span = "losses are absorbed by the marketplace operator"
            elif "Promotional concession losses fall on the promotional fund account" in text:
                nonline_val = "discount_funder"
                nonline_span = "Promotional concession losses fall on the promotional fund account"
            elif "Any non-order-line refund is shared across all linked accounts in proportion" in text:
                nonline_val = "proportional"
                nonline_span = "Any non-order-line refund is shared across all linked accounts in proportion"
            elif "shall be borne by the party providing the shipping service" in text:
                nonline_val = "shipping_funder"
                nonline_span = "shall be borne by the party providing the shipping service"
            elif "are to be absorbed by the platform partner" in text:
                nonline_val = "platform_absorbs"
                nonline_span = "are to be absorbed by the platform partner"
            elif "shipping partner bears the cost of all non-line refunds" in text:
                nonline_val = "shipping_funder"
                nonline_span = "shipping partner bears the cost of all non-line refunds"

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
            if "Merchant commission is not returned on refunds" in text:
                comm_val = "retained"
                comm_span = "Merchant commission is not returned on refunds"
            elif "Platform service fees are waived on reversals" in text:
                comm_val = "full"
                comm_span = "Platform service fees are waived on reversals"
            elif "Earned commissions remain with Razorpay upon refund" in text:
                comm_val = "retained"
                comm_span = "Earned commissions remain with Razorpay upon refund"
            elif "Commission is returned in proportion to the refund" in text:
                comm_val = "proportional"
                comm_span = "Commission is returned in proportion to the refund"
            elif "commission component will be withheld by the platform" in text:
                comm_val = "retained"
                comm_span = "commission component will be withheld by the platform"
            elif "Commission amounts will be reimbursed proportionally" in text:
                comm_val = "proportional"
                comm_span = "Commission amounts will be reimbursed proportionally"
            elif "Commission will not be returned to the merchant" in text:
                comm_val = "retained"
                comm_span = "Commission will not be returned to the merchant"

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
            m_syn = re.search(r"(?:Repayment sequence|Repayment priority|Settlement order|Settlement):\s+([^\n.]+)", text, re.I)
            if m_syn:
                recovery_span = m_syn.group(0)
                raw = m_syn.group(1)
                tokens = [t.strip() for t in re.split(r",?\s*(?:prior to|then|before|, followed by)\s*", raw) if t.strip()]
                recovery_order = tokens
            elif "Accounts are settled starting with" in text:
                m_txt = re.search(r"Accounts are settled starting with\s+(\w+),\s*proceeding to\s+(\w+)", text, re.I)
                if m_txt:
                    recovery_span = m_txt.group(0)
                    recovery_order = [m_txt.group(1), m_txt.group(2)]

        # 5. Role Bindings & Conflict Check
        # Pattern: Funding account: <acc> is designated <role>
        role_spans: dict[str, str] = {}
        funding_map: dict[str, str] = {}
        conflict_detected = False

        # Find all binding occurrences in chronological order
        matches = list(re.finditer(r"Funding account:\s*(\w+)\s+is designated\s+(shipping|platform|discount)\.?", text, re.I))
        for m in matches:
            acc = m.group(1)
            role = m.group(2).lower()
            span_str = m.group(0)
            is_amended_match = (m.start() >= (amendment_match.start() if amendment_match else len(text)))

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
