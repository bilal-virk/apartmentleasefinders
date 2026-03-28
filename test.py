import json
with open("test.json", "r") as file:
    data = json.load(file)
must_have_property_amenities = data.get('"Must Have" Property Amenities', [])
must_have_unit_amenities = data.get('"Must Have" Unit Amenities', [])
print("Must Have Property Amenities:", must_have_property_amenities)
print("Must Have Unit Amenities:", must_have_unit_amenities)