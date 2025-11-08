import json
import os
import sys
from pathlib import Path
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv

# Load environment variables
load_dotenv(".env.local")

# Preview mode flag - shows first provider only
PREVIEW_MODE = "--preview" in sys.argv


def generate_description(provider):
    """
    Generate comprehensive natural language description for embedding.
    Captures all provider information in searchable text.
    """
    # Helper for missing fields
    def get_val(key, default="not provided"):
        val = provider.get(key)
        return val if val is not None and val != "" else default

    # Format address
    addr = provider.get("address", {})
    street = addr.get("street") or "not provided"
    city = addr.get("city") or "not provided"
    state = addr.get("state") or "not provided"
    zip_code = addr.get("zip") or "not provided"
    address = f"{street}, {city}, {state} {zip_code}"

    # Format arrays
    insurance = (
        ", ".join(provider.get("insurance_accepted", []))
        if provider.get("insurance_accepted")
        else "not provided"
    )
    languages = (
        ", ".join(provider.get("languages", []))
        if provider.get("languages")
        else "not provided"
    )

    # Boolean fields
    accepting = (
        "accepting new patients"
        if provider.get("accepting_new_patients")
        else "NOT accepting new patients"
    )
    board_cert = (
        "board certified"
        if provider.get("board_certified")
        else "not board certified"
    )

    description = f"""
{get_val('full_name')} is a {get_val('specialty')} specialist.
Phone number: {get_val('phone')}.
Email: {get_val('email')}.
Address: {address}.
Years of experience: {get_val('years_experience')}.
Currently {accepting}.
Insurance accepted: {insurance}.
Patient rating: {get_val('rating')} out of 5.
License number: {get_val('license_number')}.
{board_cert}.
Languages spoken: {languages}.
Specialty: {get_val('specialty')}.
    """.strip()

    return description


def prepare_metadata(provider):
    """
    Extract filterable metadata fields.
    Includes both filter fields and full data for return.
    """
    return {
        # Filter fields
        "id": provider["id"],
        "specialty": provider.get("specialty", ""),
        "state": provider.get("address", {}).get("state", ""),
        "city": provider.get("address", {}).get("city", ""),
        "zip": provider.get("address", {}).get("zip", ""),
        "accepting_new_patients": provider.get("accepting_new_patients", False),
        "years_experience": provider.get("years_experience", 0),
        "rating": float(provider.get("rating", 0)),
        "board_certified": provider.get("board_certified", False),
        "languages": provider.get("languages", []),
        "insurance_accepted": provider.get("insurance_accepted", []),
        # Complete data for agent response
        "full_name": provider.get("full_name", ""),
        "first_name": provider.get("first_name", ""),
        "last_name": provider.get("last_name", ""),
        "phone": provider.get("phone", ""),
        "email": provider.get("email", ""),
        "address_street": provider.get("address", {}).get("street", ""),
        "license_number": provider.get("license_number", ""),
    }


def main():
    # Initialize clients
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index_name = os.getenv("PINECONE_INDEX_NAME", "healthcare-providers")

    # Load providers
    providers_path = (
        Path(__file__).parent.parent.parent
        / "vox-takehome-test"
        / "data"
        / "providerlist.json"
    )
    with open(providers_path, "r") as f:
        providers = json.load(f)

    # PREVIEW MODE: Show first provider only
    if PREVIEW_MODE:
        print("=" * 80)
        print("PREVIEW MODE - First Provider Only")
        print("=" * 80)
        print()

        provider = providers[0]
        description = generate_description(provider)
        metadata = prepare_metadata(provider)

        print("DESCRIPTION (for embedding):")
        print("-" * 80)
        print(description)
        print()
        print("METADATA (for filtering and response):")
        print("-" * 80)
        print(json.dumps(metadata, indent=2))
        print()
        print("=" * 80)
        print("Preview complete. Run without --preview to embed all providers.")
        print("=" * 80)
        return

    # Create index if doesn't exist
    if index_name not in pc.list_indexes().names():
        print(f"Creating index: {index_name}")
        pc.create_index(
            name=index_name,
            dimension=1536,  # text-embedding-3-small
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )

    index = pc.Index(index_name)

    print(f"Embedding {len(providers)} providers...")

    # Process and upload in batches
    batch_size = 100
    vectors = []

    for i, provider in enumerate(providers, 1):
        # Generate description
        description = generate_description(provider)

        # Create embedding
        response = openai_client.embeddings.create(
            model="text-embedding-3-small", input=description
        )
        embedding = response.data[0].embedding

        # Prepare metadata
        metadata = prepare_metadata(provider)

        # Add to batch
        vectors.append(
            {
                "id": str(provider["id"]),
                "values": embedding,
                "metadata": metadata,
            }
        )

        print(f"Processed {i}/{len(providers)}: Dr. {provider.get('full_name', 'Unknown')}")

        # Upload batch
        if len(vectors) >= batch_size or i == len(providers):
            index.upsert(vectors=vectors)
            print(f"✓ Uploaded batch of {len(vectors)} vectors")
            vectors = []

    # Get index stats
    stats = index.describe_index_stats()
    print(f"\n✓ Successfully embedded {stats.total_vector_count} providers to Pinecone!")
    print(f"Index: {index_name}")


if __name__ == "__main__":
    main()

