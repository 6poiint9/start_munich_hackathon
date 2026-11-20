---
name: grill-me
description: >-
  Resolve uncertainty before an agent acts or answers. Use this skill whenever
  you are not completely sure about any requirement, intended behavior, design
  decision, relevant fact, or proposed answer, even if the user did not ask to
  be interviewed. Investigate facts first, then ask the user about every
  uncertainty that remains.
---

# Grill Me

Use this workflow whenever uncertainty arises, including midway through a task.
The goal is to avoid silently guessing what the user wants or presenting an
unverified assumption as fact.

1. Identify what is uncertain and what depends on it. Check the repository,
   available tools, and reliable sources for facts you can establish yourself.
2. If anything remains uncertain, ask the user a focused question before
   relying on a guess or performing work that depends on the answer. Explain
   relevant tradeoffs and offer a recommended choice when appropriate. Use the
   available question tool and follow its formatting requirements.
3. Ask one question at a time. Start with decisions that unblock other
   questions, then revisit the remaining uncertainties after each answer.
4. Continue until the relevant uncertainties are resolved. Summarize the
   resulting understanding and obtain the user's confirmation before
   proceeding with dependent work.
5. If an uncertainty cannot be resolved, state it explicitly rather than
   implying certainty. Respect higher-priority instructions, safety rules, and
   any requirement to stop or obtain approval.

Do not ask the user to provide facts that can be established from the available
environment. Independent work that does not depend on an unanswered question
may continue when allowed.
