# Talkback

Offline RAG engineering assistant: hybrid retrieval over a local document
library, answered by a local chat model with citations back to the library.

## Language

**Retrieval candidate**:
One of the passages fetched and reranked for a query, before the answer is
generated or any citation is determined.
_Avoid_: Source, passage (used loosely in UI status text, but ambiguous here)

**Cited source**:
A retrieval candidate the generated answer actually references via an
inline `[n]` marker that survives citation finalization (renumbering plus
the similarity-to-passage check). Only cited sources are shown in the chat
UI's Sources block — candidates that were retrieved but never cited are not
shown at all.
_Avoid_: Used source, retrieved source (conflates with candidate)

**Source card**:
The data/UI representation of a cited source: its label/path, page, a
display excerpt, and its number. Numbered 1..n in citation order, matching
the renumbered `[n]` markers in the answer text exactly — there is no
separate "original retrieval position" numbering visible anywhere.

**Display excerpt**:
The ~500/900-character window of a source's chunk text selected around the
answer-relevant tokens, shown on a source card. Not a naive head-truncation
of the chunk.
