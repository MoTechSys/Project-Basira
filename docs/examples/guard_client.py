"""Minimal chatbot guard: ask Basira before the answer reaches the user (docs/GUARD.md). 15 lines, stdlib only."""
import json
import urllib.request

BASIRA = "http://localhost:8000"


def guarded_reply(model_answer: str, lang: str = "ar") -> str:
    body = json.dumps({"answer": model_answer, "ui_lang": lang}).encode("utf-8")
    req = urllib.request.Request(f"{BASIRA}/v1/guard", body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        g = json.load(resp)
    if g["verdict"] == "flagged":  # hold or annotate — never rewrite the quotation
        return f"{model_answer}\n\n⚠ {g['summary_' + lang]}"
    return model_answer


if __name__ == "__main__":
    print(guarded_reply("قال تعالى: ﴿إن الله مع الصابرين﴾ وقال ﷺ: «الدين المعاملة»"))
