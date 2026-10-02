from infrastructure.messaging.event_bus import EventBus


def test_event_flow_end_to_end():
    bus = EventBus()
    result = []

    bus.subscribe("detection", lambda e: result.append(e))
    bus.publish("detection", {"level": "HIGH"})

    assert result == [{"level": "HIGH"}]
