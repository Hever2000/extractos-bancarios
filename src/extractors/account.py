from __future__ import annotations

from src.models.document import TextBlock


def extract_account(
    header_blocks: list[tuple[TextBlock, int]],
    footer_blocks: list[tuple[TextBlock, int]],
) -> str | None:
    # Pendiente: implementar extraccion del numero de cuenta
    # El algoritmo queda pendiente hasta definir el formato real con negocio.
    # No asumir formatos ni hacer regex sin definicion funcional.
    return None
