import json
from pathlib import Path

import pytest

from src.normalizers.amount import normalize_amount
from src.parsers.macro import MacroParser

FIXTURES = Path(__file__).parent.parent / "fixtures" / "macro"


def test_golden_macro():
    input_file = FIXTURES / "sample.txt"
    golden_file = FIXTURES / "sample.json"

    if not input_file.exists():
        pytest.skip("Fixture not found. Create tests/fixtures/macro/sample.txt")

    text = input_file.read_text(encoding="utf-8")
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    parser = MacroParser()
    raw_tx = parser.parse_lines(lines)

    result = {
        "banco": "Banco Macro",
        "fecha_desde": raw_tx[0].fecha if raw_tx else None,
        "fecha_hasta": raw_tx[-1].fecha if raw_tx else None,
        "detalle": [
            {
                "fecha": t.fecha,
                "descripcion": t.descripcion,
                "importe": float(normalize_amount(t.importe).signed_value),
                "saldo": float(normalize_amount(t.saldo).signed_value) if t.saldo else None,
            }
            for t in raw_tx
        ],
    }

    if golden_file.exists():
        expected = json.loads(golden_file.read_text(encoding="utf-8"))
        assert result == expected, (
            f"Golden test failed for Macro. Diff: expected={json.dumps(expected, indent=2)} "
            f"got={json.dumps(result, indent=2)}"
        )
    else:
        golden_file.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        pytest.skip(f"Golden file created at {golden_file}. Review and re-run.")
