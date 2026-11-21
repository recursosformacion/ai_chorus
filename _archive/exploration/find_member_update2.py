with open('app/main.py', 'r') as f:
    content = f.read()

# Find the MemberUpdateBody class
idx = content.find('class MemberUpdateBody')
if idx >= 0:
    print(content[idx:idx+500])