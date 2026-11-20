with open('scripts/rebuild_test_db.py', 'r') as f:
    content = f.read()

# Add the new migration to the MIGRATIONS list
old = '''    "035_preparation_works.sql",
    # 009_legacy_baseline NO se ejecuta en reconstrucción desde cero
]'''

new = '''    "035_preparation_works.sql",
    "036_add_notification_preferences.sql",
    # 009_legacy_baseline NO se ejecuta en reconstrucción desde cero
]'''

content = content.replace(old, new)

# Also add notify columns to drop_order
old_drop = '''            "preparation_works",
                "chorus_schema_migrations",
            ]'''

new_drop = '''            "preparation_works",
                "chorus_schema_migrations",
            ]'''

content = content.replace(old_drop, new_drop)

# Add notify columns to required tables check
old_required = '''            required = {'works', 'resources', 'files', 'groups', 'group_members', 'events',
                       'group_sections', 'group_articles', 'group_article_media',
                       'group_roles', 'group_social_links', 'legacy_uploads', 'activity_log',
                       'section_templates', 'role_templates', 'authorizations', 'performances',
                       'performance_groups', 'group_types', 'group_history',
                       'preparation_works'}'''

new_required = '''            required = {'works', 'resources', 'files', 'groups', 'group_members', 'events',
                       'group_sections', 'group_articles', 'group_article_media',
                       'group_roles', 'group_social_links', 'legacy_uploads', 'activity_log',
                       'section_templates', 'role_templates', 'authorizations', 'performances',
                       'performance_groups', 'group_types', 'group_history',
                       'preparation_works'}'''

content = content.replace(old_required, new_required)

with open('scripts/rebuild_test_db.py', 'w') as f:
    f.write(content)

print('Updated rebuild script')