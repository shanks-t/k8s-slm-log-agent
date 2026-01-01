# Severity filtering configuration (query-time parsing)
# Maps user-facing severity levels to LogQL line filter patterns
#
# Design rationale:
# - "info": Operational logs that indicate normal system behavior
#   Includes: INFO, DEBUG, TRACE, successful operations, routine events
#   Use case: Understanding what the system is doing during normal operation
#
# - "error": Logs indicating actual problems or failures
#   Includes: ERROR, FATAL, CRITICAL, WARNING, exceptions, failures, panics, crashes
#   Use case: Troubleshooting issues, finding root causes
#
# - "all": No filtering, return everything
#   Use case: Comprehensive analysis when you don't know what you're looking for
#
# Note: Patterns use case-insensitive matching (?i) to handle variations
# Patterns match both structured JSON logs (e.g. "level": "ERROR") and plaintext logs
SEVERITY_PATTERNS = {
    "info": r'(?i)(INFO|DEBUG|TRACE|"level":\s*"(INFO|DEBUG|TRACE)"|successful|started|completed|ready)',
    "error": r'(?i)(ERROR|FATAL|CRITICAL|WARNING|"level":\s*"(ERROR|FATAL|CRITICAL|WARNING)"|EXCEPTION|failed|failure|panic|crash|killed|terminated)',
    "all": None,  # No filter applied
}


def build_logql_query(filters) -> str:
    """Build LogQL query from filters.

    Constructs a LogQL query using label matchers and line filters.
    Severity filtering is done at query-time by pattern matching log content.

    Args:
        filters: LogFilters object with namespace, pod, severity, etc.

    Returns:
        LogQL query string ready for Loki API
    """
    # Build label selector
    labels = []
    # ignore loki logs
    labels.append('container!="loki"')
    if filters.namespace:
        labels.append(f'namespace="{filters.namespace}"')
    if filters.pod:
        labels.append(f'pod=~"{filters.pod}"')  # Use regex match
    if filters.container:
        labels.append(f'container="{filters.container}"')
    if filters.node:
        labels.append(f'node="{filters.node}"')

    # Start with label matcher
    query = "{" + ",".join(labels) + "}" if labels else '{job=~".+"}'

    # Add severity line filter if provided (query-time filtering)
    if filters.severity:
        pattern = SEVERITY_PATTERNS.get(filters.severity)
        if pattern:  # Skip if severity is "all" (pattern is None)
            query += f' |~ "{pattern}"'

    # Add custom log line filter if provided
    if filters.log_filter:
        query += f' |~ "{filters.log_filter}"'
    # No default filter - noise is already filtered at Alloy ingestion level
    # Alloy drops: health checks, successful access logs (200), k8s probes
    # This allows operational logs (slot updates, cancellations, etc.) to be analyzed

    return query
