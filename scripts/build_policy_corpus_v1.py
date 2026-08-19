#!/usr/bin/env python3
"""
Claim 2 — Phase 1: Build the Versioned Policy Corpus (v1)

Source: ABCD agent guidelines (Chen et al. 2021, arXiv 2104.00783),
data/guidelines.json + data/kb.json + data/ontology.json from the
official ABCD repo (MIT license).

Construction procedure (documented in datasheet.md):
  1. ABCD's 55 subflows were grouped into "intent families" wherever two
     or more subflows share an (near-)identical agent action-sequence
     template per kb.json (e.g. the three "Return Due to X" subflows all
     run pull-up-account -> validate-purchase -> membership -> enter-details
     -> update-order). This yields 37 families from the 55 subflows,
     within the 25-40 target band. Families that do NOT share an action
     template with any other subflow are kept 1:1.
  2. For each family, the underlying ABCD guideline text (instructions +
     per-action text/subtext) was read and reduced to explicit,
     testable if/then rules. Every concrete number in this corpus
     (day windows, dollar thresholds, membership tiers, item counts)
     is taken VERBATIM from the ABCD guideline text — nothing was
     invented. See datasheet.md, "Known limitations", for the small
     number of places this was not possible.
  3. All 37 documents were generated through this single Python
     template/renderer in one pass, so that document voice, structure,
     and field ordering are byte-for-byte uniform across the whole v1
     corpus. This is intentional: Step 3 will later write v2 documents
     for a subset of these policies, and a text-similarity detector
     must not be able to distinguish v1 from v2 on style alone.
  4. Every rule receives a stable rule_id. Step 3 supersedes policies
     by referencing these rule_ids, not by rewriting whole documents.

This script is deterministic and idempotent given fixed input. Once run
and reviewed, the output directory is hashed and MUST NOT be edited in
place -- see freeze_and_hash.py.
"""
import json
import os
from datetime import datetime, timezone

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "policy_corpus", "v1")
os.makedirs(OUT_DIR, exist_ok=True)

# Notional effective timestamp for the entire v1 corpus. Chosen as the
# ABCD paper's publication month (NAACL-HLT 2021, June) to represent the
# baseline policy state the ABCD dialogues were collected under. This is
# a construction choice, documented in the datasheet, not a claim that
# ASAPP literally dated their internal policy this way.
V1_EFFECTIVE_TS = "2021-06-01T00:00:00Z"
CORPUS_VERSION_LABEL = "v1"
GENERATED_AT = datetime.now(timezone.utc).isoformat()

