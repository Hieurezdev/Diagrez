# ACE Playbook: Use Case Diagram

## NOTATION RULES

- [not-00001] helpful=0 harmful=0 :: Place actors outside the system boundary and use cases inside it.
- [not-00003] helpful=0 harmful=0 :: For include, point from the base use case to mandatory reused behavior.
- [not-00004] helpful=0 harmful=0 :: For extend, point from optional extending behavior to the base use case.

## SEMANTIC CHECKS

- [sem-00002] helpful=0 harmful=0 :: An association connects exactly one actor to one use case.
- [sem-00006] helpful=0 harmful=0 :: Every use case belongs to an existing system scope, while actors remain external to all scopes.

## LAYOUT GUIDANCE

- [lay-00007] helpful=0 harmful=0 :: Keep each use case visually inside its assigned scope and keep actors outside the scope boundaries.

## COMMON MISTAKES TO AVOID

- [mis-00005] helpful=0 harmful=0 :: Do not infer include or extend merely because two use cases occur in sequence.

## PROMPT CLUES & INDICATORS
