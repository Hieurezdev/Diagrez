# ACE Playbook: Sequence Diagram

## NOTATION RULES

- [not-00002] helpful=0 harmful=0 :: Use return messages only for meaningful returned results, not every call.
- [not-00003] helpful=0 harmful=0 :: Show participants across the top with lifelines below; messages are horizontal and ordered from top to bottom.
- [not-00004] helpful=0 harmful=0 :: Use solid arrows for calls and dashed arrows for returns; keep asynchronous messages explicitly marked.
- [not-00005] helpful=0 harmful=0 :: Render self and recursive messages as a loop back to the same lifeline; recursive calls target a nested activation.
- [not-00006] helpful=0 harmful=0 :: A create message starts the target lifeline at that message; a destroy message ends it with an X.
- [not-00007] helpful=0 harmful=0 :: Use a duration message only when the model explicitly describes a time interval, and use notes for non-semantic comments.
- [not-00008] helpful=0 harmful=0 :: Show focus of control as a thin activation rectangle aligned to the message start and completion on a lifeline.
- [not-00009] helpful=0 harmful=0 :: Enclose conditional, optional, parallel, and loop interactions in a combined-fragment frame labeled with its operator and guard.

## SEMANTIC CHECKS

- [sem-00001] helpful=0 harmful=0 :: Order messages chronologically and ensure every endpoint is a declared participant.
- [sem-00002] helpful=0 harmful=0 :: Describe one interaction scenario and include only participants that take part in that scenario.
- [sem-00003] helpful=0 harmful=0 :: Fragment ranges must refer to existing chronological messages and use guards that explain the alternative or repetition.

## LAYOUT GUIDANCE

## COMMON MISTAKES TO AVOID

## PROMPT CLUES & INDICATORS
