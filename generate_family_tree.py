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
from PIL import Image,  ImageDraw
import requests
from io import BytesIO
import pathlib

def build_family_graph(family_data):
    """Build a directed graph representing family relationships."""
    # Create a graph where nodes are family members and edges represent relationships
    graph = {}
    for member in family_data:
        member_id = member['id']
        if member_id not in graph:
            graph[member_id] = {"member": member, "relations": {}}
        
        # Add parent-child relationships
        if member.get('parentId'):
            parent_id = member['parentId']
            if parent_id not in graph:
                graph[parent_id] = {"member": next((m for m in family_data if m['id'] == parent_id), None), "relations": {}}
            
            # Add bidirectional relationships
            graph[member_id]["relations"][parent_id] = "parent"
            graph[parent_id]["relations"][member_id] = "child"
        
        # Add spouse relationships
        if member.get('spouse'):
            spouse_id = member['spouse']
            if spouse_id not in graph:
                graph[spouse_id] = {"member": next((m for m in family_data if m['id'] == spouse_id), None), "relations": {}}
            
            # Add bidirectional relationships
            graph[member_id]["relations"][spouse_id] = "spouse"
            graph[spouse_id]["relations"][member_id] = "spouse"
    
    return graph

def find_shortest_path(graph, start, end, max_depth=10):
    """Find shortest path between two members in the family graph."""
    if start == end:
        return []
    
    visited = {start}
    queue = [(start, [])]
    
    while queue and max_depth > 0:
        current, path = queue.pop(0)
        max_depth -= 1
        
        for neighbor, relation_type in graph[current]["relations"].items():
            if neighbor == end:
                return path + [(current, neighbor, relation_type)]
            
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [(current, neighbor, relation_type)]))
    
    return None  # No path found

def determine_relationship(path, graph, self_id):
    """Determine the relationship based on path between self and another member."""
    if not path:
        return "Myself"
    
    # Extract relevant information
    path_relations = [rel for _, _, rel in path]
    target_id = path[-1][1]
    target_gender = graph[target_id]["member"]["gender"]
    gender_suffix = "mother" if target_gender == "female" else "father"
    
    # Simple direct relationships
    if len(path) == 1:
        relation_type = path[0][2]
        
        if relation_type == "spouse":
            return "Wife" if target_gender == "female" else "Husband"
        
        if relation_type == "parent":
            return "Mother" if target_gender == "female" else "Father"
            
        if relation_type == "child":
            return "Daughter" if target_gender == "female" else "Son"
            
    # Extended relationships
    if len(path) == 2:
        if path_relations == ["parent", "parent"]:
            return "Grand" + gender_suffix
            
        if path_relations == ["child", "child"]:
            return "Grand" + ("daughter" if target_gender == "female" else "son")
            
        if path_relations == ["parent", "child"] and path[0][1] != path[1][0]:
            return "Sister" if target_gender == "female" else "Brother"
            
        if path_relations == ["spouse", "parent"]:
            return "Mother-in-law" if target_gender == "female" else "Father-in-law"
            
        if path_relations == ["parent", "spouse"]:
            return "Daughter-in-law" if target_gender == "female" else "Son-in-law"
    
    # More distant relationships
    if len(path) == 3:
        if path_relations == ["parent", "parent", "parent"]:
            return "Great-grand" + gender_suffix
            
        if path_relations == ["child", "child", "child"]:
            return "Great-grand" + ("daughter" if target_gender == "female" else "son")
            
        if path_relations == ["parent", "child", "spouse"]:
            return "Sister-in-law" if target_gender == "female" else "Brother-in-law"
            
        if path_relations[0:2] == ["parent", "parent"] and path_relations[2] == "child":
            return "Aunt" if target_gender == "female" else "Uncle"
            
        if path_relations[0:2] == ["parent", "child"] and path_relations[2] == "child":
            return "Niece" if target_gender == "female" else "Nephew"
    
    # Determine cousin relationships
    if "parent" in path_relations and "child" in path_relations:
        # Count generations up to common ancestor and down from common ancestor
        up_count = 0
        down_count = 0
        going_up = True
        
        for rel in path_relations:
            if rel == "parent":
                if going_up:
                    up_count += 1
                else:
                    down_count += 1
            elif rel == "child":
                going_up = False
                down_count += 1
        
        if up_count > 0 and down_count > 0:
            if up_count == 1 and down_count == 1:
                return "Cousin" if target_gender == "female" else "Cousin"
            else:
                ordinals = ["first", "second", "third", "fourth", "fifth"]
                removal = abs(up_count - down_count)
                degree = min(up_count, down_count) - 1
                
                if degree < len(ordinals):
                    degree_text = ordinals[degree]
                    if removal == 0:
                        return f"{degree_text} Cousin"
                    else:
                        return f"{degree_text} Cousin {removal} times removed"
    
    return "Relative"

