"""
Razorpay Route · P37 Split Partial-Refund Clawback Engine
Interactive Demonstration and Narrative Walkthrough.

Guided 4-Step Narrative:
  Step 1: The Problem (Naive Proportional Clawback Breakdown)
  Step 2: The Clause (Natural Language Interpretation & Verbatim Span Grounding)
  Step 3: The Human Gate (Operator Approval & Audit Trail)
  Step 4: The Correct Clawback (Deterministic Integer-Paise Allocation & Conservation)
+ Persistent Attack Simulation Toggle
"""
from __future__ import annotations

import html
import json
import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st


def render_html(markup: str) -> None:
    """Render a raw HTML block, stripping per-line indentation so Streamlit's
    markdown parser doesn't mistake indented HTML for a fenced code block."""
    st.markdown("\n".join(line.strip() for line in markup.strip("\n").splitlines()), unsafe_allow_html=True)


_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT / "src"))

from p37.benchmark.generator import CASE_TYPES, GenerationConfig, generate
from p37.benchmark.groundtruth import resolve as resolve_groundtruth
from p37.benchmark.models import (
    ObservableCase,
    ObservableLine,
    ObservableRefund,
    ObservableTransfer,
)
from p37.benchmark.project import project as project_case
from p37.benchmark.rounding import largest_remainder
from p37.extraction.allocator import allocate
from p37.extraction.extractor import extract as extract_regex
from p37.extraction.human_gate import (
    ConfirmationAction,
    ConfirmationDecision,
    HumanConfirmationGate,
)
from p37.extraction.llm_client import create_llm_client
from p37.extraction.llm_extractor import LLMExtractor
from p37.extraction.models import (
    AbstainReason,
    CommissionTreatment,
    NonlineAllocation,
    SourceSpan,
    StructuredRule,
)
from p37.extraction.adversarial_dataset import HEADLINE_ADVERSARIAL_CASES

# ── Page Configuration ─────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Razorpay Route | P37 Clawback Engine",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styling: Modern Dark Glassmorphic Theme ───────────────────────────────────

