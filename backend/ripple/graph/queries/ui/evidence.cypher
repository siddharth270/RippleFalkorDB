// Purpose: Known observations only, never simulator truth.
// Parameters: none. Returns: observation properties and asset_id.
// Used by: repository.scene
MATCH (o:Observation)-[:ABOUT]->(a:Asset)
WHERE o.source <> 'predicted'
RETURN a.id AS asset_id, o.property AS property, o.value AS value,
 o.source AS source, o.observed_at AS observed_at, o.id AS id
ORDER BY o.observed_at DESC
