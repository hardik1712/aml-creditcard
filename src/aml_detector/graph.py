"""
Graph extraction and visualization module for AML detection.

Extracts local neighborhoods (subgraphs) around known fraudulent accounts
and plots them interactively using NetworkX and Plotly.
"""

import logging
import pandas as pd
import networkx as nx
import plotly.graph_objects as go
from pathlib import Path
import matplotlib.pyplot as plt

from aml_detector.config import (
    COL_NAME_ORIG, COL_NAME_DEST, COL_AMOUNT, COL_TYPE, COL_IS_FRAUD, COL_STEP
)

logger = logging.getLogger(__name__)


def extract_fraud_subgraph(df: pd.DataFrame, seed_account: str, max_hops: int = 1, max_nodes: int = 100) -> nx.DiGraph:
    """Extract a local neighborhood around a seed account.
    
    Args:
        df: The raw PaySim dataset (so we have actual account names and amounts).
        seed_account: The account name to start from.
        max_hops: How many degrees of separation to search (forward and backward).
        max_nodes: Hard limit to prevent graph explosion.
        
    Returns:
        nx.DiGraph: The extracted subgraph.
    """
    logger.info(f"Extracting subgraph for seed {seed_account} (hops={max_hops})")
    
    G = nx.DiGraph()
    current_layer = {seed_account}
    visited = set()
    
    for hop in range(max_hops):
        if not current_layer or len(G.nodes) >= max_nodes:
            break
            
        next_layer = set()
        for account in current_layer:
            if account in visited:
                continue
            visited.add(account)
            
            # Find all transactions where this account is sender
            out_tx = df[df[COL_NAME_ORIG] == account]
            for _, row in out_tx.iterrows():
                if len(G.nodes) >= max_nodes:
                    break
                dest = row[COL_NAME_DEST]
                G.add_edge(account, dest, 
                           amount=row[COL_AMOUNT], 
                           type=row[COL_TYPE],
                           is_fraud=row[COL_IS_FRAUD],
                           step=row[COL_STEP])
                next_layer.add(dest)
                
            # Find all transactions where this account is receiver
            in_tx = df[df[COL_NAME_DEST] == account]
            for _, row in in_tx.iterrows():
                if len(G.nodes) >= max_nodes:
                    break
                orig = row[COL_NAME_ORIG]
                G.add_edge(orig, account, 
                           amount=row[COL_AMOUNT], 
                           type=row[COL_TYPE],
                           is_fraud=row[COL_IS_FRAUD],
                           step=row[COL_STEP])
                next_layer.add(orig)
                
        current_layer = next_layer
        
    logger.info(f"Subgraph extracted: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges.")
    return G


def plot_interactive_network(G: nx.DiGraph, out_path: Path, title: str = "Money Laundering Subgraph"):
    """Plot an interactive network graph using Plotly and save as HTML."""
    if G.number_of_nodes() == 0:
        logger.warning("Empty graph. Nothing to plot.")
        return
        
    # Use Kamada-Kawai layout which works well for small/medium clusters
    pos = nx.kamada_kawai_layout(G)
    
    # 1. Create Edges
    edge_x = []
    edge_y = []
    edge_texts = []
    
    for u, v, data in G.edges(data=True):
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])
        
        # Hover text for the middle of the edge
        text = f"Amount: ${data['amount']:,.2f}<br>Type: {data['type']}<br>Fraud: {bool(data['is_fraud'])}"
        edge_texts.append(text)
        
    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=1.5, color='#888'),
        hoverinfo='none',
        mode='lines')
        
    # Edge hover annotations (invisible scatter points in middle of edges)
    mid_x = []
    mid_y = []
    for u, v, data in G.edges(data=True):
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        mid_x.append((x0 + x1) / 2)
        mid_y.append((y0 + y1) / 2)
        
    edge_hover_trace = go.Scatter(
        x=mid_x, y=mid_y,
        mode='markers',
        marker=dict(size=0.1, color='rgba(0,0,0,0)'),
        hoverinfo='text',
        text=edge_texts
    )

    # 2. Create Nodes
    node_x = []
    node_y = []
    node_text = []
    node_color = []
    
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        
        # Calculate degree for sizing/info
        in_deg = G.in_degree(node)
        out_deg = G.out_degree(node)
        
        # Is this node involved in any fraud edge?
        is_fraud_node = False
        for u, v, data in G.edges(node, data=True):
            if data.get('is_fraud', 0) == 1:
                is_fraud_node = True
                break
        for u, v, data in G.in_edges(node, data=True):
            if data.get('is_fraud', 0) == 1:
                is_fraud_node = True
                break
                
        # Color red if involved in fraud, else blue
        color = '#d62728' if is_fraud_node else '#1f77b4'
        node_color.append(color)
        
        text = f"Account: {node}<br>In-Degree: {in_deg}<br>Out-Degree: {out_deg}"
        if is_fraud_node:
            text += "<br><b>FLAGGED FRAUD INVOLVEMENT</b>"
        node_text.append(text)
        
    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        hoverinfo='text',
        text=node_text,
        textposition="bottom center",
        marker=dict(
            showscale=False,
            color=node_color,
            size=15,
            line_width=2))
            
    # 3. Render Figure
    fig = go.Figure(data=[edge_trace, edge_hover_trace, node_trace],
             layout=go.Layout(
                title=f'<br>{title}',
                title_font_size=16,
                showlegend=False,
                hovermode='closest',
                margin=dict(b=20,l=5,r=5,t=40),
                annotations=[dict(
                    text="Red nodes = Fraud involvement",
                    showarrow=False,
                    xref="paper", yref="paper",
                    x=0.005, y=-0.002 )],
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False))
                )
                
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(out_path))
    logger.info(f"Saved interactive graph to {out_path}")


def plot_static_network(G: nx.DiGraph, out_path: Path, title: str = "Money Laundering Subgraph"):
    """Plot a static PNG network graph using Matplotlib."""
    if G.number_of_nodes() == 0:
        return
        
    plt.figure(figsize=(10, 8))
    pos = nx.kamada_kawai_layout(G)
    
    # Identify fraud nodes
    fraud_nodes = set()
    for u, v, data in G.edges(data=True):
        if data.get('is_fraud', 0) == 1:
            fraud_nodes.add(u)
            fraud_nodes.add(v)
            
    node_colors = ['red' if n in fraud_nodes else 'blue' for n in G.nodes()]
    
    # Draw graph
    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=300, alpha=0.8)
    nx.draw_networkx_edges(G, pos, width=1.0, alpha=0.5, arrows=True, arrowsize=15)
    
    # Only draw labels for fraud nodes to avoid clutter
    labels = {n: (n[:5]+"..." if len(n)>5 else n) for n in fraud_nodes}
    nx.draw_networkx_labels(G, pos, labels, font_size=8)
    
    plt.title(title)
    plt.axis('off')
    
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()
    logger.info(f"Saved static graph to {out_path}")
