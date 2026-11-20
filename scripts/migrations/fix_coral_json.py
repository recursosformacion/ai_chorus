#!/usr/bin/env python3
"""Fix: Populate coral JSON fields in groups from amigos_coral_details and amigos_coral_attributes"""

import pymysql
import json

SRC = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027', password='2027osapdb', database='osap_api', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
TGT = pymysql.connect(host='127.0.0.1', port=3306, user='osap2027_test', password='testpass', database='osap_chorus_test', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor, autocommit=False)

print("=== Poblando campos JSON de coral en groups ===")
with SRC.cursor() as scur, TGT.cursor() as tcur:
    # Get coral_details
    scur.execute("SELECT * FROM amigos_coral_details")
    details = {row['group_id']: row for row in scur.fetchall()}
    
    # Get coral_attributes grouped by group_id and facet
    scur.execute("SELECT * FROM amigos_coral_attributes")
    attributes = {}
    for row in scur.fetchall():
        gid = row['group_id']
        if gid not in attributes:
            attributes[gid] = {'language': [], 'repertoire': [], 'place': []}
        if row['facet'] in attributes[gid]:
            attributes[gid][row['facet']].append(row['value'])
    
    # Update each group
    tcur.execute("SELECT id FROM groups")
    groups = tcur.fetchall()
    
    for g in groups:
        gid = g['id']
        language = None
        repertoire = None
        venues = None
        
        if gid in details:
            d = details[gid]
            # Update scalar fields
            tcur.execute("""
                UPDATE groups SET
                    foundation_date=%s,
                    dissolution_date=%s,
                    locality=%s,
                    region=%s,
                    country_code=%s,
                    venue=%s,
                    formation_type=%s,
                    member_count=%s,
                    public_email=%s
                WHERE id=%s
            """, (
                d.get('foundation_date'),
                d.get('dissolution_date'),
                d.get('locality'),
                d.get('region'),
                d.get('country_code'),
                d.get('venue'),
                d.get('formation_type'),
                d.get('member_count'),
                d.get('public_email'),
                gid,
            ))
            print(f"  Updated scalar fields for {gid}")
        
        if gid in attributes:
            attr = attributes[gid]
            if attr['language']:
                language = json.dumps(attr['language'])
            if attr['repertoire']:
                repertoire = json.dumps(attr['repertoire'])
            if attr['place']:
                venues = json.dumps(attr['place'])
        
        # Update JSON fields
        tcur.execute("""
            UPDATE groups SET
                language=%s,
                repertoire=%s,
                venues=%s
            WHERE id=%s
        """, (language, repertoire, venues, gid))
        print(f"  Updated JSON for {gid}: language={language}, repertoire={repertoire}, venues={venues}")
    
    TGT.commit()

print("\n=== Verificando ===")
with TGT.cursor() as cur:
    cur.execute("SELECT id, name, language, repertoire, venues, foundation_date, locality, formation_type, member_count FROM groups")
    for row in cur.fetchall():
        print(f"  {row['id']} ({row['name']}):")
        print(f"    language={row['language']}")
        print(f"    repertoire={row['repertoire']}")
        print(f"    venues={row['venues']}")
        print(f"    foundation_date={row['foundation_date']} locality={row['locality']} formation_type={row['formation_type']} member_count={row['member_count']}")

SRC.close()
TGT.close()