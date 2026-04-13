def test_extraction(payload):
    username = payload.get("username") or payload.get("npm") or payload.get("sub")
    fullname = (
        payload.get("name") or 
        payload.get("fullname") or 
        payload.get("full_name") or 
        payload.get("nama") or 
        username
    )
    return username, fullname

# Case 1: sub is numeric, username is provided
p1 = {"sub": "1", "username": "3120200907", "name": "Meike"}
print(f"Case 1: {test_extraction(p1)}") # Should be ('3120200907', 'Meike')

# Case 2: sub is numeric, name is in 'nama' (common in IBIK)
p2 = {"sub": "1", "npm": "3120200907", "nama": "Meike Macww"}
print(f"Case 2: {test_extraction(p2)}") # Should be ('3120200907', 'Meike Macww')

# Case 3: Only sub is provided (fallback)
p3 = {"sub": "john_doe"}
print(f"Case 3: {test_extraction(p3)}") # Should be ('john_doe', 'john_doe')