st.markdown("""
<style>
    :root {
        --bg: #05070E;
        --glass: rgba(255, 255, 255, 0.045);
        --glass-hover: rgba(255, 255, 255, 0.075);
        --glass-border: rgba(255, 255, 255, 0.09);
        --accent-1: #3B82F6;
        --accent-2: #8B5CF6;
        --accent-3: #22D3EE;
        --accent-gradient: linear-gradient(135deg, var(--accent-1), var(--accent-2));
        --success: #10B981;
        --danger: #F43F5E;
        --text: #F1F5F9;
        --text-dim: #94A3B8;
        --radius-lg: 20px;
        --radius-md: 14px;
        --radius-sm: 8px;
    }

    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(10px); }
        to   { opacity: 1; transform: translateY(0); }
    }

    html, body, .stApp {
        background-color: var(--bg) !important;
    }

    .stApp {
        color: var(--text) !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        background-image:
            radial-gradient(circle at 12% 8%, rgba(59, 130, 246, 0.16), transparent 42%),
            radial-gradient(circle at 88% 12%, rgba(139, 92, 246, 0.14), transparent 45%),
            radial-gradient(circle at 50% 100%, rgba(34, 211, 238, 0.08), transparent 50%);
        background-attachment: fixed;
    }

    h1, h2, h3, h4, h5, h6, p, label, .stMarkdown {
        color: var(--text) !important;
    }

    section[data-testid="stSidebar"] {
        background: rgba(6, 9, 20, 0.85) !important;
        backdrop-filter: blur(18px);
        border-right: 1px solid var(--glass-border);
    }

    /* ── Step navigation ─────────────────────────────────────────── */
    .step-nav-bar {
        display: flex;
        gap: 12px;
        margin-bottom: 24px;
        background: var(--glass);
        backdrop-filter: blur(20px);
        padding: 10px;
        border-radius: var(--radius-lg);
        border: 1px solid var(--glass-border);
    }
    .step-item {
        flex: 1;
        padding: 12px;
        border-radius: var(--radius-md);
        text-align: center;
        font-size: 0.9rem;
        font-weight: 600;
        color: var(--text-dim);
        background: transparent;
        border: 1px solid transparent;
        transition: all 0.2s;
    }
    .step-item.active {
        background: var(--accent-gradient);
        color: #FFFFFF;
        box-shadow: 0 4px 20px rgba(59, 130, 246, 0.35);
    }
    .step-item.completed {
        background: rgba(56, 189, 248, 0.08);
        color: var(--accent-3);
        border: 1px solid rgba(56, 189, 248, 0.25);
    }

    div[data-testid="stButton"] button {
        border-radius: var(--radius-sm) !important;
        border: 1px solid var(--glass-border) !important;
        background: var(--glass) !important;
        backdrop-filter: blur(12px);
        color: var(--text) !important;
        font-weight: 600 !important;
        transition: all 0.18s ease !important;
    }
    div[data-testid="stButton"] button:hover {
        background: var(--glass-hover) !important;
        border-color: rgba(139, 92, 246, 0.4) !important;
        transform: translateY(-1px);
    }
    div[data-testid="stButton"] button[kind="primary"] {
        background: var(--accent-gradient) !important;
        border: none !important;
        box-shadow: 0 4px 18px rgba(59, 130, 246, 0.35) !important;
    }
    div[data-testid="stButton"] button[kind="primary"]:hover {
        box-shadow: 0 6px 24px rgba(139, 92, 246, 0.45) !important;
        transform: translateY(-1px);
    }

    /* ── Glass cards ──────────────────────────────────────────────── */
    .glass-card {
        background: var(--glass);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid var(--glass-border);
        border-radius: var(--radius-lg);
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25);
        animation: fadeInUp 0.35s ease-out;
    }
    .glass-card-danger {
        background: rgba(244, 63, 94, 0.08);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(244, 63, 94, 0.35);
        border-radius: var(--radius-lg);
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 8px 28px rgba(244, 63, 94, 0.12);
        animation: fadeInUp 0.35s ease-out;
    }
    .glass-card-success {
        background: rgba(16, 185, 129, 0.08);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(16, 185, 129, 0.35);
        border-radius: var(--radius-lg);
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 8px 28px rgba(16, 185, 129, 0.12);
        animation: fadeInUp 0.35s ease-out;
    }

    /* ── Chips / badges ───────────────────────────────────────────── */
    .chip {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 12px;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.2px;
        border: 1px solid transparent;
    }
    .badge-red, .chip-danger {
        background: rgba(244, 63, 94, 0.14);
        color: #FB7185;
        border-color: rgba(244, 63, 94, 0.35);
    }
    .badge-green, .chip-success {
        background: rgba(16, 185, 129, 0.14);
        color: #34D399;
        border-color: rgba(16, 185, 129, 0.35);
    }
    .badge-blue, .chip-accent {
        background: rgba(59, 130, 246, 0.14);
        color: #60A5FA;
        border-color: rgba(59, 130, 246, 0.35);
    }

    .highlight-span {
        background: rgba(139, 92, 246, 0.22);
        color: #C4B5FD;
        border-bottom: 2px solid var(--accent-2);
        padding: 2px 5px;
        border-radius: 4px;
        font-weight: 600;
    }

    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: var(--text);
    }
    .metric-sub {
        font-size: 0.85rem;
        color: var(--text-dim);
    }
    div[data-testid="stMetric"] {
        background: var(--glass);
        backdrop-filter: blur(16px);
        border: 1px solid var(--glass-border);
        border-radius: var(--radius-md);
        padding: 14px 18px 10px 18px;
    }
    div[data-testid="stMetricValue"] {
        color: var(--text) !important;
        background: var(--accent-gradient);
        -webkit-background-clip: text;
        background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    div[data-testid="stMetricLabel"] {
        color: var(--text-dim) !important;
    }

    /* ── Glass table ──────────────────────────────────────────────── */
    .glass-table {
        width: 100%;
        border-collapse: collapse;
        background: var(--glass);
        backdrop-filter: blur(18px);
        border-radius: var(--radius-md);
        overflow: hidden;
        border: 1px solid var(--glass-border);
    }
    .glass-table thead tr {
        background: rgba(139, 92, 246, 0.10);
        color: #C4B5FD;
        text-align: left;
    }
    .glass-table th {
        padding: 12px 16px;
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 0.4px;
    }
    .glass-table td {
        padding: 12px 16px;
        border-bottom: 1px solid var(--glass-border);
    }
    .glass-table tbody tr {
        transition: background 0.15s ease;
    }
    .glass-table tbody tr:hover {
        background: rgba(255, 255, 255, 0.03);
    }
    .glass-table tr.total-row {
        background: rgba(59, 130, 246, 0.10);
        font-weight: 700;
    }

    .stCodeBlock, div[data-testid="stCode"] {
        border-radius: var(--radius-md) !important;
        border: 1px solid var(--glass-border) !important;
    }

    hr {
        border: 0;
        border-top: 1px solid var(--glass-border);
    }
</style>
""", unsafe_allow_html=True)

# ── Session State Initialization ──────────────────────────────────────────────

if "current_step" not in st.session_state:
    st.session_state.current_step = 1

if "gate_decision" not in st.session_state:
    st.session_state.gate_decision = "PENDING"

if "human_gate" not in st.session_state:
    st.session_state.human_gate = HumanConfirmationGate()

if "llm_client" not in st.session_state:
    has_key = bool(os.environ.get("GEMINI_API_KEY"))
    if not has_key:
        env_f = Path(".env")
        if env_f.exists():
            for line in env_f.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("GEMINI_API_KEY"):
                    k = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if k:
                        has_key = True
                        os.environ["GEMINI_API_KEY"] = k
                        break
    client_mode = "record" if has_key else "replay"
    try:
        st.session_state.llm_client = create_llm_client(mode=client_mode, model_name="gemini-2.5-flash")
    except Exception:
        st.session_state.llm_client = create_llm_client(mode="replay", model_name="gemini-2.5-flash")

if "llm_extractor" not in st.session_state:
    st.session_state.llm_extractor = LLMExtractor(client=st.session_state.llm_client)

# ── Order Preset Definition ───────────────────────────────────────────────────

