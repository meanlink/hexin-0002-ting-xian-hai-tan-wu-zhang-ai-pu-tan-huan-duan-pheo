"""Evaluate both public and lifeguard paths on the same proposed tide map."""

from collections import defaultdict, deque

from .states import RoutePriority, SegmentState

ROUTES = (
    ('access', '无障碍坡道 → 浪线观察台', 'ramp', 'lookout'),
    ('rescue', '救援站 → 湿沙掉头口', 'rescue', 'turn'),
)


def check_routes(segments, retire=None, deploy=None):
    result = []
    for purpose, label, origin, goal in ROUTES:
        graph = defaultdict(list)
        for segment in segments:
            code = segment['code']
            laid = code == deploy or (code != retire and segment['state'] == SegmentState.LAID)
            if not laid or segment['priority'] not in (purpose, RoutePriority.BOTH):
                continue
            u, v = segment['from_node'], segment['to_node']
            graph[u].append((v, code))
            graph[v].append((u, code))
        visited = {origin}
        queue = deque([(origin, ())])
        path = None
        while queue:
            current, edges = queue.popleft()
            if current == goal:
                path = list(edges)
                break
            for neighbor, code in graph[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, (*edges, code)))
        result.append({'purpose': purpose, 'label': label, 'connected': path is not None, 'segments': path or []})
    return result
