# ACE Playbook: Activity Diagram

## NOTATION RULES

- [not-00002] helpful=0 harmful=0 :: Put mutually exclusive guards on outgoing decision flows.
- [not-00003] helpful=0 harmful=0 :: Use a solid circle for the single initial node, rounded rectangles for actions, diamonds for decision/merge, and a bullseye for activity final.
- [not-00004] helpful=0 harmful=0 :: Use fork and join nodes to show parallel control flows instead of drawing ambiguous crossing arrows.
- [not-00005] helpful=0 harmful=0 :: Use object nodes and object flows when a data object moves between actions; do not confuse data with control flow.
- [not-00006] helpful=0 harmful=0 :: Use partitions/swimlanes to group actions by responsible actor or role, with lane names visible.

## SEMANTIC CHECKS

- [sem-00001] helpful=0 harmful=0 :: Provide one initial node and at least one reachable final node.
- [sem-00002] helpful=0 harmful=0 :: Every flow endpoint must be a declared node; distinguish control flow from object flow when the model includes data movement.

## LAYOUT GUIDANCE

## COMMON MISTAKES TO AVOID

## PROMPT CLUES & INDICATORS
