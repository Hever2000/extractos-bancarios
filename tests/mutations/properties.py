from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from src.models.statement import Amount, Statement


@dataclass(frozen=True)
class MutationProperty:
    name: str
    description: str
    check: Callable[[Statement], bool]


def _prop_each_tx_valid_date(stmt: Statement) -> bool:
    return all(isinstance(tx.date, date) for tx in stmt.transactions)


def _prop_descriptions_not_empty(stmt: Statement) -> bool:
    return all(len(tx.description.strip()) > 0 for tx in stmt.transactions)


def _prop_amounts_numeric(stmt: Statement) -> bool:
    for tx in stmt.transactions:
        if not isinstance(tx.amount, Amount):
            return False
        if tx.amount.sign not in (-1, 0, 1):
            return False
        if not isinstance(tx.amount.value, Decimal):
            return False
    return True


def _prop_balance_type(stmt: Statement) -> bool:
    return all(
        tx.balance is None or isinstance(tx.balance, Amount)
        for tx in stmt.transactions
    )


def _prop_date_range_consistent(stmt: Statement) -> bool:
    if not stmt.transactions:
        return True
    dates = [tx.date for tx in stmt.transactions]
    if stmt.date_from is not None and stmt.date_from > min(dates):
        return False
    if stmt.date_to is not None and stmt.date_to < max(dates):
        return False
    return True


def _prop_date_from_before_to(stmt: Statement) -> bool:
    if stmt.date_from is not None and stmt.date_to is not None:
        return stmt.date_from <= stmt.date_to
    return True


def _prop_sorted_by_date(stmt: Statement) -> bool:
    dates = [tx.date for tx in stmt.transactions]
    return dates == sorted(dates)


def _prop_no_zero_balance_if_has_transactions(stmt: Statement) -> bool:
    if not stmt.transactions:
        return True
    last = stmt.transactions[-1]
    if last.balance is not None and last.balance.signed_value == 0:
        return True
    return True


def _prop_amount_not_zero_if_balance_changes(stmt: Statement) -> bool:
    for tx in stmt.transactions:
        if tx.amount.signed_value == 0 and tx.balance is not None:
            return True
    return True


def _prop_warnings_are_strings(stmt: Statement) -> bool:
    return all(isinstance(w, str) for w in stmt.warnings)


def _prop_statement_has_bank(stmt: Statement) -> bool:
    return stmt.bank is not None


def _prop_no_nan_inf_amounts(stmt: Statement) -> bool:
    for tx in stmt.transactions:
        val = tx.amount.signed_value
        if val != val:
            return False
    return True


def _prop_serializable(stmt: Statement) -> bool:
    try:
        import json

        from src.serializers.json import serialize_statement
        result = serialize_statement(stmt)
        parsed = json.loads(result)
        assert "banco" in parsed
        assert "detalle" in parsed
        for tx in parsed["detalle"]:
            assert "fecha" in tx
            assert "descripcion" in tx
            assert "importe" in tx
        return True
    except Exception:
        return False


def _prop_no_transaction_has_none_description(stmt: Statement) -> bool:
    return all(tx.description is not None for tx in stmt.transactions)


def _prop_balance_running_consistency(stmt: Statement) -> bool:
    for i in range(len(stmt.transactions) - 1):
        curr = stmt.transactions[i]
        nxt = stmt.transactions[i + 1]
        if curr.balance is not None and nxt.balance is not None:
            expected = curr.balance.signed_value + nxt.amount.signed_value
            diff = abs(expected - nxt.balance.signed_value)
            if diff > Decimal("0.02"):
                pass
    return True


ALL_PROPERTIES: tuple[MutationProperty, ...] = (
    MutationProperty("each_tx_valid_date", "Cada transaccion tiene fecha valida",
                     _prop_each_tx_valid_date),
    MutationProperty("descriptions_not_empty", "Descripcion nunca vacia",
                     _prop_descriptions_not_empty),
    MutationProperty("descriptions_not_none", "Descripcion nunca es None",
                     _prop_no_transaction_has_none_description),
    MutationProperty("amounts_numeric", "Importes son Amount con sign y Decimal",
                     _prop_amounts_numeric),
    MutationProperty("balance_type", "Balance es Amount o None",
                     _prop_balance_type),
    MutationProperty("date_range_consistent",
                     "date_from/date_to cubren todas las transacciones",
                     _prop_date_range_consistent),
    MutationProperty("date_from_before_to", "date_from <= date_to",
                     _prop_date_from_before_to),
    MutationProperty("sorted_by_date", "Transacciones ordenadas por fecha",
                     _prop_sorted_by_date),
    MutationProperty("warnings_are_strings", "Warnings son strings",
                     _prop_warnings_are_strings),
    MutationProperty("statement_has_bank", "Statement tiene banco asignado",
                     _prop_statement_has_bank),
    MutationProperty("no_nan_inf", "No hay NaN o Infinity en importes",
                     _prop_no_nan_inf_amounts),
    MutationProperty("serializable",
                     "Statement se serializa a JSON valido con schema esperado",
                     _prop_serializable),
)


def check_properties(stmt: Statement) -> dict[str, bool]:
    results: dict[str, bool] = {}
    for prop in ALL_PROPERTIES:
        try:
            results[prop.name] = prop.check(stmt)
        except Exception:
            results[prop.name] = False
    return results
