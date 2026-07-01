## Dataset Placeholder

The full 100K candidate dataset (`candidates.jsonl`, ~465 MB) is excluded from
version control because of its size.

### To run the ranker locally

1. Obtain `candidates.jsonl` from the Redrob hackathon portal (or your local copy).
2. Place the file at this exact path:

       polyhire-redrob/data/bharat/candidates.jsonl

3. From the repo root, run:

       python rank.py --candidates data/bharat/candidates.jsonl --out submission.csv

That's it. No environment variables, no network calls, no GPU required.

### Other files in this directory (checked into git)

| File                     | Purpose                                               |
|--------------------------|-------------------------------------------------------|
| `candidate_schema.json`  | JSON Schema definition for one candidate record       |
| `hinglish_lexicon.json`  | Hinglish → English keyword map for BharatContextualizer |
| `institution_tiers.json` | Tier-1/2/3 institution lookup for Bharat scoring      |
