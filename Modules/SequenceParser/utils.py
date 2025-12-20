"""
SequenceParser utility functions.
"""


def find_event_clusters(events, time_threshold):
    """
    Find clusters of events within a time window.
    
    Args:
        events: List of GameEvent objects (sorted by timestamp)
        time_threshold: Max time gap between events in same cluster
    
    Returns:
        List of event clusters (lists of events)
    """
    if not events:
        return []
    
    clusters = []
    current_cluster = [events[0]]
    
    for i in range(1, len(events)):
        time_gap = events[i].timestamp - events[i - 1].timestamp
        if time_gap <= time_threshold:
            current_cluster.append(events[i])
        else:
            clusters.append(current_cluster)
            current_cluster = [events[i]]
    
    if current_cluster:
        clusters.append(current_cluster)
    
    return clusters


def filter_events_by_confidence(events, min_confidence):
    """Filter events above confidence threshold."""
    return [e for e in events if e.confidence >= min_confidence]


def filter_events_by_type(events, event_type):
    """Filter events of a specific type."""
    return [e for e in events if e.event_type == event_type]


def get_event_duration(event1, event2):
    """Get time duration between two events."""
    return abs(event2.timestamp - event1.timestamp)
