"""El informe se descarga en PDF con jsPDF servida desde el propio contenedor (sin CDN)."""

from __future__ import annotations

from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "src/ui/static"


def test_jspdf_esta_vendorizada_con_su_licencia():
    assert (STATIC / "vendor/jspdf.umd.min.js").stat().st_size > 100_000
    assert "Permission is hereby granted" in (STATIC / "vendor/LICENSE-jspdf.txt").read_text(
        encoding="utf-8"
    )


def test_el_tablero_la_carga_desde_vendor_y_no_desde_un_cdn():
    html = (STATIC / "dashboard.html").read_text(encoding="utf-8")
    assert 'src="vendor/jspdf.umd.min.js"' in html
    assert "cdnjs" not in html and "jsdelivr" not in html


def test_el_boton_descarga_un_pdf_y_no_un_markdown():
    js = (STATIC / "js/informe.js").read_text(encoding="utf-8")
    assert ".pdf`" in js and ".save(" in js
    assert "text/markdown" not in js
