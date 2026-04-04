"""
KisanVaani — Neo4j Graph Database
Community Intelligence Layer
Stores: Farmer → Crop → Disease → Location relationships
"""

from neo4j import GraphDatabase
import logging
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+s://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "password")

_driver = None


def get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    return _driver


def close_driver():
    global _driver
    if _driver:
        _driver.close()
        _driver = None


# ── Schema Setup ────────────────────────────────────────────

SCHEMA_QUERIES = [
    "CREATE CONSTRAINT farmer_phone IF NOT EXISTS FOR (f:Farmer) REQUIRE f.phone IS UNIQUE",
    "CREATE CONSTRAINT location_key IF NOT EXISTS FOR (l:Location) REQUIRE l.district IS UNIQUE",
    "CREATE CONSTRAINT disease_key IF NOT EXISTS FOR (d:Disease) REQUIRE d.name IS UNIQUE",
    "CREATE CONSTRAINT crop_key IF NOT EXISTS FOR (c:Crop) REQUIRE c.name IS UNIQUE",
    "CREATE INDEX farmer_state IF NOT EXISTS FOR (f:Farmer) ON (f.state)",
    "CREATE INDEX disease_reported IF NOT EXISTS FOR ()-[r:REPORTED]-() ON (r.reported_at)",
]


def setup_schema():
    """Run once to create Neo4j constraints and indexes"""
    driver = get_driver()
    with driver.session() as session:
        for query in SCHEMA_QUERIES:
            try:
                session.run(query)
                logger.info(f"Schema: {query[:50]}...")
            except Exception as e:
                logger.warning(f"Schema query warning (may already exist): {e}")
    logger.info("Neo4j schema setup complete")


# ── Write Operations ─────────────────────────────────────────

def record_disease_report(
    phone: str,
    farmer_name: str,
    crop: str,
    disease: str,
    district: str,
    state: str,
    confidence: float = 0.75
):
    """
    Create/update graph nodes and relationships when a disease is reported.
    Pattern: (Farmer)-[:GROWS]->(Crop)-[:HAS_DISEASE]->(Disease)<-[:SPREAD_IN]-(Location)
    """
    driver = get_driver()
    now = datetime.utcnow().isoformat()

    with driver.session() as session:
        session.run("""
            MERGE (f:Farmer {phone: $phone})
            SET f.name = $farmer_name, f.state = $state, f.district = $district

            MERGE (c:Crop {name: $crop})
            MERGE (d:Disease {name: $disease})
            MERGE (l:Location {district: $district, state: $state})

            MERGE (f)-[:LOCATED_IN]->(l)
            MERGE (f)-[:GROWS]->(c)

            CREATE (f)-[:REPORTED {
                reported_at: $now,
                confidence: $confidence,
                crop: $crop
            }]->(d)

            MERGE (d)-[s:SPREAD_IN]->(l)
            ON CREATE SET s.count = 1, s.first_seen = $now, s.last_seen = $now
            ON MATCH SET s.count = s.count + 1, s.last_seen = $now
        """, phone=phone, farmer_name=farmer_name or "Unknown",
            crop=crop, disease=disease, district=district,
            state=state, now=now, confidence=confidence)

    logger.info(f"Recorded: {disease} on {crop} in {district}")


# ── Read Operations ──────────────────────────────────────────

def get_nearby_disease_spread(district: str, state: str, days_back: int = 7) -> list:
    """
    Get disease reports from nearby locations in the last N days.
    Returns: list of {disease, crop, count, severity, locations}
    """
    driver = get_driver()
    since = (datetime.utcnow() - timedelta(days=days_back)).isoformat()

    with driver.session() as session:
        result = session.run("""
            MATCH (d:Disease)<-[s:SPREAD_IN]-(l:Location)
            WHERE l.state = $state
            AND s.last_seen > $since
            OPTIONAL MATCH (d)<-[:REPORTED {district: $district}]-(:Farmer)
            WITH d.name AS disease,
                 sum(s.count) AS total_reports,
                 collect(l.district) AS affected_districts,
                 s.last_seen AS last_seen
            ORDER BY total_reports DESC
            LIMIT 5
            RETURN disease, total_reports, affected_districts, last_seen
        """, state=state, district=district, since=since)

        reports = []
        for record in result:
            count = record["total_reports"]
            severity = "low"
            if count >= 20: severity = "critical"
            elif count >= 10: severity = "high"
            elif count >= 5: severity = "medium"

            reports.append({
                "disease": record["disease"],
                "total_reports": count,
                "affected_districts": record["affected_districts"],
                "severity": severity,
                "last_seen": record["last_seen"]
            })

        return reports


