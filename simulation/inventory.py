"""Inventory balances and the transaction ledger (SRS section 6.2).

Closing inventory = opening + receipts + produced - consumed - issued.
Every change is recorded as a traceable transaction; negative balances are
rejected so the conservation identity can never be violated silently.
"""
from __future__ import annotations


class InventoryLedger:
    def __init__(self, initial_rows):
        self.balance = {
            (r["factory_id"], r["sku_id"]): r["quantity"] for r in initial_rows
        }
        self.transactions = []

    def get(self, factory, sku):
        return self.balance[(factory, sku)]

    def apply(self, day, factory, sku, delta, tx_type, reference):
        new_value = self.balance[(factory, sku)] + delta
        assert new_value >= 0, (
            f"negative inventory for {factory}/{sku} on day {day}: "
            f"{self.balance[(factory, sku)]} + ({delta})"
        )
        self.balance[(factory, sku)] = new_value
        self.transactions.append(dict(
            transaction_id=f"T{len(self.transactions) + 1:07}", day=day,
            factory_id=factory, sku_id=sku, quantity_delta=delta,
            transaction_type=tx_type, reference_id=reference,
        ))


def record_snapshot(day, ledger, snapshots):
    for (factory, sku), qty in ledger.balance.items():
        snapshots.append(dict(day=day, factory_id=factory, sku_id=sku, on_hand=qty))


def reconcile(initial_rows, ledger):
    """Verify that the ledger reproduces the current balances."""
    balances = {(r["factory_id"], r["sku_id"]): r["quantity"] for r in initial_rows}
    for tx in ledger.transactions:
        balances[tx["factory_id"], tx["sku_id"]] += tx["quantity_delta"]
    return balances == ledger.balance
