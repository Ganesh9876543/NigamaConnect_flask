import tempfile
import os
import base64
import io
from graphviz import Digraph
from PIL import Image, ImageDraw

def generate_relatives_tree(relatives_data):
    """
    Generate a tree visualization for relatives data
    
    Args:
        relatives_data (dict): Dictionary containing relatives data
        
    Returns:
        str: Base64 encoded image of the relatives tree
    """
    # Convert dictionary to list of relatives if needed
    if isinstance(relatives_data, dict):
        relatives_list = []
        for id, person in relatives_data.items():
            person_data = dict(person)
            person_data['id'] = id
            relatives_list.append(person_data)
    else:
        relatives_list = relatives_data
    
    # Find the self person
    self_person = next((m for m in relatives_list if m.get('isSelf') == True), None)
    if not self_person:
        return "Error: No self person found in the relatives data"
    
    self_id = self_person['id']
    
    # Create a Digraph object with enhanced background
    dot = Digraph(
        comment='Relatives Tree',
        format='png',
        engine='dot',
        graph_attr={
            'rankdir': 'TB',  # Top to bottom direction
            'splines': 'polyline',  # Use polyline for natural connections
            'bgcolor': '#FFFFFF',  # Pure white background
            'nodesep': '1.4',  # Further increased node separation
            'ranksep': '2.0',  # Further increased rank separation
            'fontname': 'Arial',
            'style': 'rounded',  # Remove filled style from graph
            'color': '#000000',  # Black border color
            'penwidth': '2.0',  # Thinner border for cleaner look
        },
        node_attr={
            'shape': 'box',
            'style': 'filled,rounded',
            'fillcolor': 'white',
            'fontcolor': 'black',  # Black text for all nodes
            'penwidth': '1.5',  # Thinner borders for nodes
            'fontsize': '22',  # Base font size
            'fontname': 'Arial',
            'height': '1.2',  # Further increased height
            'width': '2.8',  # Further increased width
            'margin': '0.5'  # Further increased margin
        },
        edge_attr={
            'color': '#444444',  # Darker gray color for better visibility
            'penwidth': '4.0'  # Significantly increased edge thickness
        }
    )

    def create_profile_image_node(profile_image, member_id):
        """Create a temporary profile image file from URL, base64 data, or use default icon."""
        temp_dir = tempfile.gettempdir()
        image_path = os.path.abspath(os.path.join(temp_dir, f'profile_{member_id}.png'))
        
        try:
            if profile_image and isinstance(profile_image, str):
                if profile_image.startswith('data:image/'):
                    try:
                        header, encoded = profile_image.split(',', 1)
                        img_data = base64.b64decode(encoded)
                        img = Image.open(io.BytesIO(img_data))
                        img = img.resize((100, 100))
                        img.save(image_path, 'PNG')
                        return image_path
                    except Exception as e:
                        print(f"Error processing base64 image: {e}")
                elif profile_image.startswith('http'):
                    img = Image.new('RGBA', (100, 100), (255, 255, 255, 0))
                    draw = ImageDraw.Draw(img)
                    draw.ellipse([25, 25, 75, 75], fill=(204, 204, 204, 255))
                    draw.polygon([(50, 70), (30, 100), (70, 100)], fill=(204, 204, 204, 255))
                    img.save(image_path, 'PNG')
                    return image_path
            
            # Default placeholder image
            img = Image.new('RGBA', (100, 100), (255, 255, 255, 0))
            draw = ImageDraw.Draw(img)
            draw.ellipse([25, 25, 75, 75], fill=(204, 204, 204, 255))
            draw.polygon([(50, 70), (30, 100), (70, 100)], fill=(204, 204, 204, 255))
            img.save(image_path, 'PNG')
            
        except Exception as e:
            print(f"Error creating profile image: {e}")
            return None
        
        return image_path

    # Add nodes for each relative member with enhanced design
    for member in relatives_list:
        # Default styling - white background, black text
        fillcolor = 'white'
        fontcolor = 'black'
        
        # Special color for "self" node - blue background
        if member.get('isSelf') == True:
            fillcolor = '#00a3ee'  # Requested blue color for self node
            fontcolor = 'white'  # White text for readability
        
        # Create profile image node
        profile_image_path = create_profile_image_node(member.get('profileImage'), member['id'])
        
        # Create a stylized label with name and relation only
        label = f"<<TABLE BORDER='0' CELLBORDER='0' CELLSPACING='0' CELLPADDING='10'>"  # Further increased padding
        if profile_image_path:
            # Convert Windows path to forward slashes for Graphviz
            image_path = profile_image_path.replace('\\', '/').replace('//', '/')
            label += f"<TR><TD ROWSPAN='2'><IMG SRC='{image_path}' SCALE='TRUE' FIXEDSIZE='TRUE' WIDTH='90' HEIGHT='90'/></TD>"  # Further increased image size
        else:
            label += "<TR><TD ROWSPAN='2'><FONT POINT-SIZE='50'>👤</FONT></TD>"  # Increased emoji size
        
        # Add name with larger font
        full_name = member.get('name', '')
        label += f"<TD ALIGN='LEFT'><FONT POINT-SIZE='35'><B>{full_name}</B></FONT></TD></TR>"
        
        # Add relation information with larger font
        relation = member.get('relation', 'Relative')
        label += f"<TR><TD ALIGN='LEFT'><FONT POINT-SIZE='31'>{relation}</FONT></TD></TR>"
        
        label += "</TABLE>>"
        
        # Add node with proper styling
        dot.node(
            str(member['id']),  # Ensure ID is a string
            label=label,
            fillcolor=fillcolor, 
            fontcolor=fontcolor,
            style='filled,rounded',
            penwidth='1.5'  # Thinner border for cleaner look
        )

    # Add marriage nodes and connections, ensuring spouses are side by side
    marriages = {}
    for member in relatives_list:
        if member.get('spouse'):
            # Sort the IDs to ensure a consistent marriage ID
            spouse_ids = sorted([str(member['id']), str(member['spouse'])])
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

                # Create a marriage node with subtle design
                dot.node(marriage_id, label="•", shape="circle", width="0.25", height="0.25", 
                         color="#444444", fontcolor="#444444", fontsize="16", 
                         style="filled", fillcolor="#FFFFFF")
                
                # Connect both spouses to the marriage node with subtle edges
                dot.edge(spouse_ids[0], marriage_id, color="#444444", penwidth="4.0", 
                         arrowhead="none", style="solid")
                dot.edge(spouse_ids[1], marriage_id, color="#444444", penwidth="4.0", 
                         arrowhead="none", style="solid")

    # Connect parents to children with subtle arrows
    for member in relatives_list:
        if member.get('parentId'):
            # If parent has a spouse, connect to marriage node
            parent = next((p for p in relatives_list if str(p['id']) == str(member['parentId'])), None)
            
            if parent and parent.get('spouse'):
                spouse_ids = sorted([str(parent['id']), str(parent['spouse'])])
                marriage_id = f"marriage_{spouse_ids[0]}_{spouse_ids[1]}"
                if marriage_id in marriages:
                    dot.edge(marriage_id, str(member['id']), color="#444444", penwidth="4.0",
                             style="solid", arrowhead="normal", arrowtail="none", 
                             arrowsize="1.5")
            else:
                dot.edge(str(member['parentId']), str(member['id']), color="#444444", penwidth="4.0",
                         style="solid", arrowhead="normal", arrowtail="none", 
                         arrowsize="1.5")

    # Group nodes by generation for better layout
    generations = {}
    for member in relatives_list:
        gen = member.get('generation', 0)
        if gen not in generations:
            generations[gen] = []
        generations[gen].append(str(member['id']))
    
    # Create subgraphs for each generation to ensure proper vertical layout
    for gen, members in sorted(generations.items()):
        with dot.subgraph(name=f'cluster_gen_{gen}') as c:
            c.attr(rank='same')
            for member_id in members:
                c.node(member_id)

    # Render the graph to PNG
    temp_dir = tempfile.gettempdir()
    output_path = os.path.abspath(os.path.join(temp_dir, 'relatives_tree'))
    
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
        for member in relatives_list:
            member_id = str(member['id'])
            temp_image = os.path.join(temp_dir, f'profile_{member_id}.png')
            if os.path.exists(temp_image):
                try:
                    os.remove(temp_image)
                except:
                    pass
        
        return img_base64
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        # For debugging
        with open(f"{output_path}.dot", 'w', encoding='utf-8') as f:
            f.write(dot.source)
        return f"Error: {str(e)}\nDetails: {error_details}\nDOT file saved to {output_path}.dot for debugging"