# -----------------------------------------------------------------------
# FAMILIES: 37 intent families distilled from ABCD's 55 subflows.
# Each entry: policy_id, slug, family (title), flow (ontology flow key),
# source_subflows (ontology subflow keys, provenance), and rules (list of
# testable statements, formalized from the ABCD guideline text).
# -----------------------------------------------------------------------
FAMILIES = [
    dict(
        id="POL-001", slug="refund_initiation", family="Refund Initiation Policy",
        flow="product_defect", source_subflows=["refund_initiate"],
        rules=[
            "Before offering a refund, the agent must validate the purchase using the customer's username, email address, and order ID via Validate Purchase.",
            "Refund method must be one of: gift card, add value, paper check, or credit card. Gift card and paper check refunds require the customer's full mailing address; add value and credit card refunds require the account ID.",
            "If the customer does not know the refund amount, the agent must enter a default refund amount of $50.",
            "The refund amount must be entered without a dollar sign and submitted via Offer Refund before the refund is considered complete.",
        ],
    ),
    dict(
        id="POL-002", slug="refund_update", family="Refund Update Policy",
        flow="product_defect", source_subflows=["refund_update"],
        rules=[
            "Before modifying an existing refund, the agent must validate the purchase using the customer's username, email address, and order ID via Validate Purchase.",
            "When a customer adds an item to an existing refund, the new total refund amount equals the previous refund amount plus the price of the new item.",
            "The updated refund total must be entered without a dollar sign and submitted via Offer Refund.",
        ],
    ),
    dict(
        id="POL-003", slug="refund_status", family="Refund Status Policy",
        flow="product_defect", source_subflows=["refund_status"],
        rules=[
            "Before reporting refund status, the agent must gather username, email address, and order ID, in that order, and validate via Validate Purchase.",
            "Refund status reported to the customer must be one of exactly three values: not started, in progress, or complete.",
            "If a customer is unsatisfied with the reported refund status, the agent must escalate by entering 'manager' into Notify Internal Team.",
            "If a customer is unsatisfied with the reported payment method, the agent must resolve it by entering 'change method' into Update Order, not by escalation.",
        ],
    ),
    dict(
        id="POL-004", slug="product_returns", family="Product Return Policy",
        flow="product_defect", source_subflows=["return_stain", "return_color", "return_size"],
        rules=[
            "Before processing any return, the agent must validate the purchase using username, email address, and order ID via Validate Purchase.",
            "Return eligibility is gated by membership level: Gold members receive unlimited returns; Silver members are eligible within 6 months of purchase, or with a receipt, or if the item is in original packaging; Bronze members are eligible within 90 days, or with a receipt, or in original packaging; Guest members are eligible within 30 days, or with a receipt.",
            "Guest members without a receipt and outside the 30-day window must be denied the return.",
            "Approved returns require the customer's full shipping address (street, city, state, zip) entered as a single line via Enter Details.",
            "The return processing method must be one of: By Mail, In Store, or Drop off Center.",
        ],
    ),
    dict(
        id="POL-005", slug="order_fee_dispute", family="Order Fee Dispute Policy",
        flow="order_issue", source_subflows=["status_mystery_fee"],
        rules=[
            "Before adjudicating a mystery fee, the agent must verify identity using full name, account ID, and order ID via Verify Identity.",
            "The agent must query Ask the Oracle to determine whether the fee was a company error; if the Oracle confirms company error, the fee must be removed regardless of membership level.",
            "If the Oracle does not confirm company error, fee removal eligibility is gated by membership: Gold and Silver members always have the extra fee removed; Guest and Bronze members do not, and the fee stands.",
        ],
    ),
    dict(
        id="POL-006", slug="order_delivery_status", family="Order Delivery Status Policy",
        flow="order_issue", source_subflows=["status_delivery_time"],
        rules=[
            "Before reporting delivery status, the agent must verify identity using full name, account ID, and order ID via Verify Identity.",
            "The agent must query Ask the Oracle to determine whether the delivery delay was a company error before making any commitment to the customer.",
        ],
    ),
    dict(
        id="POL-007", slug="order_payment_method", family="Order Payment Method Policy",
        flow="order_issue", source_subflows=["status_payment_method"],
        rules=[
            "Before changing a payment method, the agent must verify identity using full name, account ID, and order ID via Verify Identity.",
            "A payment method change may be applied immediately only if the shipping status is Order Received or In Transit; if the status is Out for Delivery or Delivered, the new payment method may only apply to future orders.",
            "The new payment method must be one of: credit card, debit card, or paypal.",
        ],
    ),
    dict(
        id="POL-008", slug="order_quantity_discrepancy", family="Order Quantity Discrepancy Policy",
        flow="order_issue", source_subflows=["status_quantity"],
        rules=[
            "Before resolving a quantity discrepancy, the agent must verify identity using full name, account ID, and order ID via Verify Identity.",
            "The agent must query Ask the Oracle; if the Oracle indicates the charge record was accurate as billed (no company error), no refund action is taken and the conversation ends.",
            "If the Oracle confirms the company's mistake, refund eligibility depends on shipping status: Order Received status permits an immediate refund; In Transit, Out for Delivery, or Delivered status requires the customer to wait until the item arrives and contact support again before any refund is offered.",
        ],
    ),
    dict(
        id="POL-009", slug="subscription_tier_change", family="Order Shipping Tier Change Policy",
        flow="order_issue", source_subflows=["manage_upgrade", "manage_downgrade"],
        rules=[
            "Before processing a shipping upgrade or downgrade, the agent must verify identity using full name, account ID, and order ID via Verify Identity.",
            "An upgrade to overnight shipping may proceed only if shipping status is Order Received; if the item has already shipped (In Transit, Out for Delivery, or Delivered), the ship date cannot be altered and the upgrade request must be denied.",
            "Overnight shipping upgrade fees are gated by membership: Gold members have the $20 fee waived; Guest, Bronze, and Silver members must be charged $20.",
            "A downgrade may proceed for any membership level if the item has not yet shipped; if the item has already shipped, Gold, Silver, and Bronze members receive a credit for the shipping fee, but Guest members receive nothing.",
        ],
    ),
    dict(
        id="POL-010", slug="order_item_addition", family="Order Item Addition Policy",
        flow="order_issue", source_subflows=["manage_create"],
        rules=[
            "Before adding an item to an order, the agent must verify identity using full name, account ID, and order ID via Verify Identity.",
            "If the order has not yet shipped (status Order Received), the new item may be added directly to the existing order.",
            "If the order has already shipped (In Transit, Out for Delivery, or Delivered), only Silver and Gold members may receive the new item as an expedited, no-fee separate shipment; other membership levels are not eligible for this accommodation.",
        ],
    ),
    dict(
        id="POL-011", slug="order_cancellation", family="Order Cancellation Policy",
        flow="order_issue", source_subflows=["manage_cancel"],
        rules=[
            "Before cancelling or returning an order, the agent must verify identity using full name, account ID, and order ID via Verify Identity.",
            "If shipping status is Order Received, the agent must immediately offer a refund and remove the item from the order.",
            "If shipping status is In Transit, Out for Delivery, or Delivered, refund eligibility is gated by membership: Bronze, Silver, and Gold members receive an immediate refund and must call back after the item arrives to complete the return; Guest members must wait for the item to arrive before any return process begins, with no immediate refund.",
        ],
    ),
    dict(
        id="POL-012", slug="username_recovery", family="Username Recovery Policy",
        flow="account_access", source_subflows=["recover_username"],
        rules=[
            "To recover a username, the agent must collect at least 3 of the following 4 identity items: full name, zip code, phone number, or email address, via Verify Identity.",
            "The recovered username must be constructed as the first letter of the first name plus the full last name plus the digit 1 (e.g., John Smith -> jsmith1).",
            "If this username-recovery step occurs as part of Validate Purchase or another external flow, the agent must treat the constructed username as valid and continue, even if the system flags it as invalid.",
        ],
    ),
    dict(
        id="POL-013", slug="password_recovery", family="Password Recovery Policy",
        flow="account_access", source_subflows=["recover_password"],
        rules=[
            "Before resetting a password, the agent must obtain the customer's username (via the Username Recovery Policy if unknown) and enter it via Enter Details.",
            "To authorize a new password via Make Password, the agent must obtain either the PIN number or the correct answer to the security question; no password may be issued without one of these two credentials.",
        ],
    ),
    dict(
        id="POL-014", slug="two_factor_reset", family="Two-Factor Reset Policy",
        flow="account_access", source_subflows=["reset_2fa"],
        rules=[
            "To send a 2FA reset code, the agent must obtain the customer's email address via Enter Details.",
            "If the email address is unavailable, the agent may substitute either the PIN number or a correct answer to the security question ('What is your mother's maiden name?') in place of the email address.",
            "Every 2FA reset conversation must conclude with the agent sending a security best-practices link via Send Link.",
        ],
    ),
    dict(
        id="POL-015", slug="card_cart_troubleshooting", family="Payment Card and Cart Troubleshooting Policy",
        flow="troubleshoot_site", source_subflows=["credit_card", "shopping_cart"],
        rules=[
            "Card and cart troubleshooting must be attempted via Try Again or Log Out/In before any account or purchase action is taken.",
            "If the customer suspects an expired card, the agent must enter 'troubleshoot' via Enter Details rather than escalating.",
            "The agent may complete the purchase on the customer's behalf via Make Purchase only after collecting the credit card number, expiration date, and the brand/item phrase.",
        ],
    ),
    dict(
        id="POL-016", slug="site_performance_troubleshooting", family="Site Performance Troubleshooting Policy",
        flow="troubleshoot_site", source_subflows=["search_results", "slow_speed"],
        rules=[
            "For search or site-speed issues, the agent must first attempt Log Out/In or Try Again before escalating to the Website Team.",
            "Escalation to the Website Team via Notify Internal Team requires entering 'website team' as the value, and must occur only after the basic troubleshooting steps have been offered.",
            "The agent may complete the purchase on the customer's behalf via Make Purchase only after collecting the credit card number, expiration date, and the brand/item phrase.",
        ],
    ),
    dict(
        id="POL-017", slug="addon_service", family="Add-on Service Dispute Policy",
        flow="manage_account", source_subflows=["status_service_added"],
        rules=[
            "The agent must record the source of the reported issue as one of: email, spouse, or news, via Record Reason.",
            "The agent must query Ask the Oracle to confirm whether an extra service was actually added in error; if the Oracle says No, the agent must explain the misunderstanding and take no account or refund action.",
            "If the Oracle confirms the error, the extra service must be removed via Update Account, and the agent must offer a refund of $40 as the standard erroneous-service-charge amount.",
        ],
    ),
    dict(
        id="POL-018", slug="service_removal", family="Service Removal Dispute Policy",
        flow="manage_account", source_subflows=["status_service_removed"],
        rules=[
            "The agent must record the source of the reported issue as one of: email, spouse, or news, via Record Reason.",
            "The agent must query Ask the Oracle to confirm whether the service was actually removed in error; if the Oracle says No, the agent must explain the misunderstanding and take no account action.",
            "If the Oracle confirms the error, the removed service must be reinstated via Update Account by entering 'add service'.",
        ],
    ),
    dict(
        id="POL-019", slug="intl_shipping_question", family="International Shipping Question Policy",
        flow="manage_account", source_subflows=["status_shipping_question"],
        rules=[
            "Before answering an international (to/from out-of-country) shipping eligibility question, the agent must pull up the account using full name or account ID via Pull up Account.",
            "The agent must query Ask the Oracle to determine whether the account is eligible for free international shipping before answering.",
            "Every resolved international shipping inquiry must conclude with the agent asking if the customer needs anything else.",
        ],
    ),
    dict(
        id="POL-020", slug="missing_credit_investigation", family="Missing Credit Investigation Policy",
        flow="manage_account", source_subflows=["status_credit_missing"],
        rules=[
            "The agent must record the origin of the credit as one of: subscription refund, previous purchase, or promotional package, via Record Reason.",
            "The agent must query Ask the Oracle to determine whether the credit is genuinely missing; if the Oracle says No, the agent must attribute this to a display issue and take no credit action.",
            "If the Oracle confirms the credit is missing, the agent must add the amount requested by the customer, or a standard amount of $40 if the customer does not know, and issue it via Promo Code.",
        ],
    ),
    dict(
        id="POL-021", slug="account_profile_update", family="Account Profile Update Policy",
        flow="manage_account",
        source_subflows=["manage_change_address", "manage_change_name", "manage_change_phone", "manage_payment_method"],
        rules=[
            "Before updating address, name, phone, or payment method, the customer must provide their current value for that field (current address, current full name, current phone in (XXX) XXX-XXXX format, or current payment method) via Record Reason.",
            "The agent must verify identity by collecting at least 3 of the following 7 items: zip code, telephone number, PIN number, username, password, email address, or order ID of a previous purchase, via Verify Identity.",
            "Payment method updates are restricted to one of: credit card, debit card, or paypal.",
            "Phone number values (current and new) must conform to the format (XXX) XXX-XXXX.",
        ],
    ),
    dict(
        id="POL-022", slug="competitor_price_match", family="Competitor Price Match Policy",
        flow="purchase_dispute", source_subflows=["bad_price_competitor", "bad_price_yesterday"],
        rules=[
            "The agent must pull up the account using full name or account ID via Pull up Account before addressing a price dispute.",
            "The agent must record the dispute reason as one of: competitor or yesterday, via Record Reason.",
            "The agent must verify identity using full name, account ID, and order ID via Verify Identity before offering any compensation.",
            "If the customer remains unsatisfied after being told prices are dynamic, the agent may offer a discount via Promo Code with no further identity or eligibility check required.",
        ],
    ),
    dict(
        id="POL-023", slug="out_of_stock_general", family="Out-of-Stock General Policy",
        flow="purchase_dispute", source_subflows=["out_of_stock_general"],
        rules=[
            "The agent must notify the Purchasing Department via Notify Internal Team by entering 'purchasing department'.",
            "If the customer remains unsatisfied, the agent may offer a discount via Promo Code with no further eligibility check required.",
        ],
    ),
    dict(
        id="POL-024", slug="out_of_stock_single_item", family="Out-of-Stock Single Item Policy",
        flow="purchase_dispute", source_subflows=["out_of_stock_one_item"],
        rules=[
            "The agent must record the affected item's brand and type via Record Reason.",
            "The agent must notify the Purchasing Department via Notify Internal Team by entering 'purchasing department'.",
            "A back-order via Make Purchase may be offered only if the customer remains unsatisfied after notification, and must use the same credit card already on file.",
        ],
    ),
    dict(
        id="POL-025", slug="promo_code_dispute", family="Promo Code Dispute Policy",
        flow="purchase_dispute", source_subflows=["promo_code_invalid", "promo_code_out_of_date"],
        rules=[
            "A promo code dispute is classified as 'out of date' if the code was issued more than 7 days ago, and 'invalid' otherwise; both classifications follow the same resolution procedure.",
            "The agent must query Ask the Oracle to determine whether the customer made an error; if the Oracle confirms the customer is correct, the agent proceeds directly to issuing a new promo code.",
            "If the Oracle indicates customer error, new-code eligibility is gated by membership: Gold, Silver, and Bronze members all qualify for a replacement promo code regardless of the error; Guest members do not qualify and must be denied.",
            "Replacement promo codes are issued via Promo Code with no additional information entered into the form.",
        ],
    ),
    dict(
        id="POL-026", slug="mistimed_billing_already_returned", family="Mistimed Billing Policy (Already Returned)",
        flow="purchase_dispute", source_subflows=["mistimed_billing_already_returned"],
        rules=[
            "Before evaluating the claim, the agent must validate the purchase using username, email address, and order ID via Validate Purchase.",
            "The agent must record the number of days the customer has waited for the refund via Record Reason; a wait of more than 7 days is treated as a valid company error and proceeds directly to crediting the account.",
            "If the wait is 7 days or less, only Gold members are eligible to receive a credit anyway; all other membership levels must be denied and the order must not be updated.",
            "An approved credit must be processed by entering 'give credit' via Update Order.",
        ],
    ),
    dict(
        id="POL-027", slug="mistimed_billing_never_bought", family="Mistimed Billing Policy (Never Bought)",
        flow="purchase_dispute", source_subflows=["mistimed_billing_never_bought"],
        rules=[
            "Before evaluating the claim, the agent must validate the purchase using username, email address, and order ID via Validate Purchase.",
            "The agent must query Ask the Oracle; if the Oracle confirms the customer is correct, the agent proceeds directly to crediting the account.",
            "If the Oracle indicates customer error, only Gold members are eligible to receive a credit anyway; all other membership levels must be denied and the order must not be updated.",
            "An approved credit must be processed by entering 'give credit' via Update Order.",
        ],
    ),
    dict(
        id="POL-028", slug="shipping_status", family="Shipping Status Inquiry Policy",
        flow="shipping_issue", source_subflows=["status"],
        rules=[
            "Before resolving a shipping status inquiry, the agent must verify identity using full name, account ID, and order ID via Verify Identity, and validate the purchase using username, email address, and order ID via Validate Purchase.",
            "The agent must query Ask the Oracle to resolve any yes/no shipping question the customer raises.",
            "If the Oracle response is unfavorable to the customer, the agent must resolve it via Update Order using one of: change date, change address, change item, or change price.",
        ],
    ),
    dict(
        id="POL-029", slug="shipping_management", family="Shipping Management Policy",
        flow="shipping_issue", source_subflows=["manage"],
        rules=[
            "The agent must record the current shipping status as one of: Order Received, In Transit, Out for Delivery, or Delivered, via Shipping Status.",
            "The agent must validate the purchase using username, email address, and order ID via Validate Purchase before making any change.",
            "The requested change must be one of: change address or change order, submitted via Update Order.",
        ],
    ),
    dict(
        id="POL-030", slug="missing_item", family="Missing Item Policy",
        flow="shipping_issue", source_subflows=["missing"],
        rules=[
            "The agent must validate the purchase using username, email address, and order ID via Validate Purchase.",
            "The agent must record the number of days the customer has been waiting via Record Reason.",
            "A replacement order (new shipment) via Update Order and Make Purchase may only be initiated if the customer has been waiting 7 days (one week) or longer; waits under 7 days do not qualify for a replacement shipment.",
        ],
    ),
    dict(
        id="POL-031", slug="shipping_cost", family="Shipping Cost Policy",
        flow="shipping_issue", source_subflows=["cost"],
        rules=[
            "The agent must validate the purchase using username, email address, and order ID via Validate Purchase.",
            "The agent must record the shipping status as one of: Order Received, In Transit, Out for Delivery, or Delivered, via Shipping Status.",
            "If status is Order Received or In Transit, the agent must waive the shipping fee entirely via Update Order rather than issuing a partial refund.",
            "If status is Out for Delivery or Delivered, the agent must instead refund the standard shipping fee of $8.00 via Offer Refund, since the fee cannot be waived after shipment.",
        ],
    ),
    dict(
        id="POL-032", slug="subscription_status", family="Subscription Status Policy",
        flow="subscription_inquiry", source_subflows=["status_active", "status_due_amount", "status_due_date"],
        rules=[
            "Before reporting subscription status, the agent must verify identity using full name, account ID, and order ID via Verify Identity.",
            "The agent must query Subscription Status to obtain the active/cancelled state, due amount, and due date, and report all three to the customer.",
            "The agent must send an account-login link via Send Link and ensure the customer knows their username, constructing it as first-letter-of-first-name + last name + 1 if unknown.",
        ],
    ),
    dict(
        id="POL-033", slug="bill_payment", family="Subscription Bill Payment Policy",
        flow="subscription_inquiry", source_subflows=["manage_pay_bill"],
        rules=[
            "Before processing a subscription payment, the agent must verify identity using full name, account ID, and order ID via Verify Identity.",
            "The standard subscription price is $99 per year; if the customer does not know the amount owed, the agent must use the Subscription Status query to determine it, defaulting to $99 if the query returns $0.",
            "A subscription payment is finalized by entering 'renew subscription' via Update Account.",
        ],
    ),
    dict(
        id="POL-034", slug="subscription_extension", family="Subscription Extension Policy",
        flow="subscription_inquiry", source_subflows=["manage_extension"],
        rules=[
            "Before evaluating an extension request, the agent must verify identity using full name, account ID, and order ID via Verify Identity.",
            "Extension eligibility is gated strictly by membership level: Gold members always qualify; Silver members qualify only if the payment is no more than 1 day late; Bronze and Guest members never qualify.",
            "An approved extension must be granted by entering 'extend subscription' via Update Account.",
            "A denied extension request must be escalated to the manager via Notify Internal Team, after collecting the customer's phone number via Enter Details.",
        ],
    ),
    dict(
        id="POL-035", slug="billing_dispute", family="Subscription Billing Dispute Policy",
        flow="subscription_inquiry", source_subflows=["manage_dispute_bill"],
        rules=[
            "Before evaluating a billing dispute, the agent must verify identity using full name, account ID, and order ID via Verify Identity.",
            "Refund eligibility is gated by membership level: Gold members always receive the disputed amount; Silver members receive a refund only if the disputed amount is less than $10; Bronze and Guest members are evaluated via Ask the Oracle.",
            "For Bronze and Guest members, a Yes response from Ask the Oracle grants the refund and a No response denies it.",
            "The refund amount owed equals the amount the customer was charged minus the amount they were supposed to be charged (e.g., charged $60, owed $50, refund $10).",
        ],
    ),
    dict(
        id="POL-036", slug="single_item_faq", family="Single-Item Product FAQ Policy",
        flow="single_item_query", source_subflows=["boots", "shirt", "jeans", "jacket"],
        rules=[
            "FAQ answers are limited to the following four product topics: boots, jacket, jeans, and shirt; questions about any other product must not be answered from this FAQ index.",
            "The agent must select the correct product toggle (boots/shirt/jeans/jacket) before retrieving an answer, since this selection is itself a recorded, scored action.",
            "The agent must select the correct answer from the list of 8 topic-specific options via Select Answer.",
            "The system-generated FAQ response is incomplete by design; the agent must restate the answer in natural language rather than copy-pasting the raw system text.",
        ],
    ),
    dict(
        id="POL-037", slug="storewide_faq", family="Storewide FAQ Policy",
        flow="storewide_query", source_subflows=["pricing", "membership", "timing", "policy"],
        rules=[
            "FAQ answers are limited to the following four topics: pricing, timing, membership, and policy; questions outside these four topics must not be answered from this FAQ index.",
            "The agent must select the correct topic toggle (pricing/timing/membership/policy) before retrieving an answer, since this selection is itself a recorded, scored action.",
            "The agent must select the correct answer from the list of 4 topic-specific options via Select Answer.",
            "The system-generated FAQ response is incomplete by design; the agent must restate the answer in natural language rather than copy-pasting the raw system text.",
        ],
    ),
]


