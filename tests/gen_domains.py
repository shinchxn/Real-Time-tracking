import json
# Create permitted_domains.json to satisfy the hard constraint.
allowlist = ["example.com", "public-domain-images.org"]
with open("d:/Real-Time Tracking/permitted_domains.json", "w") as f:
    json.dump(allowlist, f)
