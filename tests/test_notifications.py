"""Tests for Aula notifications coordinator event firing."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.core import HomeAssistant

from custom_components.hass_aula.const import EVENT_NOTIFICATION
from custom_components.hass_aula.coordinator import AulaNotificationsCoordinator

from .conftest import mock_notification


async def test_first_fetch_does_not_fire_events(hass: HomeAssistant) -> None:
    """First fetch populates known IDs but fires no events."""
    client = AsyncMock()
    notification = mock_notification(notification_id="1")
    client.get_notifications_for_active_profile = AsyncMock(return_value=[notification])

    coordinator = AulaNotificationsCoordinator(hass, client, AsyncMock())
    coordinator.config_entry = MagicMock()

    fired_events = []
    hass.bus.async_listen(EVENT_NOTIFICATION, fired_events.append)

    await coordinator._async_update_data()
    await hass.async_block_till_done()

    assert len(fired_events) == 0
    assert coordinator._known_ids == {"1"}


async def test_second_fetch_same_notifications_no_events(hass: HomeAssistant) -> None:
    """Second fetch with same notifications does not fire any events."""
    client = AsyncMock()
    notification = mock_notification(notification_id="1")
    client.get_notifications_for_active_profile = AsyncMock(return_value=[notification])

    coordinator = AulaNotificationsCoordinator(hass, client, AsyncMock())
    coordinator.config_entry = MagicMock()

    fired_events = []
    hass.bus.async_listen(EVENT_NOTIFICATION, fired_events.append)

    # First fetch
    await coordinator._async_update_data()
    await hass.async_block_till_done()

    # Second fetch — same notification
    await coordinator._async_update_data()
    await hass.async_block_till_done()

    assert len(fired_events) == 0


async def test_new_notification_fires_event_with_correct_payload(
    hass: HomeAssistant,
) -> None:
    """A new notification on the second fetch fires exactly one event."""
    client = AsyncMock()
    existing = mock_notification(notification_id="1", title="Old")
    new_notif = mock_notification(
        notification_id="2",
        title="New message",
        module="messaging",
        event_type="new_message",
        related_child_name="Emma",
        created_at="2024-01-15T10:00:00",
        is_read=False,
    )

    # First fetch returns only the existing notification
    client.get_notifications_for_active_profile = AsyncMock(return_value=[existing])
    coordinator = AulaNotificationsCoordinator(hass, client, AsyncMock())
    coordinator.config_entry = MagicMock()

    fired_events = []
    hass.bus.async_listen(EVENT_NOTIFICATION, fired_events.append)

    await coordinator._async_update_data()
    await hass.async_block_till_done()

    # Second fetch returns both notifications
    client.get_notifications_for_active_profile = AsyncMock(
        return_value=[existing, new_notif]
    )
    await coordinator._async_update_data()
    await hass.async_block_till_done()

    assert len(fired_events) == 1
    data = fired_events[0].data
    assert data["notification_id"] == "2"
    assert data["title"] == "New message"
    assert data["module"] == "messaging"
    assert data["event_type"] == "new_message"
    assert data["related_child_name"] == "Emma"
    assert data["created_at"] == "2024-01-15T10:00:00"
    assert data["is_read"] is False


async def test_multiple_new_notifications_fire_separate_events(
    hass: HomeAssistant,
) -> None:
    """Multiple new notifications each fire their own event."""
    client = AsyncMock()
    existing = mock_notification(notification_id="1")
    new_a = mock_notification(notification_id="2", title="Second")
    new_b = mock_notification(notification_id="3", title="Third")

    client.get_notifications_for_active_profile = AsyncMock(return_value=[existing])
    coordinator = AulaNotificationsCoordinator(hass, client, AsyncMock())
    coordinator.config_entry = MagicMock()

    fired_events = []
    hass.bus.async_listen(EVENT_NOTIFICATION, fired_events.append)

    await coordinator._async_update_data()
    await hass.async_block_till_done()

    client.get_notifications_for_active_profile = AsyncMock(
        return_value=[existing, new_a, new_b]
    )
    await coordinator._async_update_data()
    await hass.async_block_till_done()

    assert len(fired_events) == 2
    fired_ids = {e.data["notification_id"] for e in fired_events}
    assert fired_ids == {"2", "3"}


async def test_unread_count_sensor_state(hass: HomeAssistant) -> None:
    """Coordinator data reflects the correct unread count."""
    client = AsyncMock()
    read_notif = mock_notification(notification_id="1", is_read=True)
    unread_a = mock_notification(notification_id="2", is_read=False)
    unread_b = mock_notification(notification_id="3", is_read=False)

    client.get_notifications_for_active_profile = AsyncMock(
        return_value=[read_notif, unread_a, unread_b]
    )

    coordinator = AulaNotificationsCoordinator(hass, client, AsyncMock())
    coordinator.config_entry = MagicMock()

    data = await coordinator._async_update_data()

    unread_count = sum(1 for n in data if not n.is_read)
    assert unread_count == 2
