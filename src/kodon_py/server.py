import os

from flask import Flask, abort, render_template
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from kodon_py.database import Element, Textpart, alembic, db, run_migrations


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)

    default_db_path = os.path.abspath("kodon-db.sqlite")
    app.config.from_mapping(
        SECRET_KEY=os.getenv("FLASK_APP_SECRET_KEY", "dev"),
        SQLALCHEMY_ENGINES={"default": f"sqlite:///{default_db_path}"},
    )

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile("config.py", silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    db.init_app(app)
    alembic.init_app(app)
    run_migrations(app)

    @app.route("/hello")
    def hello():
        return "Hello, World!"

    @app.route("/<urn>")
    def passage(urn: str=""):
        text_containers = load_passage_from_urn(urn)

        return render_template(
            "components/ReadingEnvironment.html.jinja",
            current_passage_urn=urn,
            text_containers=text_containers,
        )

    return app


def element_to_dict(elements_by_textpart: dict, element: Element) -> dict:
    """Convert an Element to a dict structure for templates."""
    # Handle text_run elements specially - they just contain tokens
    if element.tagname == "text_run":
        return {
            "tagname": "text_run",
            "tokens": [
                {
                    "text": token.text,
                    "urn": token.urn,
                    "whitespace": token.whitespace,
                }
                for token in sorted(element.tokens, key=lambda t: t.position)
            ],
        }

    result = {
        "tagname": element.tagname,
        "urn": element.urn,
        "children": [],
    }

    if element.attributes:
        result.update(element.attributes)

    # Get all child elements (including text_runs) and sort by idx
    children = [
        e
        for e in elements_by_textpart.get(element.textpart_id, [])
        if e.parent_id == element.id
    ]
    for child in sorted(children, key=lambda e: e.idx):
        result["children"].append(element_to_dict(elements_by_textpart, child))

    return result


def load_passage_from_urn(urn: str):
    if ":" not in urn:
        abort(400)

    urn_parts = urn.rsplit(":", 1)
    document_urn = urn_parts[0]
    citation = urn_parts[1] if len(urn_parts) > 1 else ""
    citation_parts = citation.split(".") if citation else []

    if len(citation_parts) <= 1:
        urn_prefix = document_urn + ":"
    else:
        parent_citation = ".".join(citation_parts[:-1])
        urn_prefix = f"{document_urn}:{parent_citation}"

    textparts = db.session.execute(
        select(Textpart)
        .filter(Textpart.urn.startswith(urn_prefix))
        .order_by(Textpart.idx)
    ).scalars().all()

    if not textparts:
        abort(404)

    textpart_ids = [tp.id for tp in textparts]

    elements = db.session.execute(
        select(Element)
        .options(joinedload(Element.tokens))
        .filter(Element.textpart_id.in_(textpart_ids))
    ).unique().scalars().all()

    elements_by_textpart = {}
    for element in elements:
        elements_by_textpart.setdefault(element.textpart_id, []).append(element)

    text_containers = []
    for textpart in textparts:
        top_level_elements = sorted(
            [
                e
                for e in elements_by_textpart.get(textpart.id, [])
                if e.parent_id is None
            ],
            key=lambda e: e.idx,
        )
        text_containers.append(
            {
                "urn": textpart.urn,
                "children": [
                    element_to_dict(elements_by_textpart, e)
                    for e in top_level_elements
                ],
            }
        )

    return text_containers