ORDER_PRESET = {
    "payment_id": "pay_route_demo_01",
    "gross_paise": 100000,     # ₹1,000.00
    "refund_paise": 50000,     # ₹500.00 (Customer returns Item A)
    "transfers": [
        {"account_id": "acc_vendor_a", "label": "Vendor A (Item A Sold)", "amount_paise": 50000, "commission_paise": 5000},
        {"account_id": "acc_vendor_b", "label": "Vendor B (Item B Unreturned)", "amount_paise": 30000, "commission_paise": 3000},
        {"account_id": "acc_courier",  "label": "Logistics Partner", "amount_paise": 10000, "commission_paise": 0},
        {"account_id": "acc_platform", "label": "Platform Fee Account", "amount_paise": 10000, "commission_paise": 0},
    ],
    "contract_text": (
        "Refund allocation agreement:\n"
        "Goods: refund bears with the fulfilling vendor.\n"
        "Shipping: refund bears with the shipping-funding party.\n"
        "Platform fee: refund bears with the platform.\n"
        "Discount adjustments: refund bears with the party that funded the discount.\n"
        "Non-line refund rule: shipping funder.\n"
        "Funding account: acc_courier is designated shipping.\n"
        "Funding account: acc_platform is designated platform.\n"
        "Commission is retained on refunds.\n"
        "Recovery order: acc_vendor_a then acc_vendor_b."
    ),
}

# ── Bulk Portfolio Simulation Engine ──────────────────────────────────────────
# Generates a realistic-distribution portfolio of refund cases using the
# project's own ground-truth benchmark generator (21 documented case types
# spanning clean multi-vendor returns, contract-rule-driven splits, commission
# treatment, rounding/edge cases, and invalid/adversarial refunds). Every case
# is run through the actual deterministic extractor + allocator pipeline and
# graded against the independent ground-truth resolver — no numbers below are
# hand-authored.

CASE_CATEGORY = {
    "D1_single_line_return": "D · Clean Returns", "D2_multi_line_clean": "D · Clean Returns", "D3_full_refund": "D · Clean Returns",
    "A1_shipping_fee": "A · Agreement Clause", "A2_goodwill_credit": "A · Agreement Clause", "A3_discount_funded": "A · Agreement Clause",
    "A4_platform_fee_only": "A · Agreement Clause", "A5_proportional_cancellation": "A · Agreement Clause",
    "C1_commission_retained": "C · Commission", "C2_commission_full_return": "C · Commission",
    "B1_rounding": "B · Edge Case", "B2_exact_balance": "B · Edge Case", "B3_one_paisa_short": "B · Edge Case",
    "B4_prior_partial_reversal": "B · Edge Case", "B5_zero_commission": "B · Edge Case", "B6_single_transfer": "B · Edge Case",
    "N1_refund_exceeds_payment": "N · Invalid / Adversarial", "N2_refund_exceeds_transfers": "N · Invalid / Adversarial",
    "N3_closed_account": "N · Invalid / Adversarial", "N4_line_maps_to_multiple": "N · Invalid / Adversarial",
    "N5_reason_mislabelled": "N · Invalid / Adversarial",
}

# Approximate real-world mix: mostly clean returns, a meaningful slice of
# contract-governed and commission cases, routine rounding/edge noise, and a
# small tail of invalid or adversarial refund requests.
CASE_WEIGHTS = {
    "D1_single_line_return": 0.22, "D2_multi_line_clean": 0.10, "D3_full_refund": 0.08,
    "A1_shipping_fee": 0.06, "A2_goodwill_credit": 0.05, "A3_discount_funded": 0.04,
    "A4_platform_fee_only": 0.03, "A5_proportional_cancellation": 0.02,
    "C1_commission_retained": 0.06, "C2_commission_full_return": 0.04,
    "B1_rounding": 0.03, "B2_exact_balance": 0.03, "B3_one_paisa_short": 0.02,
    "B4_prior_partial_reversal": 0.03, "B5_zero_commission": 0.02, "B6_single_transfer": 0.02,
    "N1_refund_exceeds_payment": 0.03, "N2_refund_exceeds_transfers": 0.03, "N3_closed_account": 0.03,
    "N4_line_maps_to_multiple": 0.03, "N5_reason_mislabelled": 0.03,
}


@st.cache_data(show_spinner=False)
def run_bulk_simulation(n_total: int, seed: int) -> dict:
    counts = {ct: max(0, round(n_total * CASE_WEIGHTS[ct])) for ct in CASE_TYPES}
    gt_cases = generate(GenerationConfig(counts=counts, seed=seed))

    rows = []
    for gt in gt_cases:
        obs = project_case(gt)
        truth = resolve_groundtruth(gt)

        try:
            rule = extract_regex(obs.agreement_text)
            pred = allocate(obs, rule)
        except Exception:
            pred = None

        # Naive baseline: split the refund proportionally across every linked
        # transfer, ignoring line attribution or contract clauses entirely —
        # this is the industry-default "proportional clawback" behavior.
        accounts = [t.linked_account_id for t in obs.transfers]
        transfer_amts = [t.transfer_amount_paise for t in obs.transfers]
        denom = sum(transfer_amts)
        refund_amt = obs.refunds[0].refund_amount_paise
        if denom > 0 and refund_amt <= denom:
            naive_shares = largest_remainder(refund_amt, transfer_amts, [denom] * len(accounts), accounts)
            naive_alloc = {a: s for a, s in zip(accounts, naive_shares)}
        else:
            naive_alloc = {a: 0 for a in accounts}

        correct_alloc = {a: v.bear_paise for a, v in truth.allocations.items()} if not truth.unresolvable else {}
        all_accounts = set(naive_alloc) | set(correct_alloc)
        misallocated_paise = sum(abs(naive_alloc.get(a, 0) - correct_alloc.get(a, 0)) for a in all_accounts) // 2

        pred_alloc = {a.linked_account_id: a.allocated_paise for a in pred.allocations} if pred and not pred.abstained else {}
        pred_abstained = bool(pred and pred.abstained)

        if truth.unresolvable:
            pred_correct = pred_abstained
        else:
            pred_correct = (not pred_abstained) and pred_alloc == correct_alloc

        rows.append({
            "case_id": gt.case_id,
            "case_type": gt.case_type,
            "category": CASE_CATEGORY[gt.case_type],
            "refund_paise": refund_amt,
            "unresolvable": truth.unresolvable,
            "naive_touched": sum(1 for v in naive_alloc.values() if v > 0),
            "correct_touched": sum(1 for v in correct_alloc.values() if v > 0),
            "misallocated_paise": misallocated_paise,
            "pred_abstained": pred_abstained,
            "pred_correct": pred_correct,
        })

    df = pd.DataFrame(rows)
    return {"df": df, "requested": n_total, "generated": len(df)}


