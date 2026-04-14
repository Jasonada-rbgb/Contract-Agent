"""Offline tests for the markdown-first Q&A contract and hidden council.

These tests validate prompt structure, council orchestration logic, and
rendering helpers without requiring live Databricks endpoints.
"""

import json
import os
import re
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Markdown output contract ────────────────────────────────────────────────

class TestMarkdownContract:
    """Validate the markdown-first instructions by reading agent.py source directly.

    This avoids importing agent_server.agent (which requires litellm, mlflow,
    databricks-openai etc.) while still verifying the prompt contract.
    """

    @staticmethod
    def _get_instructions_source() -> str:
        agent_path = os.path.join(
            os.path.dirname(__file__), "..", "agent_server", "agent.py",
        )
        with open(agent_path, encoding="utf-8") as f:
            return f.read()

    def test_instructions_require_markdown_headings(self):
        src = self._get_instructions_source()
        assert "## Evidence" in src
        assert "## Answer" in src
        assert "## Comparison" in src

    def test_instructions_require_pipe_tables(self):
        src = self._get_instructions_source()
        assert "pipe table" in src.lower()

    def test_instructions_cap_table_width(self):
        src = self._get_instructions_source()
        assert "5 columns" in src

    def test_instructions_preserve_citations(self):
        src = self._get_instructions_source()
        assert "[n]" in src

    def test_instructions_preserve_not_found_behavior(self):
        src = self._get_instructions_source()
        assert "Not found in provided documents" in src

    def test_instructions_mention_github_flavored_markdown(self):
        src = self._get_instructions_source()
        assert "GitHub-flavored Markdown" in src


# ── Council module ───────────────────────────────────────────────────────────

class TestCouncilFeatureFlag:
    def test_council_disabled_by_default(self):
        from agent_server.council import is_council_enabled

        with patch.dict(os.environ, {}, clear=True):
            assert is_council_enabled() is False

    def test_council_enabled_with_true(self):
        from agent_server.council import is_council_enabled

        with patch.dict(os.environ, {"COUNCIL_ENABLED": "true"}):
            assert is_council_enabled() is True

    def test_council_enabled_with_1(self):
        from agent_server.council import is_council_enabled

        with patch.dict(os.environ, {"COUNCIL_ENABLED": "1"}):
            assert is_council_enabled() is True

    def test_council_disabled_with_false(self):
        from agent_server.council import is_council_enabled

        with patch.dict(os.environ, {"COUNCIL_ENABLED": "false"}):
            assert is_council_enabled() is False


class TestCouncilDraftPrompt:
    def test_draft_prompt_includes_evidence_and_question(self):
        from agent_server.council import _draft_prompt

        prompt = _draft_prompt("What is the warranty?", "evidence text", "profile text")
        assert "What is the warranty?" in prompt
        assert "evidence text" in prompt
        assert "profile text" in prompt
        assert "GitHub-flavored Markdown" in prompt
        assert "[n]" in prompt

    def test_draft_prompt_includes_not_found_instruction(self):
        from agent_server.council import _draft_prompt

        prompt = _draft_prompt("q", "e", "p")
        assert "Not found in provided documents" in prompt


class TestCouncilChairPrompt:
    def test_chair_prompt_includes_all_drafts(self):
        from agent_server.council import _chair_prompt

        drafts = [
            {"model": "gpt_41", "text": "Answer from GPT"},
            {"model": "gemini_25_pro", "text": "Answer from Gemini"},
        ]
        prompt = _chair_prompt("question?", drafts, "evidence")
        assert "Answer from GPT" in prompt
        assert "Answer from Gemini" in prompt
        assert "DRAFT 1" in prompt
        assert "DRAFT 2" in prompt

    def test_chair_prompt_instructs_narrow_wording(self):
        from agent_server.council import _chair_prompt

        prompt = _chair_prompt("q", [{"model": "m", "text": "t"}], "e")
        assert "narrower" in prompt.lower()
        assert "citation-backed" in prompt.lower()

    def test_chair_prompt_hides_multi_model(self):
        from agent_server.council import _chair_prompt

        prompt = _chair_prompt("q", [{"model": "m", "text": "t"}], "e")
        assert "Do NOT mention that multiple models" in prompt


