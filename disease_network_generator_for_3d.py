# -*- coding: utf-8 -*-
# import random

import igraph as ig
import numpy as np
import pandas as pd
import plotly.graph_objects as go

# SEED = 42

# random.seed(SEED)
# np.random.seed(SEED)

GROUP_MAPPING = {
    "Disorder": "Phenotype",
    "Measurement": "Phenotype",
    "Entity_Property": "Phenotype",
    "Anatomical_entity": "Organ",
    "Cell": "Cell",
    "Cell_component": "Organelle",
    "GGPs": "Molecule",
    "Organic_compound_other": "Molecule",
    "Inorganic_compound": "Molecule",
    "Pharmacological_substance": "Molecule",
    "Amino_acid_monomer": "Molecule",
    "MENTION": "Molecule",
}

GROUP_NAMES = {v: None for v in GROUP_MAPPING.values()}.keys()  # Keep order
GROUP_INDICES = {k: i for k, i in zip(GROUP_NAMES, reversed(range(len(GROUP_NAMES))))}
GROUP_COLORS = ["#f9c74f", "#f8961e", "#f3722c", "#90be6d", "#43aa8b"]


def get_graph_data(df):
    # Keep only edges containing entities of the selected categories
    mask = df["SRC_TYPE"].isin(GROUP_MAPPING) & df["DST_TYPE"].isin(GROUP_MAPPING)
    df = df.loc[mask]

    # Get unique nodes
    node_df = pd.DataFrame(
        data={
            "NODE_NAME": pd.concat([df["SRC_NAME"], df["DST_NAME"]]),
            "NODE_TYPE": pd.concat([df["SRC_TYPE"], df["DST_TYPE"]]),
        }
    ).drop_duplicates(ignore_index=True)

    node_index_mapping = dict(zip(node_df["NODE_NAME"], node_df.index))

    # Get unique edges and counts
    chained_assignment = pd.options.mode.chained_assignment
    pd.options.mode.chained_assignment = None
    df["SRC_NODE_INDEX"] = df["SRC_NAME"].map(node_index_mapping)
    df["DST_NODE_INDEX"] = df["DST_NAME"].map(node_index_mapping)
    pd.options.mode.chained_assignment = chained_assignment

    edge_df = (
        df[["SRC_NODE_INDEX", "DST_NODE_INDEX"]]
        .groupby(["SRC_NODE_INDEX", "DST_NODE_INDEX"], as_index=False)
        .size()
    )

    # Construct directed graph
    graph = ig.Graph(directed=True)

    graph.add_vertices(node_df.index.values)
    graph.add_edges(df[["SRC_NODE_INDEX", "DST_NODE_INDEX"]].values)

    # Create graph layout
    layout = graph.layout_fruchterman_reingold()

    # Scale node coordinates into range [0, 1]
    layout.fit_into(bbox=(0, 0, 1, 1), keep_aspect_ratio=True)

    # Get out-degree of nodes
    degrees = graph.degree(mode="out")

    # Prepare necessary information for ploting
    node_df["X"] = node_df.index.map(lambda i: layout[i][0])
    node_df["Y"] = node_df.index.map(lambda i: layout[i][1])
    node_df["Z"] = (
        node_df["NODE_TYPE"].map(GROUP_MAPPING).map(GROUP_INDICES)
        / (len(GROUP_NAMES) - 1)
        + 0.05
    )
    node_df["DEGREE"] = node_df.index.map(lambda i: degrees[i])

    edge_df["DUMMY"] = None
    edge_df = edge_df.join(node_df[["NODE_NAME", "X", "Y", "Z"]], on="SRC_NODE_INDEX")
    edge_df = edge_df.join(
        node_df[["NODE_NAME", "X", "Y", "Z"]],
        on="DST_NODE_INDEX",
        lsuffix="_SRC",
        rsuffix="_DST",
    )
    edge_df["LABEL"] = edge_df["NODE_NAME_SRC"] + " → " + edge_df["NODE_NAME_DST"]

    # Compute vectors
    edge_df["U"] = edge_df["X_DST"] - edge_df["X_SRC"]
    edge_df["V"] = edge_df["Y_DST"] - edge_df["Y_SRC"]
    edge_df["W"] = edge_df["Z_DST"] - edge_df["Z_SRC"]

    # Compute unit vectors
    edge_df[["U", "V", "W"]] = (
        edge_df[["U", "V", "W"]]
        .apply(lambda vs: vs / np.linalg.norm(vs), axis=1)
        .fillna(0)
    )

    return {"nodes": node_df, "edges": edge_df}


def save_graph(graph, output_file):
    traces = []

    # Create layers
    for group_name, group_index in GROUP_INDICES.items():
        traces.append(
            go.Mesh3d(
                x=[0, 1, 1, 0],
                y=[0, 0, 1, 1],
                z=[group_index / (len(GROUP_NAMES) - 1)] * 4,
                color=GROUP_COLORS[group_index],
                opacity=0.2,
                hoverinfo="skip",
                showlegend=True,
                name=group_name,
            )
        )

    # Create nodes
    traces.append(
        go.Scatter3d(
            x=graph["nodes"]["X"],
            y=graph["nodes"]["Y"],
            z=graph["nodes"]["Z"],
            text=graph["nodes"]["NODE_NAME"],
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
                size=graph["nodes"]["DEGREE"] * 2 + 20,
                line=dict(color="#000000", width=1),
            ),
        )
    )

    # Create edges
    # This is a trick to make Plotly support different edge widths, but it could slow down the graph
    for group_name, group in graph["edges"].groupby(["size"]):
        traces.append(
            go.Scatter3d(
                x=group[["X_SRC", "X_DST", "DUMMY"]].to_numpy().flatten(),
                y=group[["Y_SRC", "Y_DST", "DUMMY"]].to_numpy().flatten(),
                z=group[["Z_SRC", "Z_DST", "DUMMY"]].to_numpy().flatten(),
                text=group["LABEL"],
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
    for _, record in graph["edges"].iterrows():
        traces.append(
            go.Cone(
                x=[record["X_DST"]],
                y=[record["Y_DST"]],
                z=[record["Z_DST"]],
                u=[record["U"]],
                v=[record["V"]],
                w=[record["W"]],
                text=[record["LABEL"]],
                hoverinfo="text",
                sizemode="absolute",
                anchor="tip",
                colorscale=[[0, "#495057"], [1, "#495057"]],
                sizeref=0.025,
                showscale=False,
                legendgroup="Edge freq: " + str(record["size"]),
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

    fig = go.Figure(data=traces, layout=layout)

    fig.write_html(output_file)
