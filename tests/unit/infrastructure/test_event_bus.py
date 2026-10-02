from infrastructure.messaging.event_bus import EventBus


def test_event_bus_publish_subscribe():
    bus = EventBus()
    result = []

    def handler(payload):
        result.append(payload)

    bus.subscribe("test", handler)
    bus.publish("test", {"ok": True})

    assert result == [{"ok": True}]
