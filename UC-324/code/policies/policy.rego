# UC-324 — Rego policies for AGT governance example
package uc324.containment

import future.keywords.if
import future.keywords.in

# Default deny
default allow := false

# Roles allowed to execute high-impact actions
payment_roles := {"payment_processor", "payment.charge", "admin"}
trading_roles := {"trader", "market.order.send", "admin"}

allow if {
    input.skill.domain == "reservations"
    input.skill.name == "PaymentSkill"
    some role in input.roles
    role in payment_roles
    input.domain_state.availability_confirmed == true
    input.domain_state.user_consent == true
}

allow if {
    input.skill.domain == "trading"
    input.skill.name == "MarketExecutionSkill"
    some role in input.roles
    role in trading_roles
    input.domain_state.risk_approved == true
    input.domain_state.circuit_breaker_open == true
}

# Read-only skills are generally allowed
default_read_actions := {"MarketDataSkill", "MarketPredictionSkill", "FinancialRiskSkill", "FlightBookingSkill", "RailBookingSkill", "NotificationSkill"}

allow if {
    input.skill.name in default_read_actions
    input.skill.action_class in {"read", "predict", "analyze"}
}

# Identity validation allowed only when user_id present
allow if {
    input.skill.name == "IdentityValidationSkill"
    input.inputs.user_id != ""
}

# Block jailbreak / prompt injection markers
deny_reasons contains "jailbreak marker detected" if {
    some marker in ["ignore previous instructions", "DAN mode", "sudo", "system override"]
    contains(lower(json.marshal(input.inputs)), marker)
}

allow := false if {
    count(deny_reasons) > 0
}
