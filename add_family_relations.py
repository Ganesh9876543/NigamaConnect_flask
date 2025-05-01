import json
import copy
from typing import Dict, Any

def add_family_relations(relatives: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add family relation labels to each person in the relatives dictionary.
    
    Args:
        relatives (Dict[str, Any]): Dictionary of relatives with IDs as keys
        
    Returns:
        Dict[str, Any]: Dictionary with processed relatives under the '_j' key
    """
    # Create a clean object with a deep copy of the input data
    clean_relatives = copy.deepcopy(relatives)
    
    # Find the self node (marked with isSelf: true)
    self_node = None
    for id_key in clean_relatives:
        if clean_relatives[id_key].get('isSelf') == True:
            self_node = clean_relatives[id_key]
            break
    
    if not self_node:
        print("No self node found in the data")
        return {"_j": clean_relatives}  # Maintain consistent return structure
    
    # First pass - set basic relationships
    for id_key in clean_relatives:
        person = clean_relatives[id_key]
        
        if person.get('isSelf'):
            person['relation'] = "self"
        # Direct parents
        elif person.get('id') == self_node.get('parentId'):
            person['relation'] = "father" if person.get('gender') == "male" else "mother"
        # Spouses of parents (step-parents)
        elif person.get('spouse') == self_node.get('parentId'):
            person['relation'] = "father" if person.get('gender') == "male" else "mother"
        # Siblings (same parents)
        elif person.get('parentId') == self_node.get('parentId'):
            person['relation'] = "brother" if person.get('gender') == "male" else "sister"
        # Spouse
        elif person.get('spouse') == self_node.get('id') or self_node.get('spouse') == person.get('id'):
            person['relation'] = "husband" if person.get('gender') == "male" else "wife"
        # Children
        elif person.get('parentId') == self_node.get('id'):
            person['relation'] = "son" if person.get('gender') == "male" else "daughter"
        # Spouses of children
        elif (person.get('parentId') in clean_relatives and 
              clean_relatives[person.get('parentId')].get('spouse') == self_node.get('id')):
            person['relation'] = "son-in-law" if person.get('gender') == "male" else "daughter-in-law"
        else:
            person['relation'] = "relative"  # Default fallback
    
    # Second pass - handle extended family relationships
    for id_key in clean_relatives:
        person = clean_relatives[id_key]
        
        if person.get('relation') != "relative":
            continue  # Skip already classified
        
        # Grandparents
        if (self_node.get('parentId') and 
            self_node.get('parentId') in clean_relatives and 
            clean_relatives[self_node.get('parentId')].get('parentId') == person.get('id')):
            person['relation'] = "grandfather" if person.get('gender') == "male" else "grandmother"
        
        # Aunts/Uncles (parents' siblings)
        elif (self_node.get('parentId') and 
              self_node.get('parentId') in clean_relatives and 
              person.get('parentId') == clean_relatives[self_node.get('parentId')].get('parentId')):
            person['relation'] = "uncle" if person.get('gender') == "male" else "aunt"
        
        # Cousins (children of aunts/uncles)
        elif (self_node.get('parentId') and 
              self_node.get('parentId') in clean_relatives and 
              person.get('parentId') and 
              person.get('parentId') in clean_relatives and 
              clean_relatives[person.get('parentId')].get('parentId') == 
              clean_relatives[self_node.get('parentId')].get('parentId')):
            person['relation'] = "cousin"
        
        # Nieces/Nephews (children of siblings)
        elif (person.get('parentId') and 
              person.get('parentId') in clean_relatives and 
              clean_relatives[person.get('parentId')].get('parentId') == self_node.get('parentId')):
            person['relation'] = "nephew" if person.get('gender') == "male" else "niece"
    
    return {"_j": clean_relatives}  # Maintain consistent return structure


if __name__ == "__main__":
    # Example usage
    relatives = {
        "1": {
            "id": "1",
            "name": "John Doe",
            "gender": "male",
            "isSelf": True
        },
        "2": {
            "id": "2",
            "name": "Jane Doe",
            "gender": "female",
            "spouse": "1"
        },
        "3": {
            "id": "3",
            "name": "James Doe",
            "gender": "male",
            "parentId": "1"
        }
    }
    
    result = add_family_relations(relatives)
    print(json.dumps(result, indent=2)) 