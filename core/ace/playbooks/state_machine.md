# ACE Playbook: State Machine Diagram

## NOTATION RULES

- [not-00003] helpful=0 harmful=0 :: Use a solid circle for the initial pseudo-state and a bullseye for the final state; stable states are rounded rectangles.
- [not-00004] helpful=0 harmful=0 :: Label transitions with event [guard] / action in that order.
- [not-00005] helpful=0 harmful=0 :: Put entry/, do/, and exit/ behaviors inside the state compartment; do not turn them into separate states.
- [not-00006] helpful=0 harmful=0 :: Use H for a history pseudo-state and a diamond for a choice pseudo-state; keep both distinct from stable states.

## SEMANTIC CHECKS

- [sem-00001] helpful=0 harmful=0 :: Model stable states as nodes and events or conditions as transition labels.
- [sem-00002] helpful=0 harmful=0 :: Provide one initial state and at least one reachable final state.
- [sem-00003] helpful=0 harmful=0 :: Model one entity lifecycle; do not mix unrelated workflows or represent every activity step as a state.
- [sem-00004] helpful=0 harmful=0 :: Composite states contain substates through parent_id; concurrent regions should be explicitly named rather than implied by crossing transitions.

## LAYOUT GUIDANCE

## COMMON MISTAKES TO AVOID

## PROMPT CLUES & INDICATORS
