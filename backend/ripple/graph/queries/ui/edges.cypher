// Purpose: Operational topology, placement and robot routes for visualization.
// Parameters: none. Returns: source, target, type.
// Used by: repository.scene
MATCH (a)-[r]->(b) WHERE type(r) IN ['FEEDS','LOCATED_IN','ADJACENT_TO','AT','PROVIDES_SERVICE','INSPECTS']
RETURN a.id AS source, b.id AS target, type(r) AS type
