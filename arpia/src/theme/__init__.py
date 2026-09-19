"""El tema visual: UNICO lugar del Python que conoce un color.

Todo sale de `docs/design/design-tokens.json`, leido en runtime por
`tokens.py`. Ningun otro modulo de `src/` puede escribir un hexadecimal, y
`tests/test_theme.py` lo verifica.

El espejo de esto en el frontend es `src/ui/static/css/tokens.css`, que el
navegador consume como variables CSS. Si cambia el JSON, cambian ambos en el
mismo commit: no hay proceso que los sincronice.
"""
