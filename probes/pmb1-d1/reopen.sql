UPDATE maintenance_control SET generation = generation + 1, state = 'open'
WHERE (SELECT COUNT(*) FROM maintenance_control) = 1
  AND typeof(singleton_id) = 'integer' AND singleton_id = 1
  AND typeof(generation) = 'integer'
  AND generation BETWEEN 1 AND 9223372036854775806
  AND typeof(state) = 'text' AND state = 'closed'
  AND typeof(:expected_generation) = 'text'
  AND CAST(generation AS TEXT) = :expected_generation;
