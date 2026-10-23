"""Director (Fable 5.1), Critic (Opus 5.5) and Builder (Sonnet 5.5) on top of the LLM wrapper."""
from __future__ import annotations

import logging

from . import prompts
from .llm import BUILDER_MODEL, CRITIC_MODEL, DIRECTOR_MODEL, LLM, LLMResult

log = logging.getLogger(__name__)


class Director:
    def __init__(self, llm: LLM, model: str = DIRECTOR_MODEL, effort: str = "high"):
        self.llm, self.model, self.effort = llm, model, effort

    def propose(self, user: str, cycle: int) -> LLMResult:
        return self.llm.call("director", self.model, prompts.DIRECTOR_SYSTEM, user, prompts.DIRECTOR_SCHEMA,
                             effort=self.effort, max_tokens=24000, cycle=cycle)


class Critic:
    def __init__(self, llm: LLM, model: str = CRITIC_MODEL, effort: str = "high"):
        self.llm, self.model, self.effort = llm, model, effort
        self._system_code = prompts.CRITIC_SYSTEM + "\n\n" + prompts.strategy_contract()

    def review_hypotheses(self, hypotheses: list[dict], scrap: list[dict], datafacts_md: str, cycle: int) -> LLMResult:
        user = prompts.render_critic_review_user(hypotheses, scrap, datafacts_md)
        return self.llm.call("critic", self.model, prompts.CRITIC_SYSTEM, user, prompts.CRITIC_REVIEW_SCHEMA,
                             effort=self.effort, max_tokens=16000, cycle=cycle)

    def review_code(self, hyp: dict, code: str, checker: dict, cycle: int) -> LLMResult:
        user = prompts.render_critic_code_user(hyp, code, checker)
        return self.llm.call("critic", self.model, self._system_code, user, prompts.CRITIC_CODE_SCHEMA,
                             effort=self.effort, max_tokens=16000, cycle=cycle)


class Builder:
    def __init__(self, llm: LLM, model: str = BUILDER_MODEL, effort: str = "high"):
        self.llm, self.model, self.effort = llm, model, effort
        self._system = prompts.BUILDER_SYSTEM + "\n\n" + prompts.strategy_contract()

    def build(self, hyp: dict, critic_notes: str, cycle: int, feedback: str | None = None,
              previous_code: str | None = None) -> LLMResult:
        user = prompts.render_builder_user(hyp, critic_notes, feedback, previous_code)
        return self.llm.call("builder", self.model, self._system, user, prompts.BUILDER_SCHEMA,
                             effort=self.effort, max_tokens=24000, cycle=cycle)
