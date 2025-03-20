import matplotlib.pyplot as plt
from io import BytesIO
import base64
import networkx as nx
from matplotlib import patches
from graphviz import Digraph
from io import BytesIO
import base64

import os
import tempfile
import base64
from graphviz import Digraph
import base64
import os
import tempfile
from graphviz import Digraph

import base64
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import networkx as nx
from io import BytesIO

def generate_family_tree(family_data):
    """
    Generate a family tree visualization using Matplotlib and NetworkX
    which doesn't require external Graphviz executables.
    """
    # Create a directed graph
    G = nx.DiGraph()
    
    # Marriage tracking
    marriages = {}
    
    # Add nodes for each family member
    for member in family_data:
        # Add the member as a node
        member_id = member['id']
        
        # Create label
        label = f"{member['name']}"
        if member.get('relation') and member['relation'] != 'myself':
            label += f"\n{member['relation']}"
        label += f"\nGen: {member['generation']}"
        
        # Set node attributes including colors based on gender
        if member['gender'] == 'male':
            color = '#ADD8E6'  # Light blue
        else:
            color = '#FFD1DC'  # Light pink
            
        # Special color for "me"
        if member.get('relation') == 'myself' or member.get('name', '').lower() == 'me':
            color = '#90EE90'  # Light green
            
        G.add_node(member_id, label=label, color=color, member=True, gender=member['gender'])
        
        # Track marriages
        if member.get('spouse'):
            # Sort IDs to ensure consistent marriage node ID
            spouse_ids = sorted([member['id'], member['spouse']])
            marriage_id = f"marriage_{spouse_ids[0]}_{spouse_ids[1]}"
            
            if marriage_id not in marriages:
                marriages[marriage_id] = {
                    'id': marriage_id,
                    'partners': spouse_ids
                }
                # Add the marriage node
                G.add_node(marriage_id, label="♥", color='#FF69B4', member=False, is_marriage=True)
                # Connect spouses to marriage node
                G.add_edge(spouse_ids[0], marriage_id, relation='spouse')
                G.add_edge(spouse_ids[1], marriage_id, relation='spouse')
    
    # Add parent-child relationships
    for member in family_data:
        if member.get('parentId'):
            parent = next((p for p in family_data if p['id'] == member['parentId']), None)
            
            # If parent has spouse, connect from marriage node
            if parent and parent.get('spouse'):
                spouse_ids = sorted([parent['id'], parent['spouse']])
                marriage_id = f"marriage_{spouse_ids[0]}_{spouse_ids[1]}"
                if marriage_id in marriages:
                    G.add_edge(marriage_id, member['id'], relation='parent-child')
            else:
                # Otherwise connect directly from parent
                G.add_edge(member['parentId'], member['id'], relation='parent-child')
    
    # Add expansion points
    for member in family_data:
        if member.get('canAddWife'):
            plus_id = f"add_wife_{member['id']}"
            G.add_node(plus_id, label="+", color='#FFD700', member=False, is_plus=True)
            G.add_edge(member['id'], plus_id, relation='add-wife')
            
        if member.get('canAddChild'):
            plus_id = f"add_child_{member['id']}"
            G.add_node(plus_id, label="+", color='#FF6347', member=False, is_plus=True)
            G.add_edge(member['id'], plus_id, relation='add-child')
    
    # Use hierarchical layout
    pos = nx.nx_agraph.graphviz_layout(G, prog='dot') if nx.nx_agraph.graphviz_layout else nx.spring_layout(G)
    
    # Create figure with reasonable size
    plt.figure(figsize=(12, 10))
    
    # Draw nodes
    member_nodes = [n for n, attr in G.nodes(data=True) if attr.get('member', False)]
    marriage_nodes = [n for n, attr in G.nodes(data=True) if attr.get('is_marriage', False)]
    plus_nodes = [n for n, attr in G.nodes(data=True) if attr.get('is_plus', False)]
    
    # Draw member nodes (people)
    for node in member_nodes:
        x, y = pos[node]
        gender = G.nodes[node]['gender']
        color = G.nodes[node]['color']
        label = G.nodes[node]['label']
        
        # Draw node with gender-specific shape (rectangle for all but slightly different)
        if gender == 'male':
            rect = patches.Rectangle((x-40, y-20), 80, 40, linewidth=2, edgecolor='black', facecolor=color, zorder=2)
        else:
            rect = patches.Rectangle((x-40, y-20), 80, 40, linewidth=2, edgecolor='black', facecolor=color, zorder=2, 
                                    alpha=0.8, joinstyle='round')
        plt.gca().add_patch(rect)
        
        # Add label (multiline text)
        lines = label.split('\n')
        for i, line in enumerate(lines):
            plt.text(x, y-10+i*12, line, ha='center', va='center', fontsize=8, zorder=3)
    
    # Draw marriage nodes (hearts)
    for node in marriage_nodes:
        x, y = pos[node]
        plt.scatter(x, y, s=100, color='#FF69B4', marker='o', zorder=2)
        plt.text(x, y, '♥', ha='center', va='center', fontsize=10, color='white', zorder=3)
    
    # Draw plus nodes (addition symbols)
    for node in plus_nodes:
        x, y = pos[node]
        color = G.nodes[node]['color']
        plt.scatter(x, y, s=80, color=color, marker='s', zorder=2)
        plt.text(x, y, '+', ha='center', va='center', fontsize=10, color='black', zorder=3)
    
    # Draw edges
    for u, v, attr in G.edges(data=True):
        relation = attr.get('relation', '')
        x1, y1 = pos[u]
        x2, y2 = pos[v]
        
        if relation == 'spouse':
            plt.plot([x1, x2], [y1, y2], 'k-', alpha=0.7, zorder=1)
        elif relation == 'parent-child':
            plt.plot([x1, x2], [y1, y2], 'b-', alpha=0.7, zorder=1)
        elif relation == 'add-wife':
            plt.plot([x1, x2], [y1, y2], 'g--', alpha=0.5, zorder=1)
        elif relation == 'add-child':
            plt.plot([x1, x2], [y1, y2], 'r--', alpha=0.5, zorder=1)
        else:
            plt.plot([x1, x2], [y1, y2], 'k-', alpha=0.3, zorder=1)
    
    # Add title
    plt.title('Family Tree', fontsize=16, pad=20)
    
    # Add legend
    legend_elements = [
        patches.Patch(facecolor='#ADD8E6', edgecolor='black', label='Male'),
        patches.Patch(facecolor='#FFD1DC', edgecolor='black', label='Female'),
        patches.Patch(facecolor='#90EE90', edgecolor='black', label='Self'),
        plt.Line2D([0], [0], color='blue', lw=2, label='Parent-Child'),
        plt.Line2D([0], [0], color='black', lw=2, label='Marriage'),
        plt.Line2D([0], [0], color='green', linestyle='--', lw=2, label='Add Spouse'),
        plt.Line2D([0], [0], color='red', linestyle='--', lw=2, label='Add Child')
    ]
    plt.legend(handles=legend_elements, loc='lower right')
    
    # Remove axes
    plt.axis('off')
    
    # Use tight layout
    plt.tight_layout()
    
    # Save to BytesIO buffer rather than file
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
    buffer.seek(0)
    
    # Encode to base64
    img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
    plt.close()
    
    return img_base64