def calculate_relation(member, self_id, family_data):
    """Calculate the relation of a member to the self person based on the tree structure."""
    if member['id'] == self_id:
        return "Myself"
    
    # Build family graph
    graph = build_family_graph(family_data)
    
    # Find shortest path from self to member
    path = find_shortest_path(graph, self_id, member['id'])
    
    # Determine relationship based on path
    relationship = determine_relationship(path, graph, self_id)
    
    return relationship

def create_profile_image_node(profile_image, member_id):
    """Create a temporary profile image file from base64 data or use default icon."""
    temp_dir = tempfile.gettempdir()
    image_path = os.path.abspath(os.path.join(temp_dir, f'profile_{member_id}.png'))
    
    try:
        if profile_image and profile_image.startswith('data:image'):
            # Extract the base64 data
            base64_data = profile_image.split(',')[1]
            image_data = base64.b64decode(base64_data)
            
            # Convert to PNG and save
            img = Image.open(BytesIO(image_data))
            img = img.convert('RGBA')
            # Resize to a reasonable size (e.g., 100x100)
            img = img.resize((100, 100), Image.Resampling.LANCZOS)
            img.save(image_path, 'PNG')
        else:
            # Create a simple profile icon using PIL
            img = Image.new('RGBA', (100, 100), (255, 255, 255, 0))
            draw = ImageDraw.Draw(img)
            # Draw a circle for the head
            draw.ellipse([25, 25, 75, 75], fill=(204, 204, 204, 255))
            # Draw a path for the body
            draw.polygon([(50, 70), (30, 100), (70, 100)], fill=(204, 204, 204, 255))
            img.save(image_path, 'PNG')
    except Exception as e:
        print(f"Error creating profile image: {e}")
        return None
    
    return image_path

