import json
import os

from flask import Flask, abort, render_template

from kodon_py.config import default_config
from kodon_py.tei_parser import create_table_of_contents
from kodon_py.urn_utils import parse_urn


def create_app(json_dir=None, config=None, test_config=None):
    if config is None:
        config = default_config

    app = Flask(__name__, **config)

    app.config.from_mapping(
        SECRET_KEY=os.getenv("FLASK_APP_SECRET_KEY", "dev"),
        JSON_DIR=json_dir,
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

    return app


def load_passage_from_urn(urn: str, json_dir: str):
    parsed = parse_urn(urn)

    if not parsed.collection or not parsed.work_component:
        return None

    work_path = os.path.join(
        json_dir,
        parsed.text_group,
        parsed.work,
        f"{parsed.work_component}.json",
    )

    if not os.path.exists(work_path):
        return None

    with open(work_path) as f:
        work_data = json.load(f)

    if not parsed.passage_component:
        textparts_data = work_data.get("textparts", [])
        if not textparts_data:
            return None
        first = sorted(textparts_data, key=lambda t: t["index"])[0]
        parsed = parse_urn(first["urn"])

    passage = parsed.passage_component

    all_elements = work_data.get("elements", [])

    def textpart_matches(textpart_urn: str) -> bool:
        tp_passage = parse_urn(textpart_urn).passage_component
        return tp_passage == passage or tp_passage.startswith(passage + ".")

    matching = [e for e in all_elements if textpart_matches(e["textpart_urn"])]

    if not matching:
        return None

    # Group by textpart_urn, preserving order of first occurrence
    groups: dict[str, list] = {}
    for e in matching:
        groups.setdefault(e["textpart_urn"], []).append(e)

    return [
        {
            "urn": tpurn,
            "children": sorted(elements, key=lambda e: e.get("index", 0)),
        }
        for tpurn, elements in groups.items()
    ]


def load_toc_from_urn(urn: str, json_dir: str):
    parsed = parse_urn(urn)

    if not parsed.collection or not parsed.work_component:
        return None

    work_path = os.path.join(
        json_dir,
        parsed.text_group,
        parsed.work,
        f"metadata.json",
    )

    if not os.path.exists(work_path):
        return None

    data = None
    with open(work_path) as f:
        data = json.load(f)

    return data