def get_farmer_disease_history(phone: str) -> list:
    """Get all diseases a specific farmer has reported"""
    driver = get_driver()

    with driver.session() as session:
        result = session.run("""
            MATCH (f:Farmer {phone: $phone})-[r:REPORTED]->(d:Disease)
            RETURN d.name AS disease, r.crop AS crop,
                   r.reported_at AS reported_at, r.confidence AS confidence
            ORDER BY r.reported_at DESC
            LIMIT 10
        """, phone=phone)

        return [dict(record) for record in result]


def get_disease_spread_map(state: str) -> list:
    """Get full disease map for a state — used for demo dashboard"""
    driver = get_driver()

    with driver.session() as session:
        result = session.run("""
            MATCH (d:Disease)<-[s:SPREAD_IN]-(l:Location {state: $state})
            RETURN l.district AS district, d.name AS disease,
                   s.count AS reports, s.last_seen AS last_seen
            ORDER BY s.count DESC
        """, state=state)

        return [dict(record) for record in result]


# ── Demo Seed Data (run once for hackathon demo) ─────────────

def seed_demo_data():
    """Seed Neo4j with demo community intelligence data"""
    demo_reports = [
        ("+919876543210", "Ramesh", "tomato", "Early Blight", "Nashik", "Maharashtra"),
        ("+919111111101", "Sunil", "tomato", "Early Blight", "Nashik", "Maharashtra"),
        ("+919111111102", "Vijay", "tomato", "Early Blight", "Nashik", "Maharashtra"),
        ("+919111111103", "Anil", "tomato", "Late Blight", "Nashik", "Maharashtra"),
        ("+919111111104", "Raju", "onion", "Purple Blotch", "Nashik", "Maharashtra"),
        ("+919876543211", "Murugan", "rice", "Blast", "Coimbatore", "Tamil Nadu"),
        ("+919111111105", "Selvam", "rice", "Blast", "Coimbatore", "Tamil Nadu"),
        ("+919876543212", "Suresh", "cotton", "Pink Bollworm", "Warangal", "Telangana"),
        ("+919111111106", "Krishna", "cotton", "Pink Bollworm", "Warangal", "Telangana"),
        ("+919111111107", "Ravi", "cotton", "Whitefly", "Warangal", "Telangana"),
        ("+919876543213", "Gurpreet", "wheat", "Yellow Rust", "Ludhiana", "Punjab"),
        ("+919111111108", "Hardev", "wheat", "Yellow Rust", "Ludhiana", "Punjab"),
        ("+919111111109", "Baldev", "soybean", "Yellow Mosaic", "Indore", "Madhya Pradesh"),
        ("+919111111110", "Santosh", "soybean", "Yellow Mosaic", "Indore", "Madhya Pradesh"),
        ("+919111111111", "Mohan", "soybean", "Yellow Mosaic", "Indore", "Madhya Pradesh"),
    ]

    for report in demo_reports:
        record_disease_report(*report)

    logger.info(f"Seeded {len(demo_reports)} demo disease reports into Neo4j")


if __name__ == "__main__":
    # Run this once: python utils/neo4j_graph.py
    setup_schema()
    seed_demo_data()
    print("Neo4j setup complete!")

    # Test query
    results = get_nearby_disease_spread("Nashik", "Maharashtra")
    print(f"\nNearby diseases in Nashik: {results}")
