import httpx
import asyncio

async def test_login():
    base_url = "https://newapidevkiismanajemenuser.ibik.ac.id"
    endpoints = ["/auth/login"]
    payload = {
        "username": "3120200907",
        "password": "wrong_password" 
    }
    
    async with httpx.AsyncClient(verify=False, follow_redirects=True) as client:
        # Test OPTIONS for CORS
        print(f"Testing OPTIONS to {base_url}/auth/login...")
        try:
            resp = await client.options(f"{base_url}/auth/login", timeout=5)
            print(f"  Status: {resp.status_code}")
            print(f"  Access-Control-Allow-Origin: {resp.headers.get('Access-Control-Allow-Origin')}")
            print(f"  Access-Control-Allow-Methods: {resp.headers.get('Access-Control-Allow-Methods')}")
        except Exception as e:
            print(f"  Error: {e}")

        for path in endpoints:
            url = f"{base_url}{path}"
            print(f"\nTesting POST to {url}...")
            try:
                # Test JSON
                resp = await client.post(url, json=payload, timeout=5)
                print(f"  Status: {resp.status_code}")
                print(f"  Response: {resp.text[:200]}")
            except Exception as e:
                print(f"  Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_login())
