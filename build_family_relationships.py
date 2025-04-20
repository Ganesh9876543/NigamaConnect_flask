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
            for p in family_data:
                if p['id'] == self_node['id']:
                    temp_person = deepcopy(p)
                    temp_person['isSelf'] = False
                    temp_family_data.append(temp_person)
                elif p['id'] == spouse_node['id']:
                    temp_person = deepcopy(p)
                    temp_person['isSelf'] = True
                    temp_family_data.append(temp_person)
                else:
                    temp_family_data.append(deepcopy(p))

            # Build spouse's family tree with spouse as "self"
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
                # Only convert parents and their generation to in-laws
                # This preserves spouse's children as direct relations without in-law suffix
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
    # Skip conversion for MySelf, husband, wife
    if relation in ['MySelf', 'husband', 'wife']:
        return relation

    conversion_map = {
        # Parents become parents-in-law
        'father': 'father-in-law',
        'mother': 'mother-in-law',
        
        # Siblings become siblings-in-law
        'brother': 'brother-in-law',
        'sister': 'sister-in-law',
        
        # Aunts and uncles become aunts/uncles-in-law
        'uncle': 'uncle-in-law',
        'aunt': 'aunt-in-law',
        
        # Children don't change - spouse's children are your children
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
    mother = father.get('spouse') and family_map.get(father.get('spouse')) if father else None

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
    possible_parent_ids = [p_id for p_id in [self_node['id'], spouse and spouse['id']] if p_id]
    children = [
        person['id'] for person in family_data
        if person.get('parentId') in possible_parent_ids
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
            possible_sib_parent_ids = [p_id for p_id in [sib_id, sib.get('spouse')] if p_id]
            nieces_nephews.extend([
                person['id'] for person in family_data
                if person.get('parentId') in possible_sib_parent_ids
            ])

    # Get cousins
    cousins = []
    for ua_id in uncles_aunts:
        ua = family_map.get(ua_id)
        if ua:
            possible_ua_parent_ids = [p_id for p_id in [ua_id, ua.get('spouse')] if p_id]
            cousins.extend([
                person['id'] for person in family_data
                if person.get('parentId') in possible_ua_parent_ids
            ])

    return {
        'spouse': spouse['id'] if spouse else None,
        'parents': [p for p in [father and father['id'], mother and mother['id']] if p],
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
    # Check if the person is self
    if person['id'] == self_node['id']:
        return 'MySelf'

    # Check spouse relationship
    if person['id'] == relations['spouse']:
        return genderize('husband', 'wife', person)

    # Special handling when self has a spouse but no parents
    if relations['has_no_parents'] and self_node.get('spouse'):
        # If this person is a parent of the spouse
        if person['id'] in relations['in_laws']['spouse_parents']:
            return genderize('father-in-law', 'mother-in-law', person)
        
        # If this person is a sibling of the spouse
        if person['id'] in relations['spouse_siblings']:
            return genderize('brother-in-law', 'sister-in-law', person)
        
        # If this person is an uncle/aunt of the spouse
        if person['id'] in relations['spouse_uncles_aunts']:
            return genderize('father-in-law', 'mother-in-law', person)
        
        # If this person is spouse of uncle/aunt of spouse
        is_spouse_of_spouse_uncle_aunt = (
            person.get('spouse') and person['spouse'] in relations['spouse_uncles_aunts']
        )
        if is_spouse_of_spouse_uncle_aunt:
            related_uncle_aunt = family_map.get(person['spouse'])
            if related_uncle_aunt and related_uncle_aunt.get('gender') == 'female':
                return 'father-in-law'  # Husband of spouse's aunt is "father-in-law"
            else:
                return 'mother-in-law'  # Wife of spouse's uncle is "mother-in-law"

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

    # Check if person is one of father's siblings
    father_sibling = next((fs for fs in relations['father_siblings'] if fs['id'] == person['id']), None)
    if father_sibling:
        # If father's sibling is female, call her "mother"
        if father_sibling.get('gender') == 'female':
            return 'mother'
        else:
            return 'father'

    # Check if person is spouse of father's sibling
    is_spouse_of_father_sibling = any(
        fs['spouse'] == person['id'] for fs in relations['father_siblings']
    )
    if is_spouse_of_father_sibling:
        # Get the related sibling
        related_sibling = next(
            fs for fs in relations['father_siblings'] if fs['spouse'] == person['id']
        )
        if related_sibling.get('gender') == 'female':
            return 'father'  # Husband of father's sister is "father"
        else:
            return 'mother'  # Wife of father's brother is "mother"

    if person['id'] in relations['parents']:
        return genderize('father', 'mother', person)
    if person['id'] in relations['uncles_aunts']:
        return genderize('uncle', 'aunt', person)

    # Check if the person is the spouse of an uncle or aunt
    if person.get('spouse') and person['spouse'] in relations['uncles_aunts']:
        return genderize('uncle', 'aunt', person)

    # Check if the person is a parent of the spouse (father/mother-in-law)
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
        # Handle spouse's grandparents (when self has no parents)
        if relations['has_no_parents'] and self_node.get('spouse'):
            spouse = family_map.get(self_node['spouse'])
            spouse_gen_diff = person.get('generation', 0) - spouse.get('generation', 0)
            if spouse_gen_diff > 0:
                # This is a grandparent from spouse's side, make it in-law
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
