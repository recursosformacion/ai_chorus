with open('app/main.py', 'r') as f:
    content = f.read()

# Add return app before _can_manage_preparation_work function
old = '''        return [_activity_log_dto(row) for row in rows]


def _can_manage_preparation_work'''

new = '''        return [_activity_log_dto(row) for row in rows]

    print("DEBUG: about to return app")
    return app


def _can_manage_preparation_work'''

content = content.replace(old, new)

with open('app/main.py', 'w') as f:
    f.write(content)
print('Added missing return app')