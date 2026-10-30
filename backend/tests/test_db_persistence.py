import pytest
from sqlalchemy import text
from app.core.database import SessionLocal


@pytest.fixture
def db_session():
    """Provides a transactional database session that rolls back after each test."""
    session = SessionLocal()
    transaction = session.begin()
    try:
        yield session
    finally:
        transaction.rollback()
        session.close()


def test_insert_user_and_project(db_session):
    """Verify that a user can create a project with research question and scope."""
    # 1. Insert user
    user_sql = text("""
        INSERT INTO users (email, full_name, role)
        VALUES (:email, :name, :role)
        RETURNING id, email;
    """)
    user = db_session.execute(
        user_sql,
        {"email": "researcher@example.com", "name": "Dr. Researcher", "role": "owner"}
    ).fetchone()
    assert user is not None
    user_id = user[0]

    # 2. Insert project
    project_sql = text("""
        INSERT INTO projects (name, research_question, scope, owner_id)
        VALUES (:name, :question, :scope, :owner_id)
        RETURNING id, name, research_question;
    """)
    project = db_session.execute(
        project_sql,
        {
            "name": "Supply Chain Resiliency",
            "question": "How do geopolitical disruptions affect multi-tier supply networks?",
            "scope": "2020-2026 empirical studies",
            "owner_id": user_id
        }
    ).fetchone()
    assert project is not None
    assert project[1] == "Supply Chain Resiliency"


def test_canonical_paper_curation(db_session):
    """Verify that a paper exists once in master library and can be curated into a project."""
    # 1. Insert canonical paper into master library
    paper_sql = text("""
        INSERT INTO papers (title, doi, year, authors, access_status)
        VALUES (:title, :doi, :year, :authors, :access_status)
        RETURNING id, title;
    """)
    paper = db_session.execute(
        paper_sql,
        {
            "title": "A Survey of Supply Chain Bottlenecks",
            "doi": "10.1000/182",
            "year": 2024,
            "authors": "Smith, J., & Doe, A.",
            "access_status": "metadata_only"
        }
    ).fetchone()
    assert paper is not None
    paper_id = paper[0]

    # 2. Insert project
    project_sql = text("""
        INSERT INTO projects (name)
        VALUES (:name)
        RETURNING id;
    """)
    project_id = db_session.execute(project_sql, {"name": "Disruption Analysis"}).scalar()

    # 3. Curate the canonical paper into this project
    curate_sql = text("""
        INSERT INTO project_papers (project_id, paper_id, inclusion_status, notes)
        VALUES (:p_id, :paper_id, :status, :notes)
        RETURNING id, inclusion_status;
    """)
    curation = db_session.execute(
        curate_sql,
        {
            "p_id": project_id,
            "paper_id": paper_id,
            "status": "included",
            "notes": "Highly relevant foundational survey."
        }
    ).fetchone()
    assert curation is not None
    assert curation[1] == "included"
