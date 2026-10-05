import pytest

from viva import ai

BODY = {"file": "invoices.py", "code": "def f(): ...", "rule": "Own invoices only.", "leak_terms": ["200 OK"],
        "turns": [{"turn": 1, "question": "How?", "answer": "It takes customer_id from the query string."}]}


def ask(question):
    return {"needs_follow_up": True, "target": "consequence", "question": question}


# Questions the live model asked in eval/viva_stability.py, and what the filter makes of them.
@pytest.mark.parametrize("question, reason", [
    ("You take customer_id from the URL the frontend sends. What could go wrong, and for whom, if a request arrives "
     "with a customer_id that isn't the logged-in user's?", None),
    ("You raise the same error whether the invoice is missing or belongs to someone else. Why did you choose to treat "
     "those two cases identically?", None),
    ("Suppose a logged-in user sends customer_id=42 and that is not their own ID. Walk us through what your code does "
     "with that value, step by step.", None),
    ("Suppose a logged-in user sends a request with a customer_id that isn't theirs. In your code, which line decides "
     "what happens, and what does the user get back?", "more than one question"),
    ("Why did you take customer_id from the query string rather than from the authenticated user, and what role does "
     "the user parameter play in this function?", "more than one question"),
    ("You take customer_id from the URL and your handler receives a user object. What could go wrong, and for whom, if "
     "the id in the request isn't the one the frontend normally sends?", "too long"),
    ("Invoice 7 belongs to customer 5 and customer 9 asks for it. What response do you expect, and from which line?",
     "more than one question"),
    ("What does it return? Which test covers it?", "more than one question"),
    ("Does the caller get 200 OK back?", "gives away '200 OK'"),
])
def test_followup_filter(monkeypatch, question, reason):
    monkeypatch.setattr(ai, "ask_model", lambda *a, **k: (ask(question), "m"))
    got = ai._followup(BODY)
    assert got.get("filter_reason") == reason
    assert got["question"] == (None if reason else question)


def test_no_followup_needed(monkeypatch):
    monkeypatch.setattr(ai, "ask_model", lambda *a, **k: ({"needs_follow_up": False, "target": "concrete", "question": ""}, "m"))
    assert ai._followup(BODY) == {"needs_follow_up": False, "model": "m", "attempts": 1}


def test_filtered_question_is_asked_again_once(monkeypatch):
    sent = []

    def model(system, user, *a, **k):
        sent.append(user)
        return ask("Which line handles it, and what comes back?" if len(sent) == 1 else "Which line handles it?"), "m"
    monkeypatch.setattr(ai, "ask_model", model)
    got = ai._followup(BODY)
    assert got["question"] == "Which line handles it?" and got["attempts"] == 2
    assert 'reason="more than one question"' in sent[1] and "Which line handles it, and what comes back?" in sent[1]
