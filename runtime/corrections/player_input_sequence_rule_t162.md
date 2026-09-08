# Player input sequencing rule — T+162

Direct user correction for Tensura RP parsing.

When the player writes a mixed input containing spoken lines and parenthetical actions, resolve it strictly left-to-right in the exact order written.

Example pattern:
1. spoken phrase A;
2. parenthetical action A happens after phrase A;
3. spoken phrase B;
4. parenthetical action B happens after phrase B.

Do not merge the actions, move an action earlier, delay it past a later phrase, or paraphrase the order into a different sequence.

Parentheses in this context may describe Arlequino's deliberate in-world action/timing rather than OOC meta. Distinguish by semantics, but preserve chronology exactly when they are physical actions.

This rule supplements, not replaces, the existing rule that OOC/meta conditions in parentheses do not become NPC knowledge or forced world events.