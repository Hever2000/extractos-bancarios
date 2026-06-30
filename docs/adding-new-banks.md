# Cómo agregar un nuevo banco

## 1. Definir patrones de detección

Agregar una entrada en `src/detectors/bank.py`:

```python
Bank(
    id=BankId.NUEVO_BANCO,
    text_patterns=(
        re.compile(r"PATRON TEXTO", re.I),
    ),
    filename_patterns=(
        re.compile(r"patron_archivo", re.I),
    ),
    cbu_prefix="XXX",
)
```

## 2. Agregar al enum

Agregar a `BankId` en `src/models/bank.py`:

```python
class BankId(Enum):
    NUEVO_BANCO = "Banco Nuevo"
```

## 3. Agregar filtros (si son distintos de los genéricos)

En `src/cleaners/filters.py`:

```python
FILTERS[BankId.NUEVO_BANCO] = _build_skip_patterns([re.compile(r"^patron extra", re.I)])
```

## 4. Implementar parser

Crear `src/parsers/nuevo_banco.py`:

```python
import re
from src.parsers.base import RawTransaction

class NuevoBancoParser:
    def parse_lines(self, lines: list[str]) -> list[RawTransaction]:
        ...
```

## 5. Registrar en factory

En `src/parsers/factory.py`:

```python
from src.parsers.nuevo_banco import NuevoBancoParser

mapping = {
    ...
    BankId.NUEVO_BANCO: NuevoBancoParser,
}
```

## 6. Testear

- Unit tests con líneas de muestra
- Fixture de texto completo en `tests/fixtures/nuevo_banco/`
- Golden test con output esperado
