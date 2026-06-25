"""Generate the architecture diagram as a PNG using diagram-as-code.

Renders the same high-level view as the Mermaid flowchart in the README, with
official AWS service icons and a numbered provisioning-to-runtime sequence. Run
this script to regenerate the PNG whenever the architecture changes; the output
is committed alongside the source.

This is a dev-time tool (the `diagrams` library lives in the optional `docs`
dependency group). It is not part of the runtime pipeline or the CI gate.

Usage:
    uv run --extra docs python docs/diagrams/architecture_diagram.py

Requires Graphviz on the system (the `diagrams` library shells out to `dot`).

Output:
    architecture.png, written next to this script regardless of the working
    directory the command is launched from.
"""

from __future__ import annotations

from pathlib import Path

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.analytics import EMRCluster
from diagrams.aws.management import SystemsManagerParameterStore
from diagrams.aws.security import IAM
from diagrams.aws.storage import S3
from diagrams.generic.compute import Rack
from diagrams.onprem.client import Users
from diagrams.onprem.container import Docker
from diagrams.onprem.iac import Terraform

# ─── OUTPUT LOCATION ──────────────────────────────────────────────────────────

# The diagrams library writes `filename`.png relative to the current working
# directory. Resolve an absolute path next to this script so the PNG always
# lands in docs/diagrams/ no matter where the command is launched from.
_OUTPUT = Path(__file__).resolve().parent / "architecture"

# ─── STYLING ──────────────────────────────────────────────────────────────────

# Slate palette reads as documentation. A higher ranksep gives long edges room
# so their mid-point labels clear the cluster borders (Graphviz centers an edge
# label on the edge, which can otherwise land on a box).
_SLATE = "#3B4252"
_ACCENT = "#5E81AC"

_GRAPH_ATTR = {
    "fontname": "Helvetica",
    "fontsize": "22",
    "labelloc": "t",
    "labeljust": "l",
    "fontcolor": "#4C566A",
    "splines": "spline",
    # concentrate is OFF: confirmed incompatible with EMR inside the cluster
    # (Graphviz raises "degenerate concentrated rank" when a concentrated edge
    # crosses a cluster boundary into an in-cluster target).
    "nodesep": "0.6",
    "ranksep": "2.2",
    "pad": "0.6",
    "bgcolor": "#ECEFF4",
}

_CLUSTER_ATTR = {
    "fontname": "Helvetica-Bold",
    "fontsize": "13",
    "margin": "18",
    "penwidth": "1.2",
    "pencolor": "#B0B7C3",
    "bgcolor": "#FBFCFD",
    "fontcolor": "#2E3440",
}

_NODE_ATTR = {"fontname": "Helvetica", "fontsize": "11"}
_EDGE_ATTR = {
    "fontname": "Helvetica",
    "fontsize": "11",
    "color": _SLATE,
    "fontcolor": "#2E3440",
}


def step(n: int, text: str) -> str:
    """Prefix an edge label with a bracketed step number for sequence reading."""
    return f"  [{n}] {text}  "


# ─── DIAGRAM ──────────────────────────────────────────────────────────────────

with Diagram(
    "IMDB Sentiment Pipeline | PySpark on Amazon EMR",
    filename=str(_OUTPUT),
    direction="LR",
    show=False,
    graph_attr=_GRAPH_ATTR,
    node_attr=_NODE_ATTR,
    edge_attr=_EDGE_ATTR,
):
    # External dataset wrapped in its own cluster so the label stays legible on
    # any theme (a bare node's caption would vanish on a dark background).
    with Cluster("EXTERNAL", graph_attr=_CLUSTER_ATTR):
        imdb = Rack("IMDB dataset\n50k reviews")

    with Cluster("LOCAL | DEV", graph_attr=_CLUSTER_ATTR):
        dev = Users("Developer")
        dock = Docker("Dev Container")
        tf = Terraform("Terraform")
        # The container is the environment Terraform and the AWS CLI run inside.
        dock >> Edge(color=_ACCENT, label=step(3, "apply")) >> tf

    with Cluster("AWS (eu-west-1)", graph_attr=_CLUSTER_ATTR):
        with Cluster("S3", graph_attr=_CLUSTER_ATTR):
            state_bucket = S3("State\nbucket")
            app_bucket = S3("Project\nbucket")
            state_bucket - Edge(style="invis") - app_bucket

        with Cluster("IAM | SSM", graph_attr=_CLUSTER_ATTR):
            iam = IAM("Roles")
            ssm = SystemsManagerParameterStore("Config")
            iam - Edge(style="invis") - ssm

        emr = EMRCluster("EMR 7.13\nephemeral")

    # Provisioning sequence (accent color, numbered).
    imdb >> Edge(color=_ACCENT, label=step(1, "download")) >> dev
    dev >> Edge(color=_ACCENT, label=step(2, "compose up")) >> dock
    tf >> Edge(color=_ACCENT, label=step(4, "bootstrap")) >> state_bucket
    # \n prefix drops this label below the edge so it clears the cluster border.
    tf >> Edge(color=_ACCENT, label="\n\n[5] data-platform") >> app_bucket
    tf >> Edge(color=_ACCENT) >> iam
    tf >> Edge(color=_ACCENT, label=step(6, "provision")) >> emr

    # Runtime sequence (slate; dashed = scripts, dotted = config feed).
    app_bucket >> Edge(label=step(7, "raw CSV")) >> emr
    app_bucket >> Edge(style="dashed", label=step(8, "scripts")) >> emr
    iam >> Edge(style="dotted") >> emr
    ssm >> Edge(style="dotted") >> emr
    emr >> Edge(label=step(9, "features + models + logs")) >> app_bucket
