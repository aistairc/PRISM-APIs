from collections import OrderedDict, defaultdict
import logging

import plotly.graph_objects as go
import pandas as pd
import numpy as np


GROUPS = OrderedDict([
    ("Phenotype", ["Disorder", "Measurement", "Entity_Property"]),
    ("Organ", ["Anatomical_entity"]),
    ("Cell", ["Cell"]),
    ("Organelle", ["Cell_component"]),
    ("Molecule", ["GGPs", "Organic_compound_other", "Inorganic_compound", "Pharmacological_substance", "Amino_acid_monomer", "MENTION"]),
    ("Unknown", [])
])

GROUP_MAPPING = { t: g for g, ts in GROUPS.items() for t in ts }
GROUP_NAMES = list(GROUPS.keys())
GROUP_INDICES = defaultdict(lambda: len(GROUP_NAMES) - 1, { k: i for i, k in enumerate(GROUP_NAMES) })
GROUP_COLORS = ["#f9c74f", "#f8961e", "#f3722c", "#90be6d", "#43aa8b", "#000000"]

logger = logging.getLogger(__name__)



def create_3d_plot(data):
    num_groups = len(GROUP_NAMES) - 1

    nodes = pd.DataFrame(data["nodes"])
    for coord in ["x", "y"]:
        vals = nodes[coord]
        nodes[coord] = (vals - vals.min()) / (vals.max() - vals.min()) * 0.9 + 0.05

    unknown_types = set(nodes["type"][nodes["type"].map(GROUP_MAPPING).isnull()])
    if unknown_types:
        logger.warning(f"Unknown types: {', '.join(unknown_types)}")
        num_groups += 1
    nodes["group_index"] = nodes["type"].map(GROUP_MAPPING).map(GROUP_INDICES)
    nodes["z"] = 1 - nodes["group_index"] / (num_groups - 1)
    edges = pd.DataFrame(data["edges"])
    edges["dummy"] = None
    for endpoint in ["source", "target"]:
        for coord in ["x", "y", "z"]:
            edges[f"{endpoint}_{coord}"] = nodes[coord][edges[endpoint]].values
    edges["label"] = nodes["name"][edges["source"]].values + " → " + nodes["name"][edges["target"]].values
    # Compute vectors
    edges["u"] = edges["target_x"] - edges["source_x"]
    edges["v"] = edges["target_y"] - edges["source_y"]
    edges["w"] = edges["target_z"] - edges["source_z"]
    # Compute unit vectors
    edges[["u", "v", "w"]] = (
        edges[["u", "v", "w"]]
        .apply(lambda vs: vs / np.linalg.norm(vs), axis=1)
        .fillna(0)
    )


    traces = []

    # Create layers
    for group_index in range(num_groups):
        traces.append(
            go.Mesh3d(
                x=[0, 1, 1, 0],
                y=[0, 0, 1, 1],
                z=[1 - group_index / (num_groups - 1)] * 4,
                color=GROUP_COLORS[group_index],
                legendgroup=GROUP_NAMES[group_index],
                opacity=0.2,
                hoverinfo="skip",
                showlegend=True,
                name=GROUP_NAMES[group_index],
            )
        )

        # Create nodes
        trace_nodes = nodes[nodes["group_index"] == group_index]
        traces.append(
            go.Scatter3d(
                x=trace_nodes["x"],
                y=trace_nodes["y"],
                z=trace_nodes["z"],
                text=trace_nodes["name"],
                legendgroup=GROUP_NAMES[group_index],
                hoverinfo="text",
                mode="markers+text",
                # mode="markers",
                showlegend=False,
                name="Node",
                marker=dict(
                    symbol="circle",
                    color="#e63946",
                    opacity=1.0,
                    sizemode="diameter",
                    size=nodes["degree"] * 2 + 20,
                    line=dict(color="#000000", width=1),
                ),
            )
        )

    # Create edges
    # This is a trick to make Plotly support different edge widths, but it could slow down the graph
    for group_name, group in edges.groupby(["size"]):
        traces.append(
            go.Scatter3d(
                x=group[["source_x", "target_x", "dummy"]].to_numpy().flatten(),
                y=group[["source_y", "target_y", "dummy"]].to_numpy().flatten(),
                z=group[["source_z", "target_z", "dummy"]].to_numpy().flatten(),
                text=group[["type", "type", "dummy"]].to_numpy().flatten(),
                hoverinfo="text",
                mode="lines",
                showlegend=True,
                name="Edge freq: " + str(group_name),
                legendgroup="Edge freq: " + str(group_name),
                line=dict(color="#495057", width=min(group_name + 1.5, 10)),
            )
        )

        # Temporarily not in use
        # traces.append(go.Cone(
        #     x=group["X_DST"],
        #     y=group["Y_DST"],
        #     z=group["Z_DST"],
        #     u=group["U"],
        #     v=group["V"],
        #     w=group["W"],
        #     text=group["LABEL"],
        #     hoverinfo="text",
        #     sizemode="absolute",
        #     anchor="tip",
        #     colorscale=[[0, "#495057"], [1, "#495057"]],
        #     sizeref=0.05,
        #     showscale=False,
        #     legendgroup="Edge freq: " + str(group_name)
        # ))

    # This is also a stupid trick to draw arrow heads and avoid internal scaling of Cone
    for _, edge in edges.iterrows():
        traces.append(
            go.Cone(
                x=[edge["target_x"]],
                y=[edge["target_y"]],
                z=[edge["target_z"]],
                u=[edge["u"]],
                v=[edge["v"]],
                w=[edge["w"]],
                text=[edge["label"]],
                hoverinfo="text",
                sizemode="absolute",
                anchor="tip",
                colorscale=[[0, "#495057"], [1, "#495057"]],
                sizeref=0.025,
                showscale=False,
                legendgroup="Edge freq: " + str(edge["size"]),
            )
        )

    axis = dict(
        showbackground=False,
        showline=False,
        zeroline=False,
        showgrid=False,
        showticklabels=False,
        showspikes=False,
        title="",
    )

    # Create layout
    layout = go.Layout(
        title="Disease Network (3D visualization)",
        height=1000,
        # width=1000,
        hovermode="closest",
        scene=dict(xaxis=axis, yaxis=axis, zaxis=axis),
    )

    return go.Figure(data=traces, layout=layout)


def create_3d_plot_html(data):
    fig = create_3d_plot(data)
    return fig.to_html()
