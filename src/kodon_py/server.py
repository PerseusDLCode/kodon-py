import json
import os
from pathlib import Path

from flask import Flask
from lxml import etree

from kodon_py.config import default_config
from kodon_py.tei_parser import TEIParser
from kodon_py.urn_utils import parse_urn


def create_app(fragment_dir=None, config=None, test_config=None):
    if config is None:
        config = default_config

    app = Flask(__name__, **config)

    app.config.from_mapping(
        SECRET_KEY=os.getenv("FLASK_APP_SECRET_KEY", "dev"),
        FRAGMENT_DIR=fragment_dir,
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


def _chunk_dir_for_urn(urn: str, fragment_dir: str | Path):
    parsed = parse_urn(urn)

    if not parsed.collection or not parsed.work_component:
        return None, None

    chunk_dir = (
        Path(fragment_dir)
        / str(parsed.text_group)
        / str(parsed.work)
        / str(parsed.work_component)
    )

    return parsed, chunk_dir


def _flatten_leaves(nodes: list[dict]) -> list[dict]:
    leaves = []

    for node in nodes:
        if "path" in node:
            leaves.append(node)
        elif "subpassages" in node:
            leaves.extend(_flatten_leaves(node["subpassages"]))

    return leaves


def load_passage_from_urn(urn: str, fragment_dir: str | Path):
    parsed, chunk_dir = _chunk_dir_for_urn(urn, fragment_dir)

    if parsed is None:
        return None

    metadata_path = chunk_dir / "metadata.json"

    if not metadata_path.exists():
        return None

    with open(metadata_path) as f:
        metadata = json.load(f)

    leaves = _flatten_leaves(metadata.get("table_of_contents", []))

    if not leaves:
        return None

    if parsed.passage_component:
        leaf = next((leaf for leaf in leaves if leaf["urn"] == urn), None)

        if leaf is None:
            return None
    else:
        leaf = leaves[0]

    chunk_path = chunk_dir / leaf["path"]

    if not chunk_path.exists():
        return None

    chunk_root = etree.parse(str(chunk_path)).getroot()
    content_el = chunk_root.find("elements")

    if content_el is None:
        return None

    base_urn = chunk_root.get("base_urn", "")
    unit = chunk_root.get("unit", "")
    cts_urn = chunk_root.get("cts_urn", "")
    prev_urn = chunk_root.get("prev_urn")
    next_urn = chunk_root.get("next_urn")

    parser = TEIParser(content_el, base_urn, unit)
    children = parser.elements[0]["children"] if parser.elements else []

    return {
        "text_containers": [
            {"urn": cts_urn, "children": children},
        ],
        "previous": prev_urn,
        "next": next_urn,
    }


def load_toc_from_urn(urn: str, fragment_dir: str):
    parsed, chunk_dir = _chunk_dir_for_urn(urn, fragment_dir)

    if parsed is None:
        return None

    metadata_path = chunk_dir / "metadata.json"

    if not metadata_path.exists():
        return None

    with open(metadata_path) as f:
        return json.load(f)