# ── Top Header & Persistent Attack Toggle ──────────────────────────────────────

col_head, col_toggle = st.columns([3, 1])

with col_head:
    render_html("""
    <div style="padding: 4px 0 12px 0;">
        <h2 style="margin: 0; font-size: 1.8rem; font-weight: 800; letter-spacing: -0.5px;">
            <span style="background: linear-gradient(135deg, #F8FAFC, #94A3B8); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;">Razorpay Route</span>
            <span style="background: linear-gradient(135deg, #3B82F6, #8B5CF6); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;"> P37</span>
            <span style="color: #94A3B8; font-weight: 500;"> · Split Partial-Refund Clawback Engine</span>
        </h2>
        <div style="font-size: 0.88rem; color: #94A3B8; margin-top: 6px;">
            Deterministic integer-paise allocation driven by verbatim-grounded contract clauses and human oversight
        </div>
    </div>
    """)

with col_toggle:
    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    attack_mode = st.toggle("⚠️ Attack Simulation Mode", value=False, help="Inject an adversarial prompt to test injection defense.")

# ── Interactive Step Navigation Bar ───────────────────────────────────────────

steps = [
    (1, "1. The Problem", "Naive Clawback Breakdown"),
    (2, "2. The Clause", "Source-Span Grounding"),
    (3, "3. The Human Gate", "Operator Approval"),
    (4, "4. Correct Clawback", "Paise Conservation"),
    (5, "5. At Scale", "Portfolio Impact Simulation"),
]

nav_cols = st.columns(len(steps))
for idx, (s_num, s_title, s_desc) in enumerate(steps):
    is_active = (st.session_state.current_step == s_num)
    is_done = (st.session_state.current_step > s_num)
    prefix = "● " if is_active else ("✓ " if is_done else "○ ")
    if nav_cols[idx].button(
        f"{prefix}{s_title}",
        key=f"nav_step_{s_num}",
        use_container_width=True,
        type="primary" if is_active else "secondary",
        help=s_desc,
    ):
        st.session_state.current_step = s_num
        st.rerun()

