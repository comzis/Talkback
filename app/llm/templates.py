"""Prompt templates for citation, assistant, and explanation replies."""

from llm.followups import (
    asks_for_example,
    asks_for_steps,
    clean_history,
    _continuation_only,
    format_history,
)
from llm.language import (
    _GENERAL_MARK,
    question_language,
)


def citation_prompt(library_files: list[str]) -> str:
    """Build the answer prompt, including every document still in the library."""
    names = ", ".join(library_files) if library_files else "(none yet)"
    return (
        "You are a helpful assistant. The user can ask anything.\n"
        f"The library contains these documents: {names}.\n"
        "If the sources below answer the question, use them and cite each claim "
        "with a source number in square brackets, such as [1] or [2].\n"
        "If the sources do not answer the question, reply from your own knowledge "
        "as an assistant. Do not cite sources, and do not say you are waiting for a document.\n"
        "---------------------\n"
        "Context: {context_str}\n"
        "---------------------\n"
        "Question: {query_str}\n"
        "Answer: "
    )


def assistant_prompt(query: str, history=None) -> str:
    """Prompt for a direct assistant reply with no document requirement."""
    return (
        "You are Talkback, a helpful assistant. Reply the way a person would in a conversation.\n"
        "Reply in the language of the user's question, even when a source is in another language. "
        "Keep file names and quoted text in their original language.\n"
        "Keep it short and natural. Use plain sentences.\n"
        "Do not use markdown, headings, or a numbered manual unless the user asked for steps.\n"
        + (
            "The latest line continues the conversation above. Answer it from those turns. "
            "Do not greet the user and do not ask which topic they mean.\n"
            if clean_history(history)
            else "Do not mention documents, a library, or sources.\n"
        )
        + "If they pasted a passage, explain it briefly in your own words.\n\n"
        f"{format_history(history)}"
        f"User:\n{query}\n"
        "Assistant:"
    )


def explanation_prompt(
    query: str, library_files: list[str], excerpts: list[str], history=None
) -> str:
    """Prompt that explains pasted text and reasons only with library excerpts."""
    names = ", ".join(library_files) if library_files else "(none yet)"
    shown = "\n\n".join(f"[{index}] {text}" for index, text in enumerate(excerpts, 1))
    if not shown:
        shown = "(no matching excerpts)"
    if asks_for_steps(query):
        shape = (
            "The user asked for the steps. Walk through each step the excerpts describe, in order. "
            "Number the steps as 1. 2. 3. Use only what the excerpts say.\n"
        )
    elif asks_for_example(query):
        shape = (
            "The user asked for an example. Give one concrete example from the excerpts, "
            "copying the filter, command, or action exactly. "
            "If the excerpts do not show one, say the excerpts do not include a worked example. "
            "Do not invent a filter or a command.\n"
        )
    else:
        shape = "Keep the reply short. Use plain sentences, not a markdown manual.\n"
    return (
        "You are Talkback. The user is asking about their documents or pasted a passage.\n"
        "Reply in the language of the user's question, even when a source is in another language. "
        "Keep file names and quoted text in their original language.\n"
        f"The library contains: {names}.\n"
        "If the user pasted a passage, explain that text in plain language and walk through the lines.\n"
        "If the excerpts answer the question, answer from them and end with the excerpt number in brackets, such as [1]. "
        "Do not add general knowledge to a cited answer.\n"
        "If they do not answer the question, say so and do not cite the excerpts. "
        f'A further remark that the excerpts do not support must start with "{_GENERAL_MARK[question_language(query)]}" '
        "and must not contain a measurement.\n"
        "Do not invent a measurement. Never write a dBTP, LUFS, LU, or dB figure unless the excerpts answer the question and contain that figure.\n"
        "When the user asked for placeholders, write each one in square brackets.\n"
        f"{shape}\n"
        f"{format_history(history, continue_from_passages=_continuation_only(query))}"
        f"Library excerpts:\n{shown}\n\n"
        f"User:\n{query}\n"
        "If the excerpts do not answer the question, do not write a dBTP, LUFS, LU, or dB number.\n"
        "Assistant:"
    )


CITATION_QA_TEMPLATE = citation_prompt([])
