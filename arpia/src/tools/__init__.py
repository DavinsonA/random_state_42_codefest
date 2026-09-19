"""Las tools que puede llamar un agente, y el registro que las hace rastreables.

Toda tool se declara con `@registry.register`: eso es lo que anota la llamada en
`tools_called` y su evidencia en `retrieval_context`, que son dos campos que ADL
evalua. Una tool sin registrar funciona y no aparece en ningun lado.

Los nombres deben coincidir con los de `agent_card.json`.
"""
