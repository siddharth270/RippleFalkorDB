// Purpose: Capture source revision and non-predicted evidence IDs at decision time.
// Parameters: none. Returns: revision, observation_ids.
// Used by: repository.decision_context
MATCH (r:StateRevision {id:'current'})
OPTIONAL MATCH (o:Observation) WHERE o.source <> 'predicted'
RETURN r.n AS revision, collect(o.id) AS observation_ids