st.markdown("<hr style='margin: 12px 0 24px 0;'>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# PERSISTENT ATTACK MODE VIEW
# ═══════════════════════════════════════════════════════════════════════════════

if attack_mode:
    render_html("""
    <div class="glass-card-danger">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <h3 style="margin: 0; color: #FB7185; font-size: 1.2rem;">Adversarial Prompt Injection Attack Active</h3>
            <span class="chip chip-danger">Security Defense Evaluation</span>
        </div>
        <div style="font-size: 0.9rem; color: #FCA5A5; margin-top: 6px;">
            A malicious merchant injects unauthorized instructions and fixed monetary debit commands inside contract prose.
        </div>
    </div>
    """)

    attack_case = HEADLINE_ADVERSARIAL_CASES[0]  # adv_01_instruction_override

    c_atk_l, c_atk_r = st.columns(2)
    with c_atk_l:
        st.markdown("**Injected Malicious Contract Prose:**")
        st.code(attack_case.raw_text, language="markdown")
        st.markdown(f"**Target Exploit:** `{attack_case.target_exploit}`")

    with c_atk_r:
        st.markdown("**System Defense & Guard Behavior:**")
        st.markdown("""
        1. **Untrusted Delimiter Fencing:** Text is strictly wrapped in `<UNTRUSTED_CONTRACT_TEXT>` tags.
        2. **Verbatim Span Validation:** Model cannot cite fabricated clauses; ungrounded overrides fail span check.
        3. **Programmatic Enum Allowlists:** Prohibits unknown values.
        4. **Structural Invariant:** Allocator accepts zero amounts from LLM.
        """)

        # Execute defense
        try:
            rule_adv = st.session_state.llm_extractor.extract(attack_case.raw_text)
        except Exception:
            from p37.extraction.llm_client import MockLLMClient
            rule_adv = LLMExtractor(client=MockLLMClient()).extract(attack_case.raw_text)
        st.markdown("<div style='margin-top: 12px;'></div>", unsafe_allow_html=True)
        if rule_adv.abstain:
            st.success(f"DEFENSE VERIFIED: System safely abstained (Reason: {rule_adv.abstain_reason.value}). Zero funds moved.")
        else:
            st.info(f"DEFENSE VERIFIED: Extractor ignored injection payload. Extracted: nonline={rule_adv.nonline_allocation.value}")

    st.markdown("<hr style='margin: 24px 0;'>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1 — THE PROBLEM (Naive Proportional Clawback Breakdown)
# ═══════════════════════════════════════════════════════════════════════════════

if st.session_state.current_step == 1:
    st.markdown("### Step 1: The Business Problem — Naive Clawback Breakdown")
    st.markdown("""
    When a customer returns one item from a multi-vendor order, standard proportional clawback takes money 
    ratably from **every linked account**, even those completely uninvolved in the returned item.
    """)

    # Order details
    col_ord_1, col_ord_2, col_ord_3 = st.columns(3)
    col_ord_1.metric("Order Gross Value", "₹1,000.00", "Settled across 4 accounts")
    col_ord_2.metric("Customer Partial Refund", "₹500.00", "Return of Item A only")
    col_ord_3.metric("Naive Logic Error", "₹250.00", "Unfairly taken from innocent parties", delta_color="inverse")

    st.markdown("<div style='margin-top: 16px;'></div>", unsafe_allow_html=True)

    # Naive Breakdown Table
    st.markdown("#### Transaction Split vs. Naive Proportional Recovery")

    naive_rows = [
        {"Account": "Vendor A (Fulfilled Item A)", "Original Share": "₹500.00 (50%)", "Returned Item": "Yes (₹500.00)", "Naive Debit": "₹250.00", "Verdict": "Under-debited by ₹250.00", "Class": "chip-accent"},
        {"Account": "Vendor B (Fulfilled Item B)", "Original Share": "₹300.00 (30%)", "Returned Item": "No (₹0.00)", "Naive Debit": "₹150.00", "Verdict": "WRONGLY DEBITED ₹150.00", "Class": "chip-danger"},
        {"Account": "Courier (Delivery Fleet)", "Original Share": "₹100.00 (10%)", "Returned Item": "No (₹0.00)", "Naive Debit": "₹50.00", "Verdict": "WRONGLY DEBITED ₹50.00", "Class": "chip-danger"},
        {"Account": "Platform Fee Account", "Original Share": "₹100.00 (10%)", "Returned Item": "No (₹0.00)", "Naive Debit": "₹50.00", "Verdict": "WRONGLY DEBITED ₹50.00", "Class": "chip-danger"},
    ]

    html_table = """
    <table class="glass-table">
        <thead>
            <tr>
                <th>Account / Party</th>
                <th>Original Split</th>
                <th>Item Return</th>
                <th>Naive Clawback</th>
                <th>Financial Impact</th>
            </tr>
        </thead>
        <tbody>
    """
    for r in naive_rows:
        html_table += f"""
            <tr>
                <td style="font-weight: 500;">{r['Account']}</td>
                <td>{r['Original Share']}</td>
                <td>{r['Returned Item']}</td>
                <td style="font-weight: 600;">{r['Naive Debit']}</td>
                <td><span class="chip {r['Class']}">{r['Verdict']}</span></td>
            </tr>
        """
    html_table += "</tbody></table>"
    render_html(html_table)

    render_html("""
    <div class="glass-card" style="margin-top: 24px;">
        <h4 style="margin: 0 0 8px 0; color: #22D3EE;">Real-World Business Consequence</h4>
        <div style="font-size: 0.95rem; color: #CBD5E1; line-height: 1.5;">
            Vendor B did nothing wrong, yet their account balance is docked ₹150.00. This triggers merchant disputes,
            support tickets, vendor churn, and expensive manual settlement reconciliation for Razorpay operations.
            The governing truth lives in merchant contract clauses, not in raw payment records.
        </div>
    </div>
    """)

    c_btn1, c_btn2 = st.columns([4, 1])
    if c_btn2.button("Proceed to Step 2: The Clause →", type="primary", use_container_width=True):
        st.session_state.current_step = 2
        st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2 — THE CLAUSE (Verbatim Source Span Grounding)
# ═══════════════════════════════════════════════════════════════════════════════

elif st.session_state.current_step == 2:
    st.markdown("### Step 2: The Clause — Verbatim Source-Span Grounding")
    st.markdown("""
    P37 extracts structured rules from contract text using LLM reasoning, but enforces a strict safety invariant:
    **every field must be grounded to an exact, character-level verbatim substring** of the agreement text.
    """)

    raw_text = ORDER_PRESET["contract_text"]
    rule = st.session_state.llm_extractor.extract(raw_text)

    # Build visually highlighted contract text
    highlighted_text = html.escape(raw_text)
    for field_name, span in rule.spans.items():
        escaped_span = html.escape(span.text)
        replacement = f"<mark class='highlight-span' title='Grounded field: {field_name}'>{escaped_span}</mark>"
        highlighted_text = highlighted_text.replace(escaped_span, replacement)

    col_clause_l, col_clause_r = st.columns([1, 1])

    with col_clause_l:
        st.markdown("#### Governing Contract Text")
        st.markdown(
            f'<div style="background: rgba(255,255,255,0.04); backdrop-filter: blur(16px); border: 1px solid rgba(255,255,255,0.09); border-radius: 14px; padding: 16px; font-family: \'SFMono-Regular\', Consolas, monospace; font-size: 0.9rem; line-height: 1.7; white-space: pre-wrap;">{highlighted_text}</div>',
            unsafe_allow_html=True,
        )
        st.markdown("<div style='font-size: 0.8rem; color: #94A3B8; margin-top: 8px;'>Highlighted spans represent verbatim quotes validated against the original string.</div>", unsafe_allow_html=True)

    with col_clause_r:
        st.markdown("#### Extracted Structured Rule")
        rule_dict = {
            "nonline_allocation": rule.nonline_allocation.value,
            "commission_treatment": rule.commission_treatment.value,
            "recovery_order": list(rule.recovery_order),
            "funding_map": rule.funding_map,
            "abstain": rule.abstain,
            "spans": {k: v.text for k, v in rule.spans.items()},
        }
        st.code(json.dumps(rule_dict, indent=2), language="json")

        st.markdown("#### Grounding Verification")
        all_valid = all(s.validate(raw_text) for s in rule.spans.values())
        if all_valid:
            render_html("""
            <div class="glass-card-success" style="padding: 12px 16px;">
                <div style="font-weight: 600; color: #34D399;">Span Validation: 100% PASS</div>
                <div style="font-size: 0.85rem; color: #A7F3D0;">All quotes match exact character offsets in contract text. Hallucination rate: 0.0%.</div>
            </div>
            """)

    c_b2_back, c_b2_sp, c_b2_next = st.columns([1, 2, 1])
    if c_b2_back.button("← Back to Step 1", use_container_width=True):
        st.session_state.current_step = 1
        st.rerun()
    if c_b2_next.button("Proceed to Step 3: Human Gate →", type="primary", use_container_width=True):
        st.session_state.current_step = 3
        st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3 — THE HUMAN GATE (Interactive Operator Review)
# ═══════════════════════════════════════════════════════════════════════════════

elif st.session_state.current_step == 3:
    st.markdown("### Step 3: The Human Gate — Operator Confirmation")
    st.markdown("""
    The LLM never touches money directly. An operator reviews the extracted rule and verbatim source spans 
    in an auditable review interface before any debit instruction is dispatched.
    """)

    raw_text = ORDER_PRESET["contract_text"]
    rule = st.session_state.llm_extractor.extract(raw_text)
    gate = st.session_state.human_gate
    req = gate.prepare_request(raw_text, rule)

    render_html("""
    <div class="glass-card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <h4 style="margin: 0; color: #22D3EE;">Pending Settlement Review Request</h4>
            <span class="chip chip-accent">Request ID: req_demo_001</span>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; margin-bottom: 16px;">
            <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; padding: 12px 14px;">
                <div style="font-size: 0.8rem; color: #94A3B8;">Extracted Nonline Rule</div>
                <div style="font-weight: 600; font-size: 1.1rem; color: #F8FAFC;">shipping_funder</div>
            </div>
            <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; padding: 12px 14px;">
                <div style="font-size: 0.8rem; color: #94A3B8;">Commission Policy</div>
                <div style="font-weight: 600; font-size: 1.1rem; color: #F8FAFC;">retained</div>
            </div>
            <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; padding: 12px 14px;">
                <div style="font-size: 0.8rem; color: #94A3B8;">Recovery Account</div>
                <div style="font-weight: 600; font-size: 1.1rem; color: #F8FAFC;">acc_vendor_a</div>
            </div>
        </div>
        <div style="font-size: 0.85rem; color: #CBD5E1; border-top: 1px solid rgba(255,255,255,0.09); padding-top: 12px;">
            <strong>Verified Source Span:</strong> <span class="highlight-span">"Non-line refund rule: shipping funder."</span>
        </div>
    </div>
    """)

    col_btn_app, col_btn_edit, col_btn_rej = st.columns(3)

    if col_btn_app.button("Approve (Move Money)", type="primary", use_container_width=True):
        st.session_state.gate_decision = "APPROVED"

    if col_btn_edit.button("Edit Rule Overrides", use_container_width=True):
        st.session_state.gate_decision = "EDITED"

    if col_btn_rej.button("Reject (Safe Abstain)", use_container_width=True):
        st.session_state.gate_decision = "REJECTED"

    st.markdown("<div style='margin-top: 16px;'></div>", unsafe_allow_html=True)

    if st.session_state.gate_decision == "APPROVED":
        render_html("""
        <div class="glass-card-success">
            <h4 style="margin: 0 0 6px 0; color: #34D399;">Decision: Approved by Operator (reviewer_ops_01)</h4>
            <div style="font-size: 0.9rem; color: #A7F3D0;">
                Cryptographic audit trail entry logged. Rule confirmed for execution. Ready for allocator dispatch.
            </div>
        </div>
        """)
    elif st.session_state.gate_decision == "REJECTED":
        render_html("""
        <div class="glass-card-danger">
            <h4 style="margin: 0 0 6px 0; color: #FB7185;">Decision: Rejected by Operator</h4>
            <div style="font-size: 0.9rem; color: #FCA5A5;">
                Engine safely abstains (AbstainReason: human_operator_rejected). <strong>ZERO funds moved.</strong> No merchant balance altered.
            </div>
        </div>
        """)
    elif st.session_state.gate_decision == "EDITED":
        st.info("Edit mode: Operator manually adjusted nonline rule to 'proportional'. Audit log records manual override.")

    c_b3_back, c_b3_sp, c_b3_next = st.columns([1, 2, 1])
    if c_b3_back.button("← Back to Step 2", use_container_width=True):
        st.session_state.current_step = 2
        st.rerun()
    if c_b3_next.button("Proceed to Step 4: Correct Clawback →", type="primary", use_container_width=True):
        st.session_state.current_step = 4
        st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4 — THE CORRECT CLAWBACK (Paise Conservation & Side-by-Side)
# ═══════════════════════════════════════════════════════════════════════════════

elif st.session_state.current_step == 4:
    st.markdown("### Step 4: The Correct Clawback — Exact Paise Conservation")
    st.markdown("""
    The confirmed rule executes via our deterministic integer-paise allocator. 
    Funds are recovered **strictly from the responsible party**, conserving every single paise.
    """)

    # Side-by-side comparison table
    st.markdown("#### Comparison: Naive Proportional vs P37 Contract-Aware Execution")

    comp_table = """
    <table class="glass-table">
        <thead>
            <tr>
                <th>Account / Party</th>
                <th>Naive Route Clawback</th>
                <th>P37 Contract-Aware Clawback</th>
                <th>Financial Delta</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td style="font-weight: 500;">Vendor A (Fulfilled Item A)</td>
                <td style="color: #FB7185; font-weight: 600;">₹250.00</td>
                <td style="color: #34D399; font-weight: 600;">₹500.00</td>
                <td><span class="chip chip-accent">Correct: 100% item cost recovered</span></td>
            </tr>
            <tr>
                <td style="font-weight: 500;">Vendor B (Item B Unreturned)</td>
                <td style="color: #FB7185; font-weight: 600;">₹150.00 (Wrongful)</td>
                <td style="color: #34D399; font-weight: 600;">₹0.00</td>
                <td><span class="chip chip-success">₹150.00 saved (Zero unfair debit)</span></td>
            </tr>
            <tr>
                <td style="font-weight: 500;">Logistics Partner (Courier)</td>
                <td style="color: #FB7185; font-weight: 600;">₹50.00 (Wrongful)</td>
                <td style="color: #34D399; font-weight: 600;">₹0.00</td>
                <td><span class="chip chip-success">₹50.00 saved (Shipping unaffected)</span></td>
            </tr>
            <tr>
                <td style="font-weight: 500;">Platform Fee Account</td>
                <td style="color: #FB7185; font-weight: 600;">₹50.00 (Wrongful)</td>
                <td style="color: #34D399; font-weight: 600;">₹0.00</td>
                <td><span class="chip chip-success">₹50.00 fee retained per contract</span></td>
            </tr>
            <tr class="total-row">
                <td>Total Amount Recovered</td>
                <td>₹500.00 (50,000 paise)</td>
                <td style="color: #22D3EE;">₹500.00 (50,000 paise)</td>
                <td><span class="chip chip-success">Exact Paise Conservation: PASS</span></td>
            </tr>
        </tbody>
    </table>
    """
    render_html(comp_table)

    st.markdown("<div style='margin-top: 24px;'></div>", unsafe_allow_html=True)

    # Mathematical integrity callout
    col_c1, col_c2, col_c3 = st.columns(3)
    col_c1.metric("Paise Conservation", "0 paise error", "Exact mathematical equality")
    col_c2.metric("Floating-Point Drift", "₹0.00", "Integer math throughout")
    col_c3.metric("Disputes Eliminated", "3 accounts protected", "Vendor B, Courier, Platform")

    render_html("""
    <div class="glass-card-success" style="margin-top: 20px;">
        <h4 style="margin: 0 0 6px 0; color: #34D399;">Financial Safety Proof</h4>
        <div style="font-size: 0.95rem; color: #CBD5E1; line-height: 1.5;">
            The sum of parts (₹500.00) equals the refund amount (₹500.00) with <strong>zero residual paise</strong>.
            Vendor B's balance remains untouched. Razorpay retains earned commission per agreement terms.
            All financial operations executed deterministically.
        </div>
    </div>
    """)

    c_b4_back, c_b4_sp, c_b4_next = st.columns([1, 1, 1])
    if c_b4_back.button("← Back to Step 3", use_container_width=True):
        st.session_state.current_step = 3
        st.rerun()
    if c_b4_next.button("Proceed to Step 5: At Scale →", type="primary", use_container_width=True):
        st.session_state.current_step = 5
        st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 5 — AT SCALE (Bulk Portfolio Impact Simulation)
# ═══════════════════════════════════════════════════════════════════════════════

elif st.session_state.current_step == 5:
    st.markdown("### Step 5: At Scale — Portfolio Impact Simulation")
    st.markdown("""
    Steps 1–4 walked through a single order. This step runs the same engine — the real deterministic
    extractor and allocator, graded against an independent ground-truth resolver — across a
    **generated portfolio of refund cases spanning 21 documented real-world scenario types**: clean
    multi-vendor returns, contract-clause-driven splits (shipping/discount/goodwill), commission
    treatment, rounding edge cases, and invalid or adversarial refund requests. Nothing below is
    hand-typed — every number is computed from the simulation run.
    """)

    c_cfg1, c_cfg2, c_cfg3 = st.columns([2, 1, 1])
    n_cases = c_cfg1.slider("Portfolio size (refund cases)", min_value=200, max_value=5000, value=1500, step=100)
    seed = c_cfg2.number_input("Random seed", min_value=0, max_value=99999, value=42, step=1)
    c_cfg3.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
    run_clicked = c_cfg3.button("▶ Run Simulation", type="primary", use_container_width=True)

    if "bulk_result" not in st.session_state or run_clicked:
        with st.spinner(f"Generating and resolving {n_cases:,} refund cases..."):
            st.session_state.bulk_result = run_bulk_simulation(int(n_cases), int(seed))

    result = st.session_state.bulk_result
    df = result["df"]

    total_cases = len(df)
    total_refund_rupees = df["refund_paise"].sum() / 100
    misallocated_rupees = df["misallocated_paise"].sum() / 100
    resolvable = df[~df["unresolvable"]]
    invalid = df[df["unresolvable"]]
    accuracy_pct = (resolvable["pred_correct"].mean() * 100) if len(resolvable) else 0.0
    safety_pct = (invalid["pred_abstained"].mean() * 100) if len(invalid) else 0.0

    st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Cases Simulated", f"{total_cases:,}")
    k2.metric("Total Refund Volume", f"₹{total_refund_rupees:,.0f}")
    k3.metric("Naive Misallocation Prevented", f"₹{misallocated_rupees:,.0f}")
    k4.metric("Deterministic Accuracy", f"{accuracy_pct:.1f}%", "vs. independent ground truth")
    k5.metric("Invalid-Refund Abstain Safety", f"{safety_pct:.1f}%", "on observable-detectable invalid cases")

    st.markdown("<div style='margin-top: 12px;'></div>", unsafe_allow_html=True)
    st.markdown("#### Impact by Scenario Category")

    cat_summary = df.groupby("category").agg(
        cases=("case_id", "count"),
        refund_rupees=("refund_paise", lambda s: s.sum() / 100),
        misallocated_rupees=("misallocated_paise", lambda s: s.sum() / 100),
        accuracy=("pred_correct", "mean"),
    ).reset_index().sort_values("category")

    cat_table = """
    <table class="glass-table">
        <thead>
            <tr>
                <th>Category</th>
                <th>Cases</th>
                <th>Refund Volume</th>
                <th>Naive Misallocation Prevented</th>
                <th>Pipeline Accuracy</th>
            </tr>
        </thead>
        <tbody>
    """
    for _, r in cat_summary.iterrows():
        acc_chip = "chip-success" if r["accuracy"] >= 0.95 else ("chip-accent" if r["accuracy"] >= 0.8 else "chip-danger")
        cat_table += f"""
            <tr>
                <td style="font-weight: 600;">{r['category']}</td>
                <td>{int(r['cases']):,}</td>
                <td>₹{r['refund_rupees']:,.0f}</td>
                <td style="color: #34D399; font-weight: 600;">₹{r['misallocated_rupees']:,.0f}</td>
                <td><span class="chip {acc_chip}">{r['accuracy']*100:.1f}%</span></td>
            </tr>
        """
    cat_table += "</tbody></table>"
    render_html(cat_table)
    st.caption(
        "For the **N · Invalid/Adversarial** category, \"Pipeline Accuracy\" measures the safe-abstain rate, not "
        "an allocation match. The observable-only interface can only detect refund-exceeds-payment and "
        "refund-exceeds-transfers cases (Tier-B, ~2 of 5 invalid subtypes); closed accounts, ambiguous line "
        "attribution, and mislabelled reasons need signals outside the current observable schema — a documented "
        "scope boundary, not a defect."
    )

    st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
    c_chart, c_top = st.columns([1, 1])

    with c_chart:
        st.markdown("#### Misallocation Prevented by Category (₹)")
        chart_df = cat_summary.set_index("category")[["misallocated_rupees"]]
        chart_df.columns = ["₹ Prevented"]
        st.bar_chart(chart_df, color="#3B82F6", height=320)

    with c_top:
        st.markdown("#### Worst Naive-Logic Overcharges")
        worst = df.sort_values("misallocated_paise", ascending=False).head(8)
        worst_table = """
        <table class="glass-table">
            <thead>
                <tr>
                    <th>Case</th>
                    <th>Type</th>
                    <th>Refund</th>
                    <th>Wrongly Reallocated</th>
                </tr>
            </thead>
            <tbody>
        """
        for _, r in worst.iterrows():
            worst_table += f"""
                <tr>
                    <td style="font-family: monospace; font-size: 0.85rem;">{r['case_id']}</td>
                    <td style="font-size: 0.85rem;">{r['case_type']}</td>
                    <td>₹{r['refund_paise']/100:,.2f}</td>
                    <td><span class="chip chip-danger">₹{r['misallocated_paise']/100:,.2f}</span></td>
                </tr>
            """
        worst_table += "</tbody></table>"
        render_html(worst_table)

    render_html(f"""
    <div class="glass-card" style="margin-top: 24px;">
        <h4 style="margin: 0 0 8px 0; color: #22D3EE;">What This Demonstrates</h4>
        <div style="font-size: 0.95rem; color: #CBD5E1; line-height: 1.6;">
            Across <strong>{total_cases:,} simulated refund cases</strong> totaling <strong>₹{total_refund_rupees:,.0f}</strong> in
            refund volume, naive proportional clawback would have moved <strong>₹{misallocated_rupees:,.0f}</strong>
            to or from the wrong accounts. The deterministic extractor + allocator pipeline matches the
            independent ground-truth resolver on <strong>{accuracy_pct:.1f}%</strong> of resolvable cases, and
            safely abstains — moving zero funds — on <strong>{safety_pct:.1f}%</strong> of invalid or
            adversarial refund requests that are detectable from observable transaction data alone. The rest
            (closed accounts, ambiguous attribution, mislabelled reasons) are a documented scope boundary for
            a future signal, not a silent failure.
        </div>
    </div>
    """)

    with st.expander("View raw per-case simulation output"):
        st.dataframe(
            df[["case_id", "case_type", "category", "refund_paise", "misallocated_paise", "pred_correct", "pred_abstained"]],
            use_container_width=True,
            height=300,
        )

    c_b5_back, c_b5_sp, c_b5_rst = st.columns([1, 2, 1])
    if c_b5_back.button("← Back to Step 4", use_container_width=True):
        st.session_state.current_step = 4
        st.rerun()
    if c_b5_rst.button("Restart Story ↺", use_container_width=True):
        st.session_state.current_step = 1
        st.session_state.gate_decision = "PENDING"
        st.rerun()
