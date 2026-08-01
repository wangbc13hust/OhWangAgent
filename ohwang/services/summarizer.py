from __future__ import annotations

from .compact import Compactor, drain_text

_SESSION_SUMMARY_PROMPT = """Summarize the following conversation into a compact session brief that
will be injected at the start of a resumed session. Capture, in order of importance:
- the overall goal / task the user was working toward
- key decisions made and their rationale
- files / paths created or modified
- commands run
- open questions or explicit next steps
- any user preferences revealed

Rules:
- No greeting and no "In this session..." framing. Start directly with the facts.
- Use terse bullet points, 5-12 bullets, one line each.
- Preserve exact file paths and command syntax.
- If the conversation has no substantive content (only a greeting), return the
  single line: "(session had no substantive content)".
Return plain text only. No markdown code fences, no JSON.
"""


class SessionSummarizer:
    """Distill a conversation into a compact session brief for /resume."""

    def summarize(self, provider, messages: list[dict], max_tokens: int = 512) -> str:
        """Return the summary text, or "" if the call fails (never raises).

        Reuses Compactor._serialize + drain_text so the transcript format and
        provider streaming contract match the compaction path exactly.
        """
        transcript = Compactor._serialize(messages)
        if len(transcript) > 80_000:
            transcript = transcript[-80_000:]
        try:
            return drain_text(
                provider.chat(
                    system=_SESSION_SUMMARY_PROMPT,
                    messages=[
                        {
                            "role": "user",
                            "content": [{"type": "text", "text": transcript}],
                        }
                    ],
                    tools=[],
                    max_tokens=max_tokens,
                )
            ).strip()
        except Exception:
            return ""
