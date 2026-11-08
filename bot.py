"""
Conversation engine. Stages:
  intake          -> build the case file through follow-up questions
  notice_details  -> after the assessment, collect name, address, seller, order ID
  done            -> notice drafted
  stopped         -> a stop alert fired; the bot will not continue

Per user message: extract (LLM) -> merge and check (code) -> alerts (code) -> next question,
assessment or notice. Everything is recorded in self.log for the raw-outputs folder.
"""
import json
from datetime import date

import config
import prompts
from alerts import Alert, check_alerts, has_stop
from case import QUESTIONS, empty_case, intake_missing, merge, notice_missing, pretty_date
from llm import LLMError, parse_json
from notice import build_notice, display_fields, fallback_facts
from provisions import load_provisions, provisions_for_prompt
from rules import commission, platform_step, relief
from validator import validate_and_clean

DISCLAIMER = ("This is legal information, not legal advice. If anything is unclear, or the other side "
              "threatens you, contact your District Legal Services Authority for free legal help.")


class Bot:
    def __init__(self, llm, today=None):
        self.llm = llm
        self.today = today or date.today()
        self.case = empty_case()
        self.stage = "intake"
        self.asked, self.gave_up = {}, set()
        self.last_questions = []
        self.user_messages = []
        self.extra_alerts = []
        self.shown_alerts = set()
        self.notice = None
        self.log = []
        self.provisions = load_provisions()

    # ---------- public ----------
    def handle(self, message):
        event = {"turn": len(self.user_messages) + 1, "user": message, "stage_before": self.stage}
        self.user_messages.append(message)

        if self.stage == "stopped":
            return self._finish(event, "This case is outside what I can help with. Use **Start over** for a different problem.")
        if self.stage == "done":
            return self._finish(event, "Your notice is ready. Use **Start over** to work on another problem.")

        try:
            updates = self._extract(message, event)
        except LLMError as e:
            event["llm_error"] = str(e)
            return self._finish(event, f"I couldn't reach the AI model, so I didn't save that answer. ({e})")

        event["rejected"] = merge(self.case, updates, self.today)

        alerts = self._alerts()
        if has_stop(alerts):
            self.stage = "stopped"
            stops = [a for a in alerts if a.level == "stop"]
            text = "\n\n".join(f"**{a.title}.** {a.message}" for a in stops)
            return self._finish(event, text + "\n\nI can't take this case further here.")

        if self.stage == "intake":
            questions = self._next_questions(intake_missing(self.case))
            if questions:
                return self._finish(event, questions)
            self.stage = "notice_details"
            assessment = self._assess(event)
            questions = self._next_questions(notice_missing(self.case))
            if questions:
                return self._finish(event, assessment + "\n\n**To draft your legal notice I need a few details.**\n\n" + questions)
            return self._finish(event, assessment + "\n\n" + self._draft(event))

        # notice_details
        questions = self._next_questions(notice_missing(self.case))
        if questions:
            return self._finish(event, questions)
        return self._finish(event, self._draft(event))

    def export_log(self):
        return {"model": getattr(self.llm, "name", "unknown"), "today": self.today.isoformat(),
                "final_case": self.case, "stage": self.stage, "notice": self.notice, "turns": self.log}

    # ---------- steps ----------
    def _extract(self, message, event):
        user = prompts.EXTRACT_USER.format(
            case=json.dumps({k: v for k, v in self.case.items() if v is not None}, ensure_ascii=False),
            questions="\n".join(self.last_questions) or "(first message)",
            message=message)
        raw = self.llm.complete(prompts.EXTRACT.format(today=self.today.isoformat()), user, json_mode=True)
        event["llm_extract_raw"] = raw
        try:
            return parse_json(raw)
        except (ValueError, json.JSONDecodeError) as e:
            event["parse_error"] = str(e)
            return {}

    def _alerts(self):
        alerts = check_alerts(self.case, " ".join(self.user_messages), self.today) + self.extra_alerts
        seen, unique = set(), []
        for a in alerts:
            if a.code not in seen:
                seen.add(a.code)
                unique.append(a)
        return unique

    def _next_questions(self, missing):
        todo = []
        for field in missing:
            if field in self.gave_up:
                continue
            if self.asked.get(field, 0) >= config.MAX_ASKS_PER_FIELD:
                self.gave_up.add(field)
                self.extra_alerts.append(Alert(
                    "warning", f"MISSING_{field.upper()}", "Some information is still missing",
                    f"I asked twice but couldn't get: {QUESTIONS[field].split('?')[0].lower()}. "
                    "I'll continue without it, but your case may be weaker. A legal aid lawyer can help you fill the gaps."))
                continue
            todo.append(field)
        todo = todo[:config.MAX_QUESTIONS_PER_TURN]
        for f in todo:
            self.asked[f] = self.asked.get(f, 0) + 1
        self.last_questions = [QUESTIONS[f] for f in todo]
        if not todo:
            return ""
        if len(todo) == 1:
            return self.last_questions[0]
        return "\n".join(f"{i}. {q}" for i, q in enumerate(self.last_questions, 1))

    def _assess(self, event):
        step = platform_step(self.case, self.today)
        comm = commission(self.case["amount_paid"])
        step_text = {
            "complain_first": (f"Write to the grievance officer of {self.case['platform'] or 'the platform'} first "
                               "(their contact is on the website, usually under 'Grievance Redressal'). They must "
                               "acknowledge within 48 hours and resolve it within one month. If they don't, send "
                               "the legal notice. I can draft the notice now so it's ready."),
            "wait": (f"The platform's one-month period ends on {pretty_date(step.get('until'))}. If it isn't fixed by then, "
                     "send the legal notice. I can draft it now so it's ready."),
            "send_notice": "The platform's one-month period has passed. The next step is a legal notice to the seller and the platform.",
        }[step["step"]]

        explanation, problems = "", []
        try:
            raw = self.llm.complete(prompts.EXPLAIN, prompts.EXPLAIN_USER.format(
                provisions=provisions_for_prompt(self.provisions),
                case=json.dumps(self.case, ensure_ascii=False),
                commission=comm, step=step["step"], relief=relief(self.case)))
            event["llm_explain_raw"] = raw
            explanation, problems = validate_and_clean(raw, self.case, self.provisions, today=self.today)
        except LLMError as e:
            event["llm_error"] = str(e)
        event["explain_problems"] = problems
        if len(explanation) < 80:   # model failed or too much was removed
            explanation = ("You bought this as a consumer, and the problem has not been fixed. You can ask for the "
                           f"seller and platform to {relief(self.case)}. If they don't, you can file a complaint "
                           "yourself, without a lawyer, under the Consumer Protection Act, 2019.")
            event["explain_fallback"] = True

        return (f"**Where you stand**\n\n{explanation}\n\n"
                f"**Your next step:** {step_text}\n\n"
                f"**Where a complaint would go:** {comm}"
                + (f" for {self.case['user_district']}" if self.case.get("user_district") else "")
                + ". You can file online at e-jagriti.gov.in.")

    def _draft(self, event):
        facts, problems = "", []
        try:
            raw = self.llm.complete(prompts.FACTS, prompts.FACTS_USER.format(
                case=json.dumps(self.case, ensure_ascii=False),
                display=json.dumps(display_fields(self.case), ensure_ascii=False)))
            event["llm_facts_raw"] = raw
            facts, problems = validate_and_clean(raw, self.case, self.provisions,
                                                 allow_citations=False, today=self.today)
        except LLMError as e:
            event["llm_error"] = str(e)
        event["facts_problems"] = problems
        if len(facts) < 80:
            facts = fallback_facts(self.case)
            event["facts_fallback"] = True

        self.notice = build_notice(self.case, facts, self.today)
        _, final_problems = validate_and_clean(self.notice, self.case, self.provisions, today=self.today)
        event["notice_problems"] = final_problems     # should always be empty: template is code-controlled
        self.stage = "done"

        attach = ", ".join(self.case.get("evidence") or ["the invoice", "order confirmation"])
        return ("**Your draft legal notice**\n\n```\n" + self.notice + "\n```\n\n"
                "**Before you send it**\n\n"
                "Read it and correct anything wrong. Email it to the seller and the platform's grievance officer, "
                f"and send it by registered post if you have their address. Keep proof of sending. Attach: {attach}. "
                f"If there's no proper reply within {config.NOTICE_REPLY_DAYS} days, contact the National Consumer "
                "Helpline or file your complaint at e-jagriti.gov.in.\n\n_" + DISCLAIMER + "_")

    def _finish(self, event, reply):
        alerts = self._alerts()
        new = [a for a in alerts if a.code not in self.shown_alerts]
        self.shown_alerts |= {a.code for a in alerts}
        event.update({"reply": reply, "alerts": [a.to_dict() for a in alerts],
                      "case_after": dict(self.case), "stage_after": self.stage})
        self.log.append(event)
        return {"reply": reply, "new_alerts": [a.to_dict() for a in new if a.level != "stop"],
                "alerts": [a.to_dict() for a in alerts], "stage": self.stage, "notice": self.notice}
