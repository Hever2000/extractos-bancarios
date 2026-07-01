# Cómo agregar un nuevo banco

## 1. Agregar al enum

Agregar a `BankId` en `src/models/bank.py`:

```python
class BankId(Enum):
    NUEVO_BANCO = "Banco Nuevo"
```

## 2. Agregar patrones de detección

Registrar en `src/detectors/bank.py`:

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

Detección por scoring: texto (+30 c/u), filename (+20), prefijo CBU (+50). Umbral mínimo 30.

## 3. Verificar motor universal

El pipeline usa el **motor universal** (`src/stages/`) para TODOS los bancos. No hay parsers específicos.

Si el extracto del nuevo banco tiene estructura tabular clásica (fechas, montos, descripciones alineados), el motor universal debería procesarlo sin cambios.

### Si el motor no funciona bien:

1. **Ajustar umbrales en stages**: Los gaps de columnas (`_detect_lanes`), formato de fechas (`_classify_values`), etc. están en `src/stages/_utils.py` y `src/stages/column_detector.py`.
2. **Agregar patrones de header/footer** en `src/stages/header_detector.py` o `footer_detector.py` si el banco tiene encabezados/pies específicos.
3. **Agregar hints por banco** (a futuro): Si el motor necesita pistas sobre el layout, se pueden agregar hints configurables sin crear un parser completo.

## 4. Testear

- Unit tests para los stages que modificaste en `tests/test_stages/`
- Golden test con un PDF real del banco en `tests/samples/`

## Nota

No necesitás crear parsers, factories, filters, ni implementar `BankParser` Protocol. Esa arquitectura fue eliminada. Todo pasa por el motor universal.
