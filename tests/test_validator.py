from core.domain.diagram_ir import Actor, Relationship, SystemScope, UseCase, UseCaseIR
from core.domain.validator import validate_use_case_ir
from core.domain.normalizer import normalize_use_case_payload
from core.domain.diagram_factory import parse_diagram
from core.adapters.model import parse_json_object


def test_validator_rejects_missing_relationship_reference():
    result = validate_use_case_ir(
        UseCaseIR(
            title="Shop",
            actors=[Actor(id="customer", name="Customer")],
            use_cases=[UseCase(id="checkout", name="Checkout")],
            relationships=[
                Relationship(type="association", source="customer", target="missing")
            ],
        )
    )
    assert not result.valid
    assert result.diagnostics[0].code == "missing_node_reference"


def test_normalizer_accepts_common_model_aliases():
    normalized = normalize_use_case_payload(
        {
            "type": "UseCaseIR",
            "title": "Shop",
            "actors": [],
            "use_cases": [],
            "relationships": [
                {"type": "associates", "source": "customer", "target": "checkout"}
            ],
            "assumptions": ["Users must log in."],
        }
    )
    assert normalized["type"] == "use_case"
    assert normalized["relationships"][0]["type"] == "association"
    assert normalized["assumptions"][0]["text"] == "Users must log in."
    assert normalized["scopes"] == [{"id": "system", "name": "Shop"}]


def test_validator_rejects_missing_scope_reference():
    result = validate_use_case_ir(
        UseCaseIR(
            title="Shop",
            scopes=[SystemScope(id="storefront", name="Storefront")],
            use_cases=[UseCase(id="checkout", name="Checkout", scope_id="missing")],
        )
    )
    assert not result.valid
    assert result.diagnostics[0].code == "missing_scope_reference"


def test_normalizer_assigns_use_cases_to_first_scope():
    normalized = normalize_use_case_payload(
        {
            "title": "Shop",
            "actors": [],
            "scopes": [{"id": "storefront", "name": "Storefront"}],
            "use_cases": ["Checkout"],
            "relationships": [],
        }
    )
    assert normalized["use_cases"][0]["scope_id"] == "storefront"


def test_sequence_parser_normalizes_message_id_fragment_references():
    diagram = parse_diagram(
        "sequence",
        {
            "title": "Checkout",
            "participants": [{"id": "user", "name": "User", "kind": "actor"}],
            "messages": [
                {"label": "step 1", "source": "user", "target": "user", "type": "self"}
                for _ in range(18)
            ],
            "fragments": [
                {
                    "id": "loop_1",
                    "operator": "loop",
                    "message_start": "msg_14",
                    "message_end": "msg_17",
                }
            ],
        },
    )
    assert diagram.fragments[0].message_start == 14
    assert diagram.fragments[0].message_end == 17


def test_state_machine_parser_normalizes_label_to_name():
    diagram = parse_diagram(
        "state_machine",
        {
            "title": "Checkout",
            "states": [
                {"id": "initial", "type": "initial", "label": "Bắt đầu"},
                {
                    "id": "cart",
                    "type": "state",
                    "label": "Giỏ hàng",
                    "entry": "openCart()",
                },
                {"id": "final", "type": "final", "label": "Kết thúc"},
            ],
            "transitions": [
                {"source": "initial", "target": "cart", "event": "start"},
                {"source": "cart", "target": "final", "event": "checkout"},
            ],
        },
    )
    assert diagram.states[1].name == "Giỏ hàng"
    assert diagram.states[1].entry_action == "openCart()"


def test_model_parser_accepts_wrapped_json_object():
    parsed = parse_json_object(
        '<think>internal reasoning</think>\n```json\n{"type": "state_machine"}\n```'
    )
    assert parsed == {"type": "state_machine"}