class TestCouncilOrchestration:
    @patch("agent_server.council._log_council_run")
    @patch("agent_server.council._call_model")
    def test_council_returns_chair_synthesis(self, mock_call, mock_log):
        from agent_server.council import run_council

        def side_effect(prompt, endpoint):
            if "chair" in prompt.lower() or "council" in prompt.lower():
                return "## Answer\nSynthesized answer [1]."
            return f"Draft from {endpoint} [1]."

        mock_call.side_effect = side_effect
        result = run_council("What?", "evidence", endpoints=["ep1", "ep2"])
        assert "[1]" in result
        assert mock_log.called

    @patch("agent_server.council._log_council_run")
    @patch("agent_server.council._call_model")
    def test_council_fallback_on_chair_failure(self, mock_call, mock_log):
        from agent_server.council import run_council

        call_count = {"n": 0}

        def side_effect(prompt, endpoint):
            call_count["n"] += 1
            if "council" in prompt.lower() or "chair" in prompt.lower():
                return None
            return f"Draft {call_count['n']}"

        mock_call.side_effect = side_effect
        result = run_council("What?", "evidence", endpoints=["ep1", "ep2"])
        assert result.startswith("Draft")

    @patch("agent_server.council._log_council_run")
    @patch("agent_server.council._call_model")
    def test_council_all_not_found(self, mock_call, mock_log):
        from agent_server.council import run_council

        mock_call.return_value = "Not found in provided documents."
        result = run_council("What?", "evidence", endpoints=["ep1", "ep2"])
        assert result == "Not found in provided documents."

    @patch("agent_server.council._log_council_run")
    @patch("agent_server.council._call_model")
    def test_council_no_valid_drafts(self, mock_call, mock_log):
        from agent_server.council import run_council

        mock_call.return_value = None
        result = run_council("What?", "evidence", endpoints=["ep1", "ep2"])
        assert result == "Not found in provided documents."

    @patch("agent_server.council._log_council_run")
    @patch("agent_server.council._call_model")
    def test_single_valid_draft_skips_chair(self, mock_call, mock_log):
        from agent_server.council import run_council

        def side_effect(prompt, endpoint):
            if endpoint == "ep1":
                return "Only one answer [1]."
            return None

        mock_call.side_effect = side_effect
        result = run_council("What?", "evidence", endpoints=["ep1", "ep2"])
        assert result == "Only one answer [1]."
        assert mock_call.call_count == 2


# ── Render helper ────────────────────────────────────────────────────────────

class TestRenderHelper:
    def test_render_helper_defined_in_source(self):
        """Verify _render_assistant_md is defined in streamlit_app.py source."""
        app_path = os.path.join(os.path.dirname(__file__), "..", "streamlit_app.py")
        with open(app_path, encoding="utf-8") as f:
            src = f.read()
        assert "def _render_assistant_md(" in src

    def test_render_helper_used_for_assistant_output(self):
        """Verify assistant messages use the centralized helper."""
        app_path = os.path.join(os.path.dirname(__file__), "..", "streamlit_app.py")
        with open(app_path, encoding="utf-8") as f:
            src = f.read()
        assert "_render_assistant_md(text)" in src or "_render_assistant_md(msg" in src


# ── Markdown format validation helpers ───────────────────────────────────────

class TestMarkdownFormatValidation:
    """Utilities for checking model output structure (used in smoke tests)."""

    @staticmethod
    def has_heading(text: str, heading: str) -> bool:
        return bool(re.search(rf"^##\s+{re.escape(heading)}", text, re.MULTILINE))

    @staticmethod
    def has_citations(text: str) -> bool:
        return bool(re.search(r"\[\d+\]", text))

    @staticmethod
    def has_pipe_table(text: str) -> bool:
        return bool(re.search(r"\|.*\|.*\|", text))

    def test_heading_detection(self):
        assert self.has_heading("## Evidence\nSome text", "Evidence")
        assert not self.has_heading("# Evidence\nSome text", "Evidence")

    def test_citation_detection(self):
        assert self.has_citations("The warranty is 24 months [1].")
        assert not self.has_citations("No citations here.")

    def test_pipe_table_detection(self):
        assert self.has_pipe_table("| A | B |\n|---|---|\n| 1 | 2 |")
        assert not self.has_pipe_table("No table here.")
