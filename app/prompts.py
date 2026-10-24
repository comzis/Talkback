"""Prompt text for grounded answers."""


def citation_prompt(library_files: list[str]) -> str:
    """Build the answer prompt, including every document still in the library."""
    names = ", ".join(library_files) if library_files else "(none yet)"
    return (
        "Answer the question using the sources below.\n"
        f"The library contains these documents together: {names}.\n"
        "A newer upload does not remove an older document.\n"
        "Cite each claim with the source number in square brackets, such as [1] or [2].\n"
        "If the sources do not contain the answer, say you cannot find it in the retrieved excerpts "
        "and name the documents that are still in the library.\n"
        "---------------------\n"
        "Context: {context_str}\n"
        "---------------------\n"
        "Question: {query_str}\n"
        "Answer: "
    )


CITATION_QA_TEMPLATE = citation_prompt([])
