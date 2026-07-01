import math
import jd_profile as jd

PROFICIENCY_WEIGHT = {"beginner": 0.25, "intermediate": 0.5, "advanced": 0.75, "expert": 1.0}

MUST_HAVE_SKILL_FAMILIES = {
    "embeddings_retrieval": {
        "sentence-transformers", "embeddings", "bge", "e5", "retrieval", "rag",
        "vector search", "hybrid search", "semantic search", "dense retrieval",
    },
    "vector_db": {
        "pinecone", "weaviate", "qdrant", "milvus", "opensearch",
        "elasticsearch", "faiss",
    },
    "python": {"python"},
    "evaluation": {"ndcg", "mrr", "map", "a/b testing", "evaluation framework"},
}


def structured_skill_trust(skills: list[dict]) -> float:
    family_scores = {fam: 0.0 for fam in MUST_HAVE_SKILL_FAMILIES}
    for s in skills:
        name = (s.get("name") or "").lower()
        proficiency = PROFICIENCY_WEIGHT.get(s.get("proficiency", "beginner"), 0.25)
        duration = s.get("duration_months") or 0
        endorsements = s.get("endorsements") or 0
        trust = (
            min(1.0, duration / 12)
            * (0.5 + 0.5 * proficiency)
            * min(1.0, 1 + math.log1p(endorsements) / 10)
        )
        for fam, keywords in MUST_HAVE_SKILL_FAMILIES.items():
            if any(k in name for k in keywords):
                family_scores[fam] = max(family_scores[fam], trust)
    return sum(family_scores.values()) / len(family_scores)


def skill_match_score(candidate: dict, embed_sim_fn) -> float:
    summary = candidate.get("profile", {}).get("summary", "")
    descriptions = " ".join(r.get("description", "") for r in candidate.get("career_history", [])[:3])
    embedding_similarity = embed_sim_fn(summary + " " + descriptions, jd.MUST_HAVE_CAPABILITY_STATEMENTS)
    structured_score = structured_skill_trust(candidate.get("skills", []))
    return 0.6 * embedding_similarity + 0.4 * structured_score
