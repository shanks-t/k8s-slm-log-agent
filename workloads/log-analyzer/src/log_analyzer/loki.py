def build_logql_query(filters) -> str:
    """Build LogQL query from filters."""
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

    # Add log line filter if provided
    if filters.log_filter:
        query += f' |~ "{filters.log_filter}"'
    # No default filter - noise is already filtered at Alloy ingestion level
    # Alloy drops: health checks, successful access logs (200), k8s probes
    # This allows operational logs (slot updates, cancellations, etc.) to be analyzed

    return query
