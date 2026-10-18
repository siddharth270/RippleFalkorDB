// Purpose: Known-world graph nodes for the demo, excluding historical observations.
// Parameters: none. Returns: id, labels, properties.
// Used by: repository.scene
MATCH (n) WHERE n:Asset OR n:Location OR n:Robot OR n:Service OR n:InspectionPoint
RETURN n.id AS id, labels(n) AS labels, properties(n) AS properties
