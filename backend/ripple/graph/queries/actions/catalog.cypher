// Purpose: Action catalog and declared effects for bounded candidate generation.
// Parameters: none. Returns: action_id, kind, asset_id, property, value.
// Used by: repository.action_catalog
MATCH (a:Action)-[e:AFFECTS]->(asset:Asset)
RETURN a.id AS action_id, a.kind AS kind, asset.id AS asset_id,
       e.property AS property, e.value AS value
ORDER BY a.id
