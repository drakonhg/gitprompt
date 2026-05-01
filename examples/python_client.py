"""Minimal httpx client demoing prompt create/list against the GitPrompt API.

Usage:
    GITPROMPT_TOKEN=<jwt> python examples/python_client.py
    GITPROMPT_BASE_URL=http://localhost:8000 GITPROMPT_TOKEN=<jwt> python examples/python_client.py

POST /prompts requires a JWT (API keys are read-only). GET /prompts accepts either.
"""

import os
import httpx


def main() -> None:
    base_url = os.environ.get("GITPROMPT_BASE_URL", "http://localhost:8000")
    token = os.environ["GITPROMPT_TOKEN"]

    headers = {"Authorization": f"Bearer {token}"}

    with httpx.Client(base_url=base_url, headers=headers, timeout=10.0) as client:
        new_prompt = {
            "title": "Hello from httpx",
            "description": "Created by examples/python_client.py",
            "visibility": "private",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say hello."},
            ],
        }
        create_resp = client.post("/prompts", json=new_prompt)
        create_resp.raise_for_status()
        created = create_resp.json()
        print(f"Created prompt id={created['id']} at {created['created_at']}")

        list_resp = client.get("/prompts", params={"page": 1, "page_size": 12})
        list_resp.raise_for_status()
        page = list_resp.json()
        print(
            f"Page {page['current_page']}/{page['total_pages']} — "
            f"{page['total_prompts']} prompt(s) total"
        )
        for p in page["prompts"]:
            print(f"  - {p['title_slug']}: {p['title']}")


if __name__ == "__main__":
    main()