def generate_family_tree(family_data):
    # Find the self person
    self_person = next((m for m in family_data if m.get('isSelf')), None)
    if not self_person:
        return "Error: No self person found in the family data"
    
    self_id = self_person['id']
    
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
            'style': 'rounded,filled',  # Add rounded style to the graph
            'color': '#000000',  # Black border color
            'penwidth': '3.0',  # Thicker border
        },
        node_attr={
            'shape': 'box',
            'style': 'filled,rounded',
            'fillcolor': 'white',
            'fontcolor': 'black',  # Black text for all nodes
            'penwidth': '2.0',
            'fontsize': '14',
            'fontname': 'Arial',
            'height': '0.6',
            'width': '1.6',
            'margin': '0.2'
        },
        edge_attr={
            'color': '#000000',  # Black color for all edges
            'penwidth': '3.0'  # Thicker edges
        }
    )

    # Add nodes for each family member with enhanced design
    for member in family_data:
        # Default styling - white background, black text
        fillcolor = 'white'
        fontcolor = 'black'
        
        # Special color for "self" node only - black background
        if member['id'] == self_id:
            fillcolor = 'black'
            fontcolor = 'white'  # White text for readability on black background
        
        # Create profile image node
        profile_image_path = create_profile_image_node(member.get('profileImage'), member['id'])
        
        # Create a stylized label with name, relation, and generation
        label = f"<<TABLE BORDER='0' CELLBORDER='1' CELLSPACING='0' CELLPADDING='4'>"
        if profile_image_path:
            # Convert Windows path to forward slashes for Graphviz
            image_path = profile_image_path.replace('\\\\', '/')
            label += f"<TR><TD ROWSPAN='2'><IMG SRC='{image_path}' SCALE='TRUE' FIXEDSIZE='TRUE' WIDTH='50' HEIGHT='50'/></TD>"
        else:
            label += "<TR><TD ROWSPAN='2'>👤</TD>"
        
        label += f"<TD ALIGN='LEFT'><B>{member['name']}</B></TD></TR>"
        
        # Add relation information from the family members data
        if member.get('relation'):
            label += f"<TR><TD ALIGN='LEFT'>{member['relation']}</TD></TR>"
        else:
            label += f"<TR><TD ALIGN='LEFT'>Relative</TD></TR>"
            
        label += f"<TR><TD COLSPAN='2' ALIGN='LEFT'>Gen: {member['generation']}</TD></TR>"
        label += "</TABLE>>"
         
        # Add node with proper styling
        dot.node(
            member['id'], 
            label=label,
            fillcolor=fillcolor, 
            fontcolor=fontcolor,
            style='filled,rounded',
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
                    c.node(spouse_ids[0])  # First spouse
                    c.node(spouse_ids[1])  # Second spouse

                # Create a marriage node with enhanced design
                dot.node(marriage_id, label="*", shape="circle", width="0.25", height="0.25", 
                         color="#000000", fontcolor="#000000", fontsize="12", 
                         style="filled", fillcolor="#FF69B4:#FF1493")
                
                # Connect both spouses to the marriage node with solid black edges
                dot.edge(spouse_ids[0], marriage_id, color="#000000", penwidth="3.0", 
                         arrowhead="none", style="solid")
                dot.edge(spouse_ids[1], marriage_id, color="#000000", penwidth="3.0", 
                         arrowhead="none", style="solid")

    # Connect parents to children with thick black arrows
    for member in family_data:
        if member.get('parentId'):
            # If parent has a spouse, connect to marriage node
            parent = next((p for p in family_data if p['id'] == member['parentId']), None)
            
            if parent and parent.get('spouse'):
                spouse_ids = sorted([parent['id'], parent['spouse']])
                marriage_id = f"marriage_{spouse_ids[0]}_{spouse_ids[1]}"
                if marriage_id in marriages:
                    dot.edge(marriage_id, member['id'], color="#000000", penwidth="3.0",
                             style="solid", arrowhead="normal", arrowtail="none", 
                             arrowsize="1.2", taper="true")
            else:
                dot.edge(member['parentId'], member['id'], color="#000000", penwidth="3.0",
                         style="solid", arrowhead="normal", arrowtail="none", 
                         arrowsize="1.2", taper="true")

    # Add special symbols for expansion points with enhanced designs
    for member in family_data:
        if member.get('canAddWife'):
            plus_id = f"add_wife_{member['id']}"
            dot.node(plus_id, label="+", shape="diamond", width="0.3", height="0.3", 
                     fillcolor="#FFD700:#FFA500", style="filled", fontcolor="#000000", 
                     tooltip="Add Wife")  # Removed shadow style
            dot.edge(member['id'], plus_id, style="solid", color="#000000", penwidth="3.0", 
                     arrowhead="open", arrowsize="0.8")
            
        if member.get('canAddChild'):
            plus_id = f"add_child_{member['id']}"
            dot.node(plus_id, label="+", shape="circle", width="0.3", height="0.3", 
                     fillcolor="#FF6347:#FF4500", style="filled", fontcolor="#000000", 
                     tooltip="Add Child")  # Removed shadow style
            dot.edge(member['id'], plus_id, style="solid", color="#000000", penwidth="3.0", 
                     arrowhead="vee", arrowsize="0.8")
                
 
    # Add a title with a decorative border
    dot.attr(label=r'\nFamily Tree\n', fontsize="24", fontname="Arial Bold", 
             labelloc="t", labeljust="c", 
             style="filled", fillcolor="#F0F8FF", color="#000000", penwidth="3.0")

    # Render the graph to PNG
    temp_dir = tempfile.gettempdir()
    output_path = os.path.abspath(os.path.join(temp_dir, 'family_tree'))
    
    try:
        # Create the output directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Render the graph
        dot.render(output_path, format='png', cleanup=True)
        
        # Read the image and encode it to base64
        with open(f"{output_path}.png", 'rb') as f:
            img_data = f.read()
        img_base64 = base64.b64encode(img_data).decode('utf-8')
        
        # Clean up temporary profile images
        for member in family_data:
            temp_image = os.path.join(temp_dir, f'profile_{member["id"]}.png')
            if os.path.exists(temp_image):
                try:
                    os.remove(temp_image)
                except:
                    pass
        
        return img_base64
    except Exception as e:
        # For debugging
        with open(f"{output_path}.dot", 'w', encoding='utf-8') as f:
            f.write(dot.source)
        return f"Error: {str(e)}\nDOT file saved to {output_path}.dot for debugging"
