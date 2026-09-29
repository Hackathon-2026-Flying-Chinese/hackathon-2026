"""Curated executable fixtures. Never execute uploaded or model-generated code.

The artifact's output is a behavior oracle, NOT a business correctness oracle.
Business requirements are independently specified and versioned here.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
import json

CONCEPT = "currency_precision"
CONTRACT = "fx-contract-v1"
PRECISION = {"AUD": 2, "USD": 2, "JPY": 0, "KWD": 3, "KRW": 0, "BHD": 3}

FIXED_CODE = '''from decimal import Decimal, ROUND_HALF_UP

def payout(amount, fee, rate, currency):
    net_source = Decimal(amount) - Decimal(fee)
    converted = net_source * Decimal(rate)
    return converted.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
'''
CORRECT_CODE = FIXED_CODE.replace('Decimal("0.01")', 'Decimal(1).scaleb(-PRECISION[currency])')
TRAIN_CODE = FIXED_CODE


def artifact_run(task):
    """Run the trusted fixture's actual algorithm, including its intentional bug."""
    value = (Decimal(task["amount"]) - Decimal(task["fee"])) * Decimal(task["rate"])
    digits = PRECISION[task["currency"]] if task["correct"] else 2
    return value.quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)


def required_run(task):
    """Independent specification oracle, in integer minor units.

    For nonnegative amounts HALF_UP is floor(scaled + 0.5). This deliberately
    does not invoke artifact_run or copy its quantize implementation.
    """
    units = 10 ** PRECISION[task["currency"]]
    scaled = (Decimal(task["amount"]) - Decimal(task["fee"])) * Decimal(task["rate"]) * units
    return Decimal(int(scaled + Decimal("0.5"))) / Decimal(units)


def task(task_id, currency, amount, fee, rate, correct=False):
    item = dict(id=task_id, concept=CONCEPT, contract=CONTRACT, currency=currency,
                amount=amount, fee=fee, rate=rate, correct=correct)
    item["artifact_hash"] = sha256(json.dumps(item | {"source": CORRECT_CODE if correct else FIXED_CODE,
                                                      "precision": PRECISION}, sort_keys=True).encode()).hexdigest()
    return item


TASKS = {t["id"]: t for t in [
    task("baseline-a", "JPY", "53.41", "0.80", "97.31"),
    task("baseline-b", "KWD", "240.57", "1.10", "0.1993"),
    task("practice-a", "JPY", "1234.56", "2.00", "97.3"),
    task("practice-b", "KWD", "327.81", "1.20", "0.2017"),
    task("transfer-a-bug", "KRW", "82.37", "0.70", "891.73"),
    task("transfer-a-valid", "BHD", "152.63", "1.10", "0.2439", True),
    task("transfer-b-bug", "BHD", "196.31", "1.10", "0.2487"),
    task("transfer-b-valid", "KRW", "47.19", "0.70", "901.37", True),
    task("delayed-a-bug", "KWD", "459.17", "1.60", "0.2009"),
    task("delayed-a-valid", "JPY", "39.17", "0.60", "97.13", True),
    task("delayed-b-bug", "JPY", "241.53", "1.60", "96.77"),
    task("delayed-b-valid", "KWD", "126.83", "0.90", "0.2031", True),
    task("demo-start", "JPY", "1234.56", "2.00", "97.3"),
    task("demo-review", "KWD", "327.81", "1.20", "0.2017"),
    task("demo-review-2", "BHD", "196.31", "1.10", "0.2487"),
]}


def evidence(task):
    actual, required = artifact_run(task), required_run(task)
    return [
        {"id": "same-currency", "text": f"Regression: {task['currency']} payout compared to the written contract → {'PASS' if actual == required else 'FAIL'}"},
        {"id": "usd-only", "text": "Regression: USD payout rounded to 2 decimals → PASS"},
        {"id": "http-ok", "text": "HTTP health endpoint returns 200"},
        {"id": "format-only", "text": "Formatter reports no style changes"},
    ]


def public_task(task):
    return {
        k: task[k] for k in ("id", "concept", "contract", "currency", "amount", "fee", "rate", "artifact_hash")
    } | {
        "code": ("PRECISION = " + repr(PRECISION) + "\n\n" if task["correct"] else "") + (CORRECT_CODE if task["correct"] else FIXED_CODE),
        "requirements": [
            "Synthetic payout contract, not a representation of a live payment API.",
            f"Amount and fixed fee are in AUD. Subtract the fee exactly once BEFORE conversion; rate is destination units per AUD.",
            f"Use decimal arithmetic. Round ONCE at the final destination amount using HALF_UP. {task['currency']} allows {PRECISION[task['currency']]} decimals.",
            "All amounts are nonnegative. Calculator, code execution and supplied reference material are permitted. This is not a mental arithmetic test.",
        ],
        "evidence": evidence(task),
    }


def grade(task, answer):
    actual, required = artifact_run(task), required_run(task)
    try:
        prediction = Decimal(str(answer.get("prediction", "")))
        prediction_ok = prediction.is_finite() and prediction == actual
    except (InvalidOperation, ValueError):
        prediction_ok = False
    valid = actual == required
    scores = {
        "behavior": int(prediction_ok),
        "requirement": int(answer.get("verdict") == ("meets" if valid else "violates")),
        "evidence": int(answer.get("evidence") == "same-currency"),
    }
    return {
        "dimensions": scores, "objective_score": sum(scores.values()), "objective_max": 3,
        "passed": all(scores.values()), "actual_output": str(actual), "required_output": str(required),
        "artifact_meets_contract": valid,
        "feedback": f"The artifact returns {actual}. The independent contract requires {required} {task['currency']}. "
                    "Predicting a buggy output correctly earns behavior credit; it does not establish business correctness. "
                    "A USD-only test cannot establish correctness for this destination currency.",
        "rationale_status": "human_review_pending", "contract": CONTRACT, "artifact_hash": task["artifact_hash"],
    }