def render_policy_doc(fam):
    rules = []
    for i, statement in enumerate(fam["rules"], start=1):
        rules.append({
            "rule_id": f"{fam['id']}-R{i}",
            "statement": statement,
        })
    doc = {
        "policy_id": fam["id"],
        "family": fam["family"],
        "version": CORPUS_VERSION_LABEL,
        "effective_timestamp": V1_EFFECTIVE_TS,
        "flow": fam["flow"],
        "source_subflows": fam["source_subflows"],
        "source": "ABCD agent guidelines (Chen et al. 2021, arXiv 2104.00783), data/guidelines.json",
        "supersedes": None,
        "rules": rules,
    }
    return doc


def main():
    assert len(FAMILIES) == 37, f"expected 37 families, got {len(FAMILIES)}"
    ids = [f["id"] for f in FAMILIES]
    assert len(ids) == len(set(ids)), "duplicate policy_id"
    all_subflows = []
    for f in FAMILIES:
        all_subflows.extend(f["source_subflows"])
    assert len(all_subflows) == 55, f"expected 55 subflows covered, got {len(all_subflows)}"
    assert len(set(all_subflows)) == 55, "duplicate subflow coverage across families"

    manifest = {
        "corpus_version": CORPUS_VERSION_LABEL,
        "generated_at": GENERATED_AT,
        "effective_timestamp": V1_EFFECTIVE_TS,
        "num_policies": len(FAMILIES),
        "num_source_subflows_covered": len(all_subflows),
        "policies": [],
    }

    for fam in FAMILIES:
        doc = render_policy_doc(fam)
        fname = f"{fam['id']}_{fam['slug']}.json"
        path = os.path.join(OUT_DIR, fname)
        with open(path, "w") as fh:
            json.dump(doc, fh, indent=2, sort_keys=False)
            fh.write("\n")
        manifest["policies"].append({
            "policy_id": fam["id"],
            "file": fname,
            "family": fam["family"],
            "flow": fam["flow"],
            "source_subflows": fam["source_subflows"],
            "num_rules": len(fam["rules"]),
        })

    manifest_path = os.path.join(OUT_DIR, "_corpus_index.json")
    with open(manifest_path, "w") as fh:
        json.dump(manifest, fh, indent=2)
        fh.write("\n")

    total_rules = sum(p["num_rules"] for p in manifest["policies"])
    print(f"Wrote {len(FAMILIES)} policy documents to {OUT_DIR}")
    print(f"Total rules across corpus: {total_rules}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
