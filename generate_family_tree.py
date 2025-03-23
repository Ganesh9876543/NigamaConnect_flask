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

def generate_family_tree(family_data):
    # Create a Digraph object with enhanced background
    dot = Digraph(
        comment='Family Tree',
        format='png',
        engine='dot',
        graph_attr={
            'rankdir': 'TB',  # Top to bottom direction
            'splines': 'polyline',  # Use polyline for natural connections
            'bgcolor': 'white:lightgrey',  # Gradient background (white to light grey)
            'nodesep': '0.75',  # Node separation
            'ranksep': '1.0',  # Rank separation
            'fontname': 'Arial',
            'style': 'rounded,filled',  # Add rounded style to the graph000
            'color': '#4682B4',  # Steel blue border color
            'penwidth': '3.0',  # Thicker border
        },
        node_attr={
            'shape': 'box',
            'style': 'filled,rounded',
            'fillcolor': 'white',
            'penwidth': '2.0',
            'fontsize': '14',
            'fontname': 'Arial',
            'height': '0.6',
            'width': '1.6',
            'margin': '0.2'
        },
        edge_attr={
            'color': 'black',
            'penwidth': '2.0'
        }
    )

    # Add nodes for each family member with enhanced design
    for member in family_data:
        # Gender-specific colors with gradient
        if member['gender'] == 'male':
            fillcolor = '#ADD8E6:#87CEEB'  # Gradient: Light blue to sky blue
            fontcolor = '#000080'  # Navy blue
        else:
            fillcolor = '#FFD1DC:#FF9999'  # Gradient: Light pink to soft red
            fontcolor = '#8B0000'  # Dark red
        
        # Special color for "me" with gradient
        if member.get('relation') == 'myself' or member.get('name').lower() == 'me':
            fillcolor = '#90EE90:#32CD32'  # Gradient: Light green to lime green
            fontcolor = '#006400'  # Dark green
        
        # Create a stylized label with generation info
        label = f"{member['name']}"
        if member.get('relation') and member['relation'] != 'myself':
            label += f"\n{member['relation']}"
        label += f"\nGen: {member['generation']}"  # Add generation label
        
        # Add node with shadow and gradient
        dot.node(
            member['id'], 
            label=label, 
            fillcolor=fillcolor, 
            fontcolor=fontcolor,
            style='filled,rounded,shadow',  # Add shadow effect
            penwidth='2.0'
        )

    # Add marriage nodes and connections, ensuring spouses are side by side
    marriages = {}
    for member in family_data:
        if member.get('spouse'):
            # Sort the IDs to ensure a consistent marriage ID
            spouse_ids = sorted([member['id'], member['spouse']])
            marriage_id = f"marriage_{spouse_ids[0]}_{spouse_ids[1]}"
            
            if marriage_id not in marriages:
                marriages[marriage_id] = {
                    'id': marriage_id,
                    'partners': spouse_ids
                }

                # Create a subgraph to force the spouses to be side by side
                with dot.subgraph(name=f'cluster_{marriage_id}') as c:
                    c.attr(rank='same')  # Ensure both spouses are on the same rank
                    c.node(spouse_ids[0])  # Husband
                    c.node(spouse_ids[1])  # Wife

                # Create a marriage node with enhanced design
                dot.node(marriage_id, label="♥", shape="circle", width="0.25", height="0.25", 
                         color="#FF69B4", fontcolor="#FF69B4", fontsize="12", 
                         style="filled,shadow", fillcolor="#FF69B4:#FF1493")  # Gradient fill
                
                # Connect both spouses to the marriage node with gradient edges
                dot.edge(spouse_ids[0], marriage_id, color="#FF69B4:#FF1493", penwidth="2.0", 
                         arrowhead="none", style="solid")
                dot.edge(spouse_ids[1], marriage_id, color="#FF1493:#FF69B4", penwidth="2.0", 
                         arrowhead="none", style="dotted")

    # Connect parents to children with thicker, gradient, and tapered arrows
    for member in family_data:
        if member.get('parentId'):
            # If parent has a spouse, connect to marriage node
            parent = next((p for p in family_data if p['id'] == member['parentId']), None)
            
            # Generate different line styles based on birth order
            birth_order = member.get('birthOrder', 0)  # Default to 0 if birthOrder is None
            if birth_order is None:
                birth_order = 0  # Ensure a fallback value is set
            line_styles = ["solid", "dashed", "dotted"]
            line_style = line_styles[birth_order % len(line_styles)]
            
            # Generate gradient colors based on generation
            generation_colors = ["#1E90FF:#00BFFF", "#4169E1:#1E90FF", "#0000CD:#4169E1", "#00008B:#0000CD"]
            gen = member.get('generation', 0)
            line_color = generation_colors[abs(gen) % len(generation_colors)]
            
            if parent and parent.get('spouse'):
                spouse_ids = sorted([parent['id'], parent['spouse']])
                marriage_id = f"marriage_{spouse_ids[0]}_{spouse_ids[1]}"
                if marriage_id in marriages:
                    dot.edge(marriage_id, member['id'], color=line_color, penwidth="3.0",  # Thicker arrow
                             style=line_style, arrowhead="normal", arrowtail="none", 
                             arrowsize="1.2", taper="true")  # Tapered arrow
            else:
                dot.edge(member['parentId'], member['id'], color=line_color, penwidth="3.0",  # Thicker arrow
                         style=line_style, arrowhead="normal", arrowtail="none", 
                         arrowsize="1.2", taper="true")  # Tapered arrow

    # Add special symbols for expansion points with enhanced designs
    for member in family_data:
        if member.get('canAddWife'):
            plus_id = f"add_wife_{member['id']}"
            dot.node(plus_id, label="+", shape="diamond", width="0.3", height="0.3", 
                     fillcolor="#FFD700:#FFA500", style="filled,shadow", fontcolor="#000000", 
                     tooltip="Add Wife")  # Tooltip for clarity
            dot.edge(member['id'], plus_id, style="dashed", color="#FFD700", 
                     arrowhead="open", arrowsize="0.8")
            
        if member.get('canAddChild'):
            plus_id = f"add_child_{member['id']}"
            dot.node(plus_id, label="+", shape="circle", width="0.3", height="0.3", 
                     fillcolor="#FF6347:#FF4500", style="filled,shadow", fontcolor="#000000", 
                     tooltip="Add Child")  # Tooltip for clarity
            dot.edge(member['id'], plus_id, style="dashed", color="#FF6347", 
                     arrowhead="vee", arrowsize="0.8")

    # Add a title with a decorative border
    dot.attr(label=r'\nFamily Tree\n', fontsize="24", fontname="Arial Bold", 
             labelloc="t", labeljust="c", 
             style="filled", fillcolor="#F0F8FF", color="#4682B4", penwidth="2.0")

    # Add an enhanced legend for relationship types
    with dot.subgraph(name='cluster_legend') as legend:
        legend.attr(label='Legend', style='rounded,filled', fillcolor="#F5F5F5:#DCDCDC", 
                    color='gray', fontname='Georgia', fontsize='14', 
                    penwidth="2.0", margin="10")
        # Legend nodes with icons
        legend.node('marr_leg', label='♥ Marriage', shape='plaintext', fontcolor="#FF69B4")
        legend.node('child_leg', label='→ Parent-Child', shape='plaintext', fontcolor="#1E90FF")
        legend.node('spouse_leg', label='… Spouse', shape='plaintext', fontcolor="#FF1493")
        # Invisible edges to align legend items vertically
        legend.edge('marr_leg', 'child_leg', style="invis")
        legend.edge('child_leg', 'spouse_leg', style="invis")

    # Render the graph to PNG
    temp_dir = tempfile.gettempdir()
    output_path = os.path.join(temp_dir, 'family_tree')
    
    try:
        dot.render(output_path, format='png', cleanup=True)
        
        # Read the image and encode it to base64
        with open(f"{output_path}.png", 'rb') as f:
            img_data = f.read()
        img_base64 = base64.b64encode(img_data).decode('utf-8')
        
        return img_base64
    except Exception as e:
        # For debugging
        with open(f"{output_path}.dot", 'w') as f:
            f.write(dot.source)
        return f"Error: {str(e)}\nDOT file saved to {output_path}.dot for debugging"
