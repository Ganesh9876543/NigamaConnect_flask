import matplotlib.pyplot as plt
from io import BytesIO
import base64
import networkx as nx
from matplotlib import patches
from graphviz import Digraph
from io import BytesIO
import base64

import base64
import matplotlib.pyplot as plt
import numpy as np
from io import BytesIO
import networkx as nx

def generate_family_tree(family_data):
    """
    Generate a family tree visualization using pure Python libraries without
    any Graphviz or pygraphviz dependencies.
    """
    # Create a directed graph
    G = nx.DiGraph()
    
    # Track node positions manually
    positions = {}
    
    # First pass: organize by generations
    generations = {}
    for member in family_data:
        gen = member.get('generation', 0)
        if gen not in generations:
            generations[gen] = []
        generations[gen].append(member)
    
    # Sort each generation by horizontal position (if available) or just index
    for gen in generations:
        generations[gen].sort(key=lambda x: x.get('horizontalPosition', 0))
    
    # Assign initial positions based on generations
    max_per_row = max([len(gen_members) for gen_members in generations.values()]) if generations else 0
    
    # Add nodes for each family member
    for member in family_data:
        # Add the member as a node
        member_id = member['id']
        
        # Create label
        label = f"{member['name']}"
        if member.get('relation') and member['relation'] != 'myself':
            label += f"\n{member['relation']}"
        label += f"\nGen: {member['generation']}"
        
        # Set node color based on gender
        if member['gender'] == 'male':
            color = '#ADD8E6'  # Light blue
        else:
            color = '#FFD1DC'  # Light pink
            
        # Special color for "me"
        if member.get('relation') == 'myself' or member.get('name', '').lower() == 'me':
            color = '#90EE90'  # Light green
        
        # Add node with attributes
        G.add_node(member_id, 
                  label=label, 
                  color=color, 
                  gender=member['gender'], 
                  generation=member.get('generation', 0),
                  is_member=True)
        
    # Track marriages for later edge creation
    marriages = {}
    marriage_nodes = []
    
    # Add marriage nodes
    for member in family_data:
        if member.get('spouse'):
            # Sort IDs to ensure consistent marriage node ID
            spouse_ids = sorted([member['id'], member['spouse']])
            marriage_id = f"marriage_{spouse_ids[0]}_{spouse_ids[1]}"
            
            if marriage_id not in marriages:
                marriages[marriage_id] = {
                    'id': marriage_id,
                    'partners': spouse_ids,
                    'generation': member.get('generation', 0)  # Use member's generation
                }
                
                # Add a marriage node
                G.add_node(marriage_id, 
                          label="♥", 
                          color='#FF69B4', 
                          is_marriage=True,
                          generation=member.get('generation', 0))
                
                marriage_nodes.append(marriage_id)
                
                # Connect spouses to marriage node
                G.add_edge(spouse_ids[0], marriage_id, relation='spouse', style='solid')
                G.add_edge(spouse_ids[1], marriage_id, relation='spouse', style='dotted')
    
    # Connect parents to children
    for member in family_data:
        if member.get('parentId'):
            parent = next((p for p in family_data if p['id'] == member['parentId']), None)
            
            # If parent has spouse, connect from marriage node
            if parent and parent.get('spouse'):
                spouse_ids = sorted([parent['id'], parent['spouse']])
                marriage_id = f"marriage_{spouse_ids[0]}_{spouse_ids[1]}"
                
                if marriage_id in marriages:
                    # Generate different line styles based on birth order
                    birth_order = member.get('birthOrder', 0)
                    line_styles = ["solid", "dashed", "dotted"]
                    line_style = line_styles[birth_order % len(line_styles)]
                    
                    G.add_edge(marriage_id, member['id'], 
                              relation='parent-child', 
                              style=line_style)
            else:
                # Connect directly from parent
                G.add_edge(member['parentId'], member['id'], 
                          relation='parent-child', 
                          style='solid')
    
    # Add expansion points
    for member in family_data:
        if member.get('canAddWife'):
            plus_id = f"add_wife_{member['id']}"
            G.add_node(plus_id, 
                      label="+", 
                      color='#FFD700', 
                      is_plus=True, 
                      plus_type='add-wife',
                      generation=member.get('generation', 0))
            G.add_edge(member['id'], plus_id, relation='add-wife', style='dashed')
            
        if member.get('canAddChild'):
            plus_id = f"add_child_{member['id']}"
            G.add_node(plus_id, 
                     label="+", 
                     color='#FF6347', 
                     is_plus=True, 
                     plus_type='add-child',
                     generation=member.get('generation', 0) + 1)  # Child is next generation
            G.add_edge(member['id'], plus_id, relation='add-child', style='dashed')
    
    # Try networkx layout without pygraphviz 
    try:
        # First try hierarchical layout
        pos = nx.multipartite_layout(G, subset_key='generation', align='horizontal')
        
        # Adjust positions to have more spacing
        for node, (x, y) in pos.items():
            pos[node] = (x * 5, -y * 3)  # Scale and flip y-axis
            
    except Exception:
        # Fallback to spring layout
        pos = nx.spring_layout(G, k=2.0)
    
    # Create figure with reasonable size
    plt.figure(figsize=(14, 10))
    
    # Draw nodes by type
    member_nodes = [n for n, attr in G.nodes(data=True) if attr.get('is_member', False)]
    marriage_nodes = [n for n, attr in G.nodes(data=True) if attr.get('is_marriage', False)]
    plus_nodes = [n for n, attr in G.nodes(data=True) if attr.get('is_plus', False)]
    
    # Set node sizes
    member_size = 3000  # Larger rectangles for members
    marriage_size = 500  # Medium circle for marriages
    plus_size = 300  # Small icons for plus buttons
    
    # Draw all edges first so they appear behind nodes
    edge_styles = {
        'spouse': {'color': 'black', 'width': 1.5, 'alpha': 0.7},
        'parent-child': {'color': 'blue', 'width': 2.0, 'alpha': 0.7},
        'add-wife': {'color': 'gold', 'width': 1.5, 'alpha': 0.5},
        'add-child': {'color': 'tomato', 'width': 1.5, 'alpha': 0.5}
    }
    
    # Draw edges with different styles
    for u, v, data in G.edges(data=True):
        relation = data.get('relation', 'default')
        style = data.get('style', 'solid')
        
        # Get style properties or use defaults
        edge_props = edge_styles.get(relation, {'color': 'gray', 'width': 1.0, 'alpha': 0.5})
        
        # Draw the edge
        nx.draw_networkx_edges(
            G, pos,
            edgelist=[(u, v)],
            width=edge_props['width'],
            alpha=edge_props['alpha'],
            edge_color=edge_props['color'],
            style=style,
            arrowstyle='-|>' if relation == 'parent-child' else '-',
            arrows=True if relation == 'parent-child' else False
        )
    
    # Draw member nodes (people)
    for node in member_nodes:
        x, y = pos[node]
        node_data = G.nodes[node]
        
        # Create a rectangle for the person
        rect = plt.Rectangle(
            (x - 0.15, y - 0.1),  # position
            0.3, 0.2,              # width, height
            color=node_data['color'],
            ec='black',
            lw=2,
            alpha=0.8,
            zorder=2
        )
        plt.gca().add_patch(rect)
        
        # Add label (multiline text)
        lines = node_data['label'].split('\n')
        y_offset = 0
        for line in lines:
            plt.text(
                x, y + y_offset,
                line,
                ha='center',
                va='center',
                fontsize=8,
                fontweight='bold',
                zorder=3
            )
            y_offset -= 0.04
    
    # Draw marriage nodes (hearts)
    nx.draw_networkx_nodes(
        G, pos,
        nodelist=marriage_nodes,
        node_color=['#FF69B4' for _ in marriage_nodes],
        node_size=marriage_size,
        node_shape='o',
        alpha=0.8,
        linewidths=2,
        edgecolors='black'
    )
    
    # Add heart symbols to marriage nodes
    for node in marriage_nodes:
        x, y = pos[node]
        plt.text(
            x, y,
            '♥',
            ha='center',
            va='center',
            fontsize=10,
            color='white',
            fontweight='bold'
        )
    
    # Draw plus nodes (expansion points)
    plus_colors = [G.nodes[node]['color'] for node in plus_nodes]
    nx.draw_networkx_nodes(
        G, pos,
        nodelist=plus_nodes,
        node_color=plus_colors,
        node_size=plus_size,
        node_shape='s',
        alpha=0.7,
        linewidths=2,
        edgecolors='black'
    )
    
    # Add plus symbols
    for node in plus_nodes:
        x, y = pos[node]
        plt.text(
            x, y,
            '+',
            ha='center',
            va='center',
            fontsize=10,
            color='black',
            fontweight='bold'
        )
    
    # Add title
    plt.title('Family Tree', fontsize=20, pad=20)
    
    # Add legend
    legend_elements = [
        plt.Rectangle((0, 0), 1, 1, facecolor='#ADD8E6', edgecolor='black', label='Male'),
        plt.Rectangle((0, 0), 1, 1, facecolor='#FFD1DC', edgecolor='black', label='Female'),
        plt.Rectangle((0, 0), 1, 1, facecolor='#90EE90', edgecolor='black', label='Self'),
        plt.Line2D([0], [0], color='blue', lw=2, label='Parent-Child'),
        plt.Line2D([0], [0], color='black', lw=2, label='Marriage'),
        plt.Line2D([0], [0], color='gold', linestyle='--', lw=2, label='Add Spouse'),
        plt.Line2D([0], [0], color='tomato', linestyle='--', lw=2, label='Add Child')
    ]
    plt.legend(handles=legend_elements, loc='lower right', fontsize=10)
    
    # Remove axes
    plt.axis('off')
    
    # Use tight layout
    plt.tight_layout()
    
    # Save to BytesIO buffer
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
    buffer.seek(0)
    
    # Encode to base64
    img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
    plt.close()
    
    return img_base64
