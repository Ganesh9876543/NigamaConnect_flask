from typing import List, Dict, Optional, Union, Any
from dataclasses import dataclass
from copy import deepcopy

@dataclass
class FamilyMember:
    """Data class to represent a family member with type hints."""
    id: str
    name: str
    gender: str
    isSelf: bool = False
    spouse: Optional[str] = None
    parentId: Optional[str] = None
    generation: Optional[int] = None
    relation: Optional[str] = None

def build_family_relationships(family_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Build family relationships for all members in the family data.
    
    Args:
        family_data (List[Dict[str, Any]]): List of family member dictionaries
        
    Returns:
        List[Dict[str, Any]]: List of family members with their relationships set
    """
    # Find self node
    self_node = next((person for person in family_data if person.get('isSelf')), None)
    if not self_node:
        raise ValueError("Self node not found")

    # Create family map
    family_map = {person['id']: person for person in family_data}

    # Handle case where self has spouse but no parents
    if self_node.get('spouse') and not self_node.get('parentId'):
        spouse_node = family_map.get(self_node['spouse'])
        if spouse_node:
            # Temporarily make spouse the "self" node
            temp_family_data = []
            for person in family_data:
                if person['id'] == self_node['id']:
                    temp_person = deepcopy(person)
                    temp_person['isSelf'] = False
                    temp_family_data.append(temp_person)
                elif person['id'] == spouse_node['id']:
                    temp_person = deepcopy(person)
                    temp_person['isSelf'] = True
                    temp_family_data.append(temp_person)
                else:
                    temp_family_data.append(deepcopy(person))

            # Build spouse's family tree
            spouse_tree = build_family_relations_with_spouse(temp_family_data)

            # Convert relationships and restore original self status
            result = []
            for person in spouse_tree:
                if person['id'] == self_node['id']:
                    result.append({
                        **person,
                        'isSelf': True,
                        'relation': 'MySelf'
                    })
                elif person['id'] == spouse_node['id']:
                    result.append({
                        **person,
                        'isSelf': False,
                        'relation': genderize('husband', 'wife', person)
                    })
                elif (person.get('generation') is not None and 
                      spouse_node.get('generation') is not None and
                      (person['generation'] == spouse_node['generation'] or 
                       person['generation'] == spouse_node['generation'] + 1)):
                    result.append({
                        **person,
                        'relation': convert_to_in_law_relation(person.get('relation', ''), person)
                    })
                else:
                    result.append(person)
            return result

    # Regular case: compute all relations
    relations = compute_all_relations(self_node, family_data, family_map)

    # Build final result with relationships
    result = []
    for person in family_data:
        result.append({
            **person,
            'relation': get_relationship(self_node, person, relations, family_map)
        })

    return result

def build_family_relations_with_spouse(family_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build family relationships with spouse as self node."""
    self_node = next((person for person in family_data if person.get('isSelf')), None)
    if not self_node:
        raise ValueError("Self node not found in spouse processing")

    family_map = {person['id']: person for person in family_data}
    relations = compute_all_relations(self_node, family_data, family_map)

    return [
        {**person, 'relation': get_relationship(self_node, person, relations, family_map)}
        for person in family_data
    ]

def convert_to_in_law_relation(relation: str, person: Dict[str, Any]) -> str:
    """Convert a relation to its in-law equivalent."""
    if relation in ['MySelf', 'husband', 'wife']:
        return relation

    conversion_map = {
        'father': 'father-in-law',
        'mother': 'mother-in-law',
        'brother': 'brother-in-law',
        'sister': 'sister-in-law',
        'uncle': 'uncle-in-law',
        'aunt': 'aunt-in-law',
        'son': 'son',
        'daughter': 'daughter',
    }

    return conversion_map.get(relation, f"{relation}-in-law")

def compute_all_relations(
    self_node: Dict[str, Any],
    family_data: List[Dict[str, Any]],
    family_map: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """Compute all possible relationships for the family tree."""
    spouse = family_map.get(self_node.get('spouse'))
    father = family_map.get(self_node.get('parentId'))
    mother = family_map.get(father.get('spouse')) if father else None

    # Get father's siblings with gender info
    father_siblings = get_father_siblings_with_gender(father, family_map, family_data) if father else []

    # Get spouse's family
    spouse_parents = get_parents(spouse, family_map) if spouse else []
    spouse_siblings = get_siblings(spouse, family_map) if spouse else []

    # Get spouse's extended family
    spouse_father = family_map.get(spouse.get('parentId')) if spouse else None
    spouse_mother = family_map.get(spouse_father.get('spouse')) if spouse_father else None

    spouse_uncles_aunts = []
    if spouse_father:
        spouse_uncles_aunts.extend(get_siblings(spouse_father, family_map))
    if spouse_mother:
        spouse_uncles_aunts.extend(get_siblings(spouse_mother, family_map))

    # Get siblings
    siblings = [
        person['id'] for person in family_data
        if person['id'] != self_node['id'] and
        (person.get('parentId') == self_node.get('parentId') or
         (mother and person.get('parentId') == mother['id']))
    ]

    # Get children
    children = [
        person['id'] for person in family_data
        if person.get('parentId') in [self_node['id'], spouse['id'] if spouse else None]
    ]

    # Get uncles and aunts
    uncles_aunts = []
    if father:
        uncles_aunts.extend(get_siblings(father, family_map))
    if mother:
        uncles_aunts.extend(get_siblings(mother, family_map))

    # Get nieces and nephews
    nieces_nephews = []
    for sib_id in siblings:
        sib = family_map.get(sib_id)
        if sib:
            nieces_nephews.extend([
                person['id'] for person in family_data
                if person.get('parentId') in [sib_id, sib.get('spouse')]
            ])

    # Get cousins
    cousins = []
    for ua_id in uncles_aunts:
        ua = family_map.get(ua_id)
        if ua:
            cousins.extend([
                person['id'] for person in family_data
                if person.get('parentId') in [ua_id, ua.get('spouse')]
            ])

    return {
        'spouse': spouse['id'] if spouse else None,
        'parents': [p for p in [father['id'] if father else None, mother['id'] if mother else None] if p],
        'children': children,
        'siblings': siblings,
        'uncles_aunts': uncles_aunts,
        'nieces_nephews': nieces_nephews,
        'spouse_siblings': spouse_siblings,
        'spouse_uncles_aunts': spouse_uncles_aunts,
        'cousins': cousins,
        'father_siblings': father_siblings,
        'has_no_parents': not self_node.get('parentId'),
        'in_laws': {
            'spouse_parents': spouse_parents,
            'sibling_spouses': [
                person['id'] for person in family_data
                if person.get('spouse') and person['spouse'] in siblings
            ],
            'spouse_sibling_spouses': [
                person['id'] for person in family_data
                if person.get('spouse') and person['spouse'] in spouse_siblings
            ],
            'children_spouses': [
                person['id'] for person in family_data
                if person.get('spouse') and person['spouse'] in children
            ]
        }
    }

def get_father_siblings_with_gender(
    father: Optional[Dict[str, Any]],
    family_map: Dict[str, Dict[str, Any]],
    family_data: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Get father's siblings with their gender information."""
    if not father:
        return []

    father_siblings = get_siblings(father, family_map)
    return [
        {
            'id': sib_id,
            'gender': family_map[sib_id].get('gender'),
            'spouse': family_map[sib_id].get('spouse')
        }
        for sib_id in father_siblings
    ]

def get_relationship(
    self_node: Dict[str, Any],
    person: Dict[str, Any],
    relations: Dict[str, Any],
    family_map: Dict[str, Dict[str, Any]]
) -> str:
    """Determine the relationship between self and another person."""
    if person['id'] == self_node['id']:
        return 'MySelf'

    if person['id'] == relations['spouse']:
        return genderize('husband', 'wife', person)

    # Handle special case when self has no parents but has spouse
    if relations['has_no_parents'] and self_node.get('spouse'):
        if person['id'] in relations['in_laws']['spouse_parents']:
            return genderize('father-in-law', 'mother-in-law', person)
        if person['id'] in relations['spouse_siblings']:
            return genderize('brother-in-law', 'sister-in-law', person)
        if person['id'] in relations['spouse_uncles_aunts']:
            return genderize('father-in-law', 'mother-in-law', person)

    # Regular relationships
    if person['id'] in relations['siblings']:
        return genderize('brother', 'sister', person)
    if person['id'] in relations['spouse_siblings']:
        return genderize('brother-in-law', 'sister-in-law', person)
    if person['id'] in relations['cousins']:
        return 'cousin'
    if person['id'] in relations['in_laws']['sibling_spouses']:
        return genderize('brother-in-law', 'sister-in-law', person)
    if person['id'] in relations['in_laws']['spouse_sibling_spouses']:
        return genderize('brother-in-law', 'sister-in-law', person)

    # Check father's siblings
    father_sibling = next(
        (fs for fs in relations['father_siblings'] if fs['id'] == person['id']),
        None
    )
    if father_sibling:
        return 'mother' if father_sibling['gender'] == 'female' else 'father'

    # Check spouse of father's sibling
    is_spouse_of_father_sibling = any(
        fs['spouse'] == person['id'] for fs in relations['father_siblings']
    )
    if is_spouse_of_father_sibling:
        related_sibling = next(
            fs for fs in relations['father_siblings'] if fs['spouse'] == person['id']
        )
        return 'father' if related_sibling['gender'] == 'female' else 'mother'

    if person['id'] in relations['parents']:
        return genderize('father', 'mother', person)
    if person['id'] in relations['uncles_aunts']:
        return genderize('uncle', 'aunt', person)
    if person.get('spouse') and person['spouse'] in relations['uncles_aunts']:
        return genderize('uncle', 'aunt', person)
    if person['id'] in relations['in_laws']['spouse_parents']:
        return genderize('father-in-law', 'mother-in-law', person)
    if person['id'] in relations['children']:
        return genderize('son', 'daughter', person)
    if person['id'] in relations['nieces_nephews']:
        return genderize('nephew', 'niece', person)
    if person['id'] in relations['in_laws']['children_spouses']:
        return genderize('son-in-law', 'daughter-in-law', person)

    # Handle generational differences
    gen_diff = person.get('generation', 0) - self_node.get('generation', 0)
    if gen_diff > 1:
        if relations['has_no_parents'] and self_node.get('spouse'):
            spouse = family_map.get(self_node['spouse'])
            spouse_gen_diff = person.get('generation', 0) - spouse.get('generation', 0)
            if spouse_gen_diff > 0:
                return gendered_relation(
                    spouse_gen_diff,
                    'grandfather-in-law',
                    'grandmother-in-law',
                    person
                )
        return gendered_relation(gen_diff, 'grandfather', 'grandmother', person)

    if gen_diff < -1:
        return gendered_relation(-gen_diff, 'grandson', 'granddaughter', person)

    return 'relative'

def get_parents(
    person: Optional[Dict[str, Any]],
    family_map: Dict[str, Dict[str, Any]]
) -> List[str]:
    """Get all parents of a person."""
    if not person:
        return []
    
    result = []
    if person.get('parentId'):
        parent = family_map.get(person['parentId'])
        if parent:
            result.append(parent['id'])
            if parent.get('spouse'):
                result.append(parent['spouse'])
    
    return result

def get_siblings(
    person: Optional[Dict[str, Any]],
    family_map: Dict[str, Dict[str, Any]]
) -> List[str]:
    """Get all siblings of a person."""
    if not person or not person.get('parentId'):
        return []
    
    parents = get_parents(person, family_map)
    return [
        p['id'] for p in family_map.values()
        if p['id'] != person['id'] and p.get('parentId') in parents
    ]

def genderize(male: str, female: str, person: Dict[str, Any]) -> str:
    """Return the appropriate gendered term based on the person's gender."""
    return female if person.get('gender') == 'female' else male

def gendered_relation(level: int, male: str, female: str, person: Dict[str, Any]) -> str:
    """Return the appropriate gendered relation with proper prefix."""
    base = genderize(male, female, person)
    if level == 1:
        return base
    if level == 2:
        return base
    return f"{'great-' * (level - 2)}{base}"

if __name__ == "__main__":
    # Example usage
    family_data = [
        {
            'id': '1',
            'name': 'John Doe',
            'gender': 'male',
            'isSelf': True,
            'generation': 0
        },
        {
            'id': '2',
            'name': 'Jane Doe',
            'gender': 'female',
            'spouse': '1',
            'generation': 0
        }
    ]
    
    result = build_family_relationships(family_data)
    print(result)