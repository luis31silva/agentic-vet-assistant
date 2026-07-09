"""Normalize species and breed values using local fuzzy matching.

This avoids spending LLM tokens on standardization. The LLM extracts
whatever text it finds, and this module maps it to the canonical names
used in the frontend selects.
"""

from difflib import get_close_matches
from typing import Any, Dict, Optional

from loguru import logger

from app.utils.breeds import ALL_BREEDS, CAT_BREEDS, DOG_BREEDS, SPECIES_TITLES


# Maps any species variation to the DB value (dog/cat)
SPECIES_ALIASES = {
    "dog": "dog",
    "cao": "dog",
    "cão": "dog",
    "canino": "dog",
    "canina": "dog",
    "cachorro": "dog",
    "cadela": "dog",
    "cat": "cat",
    "gata": "cat",
    "gato": "cat",
    "felino": "cat",
    "felina": "cat",
    "gatinha": "cat",
    "gatinho": "cat",
}

BREED_ALIASES = {
    "labrador": "Labrador Retriever",
    "golden": "Golden Retriever",
    "pastor alemão": "Cão de Pastor Alemão",
    "pastor alemao": "Cão de Pastor Alemão",
    "german shepherd": "Cão de Pastor Alemão",
    "bulldog francês": "Bouledogue Francês",
    "bulldog frances": "Bouledogue Francês",
    "french bulldog": "Bouledogue Francês",
    "bulldog inglês": "Bulldog Inglês",
    "bulldog ingles": "Bulldog Inglês",
    "husky": "Siberian Husky",
    "husky siberiano": "Siberian Husky",
    "pug": "Carlin ( Pug )",
    "dalmata": "Cão da Dalmácia",
    "dálmata": "Cão da Dalmácia",
    "dalmatian": "Cão da Dalmácia",
    "teckel": "Baixote ( Teckel )",
    "dachshund": "Baixote ( Teckel )",
    "baixote": "Baixote ( Teckel )",
    "terra nova": "Cão da Terra Nova",
    "newfoundland": "Cão da Terra Nova",
    "são bernardo": "Cão de São Bernardo",
    "sao bernardo": "Cão de São Bernardo",
    "saint bernard": "Cão de São Bernardo",
    "pit bull": "Pit Bull Terrier",
    "pitbull": "Pit Bull Terrier",
    "rottweiller": "Rottweiler",
    "doberman": "Dobermann",
    "yorkshire": "Yorkshire Terrier",
    "yorkie": "Yorkshire Terrier",
    "cocker": "Cocker Spaniel Inglês",
    "cocker spaniel": "Cocker Spaniel Inglês",
    "shih-tzu": "Shih Tzu",
    "serra da estrela": "Cão da Serra da Estrela",
    "estrela": "Cão da Serra da Estrela",
    "agua portugues": "Cão de Água Português",
    "água português": "Cão de Água Português",
    "rafeiro": "Rafeiro do Alentejo",
    "podengo": "Podengo Português",
    "perdigueiro": "Perdigueiro Português",
    "maine coon": "Maine Coon",
    "persa": "Persa",
    "siamês": "Siamês",
    "siames": "Siamês",
    "bengal": "Bengal",
    "ragdoll": "Ragdoll",
    "sphynx": "Sphynx",
    "british shorthair": "Britânico de Pelo Curto",
    "british longhair": "Britânico de Pelo Longo",
    "europeu": "Europeu",
}


def normalize_species(species_input: Optional[str]) -> Optional[str]:
    """Normalize a species string to the DB value ('dog' or 'cat').

    Returns the original value if no match is found.
    """
    if not species_input:
        return species_input

    lower = species_input.strip().lower()

    # Check direct aliases
    if lower in SPECIES_ALIASES:
        return SPECIES_ALIASES[lower]

    return species_input


def normalize_breed(breed_input: Optional[str], species: Optional[str] = None) -> Optional[str]:
    """Normalize a breed string to the canonical value from the breeds list.

    Uses species context to search in the right list first.
    Returns the original value if no match is found (cutoff too low).
    """
    if not breed_input:
        return breed_input

    lower = breed_input.strip().lower()

    # Check direct aliases first
    if lower in BREED_ALIASES:
        return BREED_ALIASES[lower]

    # Determine which list to search based on species
    if species:
        species_lower = species.lower()
        if species_lower in ("cão", "cao", "dog", "canino"):
            search_list = DOG_BREEDS
        elif species_lower in ("gato", "gata", "cat", "felino"):
            search_list = CAT_BREEDS
        else:
            search_list = ALL_BREEDS
    else:
        search_list = ALL_BREEDS

    # Fuzzy match
    match = get_close_matches(breed_input, search_list, n=1, cutoff=0.6)
    if match:
        return match[0]

    # Try case-insensitive comparison as fallback
    lower_map = {b.lower(): b for b in search_list}
    if lower in lower_map:
        return lower_map[lower]

    # No match found — return original
    logger.debug(f"Breed '{breed_input}' not matched to any known breed, keeping original.")
    return breed_input


def normalize_entities(entities: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize species and breed fields in an entities dict.

    Handles both flat entities and nested (owner/patient) structures.
    Mutates and returns the same dict.
    """
    # Flat structure
    if "species" in entities:
        entities["species"] = normalize_species(entities["species"])
    if "breed" in entities:
        entities["breed"] = normalize_breed(entities["breed"], entities.get("species"))

    # Nested patient structure
    if "patient" in entities and isinstance(entities["patient"], dict):
        patient = entities["patient"]
        if "species" in patient:
            patient["species"] = normalize_species(patient["species"])
        if "breed" in patient:
            patient["breed"] = normalize_breed(patient["breed"], patient.get("species"))

    return entities
