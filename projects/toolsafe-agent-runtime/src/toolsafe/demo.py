from __future__ import annotations

from .registry import Tool, ToolRegistry


ORDERS = {"ORD-100": {"status": "shipped", "carrier": "North Parcel", "eta_days": 2}}


def registry() -> ToolRegistry:
    return ToolRegistry([
        Tool(
            name="lookup_order",
            description="Look up shipping status for an order ID.",
            parameters={
                "type": "object",
                "properties": {"order_id": {"type": "string", "minLength": 3, "maxLength": 40}},
                "required": ["order_id"],
                "additionalProperties": False,
            },
            handler=lambda args: ORDERS.get(args["order_id"], {"status": "not_found"}),
        ),
        Tool(
            name="cancel_order",
            description="Cancel an order. This action requires human approval.",
            parameters={
                "type": "object",
                "properties": {"order_id": {"type": "string", "minLength": 3, "maxLength": 40}},
                "required": ["order_id"],
                "additionalProperties": False,
            },
            handler=lambda args: {"cancelled": args["order_id"]},
            requires_approval=True,
        ),
    ])
