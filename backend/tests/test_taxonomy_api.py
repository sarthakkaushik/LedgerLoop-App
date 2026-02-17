import pytest
from httpx import AsyncClient


async def register_user(
    client: AsyncClient,
    *,
    email: str,
    household_name: str,
    full_name: str = "Admin User",
) -> dict:
    response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "testpass123",
            "full_name": full_name,
            "household_name": household_name,
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.asyncio
async def test_taxonomy_list_seeds_default_categories(client: AsyncClient) -> None:
    auth_data = await register_user(
        client,
        email="taxonomy.seed@example.com",
        household_name="Taxonomy Seed Home",
    )
    token = auth_data["token"]["access_token"]
    response = await client.get(
        "/settings/taxonomy",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    category_names = {item["name"] for item in payload["categories"]}
    assert "Other" in category_names
    assert "Groceries" in category_names


@pytest.mark.asyncio
async def test_taxonomy_admin_can_manage_and_member_cannot_mutate(client: AsyncClient) -> None:
    admin_auth = await register_user(
        client,
        email="taxonomy.admin@example.com",
        household_name="Taxonomy Admin Home",
        full_name="Taxonomy Admin",
    )
    admin_token = admin_auth["token"]["access_token"]

    invite_response = await client.post(
        "/auth/invite",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert invite_response.status_code == 200
    invite_code = invite_response.json()["invite_code"]

    join_response = await client.post(
        "/auth/join",
        json={
            "email": "taxonomy.member@example.com",
            "password": "testpass123",
            "full_name": "Taxonomy Member",
            "invite_code": invite_code,
        },
    )
    assert join_response.status_code == 201
    member_token = join_response.json()["token"]["access_token"]

    create_category_res = await client.post(
        "/settings/taxonomy/categories",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "Pets"},
    )
    assert create_category_res.status_code == 200
    categories = create_category_res.json()["categories"]
    pets_category = next((item for item in categories if item["name"] == "Pets"), None)
    assert pets_category is not None

    create_subcategory_res = await client.post(
        f"/settings/taxonomy/categories/{pets_category['id']}/subcategories",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "Vet"},
    )
    assert create_subcategory_res.status_code == 200
    categories_after_sub = create_subcategory_res.json()["categories"]
    pets_after_sub = next((item for item in categories_after_sub if item["id"] == pets_category["id"]), None)
    assert pets_after_sub is not None
    assert any(sub["name"] == "Vet" for sub in pets_after_sub["subcategories"])

    member_create_res = await client.post(
        "/settings/taxonomy/categories",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"name": "Should Fail"},
    )
    assert member_create_res.status_code == 403


@pytest.mark.asyncio
async def test_taxonomy_household_isolation(client: AsyncClient) -> None:
    family_a = await register_user(
        client,
        email="taxonomy.a@example.com",
        household_name="Taxonomy Family A",
    )
    family_b = await register_user(
        client,
        email="taxonomy.b@example.com",
        household_name="Taxonomy Family B",
    )
    token_a = family_a["token"]["access_token"]
    token_b = family_b["token"]["access_token"]

    create_a = await client.post(
        "/settings/taxonomy/categories",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"name": "FamilyA Exclusive"},
    )
    assert create_a.status_code == 200

    list_a = await client.get(
        "/settings/taxonomy",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert list_a.status_code == 200
    assert any(item["name"] == "FamilyA Exclusive" for item in list_a.json()["categories"])

    list_b = await client.get(
        "/settings/taxonomy",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert list_b.status_code == 200
    assert all(item["name"] != "FamilyA Exclusive" for item in list_b.json()["categories"])
